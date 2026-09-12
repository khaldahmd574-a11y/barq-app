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
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    print(f"🌐 [HTTP Server] يعمل الآن على المنفذ {port}", flush=True)
    server.serve_forever()

# =========================================================
# SETTINGS
# =========================================================

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()

# القيم الأصلية الخاصة بحسابك لضمان عدم توقف البوت
API_ID = 39120728
API_HASH = "1deec8393ce5aa05c54c0c7e280377d4"

GEMINI_MODEL = "gemini-2.5-flash"
gemini_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        print(f"🤖 [Gemini] تم تجهيز Gemini: {GEMINI_MODEL}", flush=True)
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
# GEMINI AI ANALYSIS
# =========================================================

def analyze_with_ai(text):
    if not GEMINI_API_KEY:
        print("❌ [AI Error] GEMINI_API_KEY غير مضاف في Render!", flush=True)
        return {"is_request": False, "type": "none", "confidence": 0}

    if not gemini_client:
        print("❌ [AI Error] Gemini Client غير جاهز!", flush=True)
        return {"is_request": False, "type": "none", "confidence": 0}

    prompt = f"""
أنت نظام ذكاء اصطناعي متخصص في فرز رسائل مجموعات التوصيل والمشاوير في السعودية.
مهمتك هي تحديد هل المنشور يمثل "طلب خدمة حقيقي من عميل" أم لا.

يجب التفريق بوضوح بين:
1. العميل: يبحث عن سواق، سواقه، مندوب، توصيل غرض، مشوار، من يوصله، مين فاضي.
2. السائق أو المندوب: يعرض خدمته هو (مثل: متوفر الآن، مندوب جاهز، توصيل طلبات) -> اختر none.
3. الإعلانات والمحادثات العامة -> اختر none.

التصنيفات المسموحة: delivery, ride, both, none.

النص:
{text}

أرجع JSON فقط بهذا الشكل:
{{"is_request": true, "type": "ride", "confidence": 0.95}}
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
            print("❌ [Gemini Error] Gemini أعاد نتيجة فارغة", flush=True)
            return {"is_request": False, "type": "none", "confidence": 0}

        ai = json.loads(raw_text)
        is_req = bool(ai.get("is_request", False))
        req_type = str(ai.get("type", "none")).lower().strip()

        try:
            conf = float(ai.get("confidence", 0))
        except:
            conf = 0

        if req_type not in ("delivery", "ride", "both") or conf < 0.60 or not is_req:
            return {"is_request": False, "type": "none", "confidence": conf}

        return {"is_request": True, "type": req_type, "confidence": conf}

    except Exception as e:
        print(f"❌ [Gemini Error] {type(e).__name__}: {e}", flush=True)
        return {"is_request": False, "type": "none", "confidence": 0}

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

    if message.from_user:
        try:
            if message.from_user.is_self:
                return
        except:
            pass

    text = clean_text(message.text or message.caption or "")
    if len(text) < 3:
        return

    content_hash = get_hash(text)
    if content_hash in PROCESSED_CONTENT:
        print("♻️ [DUPLICATE] تم تجاهل منشور مكرر", flush=True)
        return

    result = await asyncio.to_thread(analyze_with_ai, text)
    if not result["is_request"]:
        return

    PROCESSED_CONTENT.add(content_hash)
    req_type, conf = result["type"], result["confidence"]
    label = "📦 طلب توصيل" if req_type == "delivery" else ("🚗 طلب مشوار" if req_type == "ride" else "📦🚗 طلب توصيل ومشوار")

    print(f"🎯 [طلب جديد بـ Gemini] {label} | الثقة: {conf:.2f} | النص: {text[:100]}", flush=True)

    rows = []
    if message.from_user:
        try:
            username = message.from_user.username
            user_id = message.from_user.id
            first_name = message.from_user.first_name or "الزبون"

            if username:
                user_url = f"https://t.me/{username}"
                user_text = f"💬 المحادثة (@{username})"
            else:
                user_url = f"tg://openmessage?user_id={user_id}"
                user_text = f"💬 المحادثة ({first_name})"

            rows.append([InlineKeyboardButton(user_text, url=user_url)])
        except Exception as e:
            print(f"⚠️ [Button Error] {e}", flush=True)

    try:
        if message.link:
            rows.append([InlineKeyboardButton("📩 الرابط الأصلي", url=message.link)])
    except:
        pass

    reply_markup = InlineKeyboardMarkup(rows) if rows else None
    full_msg = f"<b>{label}</b>\n\n{text}"

    for user in TARGET_USERS:
        try:
            await bot.send_message(chat_id=user, text=full_msg, reply_markup=reply_markup, disable_web_page_preview=True)
            print(f"📤 تم الإرسال بنجاح إلى: {user}", flush=True)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await bot.send_message(chat_id=user, text=full_msg, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as e:
            print(f"❌ فشل الإرسال إلى {user}: {e}", flush=True)

# =========================================================
# MAIN
# =========================================================

async def main():
    print("🔍 [CHECK] جاري الفحص عن المتغيرات...", flush=True)

    if not BOT_TOKEN:
        print("❌ [CRITICAL] BOT_TOKEN غير مضاف!", flush=True)
        return
    if not SESSION_STRING:
        print("❌ [CRITICAL] SESSION_STRING غير مضاف!", flush=True)
        return
    if not GEMINI_API_KEY:
        print("❌ [CRITICAL] GEMINI_API_KEY غير مضاف!", flush=True)
        return

    userbot = Client("my_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
    bot = Client("helper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

    @userbot.on_message()
    async def global_listener(client, message):
        try:
            if not message.chat:
                return
            chat_name = message.chat.title or message.chat.username or "مجموعة"
            msg_txt = (message.text or message.caption or "")[:50]
            print(f"📩 [{chat_name}]: {msg_txt}", flush=True)
            await process_message(bot, message)
        except Exception as e:
            print(f"❌ [Listener Error]: {e}", flush=True)

    try:
        await userbot.start()
        print("✅ [Userbot] متصل بنجاح!", flush=True)

        await bot.start()
        print("✅ [Bot] متصل بنجاح!", flush=True)

        print("🔄 جاري تحميل ومزامنة قائمة المجموعات والقنوات...", flush=True)
        dialogs_count = 0
        async for dialog in userbot.get_dialogs():
            dialogs_count += 1
        print(f"🌐 تمت المزامنة بنجاح مع {dialogs_count} محادثة ومجموعة وقناة!", flush=True)

        print("🚀 [SUCCESS] النظام يعمل الآن بكفاءة مع Gemini الجديدة!", flush=True)
        await asyncio.Event().wait()
    except Exception as e:
        print(f"❌ [LOGIN ERROR] فشل الاتصال: {e}", flush=True)

if __name__ == "__main__":
    t = threading.Thread(target=run_dummy_server, daemon=True)
    t.start()

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"❌ [CRITICAL ERROR]: {e}", flush=True)

