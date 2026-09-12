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

# الاسم الجديد المعتمد للموديل
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

def analyze_with_ai(text):
    if not GEMINI_API_KEY or not gemini_client:
        return {"is_request": False, "type": "none", "confidence": 0}

    prompt = f"""
أنت نظام ذكاء اصطناعي متخصص في فرز رسائل مجموعات التوصيل والمشاوير في السعودية.
حدد هل المنشور "طلب خدمة حقيقي من عميل" أم لا.
1. العميل: يبحث عن سواق/مندوب/توصيل غرض/مشوار.
2. السائق: يعرض خدمته -> اختر none.

التصنيفات: delivery, ride, both, none.
النص: {text}
أرجع JSON فقط: {{"is_request": true, "type": "ride", "confidence": 0.95}}
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
            return {"is_request": False, "type": "none", "confidence": 0}

        ai = json.loads(raw_text)
        is_req = bool(ai.get("is_request", False))
        req_type = str(ai.get("type", "none")).lower().strip()
        conf = float(ai.get("confidence", 0))

        if req_type not in ("delivery", "ride", "both") or conf < 0.60 or not is_req:
            return {"is_request": False, "type": "none", "confidence": conf}

        return {"is_request": True, "type": req_type, "confidence": conf}

    except Exception as e:
        print(f"❌ [Gemini Error] {e}", flush=True)
        return {"is_request": False, "type": "none", "confidence": 0}

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
        return

    result = await asyncio.to_thread(analyze_with_ai, text)
    if not result["is_request"]:
        return

    PROCESSED_CONTENT.add(content_hash)
    req_type, conf = result["type"], result["confidence"]
    label = "📦 طلب توصيل" if req_type == "delivery" else ("🚗 طلب مشوار" if req_type == "ride" else "📦🚗 طلب توصيل ومشوار")

    print(f"🎯 [طلب جديد بـ Gemini] {label} | الثقة: {conf:.2f}", flush=True)

    rows = []
    if message.from_user:
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

    if message.link:
        rows.append([InlineKeyboardButton("📩 الرابط الأصلي", url=message.link)])

    reply_markup = InlineKeyboardMarkup(rows) if rows else None
    full_msg = f"<b>{label}</b>\n\n{text}"

    for user in TARGET_USERS:
        try:
            await bot.send_message(chat_id=user, text=full_msg, reply_markup=reply_markup, disable_web_page_preview=True)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await bot.send_message(chat_id=user, text=full_msg, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception:
            pass

async def main():
    userbot = Client("my_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
    bot = Client("helper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

    @userbot.on_message()
    async def global_listener(client, message):
        try:
            if message.chat:
                await process_message(bot, message)
        except Exception:
            pass

    await userbot.start()
    await bot.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    t = threading.Thread(target=run_dummy_server, daemon=True)
    t.start()
    asyncio.run(main())

