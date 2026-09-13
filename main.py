import os
import asyncio
import hashlib
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from groq import Groq

from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

# =========================================================
# KEEP ALIVE SERVER
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Free Groq AI Active!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# =========================================================
# CONFIGURATION & GROQ CLIENT
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()

API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4")

groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        print("✅ تم الاتصال بمكتبة Groq بنجاح", flush=True)
    except Exception as e:
        print(f"❌ [Groq Init Error] {e}", flush=True)

TARGET_USERS = ["@shaybq", "@Waaaaaaa33", "@abood1317"]

PROCESSED_MESSAGES = set()
PROCESSED_CONTENT = set()

def clean_text(text):
    if not text:
        return ""
    return " ".join(text.strip().split())

# =========================================================
# FREE AI ANALYSIS (GROQ)
# =========================================================

def analyze_with_ai(text):
    if not GROQ_API_KEY or not groq_client:
        return False

    prompt = f"""
أنت نظام ذكاء اصطناعي لفرز رسائل التليجرام.
حدد هل الكاتب زبون/عميل يبحث عن خدمة توصيل أو مشوار؟

قواعد صارمة جداً:
1. إذا كان زبون يطلب توصيل/مشوار/سائق -> true
2. إذا كان سائق/مندوب يعرض خدمته -> false
3. إذا كان كلام عام أو استفسارات لا تتعلق بطلب مشوار -> false

النص للتحليل: "{text}"

أرجع JSON فقط بالشكل التالي ودون أي كلام إضافي:
{{"is_client": true}} أو {{"is_client": false}}
"""

    models_to_try = [
        "llama-3.3-70b-versatile",
        "llama3-70b-8192",
        "mixtral-8x7b-32768",
        "llama-3.1-8b-instant"
    ]

    for model_name in models_to_try:
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                temperature=0,
                response_format={"type": "json_object"}
            )
            raw_text = response.choices[0].message.content.strip()
            ai = json.loads(raw_text)
            res = bool(ai.get("is_client", False))
            return res
        except Exception:
            continue

    return False

# =========================================================
# MESSAGE PROCESSING & FORWARDING
# =========================================================

async def process_and_send(userbot, bot_app, message: Message):
    if not message or not message.id:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MESSAGES:
        return
    PROCESSED_MESSAGES.add(msg_key)

    if len(PROCESSED_MESSAGES) > 10000:
        PROCESSED_MESSAGES.clear()

    raw_text = clean_text(message.text or message.caption or "")
    if len(raw_text) < 3:
        return

    content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
    if content_hash in PROCESSED_CONTENT:
        return

    chat_title = message.chat.title or message.chat.first_name or "مجموعة"
    print(f"📩 [رسالة جديدة من {chat_title}]: {raw_text[:30]}...", flush=True)

    is_client = await asyncio.to_thread(analyze_with_ai, raw_text)
    if not is_client:
        return

    PROCESSED_CONTENT.add(content_hash)

    buttons = []
    if message.from_user:
        username = message.from_user.username
        user_id = message.from_user.id
        user_url = f"https://t.me/{username}" if username else f"tg://openmessage?user_id={user_id}"
        buttons.append(InlineKeyboardButton("💬 فتح المحادثة", url=user_url))

    if message.link:
        buttons.append(InlineKeyboardButton("📩 فتح الرسالة", url=message.link))

    reply_markup = InlineKeyboardMarkup([buttons]) if buttons else None
    text_to_send = f"📍 **طلب توصيل جديد من {chat_title}:**\n\n{raw_text}"

    for user in TARGET_USERS:
        # المحاولة عبر اليوزربوت أولاً
        try:
            await userbot.send_message(chat_id=user, text=text_to_send, reply_markup=reply_markup, disable_web_page_preview=True)
            print(f"🎯 [تم الإرسال عبر اليوزربوت إلى {user}]", flush=True)
        except Exception as e1:
            # إذا فشل اليوزربوت يجرب عبر البوت المساعد
            try:
                if bot_app:
                    await bot_app.send_message(chat_id=user, text=text_to_send, reply_markup=reply_markup, disable_web_page_preview=True)
                    print(f"🎯 [تم الإرسال عبر البوت إلى {user}]", flush=True)
            except Exception as e2:
                print(f"❌ [فشل الإرسال إلى {user}]: {e1} | {e2}", flush=True)

# =========================================================
# MAIN ENTRYPOINT
# =========================================================

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "my_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    bot_app = None
    if BOT_TOKEN:
        try:
            bot_app = Client(
                "helper_bot",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                in_memory=True
            )
            await bot_app.start()
        except Exception as e:
            print(f"⚠️ لم يتم تشغيل البوت المساعد: {e}", flush=True)

    @userbot.on_message(filters.all)
    async def global_listener(client, message):
        await process_and_send(client, bot_app, message)

    await userbot.start()
    print("✅ تم تشغيل اليوزربوت بنجاح!", flush=True)

    # تحديث الحوارات مرة واحدة فقط لربط جميع الجروبات دون حظر
    print("🔄 ربط جميع الجروبات والمحادثات...", flush=True)
    try:
        async for dialog in userbot.get_dialogs(limit=200):
            pass
        print("✅ تم ربط جميع المجموعات والقنوات بنجاح دون أي حظر!", flush=True)
    except Exception as e:
        print(f"⚠️ تنبيه أثناء الربط: {e}", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

