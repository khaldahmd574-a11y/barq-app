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
        self.wfile.write(b"Barq Smart AI System Active!")

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

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "Ndhhyfvvjkcd", "fs_990"]

PROCESSED_KEYS = set()
KNOWN_CHAT_IDS = set()

USER_REQUEST_HISTORY = {} 
MIN_TIME_BETWEEN_REPEATS = 600   # 10 دقائق
SIMILARITY_THRESHOLD = 0.65       

# =========================================================
# HELPER: SMART TEXT SIMILARITY
# =========================================================

def is_similar_text(text1: str, text2: str) -> bool:
    clean1 = re.sub(r'[^\w\s]', '', text1.lower()).strip()
    clean2 = re.sub(r'[^\w\s]', '', text2.lower()).strip()
    
    ratio = SequenceMatcher(None, clean1, clean2).ratio()
    return ratio >= SIMILARITY_THRESHOLD

# =========================================================
# ADVANCED PURE AI ENGINE (تمييز الزبون والسائق والدقة العالية)
# =========================================================

def analyze_intent_with_ai(text: str) -> bool:
    clean = " ".join(text.split()).strip()
    
    if not clean or len(clean) < 2:
        return False

    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت عقل ذكاء اصطناعي خبير لفلترة وتصنيف رسائل قروبات التوصيل والمشاوير بالجنوب وجازان.

المطلوب: هل الكاتب [زبون يحتاج توصيلة/خدمة] أم [سائق يعلن عن نفسه/رد عادي]؟

[أجب بـ YES فقط إذا كانت الرسالة من زبون محتاج]:
- زبون يطلب مشوار أو مندوب أو نقل (مثل: "ابي توصيل من بطحان"، "من ابوعريش لضمد بكم"، "ابغى اروح شارع المطاعم").
- زبون يطلب توصيلة ويضع رقم جواله للتواصل معه (مثل: "محتاج سواق لصبيا وهذا رقمي 050xxx"، "دقو علي معندي نت 0530177247").

[أجب بـ NO فوراً وبدون تردد إذا كانت الرسالة]:
1. إعلان من سائق يعرض توفره أو سيارته حتى لو وضع رقم جواله (مثل: "العارضة بطحان فاضي اي مشوار تواصل خاص او واتس 050xxx"، "متوفر حالياً للطلبات"، "سيارة جاهزة للدوامات").
2. زبون يعتذر أو يخبر الأعضاء بأنه اكتفى أو ألغى الطلب (مثل: "حصلت الله يسعدكم"، "تكنسل"، "خلاص لقينا"، "استغنيت").
3. نداءات عامة أو كلمات مجردة أو تعليقات لا تحتوي تفاصيل مشوار (مثل: "مساعدة"، "وين فعلين الخير"، "سوالف"، "ههههه").

الرسالة المراد تحليلها:
"{clean}"

الجواب كلمة واحدة فقط لا غير: (YES) أو (NO):"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    models_to_try = ["deepseek/deepseek-chat", "openai/gpt-4o-mini"]

    for model_name in models_to_try:
        try:
            payload = {
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 2
            }
            res = requests.post(url, headers=headers, json=payload, timeout=3)
            if res.status_code == 200:
                answer = res.json()['choices'][0]['message']['content'].strip().upper()
                print(f"🤖 [{model_name}]: '{clean[:35]}...' -> {answer}", flush=True)
                return "YES" in answer
        except Exception:
            continue

    return False

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    try:
        if not message or not message.id or not message.chat:
            return

        if message.chat.type == ChatType.PRIVATE:
            return

        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            KNOWN_CHAT_IDS.add(message.chat.id)

        if message.reply_to_message_id or message.reply_to_message:
            return

        if message.from_user and message.from_user.is_self:
            return

        raw_text = message.text or message.caption or ""
        clean_text = raw_text.strip()
        
        if len(clean_text) < 2:
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
                    time_diff = current_time - past_request['time']
                    if time_diff < MIN_TIME_BETWEEN_REPEATS:
                        return

        PROCESSED_KEYS.add(msg_key)
        PROCESSED_KEYS.add(text_hash)

        if len(PROCESSED_KEYS) > 10000:
            PROCESSED_KEYS.clear()

        loop = asyncio.get_running_loop()
        is_client_request = await loop.run_in_executor(None, analyze_intent_with_ai, clean_text)

        if is_client_request:
            if user_id:
                if user_id not in USER_REQUEST_HISTORY:
                    USER_REQUEST_HISTORY[user_id] = []
                USER_REQUEST_HISTORY[user_id].append({'text': clean_text, 'time': current_time})

            print(f"✅ [سحب طلب زبون مقبول]: {clean_text[:30]}...", flush=True)

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
    except Exception:
        pass

# =========================================================
# HIGH-SPEED SCANNER (0.1s)
# =========================================================

async def direct_chat_history_scanner(userbot: Client, bot: Client):
    await asyncio.sleep(1)
    
    try:
        async for dialog in userbot.get_dialogs(limit=50):
            if dialog.chat and dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                KNOWN_CHAT_IDS.add(dialog.chat.id)
    except Exception:
        pass

    while True:
        if KNOWN_CHAT_IDS:
            for chat_id in list(KNOWN_CHAT_IDS):
                try:
                    async for msg in userbot.get_chat_history(chat_id=chat_id, limit=2):
                        asyncio.create_task(process_live_message(userbot, bot, msg))
                except Exception:
                    continue
        await asyncio.sleep(0.1)

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

    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        asyncio.create_task(process_live_message(client, bot, message))

    await userbot.start()
    print("🚀 تم تفعيل الكود المطور والمحدث بنجاح!", flush=True)

    asyncio.create_task(direct_chat_history_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
