import os
import re
import time
import asyncio
import hashlib
import httpx
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

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "Ndhhyfvvjkcd", "fs_990"]

PROCESSED_KEYS = set()
KNOWN_CHAT_IDS = set()

# ذاكرة تتبع طلبات العضو لمنع التكرار (10 دقائق)
USER_REQUEST_HISTORY = {} 
MIN_TIME_BETWEEN_REPEATS = 600   # 10 دقائق (600 ثانية)
SIMILARITY_THRESHOLD = 0.65       # نسبة التشابه النصي 65%

# عميل الاتصال بالسيرفر مع زيادة زمن المهلة إلى 6 ثوانٍ لضمان عدم ضياع الطلبات
HTTP_CLIENT = httpx.AsyncClient(timeout=6.0)

# =========================================================
# HELPER: SMART TEXT SIMILARITY
# =========================================================

def is_similar_text(text1: str, text2: str) -> bool:
    clean1 = re.sub(r'[^\w\s]', '', text1.lower()).strip()
    clean2 = re.sub(r'[^\w\s]', '', text2.lower()).strip()
    ratio = SequenceMatcher(None, clean1, clean2).ratio()
    return ratio >= SIMILARITY_THRESHOLD

# =========================================================
# ASYNC AI ENGINE (تحليل النية الشامل)
# =========================================================

async def analyze_intent_with_ai(text: str) -> bool:
    clean = text.strip()
    
    if not clean or len(clean) < 2:
        return False

    if clean.lower() in ["سلام", "السلام عليكم", "مرحبا", "هلا", "صباح الخير", "مساء الخير", "الو"]:
        return False

    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت عقل ذكاء اصطناعي محترف متخصص في فهم نيات النصوص لقروبات التوصيل والمشاوير بالسعودية (منطقة جازان والجنوب).

مهمتك الوحيدة: تحليل "نية الكاتب" الحقيقية والتمييز بدقة فائقة بين الزبون والسائق:

[الصنف الأول: زبون/عميل يبحث أو يطلب -> أجب بـ YES]
قبول أي نص يُفهم منه أن الكاتب زبون يبحث عن خدمة/سائق/مندوب/توصيلة/نقل أغراض أو طلبيات:
1. طلبات توصيل الطلبيات والأغراض: "ابغا مندوب ثقه ياخذ طلبيتي من ابوعريش للعارضه وبسعر كويس" -> YES.
2. الأسئلة والاستفسارات: "مين فاضي الان في جيزان؟ يتواصل معايا خاص" -> YES.
3. الطلبات الموجزة: "مندوب في ضمد"، "توصيل ضمد"، "سواق صامطة"، "ابي مندوب"، "في سواقات شهري ؟؟".
4. مشاوير ودوامات: "ابغا مشوار من صبيا"، "احتاج سواقه لمدرسة".

[الصنف الثاني: سائق يعرض خدمته وتوفره -> أجب بـ NO]
رفض أي نص يُفهم منه أن الكاتب هو السائق الذي يعلن عن توفره لنقل الناس أو البضائع:
1. إعلانات التوفر من السائق: "موجود في صامطه اي مشوار خاص"، "أنا فاضي جاهز للمشاوير"، "متواجد"، "متحرك".
2. نصوص تحتوي على أرقام جوال أو تسويق خدمات: "توصيل دوامات 055XXXXXXX".
3. سلام عابر بدون طلب.

الرسالة المراد تحليل نيتها:
"{clean}"

الجواب كلمة واحدة فقط لا غير: (YES) أو (NO):"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
        "max_tokens": 2
    }

    try:
        res = await HTTP_CLIENT.post(url, headers=headers, json=payload)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [استجابة النية]: '{clean[:30]}...' -> {answer}", flush=True)
            return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ في الاتصال بالذكاء الاصطناعي: {e}", flush=True)

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

        # 1. منع تكرار نفس الرسالة المباشرة
        msg_key = f"{message.chat.id}_{message.id}"
        text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
        
        if msg_key in PROCESSED_KEYS or text_hash in PROCESSED_KEYS:
            return

        current_time = time.time()
        user_id = message.from_user.id if message.from_user else None

        # 2. فحص التكرار الذكي (10 دقائق)
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

        # 3. التحليل بالذكاء الاصطناعي
        is_client_request = await analyze_intent_with_ai(clean_text)

        if is_client_request:
            if user_id:
                if user_id not in USER_REQUEST_HISTORY:
                    USER_REQUEST_HISTORY[user_id] = []
                USER_REQUEST_HISTORY[user_id].append({'text': clean_text, 'time': current_time})

            print(f"✅ [تم السحب بنجاح]: {clean_text[:30]}...", flush=True)

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
# BACKGROUND SCANNER (ماسح احتياطي آمن)
# =========================================================

async def direct_chat_history_scanner(userbot: Client, bot: Client):
    await asyncio.sleep(2)
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
        await asyncio.sleep(1)

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
    print("🚀 تم تشغيل النظام المحدث مع دعم كامل لطلبات نقل الطلبيات والأغراض!", flush=True)

    asyncio.create_task(direct_chat_history_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
