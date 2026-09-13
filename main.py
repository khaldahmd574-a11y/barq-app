import os
import asyncio
import hashlib
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from groq import Groq

from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
# KEEP ALIVE SERVER
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Smart AI Active!")

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
# PURE AI ANALYSIS (ذكاء اصطناعي شامل بدون كلمات محددة)
# =========================================================

def analyze_with_pure_ai(text):
    # 1. استبعاد أرقام الهواتف مباشرة لأنها عروض سائقين/تجارية
    if re.search(r'(05\d{8}|\+?9665\d{8})', text):
        return False, "تجاهل: تحتوي على رقم جوال (سائق/إعلان)"

    if not GROQ_API_KEY or not groq_client:
        return True, "تمرير تلقائي (لا يوجد مفتاح Groq)"

    prompt = f"""
أنت نظام ذكاء اصطناعي خبير لفرز الرسائل في مجموعات التوصيل السعودية (منطقة جازان وما حولها).
وظيفتك: قراءة الرسالة وتحديد هل الكاتب "زبون/عميل" يطلب توصيل أو يبحث عن سائق/مندوب/سواقة/مشوار؟

أمثلة لرسائل العميل المقبولة (أجب بـ YES):
- "مندوب فاضي قريب من مخطط 5"
- "سواقه توصلني بيش"
- "فيه مندوب ف ابو عريش ؟"
- "من يوديني المطار"
- "احتاج احد يرجعني"
- "سيارة توديني صامطه"
- "ابي مشوار"

أمثلة لرسائل السائق أو الإعلانات التلقائية (أجب بـ NO):
- "توصيل طلبات ومشاوير تواصل خاص"
- "أنا سائق متوفر الآن"
- "نوصل لجميع المناطق"
- "موجود سيارة كامري"

الرسالة المراد تحليلها: "{text}"

أجب فقط بكلمة واحدة: YES إذا كانت طلب زبون، أو NO إذا كانت عرض سائق/كلام عام.
"""

    models_to_try = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768"
    ]

    for model_name in models_to_try:
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                temperature=0,
                max_tokens=3
            )
            raw_res = response.choices[0].message.content.strip().upper()
            if "YES" in raw_res:
                return True, f"ذكاء اصطناعي مقبول ({model_name})"
            elif "NO" in raw_res:
                return False, f"ذكاء اصطناعي مرفوض - عرض سائق أو كلام عام ({model_name})"
        except Exception:
            continue

    return True, "تمرير احتياطي لتعثر AI"

# =========================================================
# MESSAGE PROCESSING & FORWARDING
# =========================================================

async def process_and_send(userbot, bot_app, message: Message):
    if not message or not message.id:
        return

    # تجاهل الرسائل الصادرة من الحساب الوهمي نفسه أو من البوت
    if message.from_user and message.from_user.is_self:
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

    # تحليل الذكاء الاصطناعي الصافي
    is_client, reason = analyze_with_pure_ai(raw_text)
    print(f"🤖 [قرار الذكاء الاصطناعي]: {is_client} | السبب: {reason}", flush=True)

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
    
    # إرسال المنشور الأصلي فقط بدون أي عناوين أو مقدمات
    text_to_send = raw_text

    # الإرسال بالبوت الحصري
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

    # استقبال الرسائل من جميع المجموعات والقنوات التي يشترك فيها الحساب الوهمي
    @userbot.on_message(filters.all)
    async def global_listener(client, message):
        await process_and_send(client, bot_app, message)

    await userbot.start()
    print("✅ تم تشغيل المحرك لجميع المجموعات والقنوات بنجاح!", flush=True)

    try:
        async for dialog in userbot.get_dialogs(limit=500):
            pass
        print("✅ تم مزامنة جميع الدردشات بنجاح!", flush=True)
    except Exception as e:
        print(f"⚠️ تنبيه أثناء المزامنة: {e}", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

