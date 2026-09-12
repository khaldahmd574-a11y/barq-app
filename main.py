import os
import asyncio
import hashlib
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from google import genai
from google.genai import types

from hydrogram import Client
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait


print("=" * 60, flush=True)
print("⚡ [START] تم تحميل السكريبت، جاري البدء مع Gemini...", flush=True)
print("=" * 60, flush=True)


# =========================================================
# KEEP ALIVE SERVER
# =========================================================

class DummyServer(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq System Active!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return


def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))

    server = HTTPServer(
        ("0.0.0.0", port),
        DummyServer
    )

    print(
        f"🌐 [HTTP Server] يعمل الآن على المنفذ {port}",
        flush=True
    )

    server.serve_forever()


# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

GEMINI_API_KEY = os.environ.get(
    "GEMINI_API_KEY",
    ""
).strip()

SESSION_STRING = os.environ.get(
    "SESSION_STRING",
    ""
).strip()


# =========================================================
# TELEGRAM API
# =========================================================

API_ID = int(
    os.environ.get(
        "TELEGRAM_API_ID",
        "0"
    )
)

API_HASH = os.environ.get(
    "TELEGRAM_API_HASH",
    ""
).strip()


# =========================================================
# GEMINI SETTINGS
# =========================================================

GEMINI_MODEL = "gemini-2.5-flash"

gemini_client = None


if GEMINI_API_KEY:

    try:

        gemini_client = genai.Client(
            api_key=GEMINI_API_KEY
        )

        print(
            f"🤖 [Gemini] تم تجهيز Gemini: {GEMINI_MODEL}",
            flush=True
        )

    except Exception as e:

        print(
            f"❌ [Gemini Init Error] {e}",
            flush=True
        )


# =========================================================
# TARGET USERS
# =========================================================

TARGET_USERS = [
    "shaybq",
    "Waaaaaaa33",
    "abood1317"
]


# =========================================================
# MEMORY / DEDUPLICATION
# =========================================================

PROCESSED_MESSAGES = set()

PROCESSED_CONTENT = set()


# =========================================================
# TEXT FUNCTIONS
# =========================================================

def clean_text(text):

    if not text:
        return ""

    return " ".join(
        text.strip().split()
    )


def get_hash(text):

    cleaned = clean_text(text).lower()

    return hashlib.sha256(
        cleaned.encode("utf-8")
    ).hexdigest()


# =========================================================
# GEMINI AI ANALYSIS
# =========================================================

