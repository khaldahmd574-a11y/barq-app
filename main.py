import os
import asyncio
import hashlib
import re
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
        self.wfile.write(b"Barq Bot Active!")

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
# SMART FILTERING SYSTEM (تمييز الزبون عن السائق)
# =========================================================

# مؤشرات صريحة لأصحاب العروض والسائقين
DRIVER_KEYWORDS = [
    "تفضل خاص", "تفضلي خاص", "تواصل خاص", "تواصل معي", "خاص", 
    "متوفر", "متوفره", "متوفرين", "جاهز", "نوصل", "توصيل طلبات", 
    "أنا سائق", "انا سائق", "خدمة توصيل", "أسعار مناسبة", "اسعار مناسبه",
    "نوصلكم", "جاهزين", "تحت خدمتكم", "ابشر بالخير", "أبشر بالخير"
]

# مؤشرات طلب العميل المباشر
CLIENT_KEYWORDS = [
    "ابغى", "أبغى", "ابي", "أبي", "احتاج", "أحتاج", "مطلوب", 
    "مين فاضي", "من فاضي", "حد فاضي", "أحد فاضي", "من يوصلني", "مين يوصلني",
    "يرجعني", "يوصلني", "يوصل صبيـا", "يوصل صامطه", "في احد يوصل", "في أحد يوصل"
]

def analyze_message_type(text):
    text_clean = text.lower()

    # 1. فحص وجود رقم جوال -> غالباً سائق يعرض رقم تواصله
    if re.search(r'(05\d{8}|\+?9665\d{8})', text):
        return False, "إعلان سائق (يحتوي على رقم جوال)"

    # 2. فحص كلمات السائق العارضة للخدمة
    for drv in DRIVER_KEYWORDS:
        if drv in text_clean:
            return False, f"عرض سائق ({drv})"

    # 3. فحص كلمات العميل المباشرة
    for cli in CLIENT_KEYWORDS:
        if cli in text_clean:
            return True, f"طلب عميل صريح ({cli})"

    # 4. الاستعانة بالذكاء الاصطناعي للرسائل غير الواضحة
    if GROQ_API_KEY and groq_client:
        prompt = f"""
تقييم رسالة تليجرام:
هل صاحب هذه الرسالة زبون/عميل يبحث عن سائق ليقوم بتوصيله؟ أم أنه سائق يعرض خدمته؟

الرسالة: "{text}"

أجب فقط بكلمة واحدة:
CUSTOMER : إذا كانت الرسالة طلب توصيل من زبون.
DRIVER : إذا كانت من سائق أو تحتوي عرض خدمة أو إعلان.
"""
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="llama-3.3-70b-versatile",
                temperature=0,
                max_tokens=5
            )
            res = response.choices[0].message.content.strip().upper()
            if "CUSTOMER" in res:
                return True, "ذكاء اصطناعي (عميل)"
            else:
                return False, "ذكاء اصطناعي (سائق/غير مطاطق)"
        except Exception:
            pass

    return False, "لم تتطابق مع طلب عميل"

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

    # التحليل والفرز
    is_client, reason = analyze_message_type(raw_text)
    print(f"🎯 [التقييم]: {is_client} | السبب: {reason}", flush=True)

    if not is_client:
        print(f"⛔ [تجاهل]: {reason}", flush=True)
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

    # الإرسال عبر البوت أولاً (bot_app)
    for user in TARGET_USERS:
        sent_successfully = False
        if bot_app:
            try:
                await bot_app.send_message(chat_id=user, text=text_to_send, reply_markup=reply_markup, disable_web_page_preview=True)
                print(f"🤖 [تم الإرسال عبر البوت إلى {user}]", flush=True)
                sent_successfully = True
            except Exception as e_bot:
                print(f"⚠️ [فشل إرسال البوت إلى {user}]: {e_bot}", flush=True)

        # البديل: الإرسال عبر الحساب إذا تعذر البوت
        if not sent_successfully:
            try:
                await userbot.send_message(chat_id=user, text=text_to_send, reply_markup=reply_markup, disable_web_page_preview=True)
                print(f"👤 [تم الإرسال عبر الحساب إلى {user}]", flush=True)
            except Exception as e_user:
                print(f"❌ [فشل الإرسال عبر الحساب والبوّت إلى {user}]: {e_user}", flush=True)

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
            print("✅ تم تشغيل البوت المساعد للتحويل بنجاح!", flush=True)
        except Exception as e:
            print(f"⚠️ خطأ في تشغيل البوت المساعد: {e}", flush=True)

    @userbot.on_message(filters.all)
    async def global_listener(client, message):
        await process_and_send(client, bot_app, message)

    await userbot.start()
    print("✅ تم تشغيل السكربت ونظام التصفية المحدث!", flush=True)

    try:
        async for dialog in userbot.get_dialogs(limit=200):
            pass
        print("✅ تم ربط المجموعات بنجاح!", flush=True)
    except Exception as e:
        print(f"⚠️ تنبيه أثناء الربط: {e}", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

