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
        self.wfile.write(b"Barq System Active!")

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

TARGET_USERS = ["abood1317"]

PROCESSED_KEYS = set()
KNOWN_CHAT_IDS = set()

USER_REQUEST_HISTORY = {} 
MIN_TIME_BETWEEN_REPEATS = 600   # 10 دقائق منع التكرار
SIMILARITY_THRESHOLD = 0.65       

def is_similar_text(text1: str, text2: str) -> bool:
    clean1 = re.sub(r'[^\w\s]', '', text1.lower()).strip()
    clean2 = re.sub(r'[^\w\s]', '', text2.lower()).strip()
    ratio = SequenceMatcher(None, clean1, clean2).ratio()
    return ratio >= SIMILARITY_THRESHOLD

def analyze_intent_with_ai(text: str) -> bool:
    clean = " ".join(text.split()).strip()
    if not clean or len(clean) < 2 or not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت عقل ذكاء اصطناعي مخصص لقروبات التوصيل والمشاوير بجازان.
هل الرسالة من [زبون يبحث عن سائق/مندوب/توصيل] أم [سائق يعلن عن نفسه]؟

[زبون يبحث أو يستفسر -> YES]
- مثل: "في حد في ضمد؟"، "فيه احد قريب من أنوش؟"، "احتاج مندوب"، "سواق يوصل دوام" -> YES

[سائق يعلن عن خدماته -> NO]
- مثل: "أنا فاضي للمشاوير"، "متواجد بضمد حياك خاص" -> NO

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
            print(f"🤖 [AI]: '{clean[:30]}...' -> {answer}", flush=True)
            return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ AI: {e}", flush=True)

    return False

async def process_message_logic(userbot: Client, bot: Client, message: Message):
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
        if len(clean_text) < 2:
            return

        msg_key = f"{message.chat.id}_{message.id}"
        text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
        
        if msg_key in PROCESSED_KEYS or text_hash in PROCESSED_KEYS:
            return

        current_time = time.time()
        user_id = message.from_user.id if message.from_user else None

        if user_id and user_id in USER_REQUEST_HISTORY:
            for past in USER_REQUEST_HISTORY[user_id]:
                if is_similar_text(clean_text, past['text']):
                    if (current_time - past['time']) < MIN_TIME_BETWEEN_REPEATS:
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

            print(f"✅ [تم سحب وإرسال طلب]: {clean_text[:30]}...", flush=True)

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

            for user in TARGET_USERS:
                try:
                    if bot:
                        await bot.send_message(
                            chat_id=user,
                            text=clean_text,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )
                    else:
                        await userbot.send_message(
                            chat_id=user,
                            text=clean_text,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )
                except Exception as e:
                    print(f"⚠️ خطأ في الإرسال للمستلم: {e}", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ في المعالجة: {e}", flush=True)

# حلقة سحب شاملة ومضمونة تفحص كافة المجموعات والقروبات المسجلة والجديدة
async def robust_global_scanner(userbot: Client, bot: Client):
    await asyncio.sleep(3)
    
    # محاولة جلب المجموعات عبر الاستعلام المباشر من الـ Dialogs
    try:
        async for dialog in userbot.get_dialogs():
            if dialog.chat and dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                KNOWN_CHAT_IDS.add(dialog.chat.id)
        print(f"🔄 [تم جلب وتحميل {len(KNOWN_CHAT_IDS)} قروب ومجموعة بنجاح تام]", flush=True)
    except Exception as e:
        print(f"⚠️ تحذير في جلب المحادثات: {e}", flush=True)

    while True:
        try:
            # تحديث دوري للقروبات كل فترة لضمان عدم تفويت أي قروب جديد
            async for dialog in userbot.get_dialogs(limit=150):
                if dialog.chat and dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                    KNOWN_CHAT_IDS.add(dialog.chat.id)
        except Exception:
            pass

        if KNOWN_CHAT_IDS:
            for chat_id in list(KNOWN_CHAT_IDS):
                try:
                    async for msg in userbot.get_chat_history(chat_id=chat_id, limit=3):
                        await process_message_logic(userbot, bot, msg)
                    await asyncio.sleep(0.05)
                except Exception:
                    continue
        await asyncio.sleep(2)

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "barq_fixed_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING
    )

    bot = None
    if BOT_TOKEN:
        try:
            bot = Client(
                "barq_fixed_helper",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN
            )
            await bot.start()
            print("🤖 [البوت المساعد يعمل بنجاح]", flush=True)
        except Exception as e:
            print(f"⚠️ خطأ في البوت المساعد: {e}", flush=True)

    @userbot.on_message()
    async def live_event_handler(client: Client, message: Message):
        asyncio.create_task(process_message_logic(client, bot, message))

    await userbot.start()
    print("🚀 [نظام برق يعمل الآن بكامل طاقته لسحب جميع القروبات]...", flush=True)

    asyncio.create_task(robust_global_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
