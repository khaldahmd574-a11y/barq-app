import os
import re
import json
import time
import asyncio
import hashlib
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

import aiohttp
from hydrogram import Client, filters
from hydrogram.types import Message
from hydrogram.errors import FloodWait


# ============================================================
#                    إعدادات Environment (مطابقة لـ Render)
# ============================================================

API_ID = os.getenv("API_ID") or os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("API_HASH") or os.getenv("TELEGRAM_API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

PORT = int(os.getenv("PORT", "10000"))

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "qwen/qwen-2.5-7b-instruct"
)

# مفتاح تفعيل الفلترة (مفعل تلقائياً)
FILTER_INTENT_ACTIVE = True

# ============================================================
#                  المستهدفون بالطلبات (المشتركون)
# ============================================================

env_targets = os.getenv("TARGET_USERS", "")
if env_targets:
    TARGET_USERS = [t.strip() for t in env_targets.split(",") if t.strip()]
else:
    TARGET_USERS = [
        "@abood1317",
        "@shaybq",
    ]


# ============================================================
#                       إعدادات عامة
# ============================================================

AI_RETRIES = 2
AI_TIMEOUT = 12
DEDUP_TTL = 60 * 60 * 24
MAX_MESSAGE_LENGTH = 6000
MAX_CONCURRENT_AI = 8


# ============================================================
#                       Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("BARQ_AI")


# ============================================================
#                  التحقق من Environment
# ============================================================

required_env = {
    "API_ID / TELEGRAM_API_ID": API_ID,
    "API_HASH / TELEGRAM_API_HASH": API_HASH,
    "SESSION_STRING": SESSION_STRING,
    "BOT_TOKEN": BOT_TOKEN,
    "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
}

missing = [name for name, value in required_env.items() if not value]
if missing:
    raise RuntimeError("Environment Variables ناقصة: " + ", ".join(missing))


# ============================================================
#                     Keep Alive Server
# ============================================================

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Barq AI Userbot Active 24/7!")
        except Exception:
            pass

    def log_message(self, format, *args):
        return


def run_keep_alive():
    try:
        server = HTTPServer(("0.0.0.0", PORT), KeepAliveHandler)
        logger.info(f"Keep Alive started on port {PORT}")
        server.serve_forever()
    except Exception as e:
        logger.exception(f"Keep Alive Error: {e}")


threading.Thread(target=run_keep_alive, daemon=True).start()


# ============================================================
#                    Hydrogram Userbot & Bot
# ============================================================

app = Client(
    "barq_userbot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True,
)

BOT_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# ============================================================
#                 منع الرسائل المكررة
# ============================================================

processed_messages = {}
processed_lock = asyncio.Lock()


async def cleanup_processed_messages():
    while True:
        try:
            now = time.time()
            async with processed_lock:
                expired = [
                    key for key, timestamp in processed_messages.items()
                    if now - timestamp > DEDUP_TTL
                ]
                for key in expired:
                    processed_messages.pop(key, None)
        except Exception as e:
            logger.exception(f"Dedup cleanup error: {e}")
        await asyncio.sleep(600)


async def is_duplicate(message: Message, text: str) -> bool:
    try:
        chat_id = getattr(message.chat, "id", 0)
        sender_id = getattr(message.from_user, "id", 0) if message.from_user else 0
        normalized = text.strip().lower()
        raw = f"{chat_id}|{sender_id}|{normalized}"
        fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        async with processed_lock:
            if fingerprint in processed_messages:
                return True
            processed_messages[fingerprint] = time.time()

        return False
    except Exception as e:
        logger.exception(f"Duplicate check error: {e}")
        return False


# ============================================================
#             AI SYSTEM PROMPT (فحص نية الزبون vs السائق)
# ============================================================

AI_SYSTEM_PROMPT = """أنت نظام ذكاء اصطناعي مخصص لفلترة طلبات التوصيل في أسرع وقت.

مهمتك: تحديد نية الكاتب بدقة عالية جداً.

أخرج كائن JSON فقط بالصيغة التالية:
{"allow": true}
أو
{"allow": false}

القواعد الصارمة للتصنيف:

1. اجعل {"allow": true} فقط إذا كان الكاتب (زبون / عميل) يحتاج توصيل أو لديه طلب حقيقي مثل:
   - "أبغى سواق من صبيا لبيش"
   - "احتاج توصيل طلب من مطعم"
   - "مين فاضي يوصلني"
   - "مطلوب سيارة لنقل أغراض"

2. اجعل {"allow": false} بشكل قاطع إذا كان الكاتب (سائق / مندوب / معلن) يعرض خدمته أو يتواجد في مكان مثل:
   - "متواجد في أبو عريش للمشاوير"
   - "فاضي للطلب"
   - "سائق خاص تحت الخدمة"
   - "نقل طرود وبضائع التواصل خاص"
   - وجود أرقام جوال (مثل 05xxxxxxxx) أو روابط وإعلانات أو تحيات ومحادثات جانبية.
"""

ai_semaphore = asyncio.Semaphore(MAX_CONCURRENT_AI)


