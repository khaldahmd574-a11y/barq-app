import os
import re
import time
import asyncio
import hashlib
import aiohttp
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
        self.wfile.write(b"Barq Pure Silent Engine Active!")

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

TARGET_USERS = ["abood1317", "Waaaaaaa33", "shaybq", "Ndhhyfvvjkcd", "fs_990", "Khaid3333"]

PROCESSED_KEYS = set()
USER_REQUEST_HISTORY = {} 
MIN_TIME_BETWEEN_REPEATS = 600   # 10 دقائق منع التكرار
SIMILARITY_THRESHOLD = 0.65       # نسبة التشابه النصي

ai_semaphore = asyncio.Semaphore(15) 
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

# =========================================================
# AI ANALYZER (Gemini 3.1 Flash-Lite)
# =========================================================

async def analyze_intent_with_ai(text: str) -> bool:
    clean = text.strip()
    
    if not clean or len(clean) < 3:
        return False

    if not re.search(r'[\u0600-\u06FFa-zA-Z]', clean):
        return False

    if clean.lower() in ["سلام", "السلام عليكم", "مرحبا", "هلا", "صباح الخير", "مساء الخير", "الو"]:
        return False

    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت عقل ذكاء اصطناعي خارق ومختص حصرياً بتحليل نية الرسائل في قروبات التوصيل والمشاوير والمناديب بمنطقة جازان بالمملكة العربية السعودية.

مهمتك الجوهرية قراءة الرسالة وتحديد ما إذا كانت طلباً من زبون أو عميل:

[اقبل الرسالة وأجب بـ (YES) فقط في هذه الحالة:]
- إذا كان الكاتب يبحث عن توصيلة، مشوار، نقل، أو مندوب لنفسه أو لمعارفه (مثل: "ابغى سواقه في صبيا توصلني العدايا"، "مين يوديني من الحمى لين الشقيري").
- إذا كان الكاتب يسأل صراحة عن توفر سائق أو شخص في أي مدينة أو قرية بجازان (مثل: "مين فاضي في جيزان"، "مين فاضي في ضمد"، "من فاضي في صبيا"، "فيه احد عند جرير؟").
- أي استفسار بريء يبحث عن خدمة نقل أو توصيل مهما كانت لهجته.

[ارفض الرسالة وأجب بـ (NO) في أي حالة أخرى، مثل:]
- إعلانات السائقين الذين يعرضون خدماتهم (مثل: "طالع من جيزان لصامطة"، "فاضي في أبوعريش").
- التنبيهات وقوائم الثقة وإرشادات الإدارة.

الرسالة المراد تحليلها:
"{clean}"

الجواب كلمة واحدة فقط لا غير (YES) أو (NO):"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "google/gemini-3.1-flash-lite",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 2,
        "stream": False
    }

    try:
        session = await get_http_session()
        async with ai_semaphore:
            async with session.post(url, headers=headers, json=payload, timeout=aiohttp.ClientTimeout(total=4)) as res:
                if res.status == 200:
                    data = await res.json()
                    choices = data.get('choices')
                    if choices and len(choices) > 0:
                        content = choices[0].get('message', {}).get('content')
                        if content:
                            return "YES" in content.strip().upper()
    except Exception:
        pass

    return False

# =========================================================
# REAL-TIME LIVE EVENT PROCESSOR (المستمع الفوري الصامت)
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    try:
        if not message or not message.id or not message.chat:
            return

        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return

        if message.reply_to_message_id or message.reply_to_message:
            return

        if message.from_user and message.from_user.is_self:
            return

        raw_text = message.text or message.caption or ""
        clean_text = raw_text.strip()
        
        if len(clean_text) < 3:
            return

        msg_key = f"{message.chat.id}_{message.id}"
        text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
        
        if msg_key in PROCESSED_KEYS or text_hash in PROCESSED_KEYS:
            return

        current_time = time.time()
        user_id = message.from_user.id if message.from_user else None

        if user_id and user_id in USER_REQUEST_HISTORY:
            user_history = USER_REQUEST_HISTORY[user_id]
            for past_request in user_history:
                if is_similar_text(clean_text, past_request['text']):
                    if current_time - past_request['time'] < MIN_TIME_BETWEEN_REPEATS:
                        return

        PROCESSED_KEYS.add(msg_key)
        PROCESSED_KEYS.add(text_hash)

        if len(PROCESSED_KEYS) > 20000:
            PROCESSED_KEYS.clear()

        print(f"🔍 [استماع فوري حي]: {clean_text[:35]}", flush=True)
        is_client_request = await analyze_intent_with_ai(clean_text)

        if is_client_request:
            if user_id:
                if user_id not in USER_REQUEST_HISTORY:
                    USER_REQUEST_HISTORY[user_id] = []
                USER_REQUEST_HISTORY[user_id].append({'text': clean_text, 'time': current_time})

            print(f"🚀 [طلب زبون فوري مقبول]: {clean_text[:35]}...", flush=True)

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
                row.append(InlineKeyboardButton("📩 الرسالة الأصلية", message.link))
            
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
    except Exception as e:
        print(f"Error in live processor: {e}", flush=True)

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

    # المستمع الفوري الصامت للأحداث الحية بدون أي طلبات سحب خارجية
    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        asyncio.create_task(process_live_message(client, bot, message))

    await userbot.start()
    me = await userbot.get_me()
    print(f"⚡ [Barq Pure Silent Live Engine] يعمل بنجاح تام وبدون أي حظر عبر الحساب: {me.first_name}", flush=True)

    await asyncio.Event().wait()

    if http_session and not http_session.closed:
        await http_session.close()

if __name__ == "__main__":
    asyncio.run(main())