def analyze_with_ai(text):

    if not GEMINI_API_KEY:

        print(
            "❌ [AI Error] GEMINI_API_KEY غير مضاف في Render!",
            flush=True
        )

        return {
            "is_request": False,
            "type": "none",
            "confidence": 0
        }


    if not gemini_client:

        print(
            "❌ [AI Error] Gemini Client غير جاهز!",
            flush=True
        )

        return {
            "is_request": False,
            "type": "none",
            "confidence": 0
        }


    prompt = f"""
أنت نظام ذكاء اصطناعي متخصص في فرز رسائل مجموعات التوصيل والمشاوير في السعودية.

مهمتك هي تحديد هل المنشور يمثل "طلب خدمة حقيقي من عميل" أم لا.

يجب التفريق بوضوح بين:

1. العميل:
- يبحث عن سواق
- يبحث عن سواقه
- يبحث عن مندوب
- يريد توصيل طلب أو غرض
- يريد مشوار
- يسأل من يستطيع توصيله
- يسأل من يستطيع أخذ أو جلب شيء
- يسأل مين فاضي أو موجود أو قريب
- يريد الذهاب من مكان إلى مكان
- يريد شخصًا يشتري أو يستلم أو يوصل له غرضًا

2. السائق أو المندوب:
إذا كان الشخص يعرض خدمته هو، فلا تعتبره طلبًا.

أمثلة:
"متوفر الآن"
"أنا مندوب"
"مندوب جاهز"
"سواق جاهز"
"توصيل طلبات"
"متوفر للمشاوير"
"أي طلب أنا حاضر"
"للتوصيل تواصل معي"

هذه عروض خدمات وليست طلبات عميل.

3. الإعلانات:
أي إعلان تجاري أو عرض خدمة أو منشور لا يبحث فيه صاحبه عن سائق/مندوب
لا تعتبره طلبًا.

4. المحادثات العامة:
التحية، الشكر، المزاح، النقاشات، الأسئلة العامة، الأخبار وغيرها
ليست طلبات.

التصنيفات المسموحة:

delivery
ride
both
none

delivery:
إذا كان العميل يريد توصيل غرض أو طلب.

ride:
إذا كان العميل يريد مشوارًا أو سائقًا لنقله.

both:
إذا كان المنشور يحتوي على طلب توصيل ومشوار معًا.

none:
إذا لم يكن طلب عميل.

مهم جدًا:
لا تعتمد فقط على كلمات معينة.
افهم معنى المنشور كاملًا وسياقه.

إذا كان النص غامضًا جدًا ولا تستطيع التأكد أنه طلب حقيقي،
اختر none.

النص:

{text}

أرجع JSON فقط بهذا الشكل:

{{
  "is_request": true,
  "type": "ride",
  "confidence": 0.95
}}

القيمة confidence يجب أن تكون رقمًا من 0 إلى 1.

لا تكتب أي شرح.
لا تستخدم Markdown.
لا تضف أي نص خارج JSON.
"""


    try:

        response = gemini_client.models.generate_content(

            model=GEMINI_MODEL,

            contents=prompt,

            config=types.GenerateContentConfig(

                response_mime_type="application/json",

                temperature=0

            )
        )


        raw_text = (response.text or "").strip()


        if not raw_text:

            print(
                "❌ [Gemini Error] Gemini أعاد نتيجة فارغة",
                flush=True
            )

            return {
                "is_request": False,
                "type": "none",
                "confidence": 0
            }


        ai = json.loads(raw_text)


        is_req = bool(
            ai.get(
                "is_request",
                False
            )
        )


        req_type = str(
            ai.get(
                "type",
                "none"
            )
        ).lower().strip()


        try:

            conf = float(
                ai.get(
                    "confidence",
                    0
                )
            )

        except:

            conf = 0


        # حماية من نتائج غير صحيحة

        if req_type not in (
            "delivery",
            "ride",
            "both"
        ):

            return {
                "is_request": False,
                "type": "none",
                "confidence": 0
            }


        if conf < 0.60:

            return {
                "is_request": False,
                "type": "none",
                "confidence": conf
            }


        if not is_req:

            return {
                "is_request": False,
                "type": "none",
                "confidence": conf
            }


        return {
            "is_request": True,
            "type": req_type,
            "confidence": conf
        }


    except json.JSONDecodeError as e:

        print(
            f"❌ [Gemini JSON Error] {e}",
            flush=True
        )

        return {
            "is_request": False,
            "type": "none",
            "confidence": 0
        }


    except Exception as e:

        print(
            f"❌ [Gemini Error] {type(e).__name__}: {e}",
            flush=True
        )

        return {
            "is_request": False,
            "type": "none",
            "confidence": 0
        }


# =========================================================
# MESSAGE PROCESSING
# =========================================================