async def ask_openrouter(text: str) -> bool:
    async with ai_semaphore:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://render.com/",
            "X-Title": "Barq Intent AI Filter",
        }

        payload = {
            "model": OPENROUTER_MODEL,
            "messages": [
                {"role": "system", "content": AI_SYSTEM_PROMPT},
                {"role": "user", "content": f"حلل نية الرسالة التالية: \"{text}\""}
            ],
            "temperature": 0.0,
            "max_tokens": 20
        }

        timeout = aiohttp.ClientTimeout(total=AI_TIMEOUT)

        for attempt in range(AI_RETRIES + 1):
            try:
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(OPENROUTER_URL, headers=headers, json=payload) as response:
                        raw = await response.text()
                        if response.status != 200:
                            if attempt < AI_RETRIES:
                                await asyncio.sleep(1.0)
                                continue
                            return False

                        data = json.loads(raw)
                        choices = data.get("choices", [])
                        if not choices:
                            return False

                        content = choices[0].get("message", {}).get("content", "").strip()
                        content_clean = re.sub(r"```json|```", "", content).strip()
                        
                        try:
                            result = json.loads(content_clean)
                            return bool(result.get("allow", False))
                        except json.JSONDecodeError:
                            return "true" in content_clean.lower()

            except Exception:
                pass

            if attempt < AI_RETRIES:
                await asyncio.sleep(1.0)

        return False


# ============================================================
#                  أدوات بناء الرسالة وتوجيهها
# ============================================================

def get_user_link(message: Message) -> Optional[str]:
    user = message.from_user
    if not user:
        return None
    if user.username:
        return f"https://t.me/{user.username}"
    if user.id:
        return f"tg://user?id={user.id}"
    return None


def get_message_link(message: Message) -> Optional[str]:
    chat = message.chat
    if not message.id:
        return None
    if chat.username:
        return f"https://t.me/{chat.username}/{message.id}"
    if chat.id and str(chat.id).startswith("-100"):
        return f"https://t.me/c/{str(chat.id)[4:]}/{message.id}"
    return None


def build_output_message(message: Message, text: str) -> str:
    chat_name = message.chat.title or message.chat.first_name or "مجموعة"
    sender_name = message.from_user.first_name if message.from_user else "عميل"
    
    return (
        "📦 <b>طلب عميل جديد (نية طلب مؤكدة)</b>\n\n"
        f"👤 <b>العميل:</b> {sender_name}\n"
        f"📍 <b>المصدر:</b> {chat_name}\n\n"
        "💬 <b>تفاصيل الطلب:</b>\n"
        f"{text}"
    )


async def bot_api_request(method: str, payload: dict):
    url = f"{BOT_API}/{method}"
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as response:
            return await response.json()


async def send_to_targets(message: Message, text: str):
    user_link = get_user_link(message)
    message_link = get_message_link(message)

    buttons = []
    if user_link:
        buttons.append({"text": "👤 محادثة العميل", "url": user_link})
    if message_link:
        buttons.append({"text": "🔗 الرسالة الأصلية", "url": message_link})

    keyboard = {"inline_keyboard": [buttons]} if buttons else None
    output = build_output_message(message, text)

    for target in TARGET_USERS:
        payload = {
            "chat_id": target,
            "text": output,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        if keyboard:
            payload["reply_markup"] = keyboard
        try:
            await bot_api_request("sendMessage", payload)
            logger.info(f"إرسال ناجح للمشترك -> {target}")
        except Exception as e:
            logger.error(f"فشل الإرسال إلى {target}: {e}")


# ============================================================
#                  معالجة الرسائل والأوامر
# ============================================================

@app.on_message(filters.incoming)
async def process_incoming(client: Client, message: Message):
    global FILTER_INTENT_ACTIVE
    try:
        text = message.text or message.caption or ""
        if not text:
            return

        # 1. الاستجابة لأمر تثبيت الفلترة /نية_طلب
        if text.startswith("/نية_طلب") or text.startswith("/نية طلب"):
            FILTER_INTENT_ACTIVE = True
            await message.reply_text(
                "✅ **تم تثبيت وتفعيل الفلترة بالذكاء الاصطناعي (نية الطلب)!**\n"
                "سيقوم البوت الآن بسحب طلبات العملاء فقط وتجاهل كافة إعلانات المندوبين والسائقين."
            )
            return

        # 2. تجاهل رسائل الحساب نفسه
        me = await client.get_me()
        if message.from_user and message.from_user.id == me.id:
            return

        # 3. التأكد من تفعيل نظام الفلترة ووضع منع التكرار
        if not FILTER_INTENT_ACTIVE or await is_duplicate(message, text):
            return

        # 4. تحليل النية عبر الذكاء الاصطناعي
        logger.info(f"فحص نية الطلب بالذكاء الاصطناعي: {text[:50]}")
        is_customer_request = await ask_openrouter(text)

        if is_customer_request:
            logger.info("✅ نية طلب زبون مؤكدة -> جاري الإرسال للمشتركين")
            await send_to_targets(message, text)
        else:
            logger.info("❌ تم استبعاد الرسالة (إعلان سائق/مندوب أو ليست طلب توصيل)")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.exception(f"خطأ أثناء معالجة الرسالة: {e}")


# ============================================================
#                       التشغيل الرئيسي
# ============================================================

async def main():
    logger.info("🚀 جاري تشغيل البوت ونظام فلترة النية بالذكاء الاصطناعي...")
    asyncio.create_task(cleanup_processed_messages())
    await app.start()
    logger.info("✅ الحساب متصل بنجاح وجاهز لاستقبال طلبات الزبائن.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("تم إيقاف التشغيل.")

