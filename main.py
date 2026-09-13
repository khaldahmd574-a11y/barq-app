import os
import asyncio
import hashlib
import json
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from groq import Groq

from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait


# =========================================================
# KEEP ALIVE - RENDER
# =========================================================

class DummyServer(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(
            b"Barq Jazan - Groq AI is running!"
        )

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return


def run_dummy_server():
    port = int(os.environ.get("PORT", "10000"))

    server = HTTPServer(
        ("0.0.0.0", port),
        DummyServer
    )

    print(
        f"🌐 Keep-Alive server running on port {port}",
        flush=True
    )

    server.serve_forever()


# =========================================================
# ENVIRONMENT
# =========================================================

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    ""
).strip()

GROQ_API_KEY = os.environ.get(
    "GROQ_API_KEY",
    ""
).strip()

SESSION_STRING = os.environ.get(
    "SESSION_STRING",
    ""
).strip()


API_ID = int(
    os.environ.get(
        "TELEGRAM_API_ID",
        "39120728"
    )
)

API_HASH = os.environ.get(
    "TELEGRAM_API_HASH",
    "1deec8393ce5aa05c54c0c7e280377d4"
).strip()


# =========================================================
# TARGET USERS
# =========================================================

TARGET_USERS = [
    "@abood1317",
    "@Waaaaaaa33",
    "@shaybq"
]


# =========================================================
# GROQ
# =========================================================

groq_client = None

if GROQ_API_KEY:

    try:

        groq_client = Groq(
            api_key=GROQ_API_KEY
        )

        print(
            "✅ Groq AI connected successfully",
            flush=True
        )

    except Exception as e:

        print(
            f"❌ Groq initialization error: {e}",
            flush=True
        )

else:

    print(
        "❌ GROQ_API_KEY غير موجود",
        flush=True
    )


# =========================================================
# MEMORY / DEDUPLICATION
# =========================================================

PROCESSED_MESSAGES = set()
PROCESSED_CONTENT = {}

MEMORY_LOCK = asyncio.Lock()


# =========================================================
# AI SETTINGS
# =========================================================

AI_MODEL = "openai/gpt-oss-120b"

# عدد طلبات AI المتزامنة
AI_CONCURRENCY = 8

AI_SEMAPHORE = asyncio.Semaphore(
    AI_CONCURRENCY
)


# =========================================================
# TEXT CLEANING
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = str(text)

    # إزالة المسافات الزائدة
    text = " ".join(
        text.strip().split()
    )

    return text


# =========================================================
# HASH
# =========================================================

def make_hash(text):

    normalized = clean_text(text).lower()

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


# =========================================================
# CLEAN MEMORY
# =========================================================

def cleanup_memory():

    now = time.time()

    # الاحتفاظ بالمحتوى لمدة 24 ساعة
    expired = [
        h
        for h, timestamp in PROCESSED_CONTENT.items()
        if now - timestamp > 86400
    ]

    for h in expired:
        PROCESSED_CONTENT.pop(
            h,
            None
        )

    # منع تضخم الذاكرة
    if len(PROCESSED_MESSAGES) > 50000:

        PROCESSED_MESSAGES.clear()

    if len(PROCESSED_CONTENT) > 50000:

        PROCESSED_CONTENT.clear()


# =========================================================
# GROQ AI CLASSIFIER
# =========================================================

