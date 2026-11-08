import os
import re
import time
import asyncio
import hashlib
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.enums import ChatType

# =========================================================
# 1. 24/7 DUMMY SERVER FOR RENDER
# =========================================================

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Simple Engine is Live!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# =========================================================
# 2. CONFIGURATION & SETTINGS
# =========================================================

SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
API_HASH = os.environ.get("TELEGRAM_API_HASH", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

# قراءة API_ID بشكل آمن تماماً
try:
    API_ID = int(os.environ.get("TELEGRAM_API_ID", "0"))
except ValueError:
    API_ID = 0

# قائمة المشتركين المستهدفين بالكامل
TARGET_USERS = [
    "abood1317", 
    "Waaaaaaa33", 
    "shaybq", 
    "Ndhhyfvvjkcd", 
    "fs_990", 
    "Khaid3333", 
    "anas14440"
]

PROCESSED_MESSAGES = set()

# =========================================================
# 3. AI INTENT ANALYZER (Gemini Flash-Lite)
# =========================================================

def analyze_intent(text: str) -> bool:
    clean = text.strip()
    if not clean or len(clean) < 3:
        return False

    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت مساعد ذكي لتحليل رسائل قروبات التوصيل والمشاوير في جازان (السعودية).
اقرأ الرسالة التالية وحدد هل هي طلب زبون حقيقي يبحث عن توصيلة أو مشوار أو ينادي على سواق؟

الرسالة: "{clean}"

أجب بكلمة واحدة فقط لا غير:
إذا كانت طلب توصيل/مشوار حقيقي أجب: YES
إذا كانت غير ذلك (إعلان سائق، دردشة، إعلان تجاري، تنبيه، إلخ) أجب: NO"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        payload = {
            "model": "google/gemini-3.1-flash-lite",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 2
        }
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"AI Analysis: '{clean[:25]}...' -> {answer}", flush=True)
            return "YES" in answer
    except Exception as e:
        print(f"OpenRouter Error: {e}", flush=True)

    return False

# =========================================================
# 4. MAIN TELEGRAM CLIENTS
# =========================================================

async def main():
    threading.Thread(target=run_server, daemon=True).start()
    print("Dummy server started on Render port.", flush=True)

    # التحقق من المتغيرات البيئية وطباعة تنبيه تفصيلي إن نقص شيء
    missing = []
    if not SESSION_STRING: missing.append("SESSION_STRING")
    if not API_ID: missing.append("TELEGRAM_API_ID")
    if not API_HASH: missing.append("TELEGRAM_API_HASH")
    if not BOT_TOKEN: missing.append("BOT_TOKEN")
    if not OPENROUTER_API_KEY: missing.append("OPENROUTER_API_KEY")

    if missing:
        print(f"CRITICAL WARNING: Missing environment variables: {', '.join(missing)}", flush=True)
    else:
        print("All environment variables loaded successfully!", flush=True)

    userbot = Client(
        "my_user_session",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    bot = Client(
        "my_helper_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True
    )

    @userbot.on_message(filters.group & filters.text & ~filters.me)
    async def handle_new_message(client: Client, message: Message):
        try:
            if not message or not message.text or not message.chat:
                return

            if message.reply_to_message_id:
                return

            msg_key = f"{message.chat.id}_{message.id}"
            if msg_key in PROCESSED_MESSAGES:
                return

            PROCESSED_MESSAGES.add(msg_key)
            if len(PROCESSED_MESSAGES) > 5000:
                PROCESSED_MESSAGES.clear()

            text = message.text.strip()
            if len(text) < 3:
                return

            loop = asyncio.get_running_loop()
            is_request = await loop.run_in_executor(None, analyze_intent, text)

            if is_request:
                print(f"Target Request Captured: {text[:35]}...", flush=True)

                buttons = []
                row = []
                if message.from_user:
                    if message.from_user.username:
                        user_url = f"https://t.me/{message.from_user.username}"
                        label = f"محادثة (@{message.from_user.username})"
                    else:
                        user_url = f"tg://openmessage?user_id={message.from_user.id}"
                        label = "محادثة مستخدم"
                    row.append(InlineKeyboardButton(label, url=user_url))

                if message.link:
                    row.append(InlineKeyboardButton("الرسالة الأصلية", url=message.link))

                if row:
                    buttons.append(row)
                
                markup = InlineKeyboardMarkup(buttons) if buttons else None

                for username in TARGET_USERS:
                    sent = False
                    try:
                        await bot.send_message(
                            chat_id=username,
                            text=text,
                            reply_markup=markup,
                            disable_web_page_preview=True
                        )
                        sent = True
                    except Exception:
                        pass

                    if not sent:
                        try:
                            await userbot.send_message(
                                chat_id=username,
                                text=text,
                                disable_web_page_preview=True
                            )
                        except Exception:
                            pass

        except Exception as ex:
            print(f"Message Processing Error: {ex}", flush=True)

    await userbot.start()
    await bot.start()
    print("Barq Engine is up and running successfully!", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