async def process_message(bot, message: Message):

    if not message:

        return


    if not message.id:

        return


    # -----------------------------------------
    # منع تكرار نفس الرسالة داخل نفس المجموعة
    # -----------------------------------------

    message_key = (
        f"{message.chat.id}:{message.id}"
    )


    if message_key in PROCESSED_MESSAGES:

        return


    PROCESSED_MESSAGES.add(
        message_key
    )


    # -----------------------------------------
    # لا نعالج رسائل اليوزربوت نفسه
    # -----------------------------------------

    if message.from_user:

        try:

            if message.from_user.is_self:

                return

        except:

            pass


    # -----------------------------------------
    # استخراج النص
    # -----------------------------------------

    text = clean_text(
        message.text
        or message.caption
        or ""
    )


    if len(text) < 3:

        return


    # -----------------------------------------
    # بصمة المحتوى
    # -----------------------------------------

    content_hash = get_hash(
        text
    )


    # إذا نفس المنشور ظهر في أكثر من مجموعة
    # لا نرسله مرة ثانية
    if content_hash in PROCESSED_CONTENT:

        print(
            "♻️ [DUPLICATE] تم تجاهل منشور مكرر",
            flush=True
        )

        return


    # -----------------------------------------
    # تحليل Gemini
    # -----------------------------------------

    result = await asyncio.to_thread(
        analyze_with_ai,
        text
    )


    if not result["is_request"]:

        return


    # -----------------------------------------
    # تسجيل المحتوى بعد التأكد أنه طلب
    # -----------------------------------------

    PROCESSED_CONTENT.add(
        content_hash
    )


    req_type = result["type"]

    conf = result["confidence"]


    # -----------------------------------------
    # اسم التصنيف
    # -----------------------------------------

    if req_type == "delivery":

        label = "📦 طلب توصيل"

    elif req_type == "ride":

        label = "🚗 طلب مشوار"

    else:

        label = "📦🚗 طلب توصيل ومشوار"


    print(
        f"🎯 [طلب جديد بـ Gemini] "
        f"{label} | "
        f"الثقة: {conf:.2f} | "
        f"النص: {text[:100]}",
        flush=True
    )


    # =====================================================
    # أزرار التواصل
    # =====================================================

    rows = []


    if message.from_user:

        try:

            username = message.from_user.username

            user_id = message.from_user.id

            first_name = (
                message.from_user.first_name
                or "الزبون"
            )


            if username:

                user_url = (
                    f"https://t.me/{username}"
                )

                user_text = (
                    f"💬 المحادثة (@{username})"
                )

            else:

                user_url = (
                    f"tg://openmessage?user_id={user_id}"
                )

                user_text = (
                    f"💬 المحادثة ({first_name})"
                )


            rows.append(
                [
                    InlineKeyboardButton(
                        user_text,
                        url=user_url
                    )
                ]
            )

        except Exception as e:

            print(
                f"⚠️ [Button Error] {e}",
                flush=True
            )


    # -----------------------------------------
    # رابط المنشور الأصلي
    # -----------------------------------------

    try:

        if message.link:

            rows.append(
                [
                    InlineKeyboardButton(
                        "📩 الرابط الأصلي",
                        url=message.link
                    )
                ]
            )

    except:

        pass


    reply_markup = (
        InlineKeyboardMarkup(rows)
        if rows
        else None
    )


    # -----------------------------------------
    # الرسالة النهائية
    # -----------------------------------------

    full_msg = (
        f"<b>{label}</b>\n\n"
        f"{text}"
    )


    # =====================================================
    # إرسال الطلب للمستخدمين المستهدفين
    # =====================================================

    for user in TARGET_USERS:

        try:

            await bot.send_message(

                chat_id=user,

                text=full_msg,

                reply_markup=reply_markup,

                disable_web_page_preview=True
            )


            print(
                f"📤 تم الإرسال بنجاح إلى: {user}",
                flush=True
            )


        except FloodWait as e:

            print(
                f"⏳ [FloodWait] انتظار {e.value} ثانية...",
                flush=True
            )


            await asyncio.sleep(
                e.value
            )


            try:

                await bot.send_message(

                    chat_id=user,

                    text=full_msg,

                    reply_markup=reply_markup,

                    disable_web_page_preview=True
                )


                print(
                    f"📤 تم الإرسال بعد الانتظار إلى: {user}",
                    flush=True
                )

            except Exception as retry_error:

                print(
                    f"❌ فشل الإرسال بعد الانتظار إلى "
                    f"{user}: {retry_error}",
                    flush=True
                )


        except Exception as e:

            print(
                f"❌ فشل الإرسال إلى {user}: {e}",
                flush=True
            )


# =========================================================
# MAIN
# =========================================================