def analyze_with_ai_sync(text):

    if not groq_client:
        return False

    if not text:
        return False

    system_prompt = """
أنت نظام تصنيف ذكي لرسائل مجموعات تيليجرام في السعودية.

مهمتك الوحيدة:
تحديد هل الرسالة كتبها "عميل/زبون" يبحث فعليًا عن سائق أو مندوب أو توصيل أو مشوار أو نقل غرض/طلب.

لا تعتمد على كلمات محددة.
افهم معنى الرسالة وسياقها بالكامل.

صنّف TRUE إذا كان واضحًا أو مرجحًا أن الكاتب:
- يبحث عن شخص يوصله.
- يبحث عن سائق أو سائقة.
- يريد مندوبًا.
- يريد توصيل طلب أو غرض.
- يسأل عن شخص فاضي/قريب لتنفيذ مشوار.
- يريد نقل شيء من مكان إلى مكان.
- يطلب مشوارًا له أو لشخص آخر.
- يبحث عن خدمة توصيل أو مشوار.

صنّف FALSE إذا كان:
- سائقًا أو مندوبًا يعرض خدماته.
- إعلانًا عن سائق أو مندوب.
- إعلانًا تجاريًا.
- منشورًا عامًا.
- نقاشًا.
- تحية.
- سؤالًا غير متعلق بطلب خدمة.
- رسالة لا يوجد فيها طلب حقيقي.
- شخصًا يعلن أنه متوفر للعمل.
- منشورًا يشرح أسعار أو خدمات سائق دون أن يكون الكاتب طالبًا للخدمة.

مهم جدًا:
لا تعتبر وجود كلمة "سواق" أو "مندوب" وحدها كافيًا.
افهم من هو الطالب ومن هو مقدم الخدمة.

إذا كان هناك شك حقيقي، اختر FALSE.

أرجع JSON فقط:

{"is_client": true}

أو:

{"is_client": false}
"""

    try:

        response = groq_client.chat.completions.create(

            model=AI_MODEL,

            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": text
                }
            ],

            temperature=0,

            max_tokens=20,

            response_format={
                "type": "json_object"
            }
        )

        result = (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

        data = json.loads(result)

        return bool(
            data.get(
                "is_client",
                False
            )
        )

    except Exception as e:

        print(
            f"⚠️ Groq AI Error: {e}",
            flush=True
        )

        return False


# =========================================================
# ASYNC AI
# =========================================================

async def analyze_with_ai(text):

    async with AI_SEMAPHORE:

        return await asyncio.to_thread(
            analyze_with_ai_sync,
            text
        )


# =========================================================
# MESSAGE LINK
# =========================================================

def get_message_link(message):

    try:

        if message.link:
            return message.link

    except Exception:
        pass

    return None


# =========================================================
# USER LINK
# =========================================================

def get_user_link(message):

    try:

        if not message.from_user:
            return None

        username = (
            message.from_user.username
        )

        user_id = (
            message.from_user.id
        )

        if username:

            return (
                f"https://t.me/{username}"
            )

        if user_id:

            return (
                f"tg://openmessage?user_id={user_id}"
            )

    except Exception:
        pass

    return None


# =========================================================
# SEND TO TARGET
# =========================================================

async def send_to_target(
    userbot,
    bot_app,
    target,
    text,
    reply_markup
):

    # أولاً Userbot
    try:

        await userbot.send_message(
            chat_id=target,
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

        print(
            f"🎯 تم الإرسال إلى {target} عبر Userbot",
            flush=True
        )

        return True

    except FloodWait as e:

        print(
            f"⏳ FloodWait: {e.value} ثانية",
            flush=True
        )

        await asyncio.sleep(
            e.value
        )

    except Exception as e:

        print(
            f"⚠️ Userbot لم يرسل إلى {target}: {e}",
            flush=True
        )

    # ثانياً البوت المساعد
    if bot_app:

        try:

            await bot_app.send_message(
                chat_id=target,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )

            print(
                f"🎯 تم الإرسال إلى {target} عبر Bot",
                flush=True
            )

            return True

        except Exception as e:

            print(
                f"❌ فشل الإرسال إلى {target}: {e}",
                flush=True
            )

    return False


# =========================================================
# PROCESS MESSAGE
# =========================================================

async def process_and_send(
    userbot,
    bot_app,
    message
):

    if not message:
        return

    if not message.id:
        return

    # -----------------------------------------------------
    # Message ID dedupe
    # -----------------------------------------------------

    msg_key = (
        f"{message.chat.id}:"
        f"{message.id}"
    )

    async with MEMORY_LOCK:

        if msg_key in PROCESSED_MESSAGES:
            return

        PROCESSED_MESSAGES.add(
            msg_key
        )

    # -----------------------------------------------------
    # Text
    # -----------------------------------------------------

    raw_text = clean_text(
        message.text
        or
        message.caption
        or
        ""
    )

    if len(raw_text) < 3:
        return

    # -----------------------------------------------------
    # Content dedupe
    # -----------------------------------------------------

    content_hash = make_hash(
        raw_text
    )

    async with MEMORY_LOCK:

        cleanup_memory()

        if content_hash in PROCESSED_CONTENT:

            print(
                "♻️ طلب مكرر - تم تجاهله",
                flush=True
            )

            return

    # -----------------------------------------------------
    # Chat name
    # -----------------------------------------------------

    try:

        chat_title = (
            message.chat.title
            or
            message.chat.first_name
            or
            "مجموعة"
        )

    except Exception:

        chat_title = "مجموعة"

    print(
        f"📩 [{chat_title}] "
        f"{raw_text[:100]}",
        flush=True
    )

    # -----------------------------------------------------
    # AI
    # -----------------------------------------------------

    is_client = await analyze_with_ai(
        raw_text
    )

    if not is_client:

        print(
            "🚫 AI: ليست رسالة عميل",
            flush=True
        )

        return

    # -----------------------------------------------------
    # Mark as processed only AFTER AI
    # -----------------------------------------------------

    async with MEMORY_LOCK:

        PROCESSED_CONTENT[
            content_hash
        ] = time.time()

    print(
        "✅ AI: تم اكتشاف طلب عميل",
        flush=True
    )

    # -----------------------------------------------------
    # Buttons
    # -----------------------------------------------------

    buttons = []

    user_link = get_user_link(
        message
    )

    if user_link:

        buttons.append(
            InlineKeyboardButton(
                "💬 فتح حساب العميل",
                url=user_link
            )
        )

    message_link = get_message_link(
        message
    )

    if message_link:

        buttons.append(
            InlineKeyboardButton(
                "📩 فتح الرسالة",
                url=message_link
            )
        )

    reply_markup = None

    if buttons:

        reply_markup = InlineKeyboardMarkup(
            [buttons]
        )

    # -----------------------------------------------------
    # Final message
    # -----------------------------------------------------

    text_to_send = (
        f"🚗 **طلب عميل جديد**\n\n"
        f"📍 **المجموعة:** {chat_title}\n\n"
        f"💬 **الطلب:**\n"
        f"{raw_text}"
    )

    # -----------------------------------------------------
    # Send to all targets
    # -----------------------------------------------------

    for target in TARGET_USERS:

        await send_to_target(
            userbot,
            bot_app,
            target,
            text_to_send,
            reply_markup
        )


# =========================================================
# MAIN
# =========================================================

async def main():

    # -----------------------------------------------------
    # Render server
    # -----------------------------------------------------

    threading.Thread(
        target=run_dummy_server,
        daemon=True
    ).start()

    # -----------------------------------------------------
    # Validate Session
    # -----------------------------------------------------

    if not SESSION_STRING:

        print(
            "❌ SESSION_STRING غير موجود!",
            flush=True
        )

        return

    if not GROQ_API_KEY:

        print(
            "❌ GROQ_API_KEY غير موجود!",
            flush=True
        )

        return

    # -----------------------------------------------------
    # Userbot
    # -----------------------------------------------------

    userbot = Client(

        "barq_userbot",

        api_id=API_ID,

        api_hash=API_HASH,

        session_string=SESSION_STRING,

        in_memory=True
    )

    # -----------------------------------------------------
    # Helper Bot
    # -----------------------------------------------------

    bot_app = None

    if BOT_TOKEN:

        try:

            bot_app = Client(

                "barq_helper_bot",

                api_id=API_ID,

                api_hash=API_HASH,

                bot_token=BOT_TOKEN,

                in_memory=True
            )

            await bot_app.start()

            print(
                "🤖 البوت المساعد يعمل",
                flush=True
            )

        except Exception as e:

            print(
                f"⚠️ البوت المساعد لم يعمل: {e}",
                flush=True
            )

            bot_app = None

    # -----------------------------------------------------
    # Listener
    # -----------------------------------------------------

    @userbot.on_message(
        filters.all
    )
    async def global_listener(
        client,
        message
    ):

        try:

            await process_and_send(
                client,
                bot_app,
                message
            )

        except Exception as e:

            print(
                f"❌ Message Handler Error: {e}",
                flush=True
            )

    # -----------------------------------------------------
    # Start Userbot
    # -----------------------------------------------------

    try:

        await userbot.start()

        print(
            "✅ Userbot يعمل بنجاح!",
            flush=True
        )

    except Exception as e:

        print(
            f"❌ فشل تشغيل Userbot: {e}",
            flush=True
        )

        return

    # -----------------------------------------------------
    # Load dialogs
    # -----------------------------------------------------

    print(
        "🔄 تحميل المحادثات والقروبات...",
        flush=True
    )

    try:

        count = 0

        async for dialog in userbot.get_dialogs():

            count += 1

            if count % 50 == 0:

                print(
                    f"📚 تم تحميل {count} محادثة...",
                    flush=True
                )

        print(
            f"✅ تم تحميل {count} محادثة",
            flush=True
        )

    except Exception as e:

        print(
            f"⚠️ خطأ أثناء تحميل المحادثات: {e}",
            flush=True
        )

    # -----------------------------------------------------
    # Ready
    # -----------------------------------------------------

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        flush=True
    )

    print(
        "🚀 Barq Jazan AI Listener جاهز",
        flush=True
    )

    print(
        f"🧠 AI Model: {AI_MODEL}",
        flush=True
    )

    print(
        f"⚡ AI Concurrency: {AI_CONCURRENCY}",
        flush=True
    )

    print(
        "📡 يراقب الرسائل التي يستطيع الحساب رؤيتها",
        flush=True
    )

    print(
        "🎯 الإرسال إلى:",
        flush=True
    )

    for target in TARGET_USERS:

        print(
            f"   • {target}",
            flush=True
        )

    print(
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        flush=True
    )

    # -----------------------------------------------------
    # Keep alive
    # -----------------------------------------------------

    await asyncio.Event().wait()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "🛑 تم إيقاف البرنامج",
            flush=True
        )

    except Exception as e:

        print(
            f"💥 Fatal Error: {e}",
            flush=True
        )

