import os
import re
import time
import asyncio
import hashlib
import requests
from difflib import SequenceMatcher
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.enums import ChatType

# =========================================================
# KEEP ALIVE SERVER 24/7
# =========================================================
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Clean Active!")

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

TARGET_USER = "abood1317"
PROCESSED_KEYS = set()

def analyze_intent_with_ai(text: str) -> bool:
    clean = " ".join(text.split()).strip()
    if not clean or len(clean) < 2 or not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت ذكاء اصطناعي لقروبات التوصيل والمشاوير بجازان. هل الرسالة من زبون يبحث عن توصيل/سواق (YES) أم سائق يعلن عن نفسه (NO)؟
الرسالة: "{clean}"
الجواب بكلمة واحدة فقط: (YES) أو (NO):"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 2
        }
        res = requests.post(url, headers=headers, json=payload, timeout=4)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            return "YES" in answer
    except Exception:
        pass
    return False

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "barq_userbot_final",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING
    )

    bot = Client(
        "barq_helper_final",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN
    )

    @userbot.on_message()
    async def handle_all_messages(client: Client, message: Message):
        try:
            if not message or not message.chat:
                return
            if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
                return
            
            if message.from_user and message.from_user.is_self:
                return
            if message.reply_to_message_id or message.reply_to_message:
                return

            text = message.text or message.caption or ""
            text = text.strip()
            if len(text) < 2:
                return

            msg_key = f"{message.chat.id}_{message.id}"
            if msg_key in PROCESSED_KEYS:
                return
            PROCESSED_KEYS.add(msg_key)
            if len(PROCESSED_KEYS) > 5000:
                PROCESSED_KEYS.clear()

            loop = asyncio.get_running_loop()
            is_client = await loop.run_in_executor(None, analyze_intent_with_ai, text)
            
            if not is_client:
                return

            print(f"✅ [تم سحب الطلب بنجاح]: {text[:30]}", flush=True)

            row = []
            if message.from_user:
                if message.from_user.username:
                    user_url = f"https://t.me/{message.from_user.username}"
                    user_label = f"💬 فتح المحادثة (@{message.from_user.username})"
                else:
                    user_url = f"tg://openmessage?user_id={message.from_user.id}"
                    user_label = "💬 فتح المحادثة"
                row.append(InlineKeyboardButton(user_label, url=user_url))

            if message.link:
                row.append(InlineKeyboardButton("📩 الرسالة الأصلية", url=message.link))

            reply_markup = InlineKeyboardMarkup([row]) if row else None

            await bot.send_message(
                chat_id=TARGET_USER,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )

        except Exception as e:
            print(f"Error: {e}", flush=True)

    await bot.start()
    await userbot.start()
    print("🚀 [برق يعمل الآن بشكل نظامي وسليم]...", flush=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
