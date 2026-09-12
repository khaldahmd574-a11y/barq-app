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
# KEEP ALIVE SERVER (سيرفر منع توقف الخادم)
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
# TELEGRAM & GROQ SETTINGS (الإعدادات المباشرة)
# =========================================================

# قراءة BOT_TOKEN فقط من Render Environment
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# باقي البيانات مدمجة في الكود مباشرة
API_ID = 39120728
API_HASH = "1deec8393ce5aa05c54c0c7e280377d4"

# اكتب SESSION_STRING الخاص بك هنا بين التنصيص إذا لم ترغب بوضعه في Environment
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()

# اكتب مفتاح GROQ الخاص بك هنا بين التنصيص إذا لم ترغب بوضعه في Environment
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = "llama-3.3-70b-versatile"

# قائمة الحسابات المستلمة للطلبات
TARGET_USERS = [
    "shaybq",
    "Waaaaaaa33",
    "abood1317",
]


# =========================================================
# MEMORY & CLEANUP (ذاكرة منع التكرار)
# =========================================================

PROCESSED_MESSAGES = set()
PROCESSED_CONTENT = set()


def clean_text(text):
    if not text:
        return ""
    return " ".join(text.strip().split())


def get_hash(text):
    text = clean_text(text).lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# =========================================================
# AI ANALYSIS (تحليل الذكاء الاصطناعي)
# =========================================================

def analyze_with_ai(text):
    if not GROQ_API_KEY:
        print("❌ GROQ_API_KEY غير مضاف في الكود أو البيئة!")
        return {"is_request": False, "type": "none", "confidence": 0}

    system_prompt = """
أنت نظام ذكاء اصطناعي متخصص في فهم رسائل العملاء في مجموعات التوصيل والمشاوير في السعودية.
مهمتك تحليل الرسالة كاملة وفهم معناها وسياقها.
لا تعتمد على كلمات محددة ولا على قائمة كلمات.
نريد فقط اكتشاف الشخص الذي يبحث عن خدمة لنفسه.

التصنيفات:
delivery = العميل يريد مندوب أو توصيل غرض أو طلب أو شيء.
ride = العميل يريد مشوار أو سائق أو سائقة لإيصاله هو.
both = العميل يريد توصيلًا ومشوارًا في نفس الرسالة.
none = ليست رسالة طلب من عميل.

مهم جدًا:
إذا كان الشخص يعرض خدماته هو، فالنتيجة none. (مثال: أنا مندوب، سواق متوفر، جاهز للتوصيل).
أيضاً تجاهل: الإعلانات، الإجازات المرضية، الوظائف، والخدمات الحكومية.

أرجع JSON فقط بهذا الشكل:
{
  "is_request": true,
  "type": "delivery",
  "confidence": 0.95
}
"""

    user_prompt = f"حلل الرسالة التالية:\n{text}"

    payload = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0,
        "response_format": {"type": "json_object"}
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=data,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(request, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))

        content = result["choices"][0]["message"]["content"]
        ai = json.loads(content)

        is_request = bool(ai.get("is_request", False))
        request_type = ai.get("type", "none")
        confidence = float(ai.get("confidence", 0))

        if request_type not in ("delivery", "ride", "both", "none") or confidence < 0.65:
            is_request = False
            request_type = "none"

        return {"is_request": is_request, "type": request_type, "confidence": confidence}

    except Exception as e:
        print(f"❌ Groq Error: {e}")
        return {"is_request": False, "type": "none", "confidence": 0}


# =========================================================
# PROCESS MESSAGE (معالجة الرسائل وإرسالها)
# =========================================================

async def process_message(bot, message: Message):
    if not message or not message.id:
        return

    message_key = f"{message.chat.id}:{message.id}"
    if message_key in PROCESSED_MESSAGES:
        return
    PROCESSED_MESSAGES.add(message_key)

    if message.from_user and message.from_user.is_self:
        return

    text = clean_text(message.text or message.caption or "")
    if len(text) < 4:
        return

    content_hash = get_hash(text)
    if content_hash in PROCESSED_CONTENT:
        return

    result = await asyncio.to_thread(analyze_with_ai, text)
    request_type = result["type"]
    confidence = result["confidence"]

    if not result["is_request"]:
        print(f"🚫 تجاهل | {confidence:.2f} | {text[:50]}")
        return

    PROCESSED_CONTENT.add(content_hash)
    label = "📦 طلب توصيل" if request_type == "delivery" else ("🚗 طلب مشوار" if request_type == "ride" else "📦🚗 طلب مشترك")
    print(f"✅ {label} | الثقة: {confidence:.2f} | {text[:60]}")

    rows = []
    if message.from_user:
        if message.from_user.username:
            user_url = f"https://t.me/{message.from_user.username}"
            user_text = f"💬 المحادثة (@{message.from_user.username})"
        else:
            user_url = f"tg://openmessage?user_id={message.from_user.id}"
            user_text = f"💬 المحادثة ({message.from_user.first_name or 'الزبون'})"
        rows.append(InlineKeyboardButton(user_text, url=user_url))

    if message.link:
        rows.append(InlineKeyboardButton("📩 الرابط الأصلي", url=message.link))

    reply_markup = InlineKeyboardMarkup([rows]) if rows else None

    for user in TARGET_USERS:
        try:
            await bot.send_message(chat_id=user, text=text, reply_markup=reply_markup, disable_web_page_preview=True)
            print(f"📤 تم الإرسال إلى: {user}")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await bot.send_message(chat_id=user, text=text, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as e:
            print(f"❌ فشل الإرسال: {e}")


# =========================================================
# MAIN (التشغيل الرئيسي)
# =========================================================

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    if not BOT_TOKEN:
        print("❌ خطأ: BOT_TOKEN غير مضاف في Environment في لوحة Render!")
        return

    if not SESSION_STRING:
        print("❌ خطأ: SESSION_STRING غير مضاف!")
        return

    userbot = Client("my_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
    bot = Client("helper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

    # تم استخدام filters.group بدون supergroup لتجنب خطأ المكتبة
    @userbot.on_message(filters.group | filters.channel)
    async def global_listener(client, message):
        try:
            await process_message(bot, message)
        except Exception as e:
            print(f"❌ Listener Error: {e}")

    await userbot.start()
    print("👤 حساب السحب متصل")
    await bot.start()
    print("🤖 بوت برق جازان متصل")
    print("🚀 النظام يعمل الآن بنجاح 24/7")

    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 تم إيقاف النظام")
    except Exception as e:
        print(f"❌ خطأ رئيسي: {e}")