أهم شيء في Render

تأكد أن Environment Variables عندك بهذا الشكل:

GROQ_API_KEY=مفتاح_Groq
SESSION_STRING=جلسة_الحساب
TELEGRAM_API_ID=39120728
TELEGRAM_API_HASH=مفتاح_API_HASH
BOT_TOKEN=توكن_البوت

"BOT_TOKEN" اختياري في هذه النسخة، لكن "SESSION_STRING" و"GROQ_API_KEY" أساسيان.

والـAI هنا لا يعتمد على قائمة كلمات؛ أعطيته وصفًا للسلوك الذي نريد اكتشافه، بحيث يميز مثلًا:

«"يا جماعة احتاج أحد يوديني من صبيا لجيزان"»

على أنه عميل،

بينما:

«"متوفر مشاوير داخل جيزان وصبيا"»

على أنه سائق ولا يرسله.

وهذا النوع من التصنيف مناسب جدًا لـGroq؛ Groq يدعم JSON mode، والـAPI الحالي يدعم نماذج حديثة مخصصة للتصنيف السريع.

تنبيه مهم: الكود لا يستطيع التقاط رسائل من قروبات لا يكون حساب الـSession عضوًا فيها أو لا يستطيع رؤيتها. لا توجد طريقة تجعل Hydrogram يرى قروبات غير متاحة للحساب.

بعد تشغيله في Render، أول شيء راقب الـLogs. المفروض تشوف:

✅ Groq AI connected successfully
🤖 البوت المساعد يعمل
✅ Userbot يعمل بنجاح!
🔄 تحميل المحادثات والقروبات...
🚀 Barq Jazan AI Listener جاهز

ثم عند أي رسالة:

📩 [اسم القروب] ...
🚫 AI: ليست رسالة عميل

أو:

📩 [اسم القروب] ...
✅ AI: تم اكتشاف طلب عميل
🎯 تم الإرسال إلى @abood1317 عبر Userbot

إذا ظهر عندك خطأ في Render بعد وضع هذه النسخة، أرسل لي الـLogs كما تظهر، وسأحدد لك السطر الذي يوقف التشغيل.
