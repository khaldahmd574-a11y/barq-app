import os
import re
import asyncio
import hashlib
import threading
from difflib import SequenceMatcher
from http.server import HTTPServer, BaseHTTPRequestHandler

import aiohttp
from cachetools import TTLCache
from hydrogram import Client, filters
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
        self.wfile.write(b"Barq Instant Pure AI Engine Active!")

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

TARGET_USERS = ["abood1317", "Waaaaaaa33", "shaybq", "Ndhhyfvvjkcd", "fs_990", "anas14440"]

seen_messages = TTLCache(maxsize=20000, ttl=10800)
USER_REQUEST_HISTORY = {} 
MIN_TIME_BETWEEN_REPEATS = 600
SIMILARITY_THRESHOLD = 0.65

ai_semaphore = asyncio.Semaphore(5)
http_session = None

async def get_http_session():
    global http_session
    if http_session is None or http_session.closed:
        http_session = aiohttp.ClientSession()
    return http_session

def is_similar_text(text1: str, text2: str) -> bool:
    clean1 = re.sub(r'[^\w\s]', '', text1.lower()).strip()
    clean2 = re.sub(r'[^\w\s]', '', text2.lower()).strip()
    return SequenceMatcher(None, clean1, clean2).ratio() >= SIMILARITY_THRESHOLD

def get_message_text(message: Message) -> str:
    return (message.text or message.caption or "").strip()

def make_fingerprint(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip()).casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

# =========================================================
# FAST ASYNC AI INTENT ANALYZER
# =========================================================

async def analyze_intent_with_ai(text: str) -> bool:
    clean = text.strip()
    if not clean or len(clean) < 3 or not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت نظام ذكاء اصطناعي فائق السرعة والدقة لاكتشاف طلبات التوصيل والمشاوير في جازان.
أجب بـ (YES) فقط إذا كان الكاتب زبوناً حقيقيياً يطلب مشواراً أو توصيلاً لنفسه أو لغرضه.
أجب بـ (NO) إذا كان سائقاً يعرض خدماته أو إعلاناً تجارياً.

النص: "{clean}"
الجواب بكلمة واحدة (YES) أو (NO):"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 2,
        "stream": False
    }

    try:
        session = await get_http_session()
        async with ai_semaphore:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=6)) as res:
                if res.status == 200:
                    data = await res.json()
                    answer = data['choices'][0]['message']['content'].strip().upper()
                    print(f"🧠 [فحص فوري]: '{clean[:30]}...' -> {answer}", flush=True)
                    return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ AI: {e}", flush=True)

    return False

# =========================================================
# INSTANT EVENT HANDLER (بدون تأخير)
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    try:
        if not message or not message.id or not message.chat:
            return

        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return

        if message.from_user and message.from_user.is_self:
            return

        raw_text = get_message_text(message)
        if len(raw_text) < 3:
            return

        # تجاهل التكرار الفوري عبر البصمة
        msg_key = f"{message.chat.id}_{message.id}"
        text_hash = make_fingerprint(raw_text)
        
        if msg_key in seen_messages or text_hash in seen_messages:
            return

        seen_messages[msg_key] = True
        seen_messages[text_hash] = True

        # تحليل فوري بالذكاء الاصطناعي
        is_client_request = await analyze_intent_with_ai(raw_text)

        if is_client_request:
            print(f"✅ [طلب زبون فوري مقبول]: {raw_text[:30]}...", flush=True)

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
                            text=raw_text,
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
                            text=raw_text,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )
                    except Exception:
                        pass
    except Exception as e:
        print(f"Error: {e}", flush=True)

# =========================================================
# MAIN ENTRYPOINT
# =========================================================

async def main():
    global http_session
    threading.Thread(target=run_dummy_server, daemon=True).start()

    http_session = aiohttp.ClientSession()

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

    # ⚡ استقبال لحظي فوري بدون أي حلقات فحص دورية (Polling)
    @userbot.on_message(filters.group & (filters.text | filters.caption))
    async def instant_listener(client: Client, message: Message):
        asyncio.create_task(process_live_message(client, bot, message))

    await userbot.start()
    print("🚀 تم تشغيل نظام برق اللحظي الفوري بدون أي تأخير!", flush=True)

    await asyncio.Event().wait()

    if http_session and not http_session.closed:
        await http_session.close()

if __name__ == "__main__":
    asyncio.run(main())
