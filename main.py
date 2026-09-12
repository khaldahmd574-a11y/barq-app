import os
import asyncio
import hashlib
import json
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait


# =========================================================
# KEEP ALIVE SERVER
# =========================================================

class DummyServer(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Barq System Active 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()


def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()


# =========================================================
# TELEGRAM SETTINGS
# =========================================================

SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()

API_ID = int(
    os.environ.get(
        "TELEGRAM_API_ID",
        "39120728"
    )
)

API_HASH = os.environ.get(
    "TELEGRAM_API_HASH",
    ""
).strip()

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    ""
).strip()


# =========================================================
# GROQ
# =========================================================

GROQ_API_KEY = os.environ.get(
    "GROQ_API_KEY",
    ""
).strip()

GROQ_MODEL = "llama-3.3-70b-versatile"


# =========================================================
# PEOPLE WHO RECEIVE REQUESTS
# =========================================================

TARGET_USERS = [
    "shaybq",
    "Waaaaaaa33",
    "abood1317",

    # أضف معرف حسابك هنا إذا أردت:
    # "YOUR_USERNAME",
]


# =========================================================
# DUPLICATE MEMORY
# =========================================================

PROCESSED_MESSAGES = set()
PROCESSED_CONTENT = set()


# =========================================================
# CLEAN TEXT
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = text.strip()

    text = " ".join(text.split())

    return text


# =========================================================
# CONTENT HASH
# =========================================================

def get_hash(text):

    text = clean_text(text).lower()

    return hashlib.sha256(
        text.encode("utf-8")
    ).hexdigest()


# =========================================================
# AI ANALYSIS
# =========================================================

def analyze_with_ai(text):

    if not GROQ_API_KEY:

        print("❌ GROQ_API_KEY غير موجود")

        return {
            "is_request": False,
            "type": "none",
            "confidence": 0
        }

    system_prompt = """
أنت نظام ذكاء اصطناعي متخصص في فهم رسائل العملاء
في مجموعات التوصيل والمشاوير في السعودية.

مهمتك تحليل الرسالة كاملة وفهم معناها وسياقها.
لا تعتمد على كلمات محددة ولا على قائمة كلمات.

نريد فقط اكتشاف الشخص الذي يبحث عن خدمة لنفسه.

التصنيفات:

delivery
= العميل يريد مندوب أو توصيل غرض أو طلب أو شيء.

ride
= العميل يريد مشوار أو سائق أو سائقة لإيصاله هو.

both
= العميل يريد توصيلًا ومشوارًا في نفس الرسالة.

none
= ليست رسالة طلب من عميل.

مهم جدًا:

إذا كان الشخص يعرض خدماته هو، فالنتيجة none.

مثل:
أنا مندوب
مندوب متوفر
أنا سواق
متواجد للمشاوير
أوصل طلبات
جاهز للتوصيل
عندي سيارة
متوفر الآن

هذه ليست طلبات عملاء.

أيضًا تجاهل:
السلام والترحيب
الشكر
النقاش
الأسئلة العامة
الاستفسارات عن الأسعار فقط
الاستفسارات عن المسافات فقط
الإعلانات
الوظائف
الخدمات الحكومية
الروابط والإعلانات العامة
أي كلام غير واضح كطلب خدمة.

لكن إذا كان الشخص يطلب خدمة بطريقة غير مباشرة
فهم المقصود من سياق الرسالة.

مثال:
"أحتاج أحد يجيب لي شيء من الجامعة"
= delivery

"مين يقدر يوديني للجامعة؟"
= ride

"أبغى أحد يستلم طلبي ويوصله لي"
= delivery

"محتاجة سيارة توصلني"
= ride

"أحتاج شخص يجيب الغرض ويوصلني بعدين"
= both

لا تحكم من كلمة واحدة.
افهم من هو المتكلم وماذا يريد.

إذا لم تكن متأكدًا أن الشخص عميل ويطلب خدمة،
اختر none.

أرجع JSON فقط بهذا الشكل:

{
  "is_request": true,
  "type": "delivery",
  "confidence": 0.95
}

القيم المسموحة لـ type:
delivery
ride
both
none

confidence رقم بين 0 و 1.
"""

    user_prompt = f"""
حلل الرسالة التالية:

{text}
"""

    payload = {

        "model": GROQ_MODEL,

        "messages": [

            {
                "role": "system",
                "content": system_prompt
            },

            {
                "role": "user",
                "content": user_prompt
            }

        ],

        "temperature": 0,

        "response_format": {
            "type": "json_object"
        }
    }

    try:

        data = json.dumps(
            payload
        ).encode("utf-8")

        request = urllib.request.Request(

            "https://api.groq.com/openai/v1/chat/completions",

            data=data,

            headers={
                "Authorization":
                    f"Bearer {GROQ_API_KEY}",

                "Content-Type":
                    "application/json"
            },

            method="POST"
        )

        with urllib.request.urlopen(
            request,
            timeout=8
        ) as response:

            result = json.loads(
                response.read().decode("utf-8")
            )

        content = (
            result["choices"][0]
            ["message"]["content"]
        )

        ai = json.loads(content)

        is_request = bool(
            ai.get(
                "is_request",
                False
            )
        )

        request_type = ai.get(
            "type",
            "none"
        )

        confidence = float(
            ai.get(
                "confidence",
                0
            )
        )

        if request_type not in (
            "delivery",
            "ride",
            "both",
            "none"
        ):

            request_type = "none"
            is_request = False

        # الثقة المطلوبة لقبول الطلب
        if confidence < 0.65:

            is_request = False
            request_type = "none"

        return {
            "is_request": is_request,
            "type": request_type,
            "confidence": confidence
        }

    except Exception as e:

        print(
            f"❌ Groq Error: {e}"
        )

        return {
            "is_request": False,
            "type": "none",
            "confidence": 0
        }


