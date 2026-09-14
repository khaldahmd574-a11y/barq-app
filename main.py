import os
import asyncio
import re
import hashlib
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

# =========================================================
# KEEP ALIVE SERVER 24/7
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq OpenRouter Active 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# =========================================================
# CONFIGURATION
# =========================================================

SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

PROCESSED_MSG_IDS = set()
PROCESSED_TEXT_HASHES = set()

# الكلمات المفتاحية المحلية المباشرة (تتجاوز الذكاء الاصطناعي فوراً إذا وجدت)
EXPRESS_KEYWORDS = [
    "فاضي", "من فاضي", "مين فاضي", "أبغى", "ابغى", "نوصل", "توصيل", 
    "سائق", "سواق", "سواقة", "سواقه", "مندوب", "مشوار", "ويرجعني", "يرجعني"
]

# =========================================================
# OPENROUTER AI ENGINE WITH LOCAL HYBRID FALLBACK
# =========================================================

def analyze_message(text: str) -> bool:
    # 1. استبعاد أرقام الجوال فوراً (عروض سائقين)
    if re.search(r'(05\d{8}|\+?9665\d{8})', text):
        print(f"🚫 [استبعاد]: تحتوي على رقم جوال", flush=True)
        return False

    clean = text.lower()

    # 2. فحص الكلمات السريعة التلقائية (مثل "مين فاضي")
    for kw in EXPRESS_KEYWORDS:
        if kw in clean:
            print(f"⚡ [اعتماد فوري محلي]: احتوت على كلمة مفتاحية '{kw}'", flush=True)
            return True

    # 3. التحليل عبر الذكاء الاصطناعي للعبارات المركبة
    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""هل الرسالة التالية عبارة عن طلب توصيل أو مشوار أو بحث عن سائق/باص/مندوب أو استفسار عن شخص فاضي للتوصيل؟
أجب بكلمة واحدة فقط: YES أو NO.

الرسالة: "{text}"
الجواب:"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    models_to_try = [
        "qwen/qwen-2.5-7b-instruct",
        "meta-llama/llama-3.3-70b-instruct:free",
        "mistralai/mistral-small-24b-instruct-2501:free"
    ]

    for model_name in models_to_try:
        try:
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 5
            }
            res = requests.post(url, headers=headers, json=payload, timeout=4)
            if res.status_code == 200:
                answer = res.json()['choices'][0]['message']['content'].strip().upper()
                print(f"🤖 [تحليل AI عبر {model_name}]: '{text[:30]}...' -> {answer}", flush=True)
                return "YES" in answer
        except Exception:
            continue

    return False

# =========================================================
# LIVE MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    if not message or not message.id:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MSG_IDS:
        return
    PROCESSED_MSG_IDS.add(msg_key)

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    clean_text = raw_text.strip()
    if len(clean_text) < 3:
        return

    text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    if text_hash in PROCESSED_TEXT_HASHES:
        return

    loop = asyncio.get_event_loop()
    is_valid = await loop.run_in_executor(None, analyze_message, clean_text)

    if is_valid:
        print("✅ [تم الاعتماد]: جارٍ الإرسال إلى الحسابات المستهدفة...", flush=True)
        PROCESSED_TEXT_HASHES.add(text_hash)

        buttons = []
        row = []
        
        if message.from_user:
            if message.from_user.username:
                user_url = f"https://t.me/{message.from_user.username}"
                user_label = f"💬 فتح المحادثة (@{message.from_user.username})"
            else:
                user_url = f"tg://openmessage?user_id={message.from_user.id}"
                user_label = f"💬 فتح المحادثة ({message.from_user.first_name or 'المستخدم'})"
            row.append(InlineKeyboardButton(user_label, url=user_url))

        if message.link:
            row.append(InlineKeyboardButton("📩 الرسالة الأصلية", url=message.link))
        
        if row:
            buttons.append(row)
            
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

        for user in TARGET_USERS:
            sent = False
            if bot:
                try:
                    await bot.send_message(
                        chat_id=user,
                        text=clean_text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                    sent = True
                except Exception:
                    pass

            if not sent:
                try:
                    await userbot.send_message(
                        chat_id=user,
                        text=clean_text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except Exception:
                    pass

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

    bot = None
    if BOT_TOKEN:
        try:
            bot = Client(
                "helper_bot",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                in_memory=True
            )
            await bot.start()
        except Exception:
            pass

    # الاستماع لجميع المحادثات والقروبات والسنوات الكبيرة ومجموعات السوبر
    @userbot.on_message(filters.group | filters.channel | filters.supergroup)
    async def global_live_listener(client: Client, message: Message):
        await process_live_message(client, bot, message)

    await userbot.start()
    print("🚀 تم تشغيل النظام المطور (AI + فحص فوري للقروبات الكبيرة)!", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

