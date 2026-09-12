import os
import asyncio
import hashlib
import json
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from hydrogram import Client
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

print("=" * 50, flush=True)
print("⚡ [START] تم تحميل السكريبت، جاري البدء مع Gemini...", flush=True)
print("=" * 50, flush=True)

# =========================================================
# KEEP ALIVE SERVER
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
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

API_ID = 39120728
API_HASH = "1deec8393ce5aa05c54c0c7e280377d4"

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

PROCESSED_MESSAGES = set()
PROCESSED_CONTENT = set()

def clean_text(text):
    return " ".join(text.strip().split()) if text else ""

def get_hash(text):
    return hashlib.sha256(clean_text(text).lower().encode("utf-8")).hexdigest()

# =========================================================
# GEMINI AI ANALYSIS
# =========================================================

def analyze_with_ai(text):
    if not GEMINI_API_KEY:
        print("❌ [AI Error] GEMINI_API_KEY غير مضاف في Render!", flush=True)
        return {"is_request": False, "type": "none", "confidence": 0}

    prompt = f"""
أنت خبير في فهم منشورات مجموعات التوصيل والمشاوير بالسعودية.
مهمتك: الفرز بين (الزبون الذي يطلب خدمة) و(السائق/المندوب الذي يعرض خدمته).

قواعد الفرز:
1. العميل (Customer): يبحث عن سيارة، سواق، توصيل غرض، مشوار، من يرجعني، مين يوصلني.
2. السائق (Driver): يعرض خدمته هو (مثل: متوفر الآن، سواق جاهز، توصيل طلبات، جاهز للمشاوير) -> النتيجة دائمًا none.
3. الإعلانات والخدمات الأخرى -> النتيجة دائمًا none.

التصنيفات المتاحة: delivery, ride, both, none.

النص للمراجعة:
"{text}"

أرجع JSON فقط بهذا الشكل وبدون أي تنسيق إضافي أو markdown:
{{"is_request": true, "type": "ride", "confidence": 0.90}}
"""

    # تم تصحيح الموديل إلى gemini-1.5-flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read().decode("utf-8"))

        raw_text = result["candidates"][0]["content"]["parts"][0]["text"]
        ai = json.loads(raw_text)

        is_req = bool(ai.get("is_request", False))
        req_type = ai.get("type", "none")
        conf = float(ai.get("confidence", 0))

        if req_type not in ("delivery", "ride", "both") or conf < 0.60:
            return {"is_request": False, "type": "none", "confidence": 0}

        return {"is_request": is_req, "type": req_type, "confidence": conf}
    except Exception as e:
        print(f"❌ [Gemini Error]: {e}", flush=True)
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
    label = "📦 طلب توصيل" if req_type == "delivery" else ("🚗 طلب مشوار" if req_type == "ride" else "📦🚗 طلب مشترك")
    
    print(f"🎯 [طلب جديد بـ Gemini] {label} | الثقة: {conf:.2f} | النص: {text[:40]}", flush=True)

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
        rows.append([InlineKeyboardButton("📩 الرابط الأصلي", url=message.link)])

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

    userbot = Client("my_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
    bot = Client("helper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)

    @userbot.on_message()
    async def global_listener(client, message):
        try:
            if message.chat:
                chat_name = message.chat.title or message.chat.username or "مجموعة"
                msg_txt = (message.text or message.caption or '')[:30]
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
        print(f"🌐 تم المزامنة بنجاح مع {dialogs_count} محادثة ومجموعة وقناة!", flush=True)

        print("🚀 [SUCCESS] النظام يعمل الآن بكفاءة وبدون أخطاء!", flush=True)
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