async def main():

    print(
        "🔍 [CHECK] جاري الفحص عن المتغيرات...",
        flush=True
    )


    # -----------------------------------------
    # BOT TOKEN
    # -----------------------------------------

    if not BOT_TOKEN:

        print(
            "❌ [CRITICAL] BOT_TOKEN غير مضاف!",
            flush=True
        )

        return


    # -----------------------------------------
    # SESSION STRING
    # -----------------------------------------

    if not SESSION_STRING:

        print(
            "❌ [CRITICAL] SESSION_STRING غير مضاف!",
            flush=True
        )

        return


    # -----------------------------------------
    # TELEGRAM API ID
    # -----------------------------------------

    if not API_ID:

        print(
            "❌ [CRITICAL] TELEGRAM_API_ID غير مضاف!",
            flush=True
        )

        return


    # -----------------------------------------
    # TELEGRAM API HASH
    # -----------------------------------------

    if not API_HASH:

        print(
            "❌ [CRITICAL] TELEGRAM_API_HASH غير مضاف!",
            flush=True
        )

        return


    # -----------------------------------------
    # GEMINI KEY
    # -----------------------------------------

    if not GEMINI_API_KEY:

        print(
            "❌ [CRITICAL] GEMINI_API_KEY غير مضاف!",
            flush=True
        )

        return


    # =====================================================
    # إنشاء Userbot
    # =====================================================

    userbot = Client(

        "my_userbot",

        api_id=API_ID,

        api_hash=API_HASH,

        session_string=SESSION_STRING,

        in_memory=True
    )


    # =====================================================
    # إنشاء البوت
    # =====================================================

    bot = Client(

        "helper_bot",

        api_id=API_ID,

        api_hash=API_HASH,

        bot_token=BOT_TOKEN,

        in_memory=True
    )


    # =====================================================
    # LISTENER
    # =====================================================

    @userbot.on_message()
    async def global_listener(
        client,
        message
    ):

        try:

            if not message.chat:

                return


            chat_name = (
                message.chat.title
                or message.chat.username
                or "مجموعة"
            )


            msg_txt = (
                message.text
                or message.caption
                or ""
            )


            msg_txt = msg_txt[:50]


            print(
                f"📩 [{chat_name}]: {msg_txt}",
                flush=True
            )


            await process_message(
                bot,
                message
            )


        except Exception as e:

            print(
                f"❌ [Listener Error]: {e}",
                flush=True
            )


    # =====================================================
    # START
    # =====================================================

    try:

        # -----------------------------------------
        # تشغيل Userbot
        # -----------------------------------------

        await userbot.start()


        print(
            "✅ [Userbot] متصل بنجاح!",
            flush=True
        )


        # -----------------------------------------
        # تشغيل البوت
        # -----------------------------------------

        await bot.start()


        print(
            "✅ [Bot] متصل بنجاح!",
            flush=True
        )


        # -----------------------------------------
        # مزامنة المحادثات
        # -----------------------------------------

        print(
            "🔄 جاري تحميل ومزامنة قائمة "
            "المجموعات والقنوات...",
            flush=True
        )


        dialogs_count = 0


        async for dialog in userbot.get_dialogs():

            dialogs_count += 1


        print(
            f"🌐 تمت المزامنة بنجاح مع "
            f"{dialogs_count} محادثة ومجموعة وقناة!",
            flush=True
        )


        # -----------------------------------------
        # نجاح النظام
        # -----------------------------------------

        print(
            "🚀 [SUCCESS] النظام يعمل الآن "
            "بكفاءة مع Gemini الجديدة!",
            flush=True
        )


        print(
            f"🤖 [AI] النموذج المستخدم: {GEMINI_MODEL}",
            flush=True
        )


        print(
            "🧠 [AI] تحليل المنشورات يتم تلقائيًا "
            "بدون قائمة كلمات ثابتة.",
            flush=True
        )


        # -----------------------------------------
        # إبقاء النظام يعمل
        # -----------------------------------------

        await asyncio.Event().wait()


    except Exception as e:

        print(
            f"❌ [LOGIN ERROR] فشل الاتصال: {e}",
            flush=True
        )


# =========================================================
# PROGRAM START
# =========================================================

if __name__ == "__main__":

    # تشغيل سيرفر Render
    t = threading.Thread(
        target=run_dummy_server,
        daemon=True
    )

    t.start()


    try:

        asyncio.run(
            main()
        )

    except Exception as e:

        print(
            f"❌ [CRITICAL ERROR]: {e}",
            flush=True
    )
