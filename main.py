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
# SMART HYBRID ANALYSIS (فحص ذكي مزدوج لا يخطئ)
# =========================================================

# كلمات عروض السائقين الصريحة فقط للاستبعاد
DRIVER_EXCLUDES = [
    "متوفر توصيل", "أنا سائق", "انا سائق", "سيارة مع سائق", 
    "يتوفر لدينا توصيل", "نوصل طلباتكم", "أبشر بالخدمة"
]

# مؤشرات سياق الطلب المباشر
CLIENT_INDICATORS = [
    "احتاج", "أحتاج", "ابي", "أبي", "مطلوب", "مين فاضي", "من فاضي", 
    "يوصلني", "يرجعني", "يوصل", "مشوار", "توصيله", "توصيلة", "في احد", "سواق"
]

def analyze_smart(text):
    text_lower = text.lower()

    # 1. إذا كان إعلان سائق صريح -> استبعاد
    for ex in DRIVER_EXCLUDES:
        if ex in text_lower:
            return False, "إعلان سائق"

    # 2. فحص سياق العميل الفوري (إذا احتوت أي مؤشر عميل تعتبر صحيحة مباشرة)
    for ind in CLIENT_INDICATORS:
        if ind in text_lower:
            return True, "مطابقة سياق العميل الفوري"

    # 3. الاستعانة بالذكاء الاصطناعي للرسائل المبهمة فقط
    if GROQ_API_KEY and groq_client:
        prompt = f"""Is this message a request from a customer looking for a taxi/ride/delivery service?
Message: "{text}"
Reply with ONLY 'YES' or 'NO'."""
        
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0,
                max_tokens=3
            )
            res = response.choices[0].message.content.strip().upper()
            if "YES" in res:
                return True, "تحليل Groq AI"
        except Exception:
            pass

    return False, "غير مطابقة"

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
    print(f"📩 [رسالة جديدة من {chat_title}]: {raw_text}", flush=True)

    # التحليل المزدوج
    is_client, reason = analyze_smart(raw_text)
    print(f"🎯 [النتيجة]: {is_client} | السبب: ({reason})", flush=True)

    if not is_client:
        print(f"⛔ [تجاهل الرسالة]: {reason}", flush=True)
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
        try:
            await userbot.send_message(chat_id=user, text=text_to_send, reply_markup=reply_markup, disable_web_page_preview=True)
            print(f"✅ [تم الإرسال بنجاح عبر اليوزربوت إلى {user}]", flush=True)
        except Exception as e1:
            if bot_app:
                try:
                    await bot_app.send_message(chat_id=user, text=text_to_send, reply_markup=reply_markup, disable_web_page_preview=True)
                    print(f"✅ [تم الإرسال بنجاح عبر البوت إلى {user}]", flush=True)
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
    print("✅ تم تشغيل نظام التصفية المزدوج الذكي بنجاح!", flush=True)

    try:
        async for dialog in userbot.get_dialogs(limit=200):
            pass
        print("✅ تم ربط جميع المجموعات والقنوات بنجاح!", flush=True)
    except Exception as e:
        print(f"⚠️ تنبيه أثناء الربط: {e}", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
