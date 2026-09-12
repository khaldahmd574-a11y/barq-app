import os
import asyncio
import hashlib
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from google import genai
from google.genai import types

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
        self.wfile.write(b"Barq System Active!")

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
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()

API_ID = 39120728
API_HASH = "1deec8393ce5aa05c54c0c7e280377d4"

# الموديل المعتمد لـ Gemini 2.5
GEMINI_MODEL = "gemini-2.5-flash"
gemini_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"❌ [Gemini Init Error] {e}", flush=True)

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

PROCESSED_MESSAGES = set()
PROCESSED_CONTENT = set()

def clean_text(text):
    if not text:
        return ""
    return " ".join(text.strip().split())

def get_hash(text):
    cleaned = clean_text(text).lower()
    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

# =========================================================
# STRICT AI FILTER
# =========================================================

def analyze_with_ai(text):
    if not GEMINI_API_KEY or not gemini_client:
        return False

    prompt = f"""
أنت فلاتر ذكي متخصص لفلترة رسائل المجموعات.
وظيفتك الوحيدة تحديد هل الرسالة صادرة من (عميل/زبون) يريد خدمة توصيل أو مشوار.

قواعد صارمة جداً:
1. إذا كانت الرسالة من (سائق، مندوب، موصل، يعرض خدمته، يقول: فاضي، متوفر، جاهز، يوصل، رقم جوال للإعلان) -> إجابة حتمية: false
2. إذا كانت الرسالة مجرد سلام، إعلان، أو استفسار عام -> إجابة حتمية: false
3. فقط إذا كان كاتب الرسالة (زبون يبحث عن توصيل/مشوار، مثل: ابغى احد يجيب، فيه توصيل، ابغى مشوار، مين فاضي يوصلني) -> إجابة: true

النص للتحليل:
"{text}"

أرجع النتيجة بصيغة JSON فقط:
{{"is_client_request": true}} أو {{"is_client_request": false}}
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
        ai = json.loads(raw_text)
        return bool(ai.get("is_client_request", False))
    except Exception as e:
        print(f"❌ [AI Error]: {e}", flush=True)
        return False

# =========================================================
# MESSAGE PROCESSING
# =========================================================

async def process_message(bot, message: Message):
    if not message or not message.id:
        return

    message_key = f"{message.chat.id}:{message.id}"
    if message_key in PROCESSED_MESSAGES:
        return
    PROCESSED_MESSAGES.add(message_key)

    # تجاهل رسائل البوت أو الحساب نفسه
    if message.from_user and message.from_user.is_self:
        return

    text = clean_text(message.text or message.caption or "")
    if len(text) < 3:
        return

    content_hash = get_hash(text)
    if content_hash in PROCESSED_CONTENT:
        return

    # الفحص الصارم عبر الذكاء الاصطناعي
    is_client_request = await asyncio.to_thread(analyze_with_ai, text)
    if not is_client_request:
        return

    PROCESSED_CONTENT.add(content_hash)

    # تجهيز الأزرار في صف واحد (بجانب بعض)
    buttons = []

    if message.from_user:
        username = message.from_user.username
        user_id = message.from_user.id

        if username:
            user_url = f"https://t.me/{username}"
        else:
            user_url = f"tg://openmessage?user_id={user_id}"

        buttons.append(InlineKeyboardButton("💬 فتح المحادثة", url=user_url))

    if message.link:
        buttons.append(InlineKeyboardButton("📩 فتح الرسالة", url=message.link))

    # التجميع في صف واحد افقي [[زر1, زر2]]
    reply_markup = InlineKeyboardMarkup([buttons]) if buttons else None

    # إرسال نص الزبون المباشر بدون عناوين
    for user in TARGET_USERS:
        try:
            await bot.send_message(chat_id=user, text=text, reply_markup=reply_markup, disable_web_page_preview=True)
            print(f"✅ تم إرسال طلب عميل موثوق إلى: {user}", flush=True)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await bot.send_message(chat_id=user, text=text, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as e:
            print(f"❌ خطأ إرسال: {e}", flush=True)

# =========================================================
# MAIN ENTRYPOINT
# =========================================================

async def main():
    userbot = Client("my_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
    bot = Client("helper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

    # استماع لكافة المجموعات والقنوات والمحادثات
    @userbot.on_message(filters.all)
    async def global_listener(client, message):
        try:
            await process_message(bot, message)
        except Exception as e:
            print(f"❌ [Listener Error]: {e}", flush=True)

    await userbot.start()
    await bot.start()

    print("🚀 تم تشغيل النظام بالفلترة الدقيقة واستماع كافة المجموعات!", flush=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    t = threading.Thread(target=run_dummy_server, daemon=True)
    t.start()
    asyncio.run(main())