# =========================================================
# PROCESS MESSAGE
# =========================================================

async def process_message(
    bot,
    message: Message
):

    if not message:
        return

    if not message.id:
        return

    # -----------------------------------------------------
    # نفس الرسالة
    # -----------------------------------------------------

    message_key = (
        f"{message.chat.id}:"
        f"{message.id}"
    )

    if message_key in PROCESSED_MESSAGES:
        return

    PROCESSED_MESSAGES.add(
        message_key
    )

    # -----------------------------------------------------
    # تجاهل رسائل الحساب نفسه
    # -----------------------------------------------------

    if message.from_user:

        if message.from_user.is_self:
            return

    # -----------------------------------------------------
    # استخراج النص
    # -----------------------------------------------------

    text = (
        message.text
        or message.caption
        or ""
    )

    text = clean_text(text)

    if len(text) < 4:
        return

    # -----------------------------------------------------
    # نفس المحتوى في قروب آخر
    # -----------------------------------------------------

    content_hash = get_hash(text)

    if content_hash in PROCESSED_CONTENT:

        print(
            f"♻️ مكرر: {text[:60]}"
        )

        return

    # -----------------------------------------------------
    # AI
    # -----------------------------------------------------

    result = await asyncio.to_thread(
        analyze_with_ai,
        text
    )

    request_type = result["type"]
    confidence = result["confidence"]

    if not result["is_request"]:

        print(
            f"🚫 تجاهل | "
            f"{request_type} | "
            f"{confidence:.2f} | "
            f"{text[:70]}"
        )

        return

    # -----------------------------------------------------
    # قبول الطلب
    # -----------------------------------------------------

    PROCESSED_CONTENT.add(
        content_hash
    )

    if request_type == "delivery":

        label = "📦 طلب توصيل"

    elif request_type == "ride":

        label = "🚗 طلب مشوار"

    else:

        label = "📦🚗 طلب توصيل + مشوار"

    print(
        f"✅ {label} | "
        f"الثقة: {confidence:.2f} | "
        f"{text[:100]}"
    )

    # -----------------------------------------------------
    # BUTTONS
    # -----------------------------------------------------

    rows = []

    if message.from_user:

        if message.from_user.username:

            username = (
                message.from_user.username
            )

            user_url = (
                f"https://t.me/{username}"
            )

            user_text = (
                f"💬 المحادثة (@{username})"
            )

        else:

            user_url = (
                "tg://openmessage?"
                f"user_id={message.from_user.id}"
            )

            user_text = (
                "💬 المحادثة "
                f"({message.from_user.first_name or 'الزبون'})"
            )

        rows.append(
            InlineKeyboardButton(
                user_text,
                url=user_url
            )
        )

    if message.link:

        rows.append(
            InlineKeyboardButton(
                "📩 الرابط الأصلي",
                url=message.link
            )
        )

    reply_markup = None

    if rows:

        reply_markup = InlineKeyboardMarkup(
            [rows]
        )

    # -----------------------------------------------------
    # SEND
    # -----------------------------------------------------

    for user in TARGET_USERS:

        try:

            await bot.send_message(

                chat_id=user,

                text=text,

                reply_markup=reply_markup,

                disable_web_page_preview=True
            )

            print(
                f"📤 أرسل إلى: {user}"
            )

        except FloodWait as e:

            print(
                f"⏳ FloodWait: {e.value}"
            )

            await asyncio.sleep(
                e.value
            )

            try:

                await bot.send_message(

                    chat_id=user,

                    text=text,

                    reply_markup=reply_markup,

                    disable_web_page_preview=True
                )

            except Exception as retry_error:

                print(
                    f"❌ إعادة الإرسال فشلت: "
                    f"{retry_error}"
                )

        except Exception as e:

            print(
                f"❌ إرسال فشل: {e}"
            )


