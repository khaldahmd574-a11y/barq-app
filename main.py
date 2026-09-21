import os
import json
import time
import asyncio
import hashlib
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp
from hydrogram import Client
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
    TARGET_USERS = ["@abood1317", "@shaybq"]

# ============================================================
#                       Logging الشامل
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("BARQ_DEBUG")

# ============================================================
#                     Keep Alive Server
# ============================================================

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Barq Userbot Active")
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
#             AI SYSTEM PROMPT (فحص نية الزبون)
# ============================================================

AI_SYSTEM_PROMPT = "حدد هل الرسالة طلب توصيل من زبون؟ أجب بـ YES أو NO فقط."

async def ask_openrouter(text: str) -> bool:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        "temperature": 0.0,
        "max_tokens": 10
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(OPENROUTER_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"].strip().upper()
                    res_bool = "YES" in content
                    logger.info(f"🤖 [استجابة الذكاء الاصطناعي]: {res_bool} ({content})")
                    return res_bool
                else:
                    logger.error(f"❌ [خطأ OpenRouter]: رمز {response.status}")
    except Exception as e:
        logger.error(f"❌ [خطأ الذكاء الاصطناعي]: {e}")
    return False

# ============================================================
#            إرسال النتائج للمستهدفين وتتبع الأخطاء
# ============================================================

async def send_to_targets(message: Message, text: str):
    sender_name = message.from_user.first_name if message.from_user else "عميل"
    chat_name = message.chat.title or "محادثة خاصة"
    
    user_link = f"https://t.me/{message.from_user.username}" if message.from_user and message.from_user.username else f"tg://user?id={message.from_user.id}" if message.from_user else ""

    output = f"📦 طلب جديد من: {sender_name}\n📍 المصدر: {chat_name}\n\n💬 التفاصيل:\n{text}"
    if user_link:
        output += f"\n\n👤 رابط العميل: {user_link}"

    for target in TARGET_USERS:
        payload = {
            "chat_id": target,
            "text": output,
            "disable_web_page_preview": True,
        }
        try:
            url = f"{BOT_API}/sendMessage"
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    res_json = await resp.json()
                    if res_json.get("ok"):
                        logger.info(f"✅ [تم الإرسال بنجاح للهدف]: {target}")
                    else:
                        logger.error(f"❌ [فشل إرسال البوت لـ {target}]: {res_json}")
        except Exception as e:
            logger.error(f"❌ [خطأ شبكة مع {target}]: {e}")

# ============================================================
#               معالج الرسائل واكتشاف المشاكل
# ============================================================

@app.on_message()
async def process_all_messages(client: Client, message: Message):
    try:
        text = message.text or message.caption or ""
        if not text:
            return

        chat_title = message.chat.title or "خاص"
        logger.info(f"📥 [رسالة من: {chat_title}]: {text[:40]}")

        # أمر اختبار فوري
        if text.strip() in ["/تست", "/test"]:
            logger.info("🧪 [تشغيل اختبار الإرسال...]")
            await send_to_targets(message, "اختبار إرسال مباشر لتأكد وصول الرسائل ✅")
            return

        me = await client.get_me()
        if message.from_user and message.from_user.id == me.id:
            return

        if await is_duplicate(message, text):
            return

        is_request = await ask_openrouter(text)

        if is_request:
            logger.info("✅ طلب عميل -> جاري الإرسال...")
            await send_to_targets(message, text)
        else:
            logger.info("❌ ليست طلب عميل")

    except Exception as e:
        logger.exception(f"❌ [خطأ]: {e}")

# ============================================================
#                       التشغيل
# ============================================================

async def main():
    logger.info("🚀 جاري بدء اليوزربوت...")
    await app.start()
    me = await app.get_me()
    logger.info(f"✅ الحساب متصل: {me.first_name}")
    logger.info(f"🎯 المستهدفين: {TARGET_USERS}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

