import os
import re
import time
import asyncio
import hashlib
import sqlite3
import requests
from difflib import SequenceMatcher
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.enums import ChatType
from hydrogram.errors import FloodWait

# =========================================================
# 1. KEEP ALIVE SERVER 24/7
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Ultra-Fast Safe Engine Active!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# =========================================================
# 2. CONFIGURATION & DATABASE SETUP
# =========================================================

SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

TARGET_USERS = ["abood1317", "Waaaaaaa33", "shaybq", "Ndhhyfvvjkcd", "fs_990", "Khaid3333", "anas14440"]

MIN_TIME_BETWEEN_REPEATS = 600   # 10 دقائق منع التكرار
SIMILARITY_THRESHOLD = 0.65       # نسبة التشابه النصي
USER_REQUEST_HISTORY = {} 
message_queue = asyncio.Queue()
KNOWN_CHAT_IDS = set()

def init_db():
    conn = sqlite3.connect("barq_ultrafast_safe.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS processed_messages (
            msg_key TEXT PRIMARY KEY,
            timestamp REAL
        )
    """)
    conn.commit()
    conn.close()

def is_processed_in_db(msg_key: str) -> bool:
    conn = sqlite3.connect("barq_ultrafast_safe.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM processed_messages WHERE msg_key = ?", (msg_key,))
    row = cursor.fetchone()
    conn.close()
    return row is not None

def save_processed_to_db(msg_key: str):
    conn = sqlite3.connect("barq_ultrafast_safe.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO processed_messages (msg_key, timestamp) VALUES (?, ?)", (msg_key, time.time()))
    conn.commit()
    conn.close()

def is_similar_text(text1: str, text2: str) -> bool:
    clean1 = re.sub(r'[^\w\s]', '', text1.lower()).strip()
    clean2 = re.sub(r'[^\w\s]', '', text2.lower()).strip()
    return SequenceMatcher(None, clean1, clean2).ratio() >= SIMILARITY_THRESHOLD

def analyze_intent_with_ai(text: str) -> bool:
    clean = text.strip()
    if not clean or len(clean) < 3:
        return False
    if not re.search(r'[\u0600-\u06FFa-zA-Z]', clean):
        return False
    if clean.lower() in ["سلام", "السلام عليكم", "مرحبا", "هلا", "صباح الخير", "مساء الخير", "الو"]:
        return False
    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت عقل ذكاء اصطناعي خارق وواعي تماماً، ومختص حصرياً بتحليل نية الرسائل في قروبات التوصيل والمشاوير والمناديب بمنطقة جازان بالمملكة العربية السعودية.

مهمتك الجوهرية هي قراءة الرسالة التالية وتحديد هدف الكاتب بدقة مطلقة:

[اقبل الرسالة وأجب بـ (YES) فقط في هذه الحالة:]
- إذا كان الكاتب زبوناً أو عميلاً حقيقياً يبحث عن توصيلة، مشوار، نقل، أو مندوب لنفسه أو لأحد معارفه (بما في ذلك طلبات الشراء أو الاستفسار عن متواجدين في أماكن مثل جرير وغيرها).
- إذا كان الكاتب يسأل أو يستفسر عن توفر شخص، سائق، أو مندوب في أي مدينة أو قرية في جازان (مثل: "من فاضي في ضمد"، "احد موجود في إسكان الحصمة ابغا مشوار").
- أي طلب أو استفسار بريء يبحث عن خدمة نقل أياً كانت طريقته أو لهجته.

[ارفض الرسالة وأجب بـ (NO) في أي حالة أخرى، مثل:]
- إعلانات السائقين الذين يعرضون خدماتهم ورحلاتهم أو أرقام جوالاتهم.
- قوائم الثقة، أسماء الكباتن المعتمدين، أو تنبيهات الإدارة.
- التحذيرات الأمنية، رسائل إبراء الذمة، الإعلانات التجارية والقروض.

الرسالة المراد تحليلها بعمق:
"{clean}"

الجواب كلمة واحدة فقط لا غير (YES) أو (NO):"""

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
        res = requests.post(url, headers=headers, json=payload, timeout=6)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            return "YES" in answer
    except Exception:
        pass
    return False

# =========================================================
# 3. MESSAGE WORKER & QUEUE
# =========================================================