# =========================================================
# MAIN
# =========================================================

async def main():

    # تشغيل السيرفر
    threading.Thread(
        target=run_dummy_server,
        daemon=True
    ).start()

    # -----------------------------------------------------
    # التحقق من الإعدادات
    # -----------------------------------------------------

    if not SESSION_STRING:

        print(
            "❌ SESSION_STRING غير موجود"
        )

        return

    if not BOT_TOKEN:

        print(
            "❌ BOT_TOKEN غير موجود"
        )

        return

    if not GROQ_API_KEY:

        print(
            "❌ GROQ_API_KEY غير موجود"
        )

        return

    # -----------------------------------------------------
    # USER ACCOUNT
    # -----------------------------------------------------

    userbot = Client(

        "my_userbot",

        api_id=API_ID,

        api_hash=API_HASH,

        session_string=SESSION_STRING,

        in_memory=True
    )

    # -----------------------------------------------------
    # BOT
    # -----------------------------------------------------

    bot = Client(

        "helper_bot",

        api_id=API_ID,

        api_hash=API_HASH,

        bot_token=BOT_TOKEN,

        in_memory=True
    )

    # -----------------------------------------------------
    # LISTENER
    # -----------------------------------------------------

    @userbot.on_message(
        filters.group
        | filters.supergroup
        | filters.channel
    )
    async def global_listener(
        client,
        message
    ):

        try:

            await process_message(
                bot,
                message
            )

        except Exception as e:

            print(
                f"❌ Listener Error: {e}"
            )

    # -----------------------------------------------------
    # START
    # -----------------------------------------------------

    await userbot.start()

    print(
        "👤 حساب السحب متصل"
    )

    await bot.start()

    print(
        "🤖 بوت الإرسال متصل"
    )

    print(
        "🚀 BARQ AI يعمل الآن"
    )

    print(
        "🧠 كل رسالة يتم فهمها بواسطة Groq"
    )

    print(
        "📦 delivery | 🚗 ride | 📦🚗 both | 🚫 none"
    )

    print(
        "📡 السحب من القروبات يعمل لحظيًا"
    )

    await asyncio.Event().wait()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    try:

        asyncio.run(main())

    except KeyboardInterrupt:

        print(
            "🛑 تم إيقاف النظام"
        )

    except Exception as e:

        print(
            f"❌ خطأ رئيسي: {e}"
    )
