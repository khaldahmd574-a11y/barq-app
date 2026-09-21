import os
import re
import json
import time
import asyncio
import hashlib
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp
from hydrogram import Client, filters
from hydrogram.types import Message


# ============================================================
#                    إعدادات Environment
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

AI_TIMEOUT = 12
DEDUP_TTL = 60 * 60 * 24

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("BARQ_AI")


# ============================================================
#                     Keep Alive Server
# ============================================================

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Barq AI Userbot Active")
        except Exception:
            pass

    def log_message(self, format, *args):
        return

threading.Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), KeepAliveHandler).serve_forever(), daemon=True).start()


# ============================================================
#                    Hydrogram Client
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
    except Exception:
        return False


# ============================================================
#             AI SYSTEM PROMPT (فحص نية الزبون vs السائق)
# ============================================================

AI_SYSTEM_PROMPT = """أنت نظام ذكاء اصطناعي مخصص لفلترة طلبات التوصيل.

مهمتك: تحديد هل الرسالة صادرة من زبون يحتاج توصيل أم من سائق يعرض خدمته.

أخرج كائن JSON فقط:
{"allow": true} أو {"allow": false}

القواعد:
1. اجعل {"allow": true} فقط إذا كان الكاتب زبوناً يطلب توصيل أو مشوار (مثال: "مين يوصلني"، "احتاج سواق"، "مطلوب توصيل اغراض").
2. اجعل {"allow": false} إذا كان الكاتب سائقاً أو مندوباً يعرض خدماته أو يتواجد في مكان (مثال: "متواجد للمشاوير"، "سائق خاص"، "فاضي للطلب"، وجود أرقام جوال وإعلانات).
"""

async def ask_openrouter(text: str) -> bool:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": f"حلل النية: \"{text}\""}
        ],
        "temperature": 0.0,
        "max_tokens": 20
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT)) as session:
            async with session.post(OPENROUTER_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    content_clean = re.sub(r"```json|```", "", content).strip()
                    result = json.loads(content_clean)
                    return bool(result.get("allow", False))
    except Exception as e:
        logger.error(f"AI Error: {e}")
    return False


# ============================================================
#                  إرسال النتائج للمستهدفين
# ============================================================

async def send_to_targets(message: Message, text: str):
    sender_name = message.from_user.first_name if message.from_user else "عميل"
    chat_name = message.chat.title or "مجموعة"
    
    user_link = f"https://t.me/{message.from_user.username}" if message.from_user and message.from_user.username else f"tg://user?id={message.from_user.id}" if message.from_user else None

    output = (
        "📦 <b>طلب عميل جديد (نية طلب)</b>\n\n"
        f"👤 <b>العميل:</b> {sender_name}\n"
        f"📍 <b>المصدر:</b> {chat_name}\n\n"
        f"💬 <b>التفاصيل:</b>\n{text}"
    )

    buttons = []
    if user_link:
        buttons.append({"text": "👤 محادثة العميل", "url": user_link})
    
    keyboard = {"inline_keyboard": [buttons]} if buttons else None

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
            url = f"{BOT_API}/sendMessage"
            async with aiohttp.ClientSession() as session:
                await session.post(url, json=payload)
            logger.info(f"تم الإرسال لـ {target}")
        except Exception as e:
            logger.error(f"فشل الإرسال لـ {target}: {e}")


# ============================================================
#              معالج الرسائل (التقاط شامل وشفاف)
# ============================================================

@app.on_message()
async def process_all_messages(client: Client, message: Message):
    try:
        # 1. عدم معالجة الرسائل التي يكتبها الحساب بنفسه
        me = await client.get_me()
        if message.from_user and message.from_user.id == me.id:
            return

        text = message.text or message.caption or ""
        if not text:
            return

        # 2. طباعة الرسالة فوراً في الـ Logs لتأكيد السحب
        logger.info(f"📥 [تم سحب رسالة]: {text[:60]}")

        # 3. منع التكرار
        if await is_duplicate(message, text):
            return

        # 4. فحص نية الطلب بالذكاء الاصطناعي
        is_request = await ask_openrouter(text)

        if is_request:
            logger.info("✅ طلب زبون مؤكد -> جاري الإرسال للمشتركين")
            await send_to_targets(message, text)
        else:
            logger.info("❌ إعلان سائق / غير مطابقة")

    except Exception as e:
        logger.exception(f"خطأ أثناء معالجة الرسالة: {e}")


# ============================================================
#                       التشغيل
# ============================================================

async def main():
    logger.info("🚀 تشغيل اليوزربوت واستماع جميع الرسائل بدون فلاتر معقدة...")
    await app.start()
    logger.info("✅ الحساب متصل بنجاح وجاهز لسحب كل النص الصادر والوارد.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

