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

# حسابك المستهدف الذي سيستقبل الرسائل من البوت المساعد
TARGET_USERS = ["abood1317"]

PROCESSED_KEYS = set()
USER_REQUEST_HISTORY = {} 
MIN_TIME_BETWEEN_REPEATS = 600   # 10 دقائق منع تكرار نفس الطلب
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

    prompt = f"""أنت ذكاء اصطناعي محترف مخصص لقروبات التوصيل والمشاوير بجازان والجنوب.
مهمتك: هل الرسالة من [زبون يبحث عن سائق/مندوب/توصيل/أغراض] أم [سائق يعلن عن نفسه]؟

[زبون/عميل يبحث أو يستفسر -> YES]
- مثل: "مين في صبيا؟"، "فيه احد قريب من أنوش جيزان؟"، "احتاج مندوب"، "سواق يوصل دوام" -> YES

[سائق يعلن عن خدماته -> NO]
- مثل: "أنا فاضي جاهز للمشاوير"، "متواجد بضمد حياك خاص"، الإعلانات التي فيها أرقام جوالات للتوصيل -> NO

الرسالة المراد تحليلها:
"{clean}"
الجواب بكلمة واحدة فقط: (YES) أو (NO):"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        payload = {
            "model": "openai/gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 2
        }
        res = requests.post(url, headers=headers, json=payload, timeout=4)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [الذكاء الاصطناعي]: '{clean[:30]}...' -> {answer}", flush=True)
            return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ بالاتصال: {e}", flush=True)

    return False

async def process_live_message(userbot: Client, bot: Client, message: Message):
    try:
        if not message or not message.id or not message.chat:
            return
        if message.chat.type == ChatType.PRIVATE:
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

            print(f"✅ [تم سحب طلب زبون وإرساله للبوت المساعد]: {clean_text[:30]}...", flush=True)

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

            # إرسال الطلب عبر البوت المساعد (Bot Token) إلى حسابك
            if bot:
                for user in TARGET_USERS:
                    try:
                        await bot.send_message(
                            chat_id=user, 
                            text=f"📥 طلب جديد:\n\n{clean_text}", 
                            reply_markup=reply_markup, 
                            disable_web_page_preview=True
                        )
                    except Exception as e:
                        print(f"⚠️ خطأ إرسال البوت المساعد: {e}", flush=True)
    except Exception:
        pass

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client("barq_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
    
    bot = None
    if BOT_TOKEN:
        try:
            bot = Client("barq_helper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
            await bot.start()
            print("🤖 [البوت المساعد متصل بنجاح]", flush=True)
        except Exception as e:
            print(f"⚠️ خطأ تشغيل البوت المساعد: {e}", flush=True)

    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        asyncio.create_task(process_live_message(client, bot, message))

    await userbot.start()
    print("🚀 [برق الشامل يعمل]: اليوزربوت يراقب القروبات ويسحب، والبوت المساعد يوصلك الطلبات!", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
