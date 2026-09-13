import os
import asyncio
import hashlib
import re
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from groq import Groq

from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
# KEEP ALIVE SERVER & SELF PINGER (منع النوم نهائياً)
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Smart AI Active 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# وظيفة إيقاظ السيرفر كل 3 دقائق لئلا ينام على منصة Render
def keep_awake():
    app_name = os.environ.get("RENDER_SERVICE_NAME", "")
    url = f"https://{app_name}.onrender.com" if app_name else "http://127.0.0.1:10000"
    while True:
        try:
            asyncio.run(asyncio.sleep(180)) # كل 3 دقائق
            urllib.request.urlopen(url, timeout=10)
            print("⏰ [Self-Ping]: تم تنشيط السيرفر لمنع النوم.", flush=True)
        except Exception:
            pass

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
AI_CACHE = {}

def clean_text(text):
    if not text:
        return ""
    return " ".join(text.strip().split())

# =========================================================
# ADVANCED GROQ AI ANALYSIS
# =========================================================

def analyze_with_groq_smart(text):
    if re.search(r'(05\d{8}|\+?9665\d{8})', text):
        return False, "تجاهل: رقم جوال (إعلان/سائق)"

    if text in AI_CACHE:
        return AI_CACHE[text], "مقبول من الذاكرة المؤقتة (Cache)"

    fallback_keywords = ["مين", "من", "فاضي", "ابي", "ابغى", "احتاج", "يوصلني", "توديني", "مشوار", "مندوب", "صامطه", "صامطة", "المطار", "سواقه", "سواقة"]

    if not GROQ_API_KEY or not groq_client:
        for kw in fallback_keywords:
            if kw in text.lower():
                return True, "مقبول عبر الطوارئ المحلية"
        return False, "تجاهل: لا يوجد مفتاح Groq"

    prompt = f"""أنت ذكاء اصطناعي لتصنيف رسائل مجموعات تليجرام.
حدد هل الرسالة التالية هي "طلب توصيل / مشوار / بحث عن سواق أو مندوب" قادم من زبون؟
أجب بكلمة واحدة فقط: YES أو NO.

الرسالة: "{text}"
الجواب:"""

    models = [
        "llama-3.1-8b-instant",
        "llama3-8b-8192",
        "mixtral-8x7b-32768"
    ]

    for model_name in models:
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                temperature=0,
                max_tokens=2
            )
            raw_res = response.choices[0].message.content.strip().upper()
            is_valid = "YES" in raw_res
            
            AI_CACHE[text] = is_valid
            if len(AI_CACHE) > 500:
                AI_CACHE.clear()
                
            return is_valid, f"قرار Groq الذكي ({model_name})"
        except Exception:
            continue

    for kw in fallback_keywords:
        if kw in text.lower():
            return True, "مقبول عبر الطوارئ الذكية"

    return False, "غير مقبول"

# =========================================================
# MESSAGE PROCESSING & FORWARDING
# =========================================================

async def process_and_send(userbot, bot_app, message: Message):
    if not message or not message.id:
        return

    if message.from_user and message.from_user.is_self:
        return

    chat_title = message.chat.title or message.chat.first_name or f"Chat_{message.chat.id}"
    
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

    print(f"📩 [رسالة واردة من {chat_title}]: {raw_text}", flush=True)

    is_client, reason = analyze_with_groq_smart(raw_text)
    print(f"🤖 [التقييم]: {is_client} | السبب: {reason}", flush=True)

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
    text_to_send = f"📌 من: {chat_title}\n\n{raw_text}"

    for user in TARGET_USERS:
        sent = False
        if bot_app:
            try:
                await bot_app.send_message(chat_id=user, text=text_to_send, reply_markup=reply_markup, disable_web_page_preview=True)
                print(f"🤖 [تم الإرسال عبر البوت إلى {user}]", flush=True)
                sent = True
            except Exception as e_bot:
                print(f"⚠️ [فشل إرسال البوت إلى {user}]: {e_bot}", flush=True)

        if not sent:
            try:
                await userbot.send_message(chat_id=user, text=text_to_send, reply_markup=reply_markup, disable_web_page_preview=True)
                print(f"👤 [تم الإرسال عبر الحساب إلى {user}]", flush=True)
            except Exception as e_user:
                print(f"❌ [فشل الإرسال إلى {user}]: {e_user}", flush=True)

# =========================================================
# MAIN ENTRYPOINT
# =========================================================

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()
    threading.Thread(target=keep_awake, daemon=True).start()

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
            print("✅ تم تشغيل البوت المساعد لإرسال التنبيهات!", flush=True)
        except Exception as e:
            print(f"⚠️ خطأ في تشغيل البوت: {e}", flush=True)

    # الاستماع لجميع القنوات والجروبات بدون مرشحات معقدة
    @userbot.on_message()
    async def global_listener(client, message):
        if message.chat and message.chat.type.value in ["group", "supergroup", "channel"]:
            await process_and_send(client, bot_app, message)

    await userbot.start()
    print("✅ تم تشغيل المحرك الرئيسي!", flush=True)

    # جلب وإجبار الاشتراك في أحداث جميع المجموعات بلا استثناء
    try:
        count = 0
        async for dialog in userbot.get_dialogs():
            count += 1
        print(f"🔥 تم تفعيل البث المباشر وربط {count} مجموعة وقناة بنجاح 24/7!", flush=True)
    except Exception as e:
        print(f"⚠️ تنبيه أثناء الربط: {e}", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