async def message_worker(userbot: Client, bot: Client):
    while True:
        message = await message_queue.get()
        try:
            if not message or not message.id or not message.chat:
                message_queue.task_done()
                continue

            if message.chat.type == ChatType.PRIVATE:
                message_queue.task_done()
                continue

            if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                KNOWN_CHAT_IDS.add(message.chat.id)

            if message.reply_to_message_id or message.reply_to_message:
                message_queue.task_done()
                continue

            if message.from_user and message.from_user.is_self:
                message_queue.task_done()
                continue

            raw_text = message.text or message.caption or ""
            clean_text = raw_text.strip()
            
            if len(clean_text) < 3:
                message_queue.task_done()
                continue

            msg_key = f"{message.chat.id}_{message.id}"
            text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
            
            if is_processed_in_db(msg_key) or is_processed_in_db(text_hash):
                message_queue.task_done()
                continue

            current_time = time.time()
            user_id = message.from_user.id if message.from_user else None

            if user_id and user_id in USER_REQUEST_HISTORY:
                user_history = USER_REQUEST_HISTORY[user_id]
                skip = False
                for past_request in user_history:
                    if is_similar_text(clean_text, past_request['text']):
                        if (current_time - past_request['time']) < MIN_TIME_BETWEEN_REPEATS:
                            skip = True
                            break
                if skip:
                    message_queue.task_done()
                    continue

            save_processed_to_db(msg_key)
            save_processed_to_db(text_hash)

            loop = asyncio.get_running_loop()
            is_client_request = await loop.run_in_executor(None, analyze_intent_with_ai, clean_text)

            if is_client_request:
                if user_id:
                    if user_id not in USER_REQUEST_HISTORY:
                        USER_REQUEST_HISTORY[user_id] = []
                    USER_REQUEST_HISTORY[user_id].append({'text': clean_text, 'time': current_time})

                print(f"🚀 [طلب زبون فائق السرعة ومقبول]: {clean_text[:30]}...", flush=True)

                buttons = []
                row = []
                
                if message.from_user:
                    if message.from_user.username:
                        user_url = f"https://t.me/{message.from_user.username}"
                        user_label = f"💬 فتح المحادثة (@{message.from_user.username})"
                    else:
                        user_url = f"tg://openmessage?user_id={message.from_user.id}"
                        first_n = message.from_user.first_name or 'المستخدم'
                        user_label = f"💬 فتح المحادثة ({first_n[:10]})"
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
                            await bot.send_message(chat_id=user, text=clean_text, reply_markup=reply_markup, disable_web_page_preview=True)
                            sent = True
                        except Exception:
                            pass
                    if not sent:
                        try:
                            await userbot.send_message(chat_id=user, text=clean_text, reply_markup=reply_markup, disable_web_page_preview=True)
                        except Exception:
                            pass
        except Exception as e:
            print(f"⚠️ خطأ في معالجة الرسالة: {e}", flush=True)
        finally:
            message_queue.task_done()

# =========================================================
# 4. ULTRA-FAST POLLING KEEPER WITH FLOODWAIT HANDLING
# =========================================================

async def ultrafast_polling_keeper(userbot: Client, bot: Client):
    await asyncio.sleep(5)
    try:
        async for dialog in userbot.get_dialogs(limit=60):
            if dialog.chat and dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                KNOWN_CHAT_IDS.add(dialog.chat.id)
    except Exception:
        pass

    while True:
        if KNOWN_CHAT_IDS:
            for chat_id in list(KNOWN_CHAT_IDS):
                try:
                    async for msg in userbot.get_chat_history(chat_id=chat_id, limit=3):
                        await message_queue.put(msg)
                except FloodWait as e:
                    print(f"⚠️ تم رصد FloodWait لمدة {e.value} ثانية، جارٍ الانتظار...", flush=True)
                    await asyncio.sleep(e.value)
                except Exception:
                    pass
                await asyncio.sleep(0.5) # فاصل نصف ثانية فائق السرعة
        await asyncio.sleep(5.0)

# =========================================================
# 5. MAIN ENTRYPOINT
# =========================================================

async def main():
    init_db()
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
        await message_queue.put(message)

    await userbot.start()
    print("🚀 [Barq Ultra-Fast Safe Engine] يعمل بأقصى سرعة ومعالجة ذاتية للأخطاء!", flush=True)

    asyncio.create_task(message_worker(userbot, bot))
    asyncio.create_task(ultrafast_polling_keeper(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
