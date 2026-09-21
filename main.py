import os
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
PORT = int(os.getenv("PORT", "10000"))

env_targets = os.getenv("TARGET_USERS", "")
if env_targets:
    TARGET_USERS = [t.strip() for t in env_targets.split(",") if t.strip()]
else:
    TARGET_USERS = ["@abood1317", "@shaybq"]

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

# ============================================================
#            إرسال النتائج المباشرة للمستهدفين
# ============================================================

async def send_to_targets(message: Message, text: str):
    sender_name = message.from_user.first_name if message.from_user else "عميل"
    chat_name = message.chat.title or "محادثة خاصة"
    
    user_link = f"https://t.me/{message.from_user.username}" if message.from_user and message.from_user.username else f"tg://user?id={message.from_user.id}" if message.from_user else ""

    output = f"📦 رسالة جديدة من: {sender_name}\n📍 المصدر: {chat_name}\n\n💬 النص:\n{text}"
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
                        logger.error(f"❌ [فشل الإرسال لـ {target}]: {res_json}")
        except Exception as e:
            logger.error(f"❌ [خطأ شبكة مع {target}]: {e}")

# ============================================================
#           استماع مباشر وصريح لكافة الرسائل (Direct Hook)
# ============================================================

@app.on_message(filters.all)
async def process_all_messages(client: Client, message: Message):
    try:
        text = message.text or message.caption or ""
        if not text:
            return

        chat_title = message.chat.title or "خاص"
        logger.info(f"📥 [تم سحب رسالة من {chat_title}]: {text[:40]}")

        # عدم إعادة معالجة الرسائل التي يكتبها الحساب نفسه
        me = await client.get_me()
        if message.from_user and message.from_user.id == me.id:
            return

        # إرسال مباشر بدون التعقيد بالذكاء الاصطناعي لتأكيد السحب
        await send_to_targets(message, text)

    except Exception as e:
        logger.exception(f"❌ [خطأ]: {e}")

# ============================================================
#                       التشغيل
# ============================================================

async def main():
    logger.info("🚀 تشغيل اليوزربوت واستماع كلي مباشر...")
    await app.start()
    me = await app.get_me()
    logger.info(f"✅ الحساب متصل: {me.first_name}")
    logger.info(f"🎯 المستهدفين: {TARGET_USERS}")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

