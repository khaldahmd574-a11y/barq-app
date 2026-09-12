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
# KEEP ALIVE SERVER (سيرفر منع توقف الخدمة على Render)
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
# CONFIGURATION & ENVIRONMENT VARIABLES
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()

API_ID = 39120728
API_HASH = "1deec8393ce5aa05c54c0c7e280377d4"
GROQ_MODEL = "llama-3.3-70b-versatile"

# قائمة المستلمين (يمكنك وضع المعرفات بالأحرف أو بأرقام الـ ID)
TARGET_USERS = [
    "shaybq",
    "Waaaaaaa33",
    "abood1317",
]

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
# AI ANALYSIS (تحليل الرسائل بالذكاء الاصطناعي)
# =========================================================

def analyze_with_ai(text):
    if not GROQ_API_KEY:
        print("❌ [AI Error] GROQ_API_KEY غير مضاف في Environment Variables!")
        return {"is_request": False, "type": "none", "confidence": 0}

    system_prompt = """
أنت خبير في تحليل منشورات مجموعات التوصيل والمشاوير بالسعودية.
وظيفتك الوحيدة: التمييز بين (الزبون الذي يطلب الخدمة) و(السائق/المندوب الذي يعرض خدمته).

قواعد الفرز:
1. العميل (Customer): يبحث عن سيارة، سائق، توصيل غرض، مشوار. (مثال: محتاج سواق، من يوصلني، ابغى مندوب، مين يوصل طلب، ابي احد يحرك الحين).
2. السائق (Driver): يعرض خدمته هو. (مثال: متوفر الآن، سواق جاهز، توصيل طلبات، للتواصل خاص، توصيل مشاوير). -> النتيجة دائمًا none.
3. الإعلانات والخدمات الأخرى (وظائف، صحي، إلكترونيات...) -> النتيجة دائمًا none.

التصنيفات المتاحة:
- delivery: زبون يطلب توصيل طرد/طلب/أغراض.
- ride: زبون يطلب مشوار لنفسه أو لأشخاص.
- both: زبون يطلب مشوار وتوصيل طلب.
- none: ليس طلب زبون (سائق يعرض خدمته، أو إعلان، أو كلام عام).

أرجع JSON فقط بهذا الشكل وبدون أي نص آخر:
{
  "is_request": true,
  "type": "ride",
  "confidence": 0.90
}
"""

    user_prompt = f"حلل النص التالي:\n{text}"

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

        with urllib.request.urlopen(request, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8"))

        content = result["choices"][0]["message"]["content"]
        ai = json.loads(content)

        is_request = bool(ai.get("is_request", False))
        request_type = ai.get("type", "none")
        confidence = float(ai.get("confidence", 0))

        if request_type not in ("delivery", "ride", "both") or confidence < 0.60:
            is_request = False
            request_type = "none"

        return {"is_request": is_request, "type": request_type, "confidence": confidence}

    except Exception as e:
        print(f"❌ [Groq Error]: {e}")
        return {"is_request": False, "type": "none", "confidence": 0}


# =========================================================
# MESSAGE PROCESSING LOGIC
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
    if len(text) < 3:
        return

    content_hash = get_hash(text)
    if content_hash in PROCESSED_CONTENT:
        print(f"🔄 تجاهل منشور مكرر: {text[:30]}...")
        return

    print(f"🤖 جاري تحليل النص بالذكاء الاصطناعي: {text[:40]}...")
    result = await asyncio.to_thread(analyze_with_ai, text)

    if not result["is_request"]:
        print(f"🚫 تم تصنيفها كـ (غير طلب عميل) - تجاهل.")
        return

    PROCESSED_CONTENT.add(content_hash)
    request_type = result["type"]
    confidence = result["confidence"]

    label = "📦 طلب توصيل" if request_type == "delivery" else ("🚗 طلب مشوار" if request_type == "ride" else "📦🚗 طلب مشترك")
    print(f"🎯 تم اكتشاف طلب جديد! [{label}] (الثقة: {confidence:.2f})")

    rows = []
    if message.from_user:
        if message.from_user.username:
            user_url = f"https://t.me/{message.from_user.username}"
            user_text = f"💬 المحادثة (@{message.from_user.username})"
        else:
            user_url = f"tg://openmessage?user_id={message.from_user.id}"
            user_text = f"💬 المحادثة ({message.from_user.first_name or 'الزبون'})"
        rows.append([InlineKeyboardButton(user_text, url=user_url)])

    if message.link:
        rows.append([InlineKeyboardButton("📩 الرابط الأصلي للرسالة", url=message.link)])

    reply_markup = InlineKeyboardMarkup(rows) if rows else None
    full_msg = f"<b>{label}</b>\n\n{text}"

    for user in TARGET_USERS:
        try:
            await bot.send_message(chat_id=user, text=full_msg, reply_markup=reply_markup, disable_web_page_preview=True)
            print(f"📤 تم الإرسال بنجاح إلى: {user}")
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await bot.send_message(chat_id=user, text=full_msg, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as e:
            print(f"❌ فشل إرسال الرسالة إلى [{user}]: {e}")
            print(f"👉 ملاحظة: تأكد أن {user} قام ببدء المحادثة مع البوت عبر إرسال /start أولاً.")


# =========================================================
# MAIN ENTRY POINT
# =========================================================

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    print("🚀 جاري بدء تشغيل النظام...")

    if not BOT_TOKEN:
        print("❌ خطأ قاتل: BOT_TOKEN مفقود من Environment Variables!")
        return
    if not SESSION_STRING:
        print("❌ خطأ قاتل: SESSION_STRING مفقود من Environment Variables!")
        return
    if not GROQ_API_KEY:
        print("⚠️ تحذير: GROQ_API_KEY غير مضاف! الذكاء الاصطناعي لن يعمل بإنصات.")

    userbot = Client("my_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
    bot = Client("helper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

    @userbot.on_message()
    async def global_listener(client, message):
        try:
            # طباعة فورية لتأكيد وصول أي منشور من المجموعات
            if message.chat and message.chat.type.value in ["group", "supergroup", "channel"]:
                print(f"📩 [رسالة جديدة] من مجموعة [{message.chat.title}]: {(message.text or message.caption or '')[:30]}")
                await process_message(bot, message)
        except Exception as e:
            print(f"❌ Listener Error: {e}")

    await userbot.start()
    print("✅ حساب السحب (Userbot) متصل ويستمع للمجموعات القادم منها المنشورات...")
    await bot.start()
    print("✅ بوت التوجيه (Bot) متصل وجاهز لإرسال الرسائل...")
    print("🎉 النظام يعمل بالكامل الآن 24/7!")

    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("🛑 تم إيقاف التشغيل يدويًا")
    except Exception as e:
        print(f"❌ خطأ رئيسي أثناء التشغيل: {e}")

