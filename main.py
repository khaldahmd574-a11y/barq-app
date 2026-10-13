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
        self.wfile.write(b"Barq Mega Master AI System Active!")

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

TARGET_USERS = ["abood1317", "Waaaaaaa33", "shaybq", "Ndhhyfvvjkcd", "fs_990"]

PROCESSED_KEYS = set()
KNOWN_CHAT_IDS = set()

USER_REQUEST_HISTORY = {} 
MIN_TIME_BETWEEN_REPEATS = 600   # 10 دقائق بالثواني
SIMILARITY_THRESHOLD = 0.65       # نسبة التشابه النصي

# =========================================================
# HELPER: SMART TEXT SIMILARITY
# =========================================================

def is_similar_text(text1: str, text2: str) -> bool:
    clean1 = re.sub(r'[^\w\s]', '', text1.lower()).strip()
    clean2 = re.sub(r'[^\w\s]', '', text2.lower()).strip()
    
    ratio = SequenceMatcher(None, clean1, clean2).ratio()
    return ratio >= SIMILARITY_THRESHOLD

# =========================================================
# PURE INTENT AI ENGINE
# =========================================================

def analyze_intent_with_ai(text: str) -> bool:
    clean = text.strip()
    
    # 🛑 رفض قاطع للرسائل القليلة الحروف أو الرموز والنقاط المكررة
    if not clean or len(clean) < 4:
        return False

    # إذا كانت الرسالة عبارة عن نقاط أو رموز فقط بدون كلمات حقيقية
    if not re.search(r'[\u0600-\u06FFa-zA-Z]', clean):
        return False

    if clean.lower() in ["سلام", "السلام عليكم", "مرحبا", "هلا", "صباح الخير", "مساء الخير", "الو"]:
        return False

    lower_clean = clean.lower()

    # 🛑 القائمة السوداء الشاملة والمشددة (حظر السائقين، السائقات، المناديب، السطحات، المعلمين)
    blacklist_patterns = [
        "فاضي في", "فاضي بـ", "فاضي ب", "فاضية في", "فاضيه في", "فاضية بـ", "فاضيه بـ",
        "متوفر الان", "متوفر الآن", "متوفرة الان", "متوفره الان", "موجود الان", "موجودة الان", "موجوده الان",
        "شغال الان", "شغالة الان", "شغاله الان", "جاهز للطلب", "جاهزة للطلب", "جاهزه للطلب",
        "جاهز للمشوار", "جاهزة للمشوار", "جاهزه للمشوار", "جاهز للتوصيل", "جاهزة للتوصيل", "جاهزه للتوصيل",
        "موجود في صبيا", "موجودة في صبيا", "موجود في جيزان", "موجودة في جيزان", "موجود في صامطة",
        "موجود في ابو عريش", "موجود في ضمد", "متواجد في", "متواجدة في", "أنا سواقة", "انا سواقه",
        "طالع من", "طالعة من", "نازل من", "نازلة من", "اللي يبي مشوار", "اللي تبي مشوار",
        "تواصل خاص", "تعال خاص", "تعالي خاص", "تواصلين خاص", "تواصل معي", "تواصل معي خاص",
        "تواصل واتس", "تواصل واتساب", "اسعار مناسبة", "بأسعار مناسبة", "خدمة ممتازة", "سيارات حديثة",
        "توصيل طلبات", "توصيل شحنات", "مندوب توصيل", "مندوبة توصيل", "مندوب جاهز", "نوفر نقل",
        "نوفر سواقات", "نوفر سائقات", "يوجد لدينا سواقات", "سيارة خاصة", "سياره خاصه",
        "اللي يحتاج نقل", "الي يحتاج نقل", "يتوفر لدينا", "نوفر لكم", "خدمة توصيل",
        "نقل معلمات", "نقل طالبات", "نقل موظفات", "نقل طلاب",
        "سطحة", "سطحه", "نقل سيارات", "تعطلت", "اتصل نصل", "ورشة", "ميكانيكي",
        "معلم", "معلمة", "مدرس", "درسة", "تدريس خصوصي", "مدرسة أهلية", "تأسيس ومتابعة", "باكالريوس تربية", "أبحث عن تدريس"
    ]

    if any(bad in lower_clean for bad in blacklist_patterns):
        print(f"🛑 [حظر فوري - إعلان/خدمة]: '{clean[:35]}...'", flush=True)
        return False

    # ✅ قاعدة بيانات ضخمة جداً (أكثر من 50+ عبارة وصيغة طلب حقيقية للمشاوير والمناديب)
    forced_phrases = [
        "ابي مندوب", "ابغا مندوب", "أبي مندوب", "أبغا مندوب", "ابغى مندوب", "أبغى مندوب", 
        "محتاج مندوب", "محتاجة مندوب", "محتاجه مندوب", "مطلوب مندوب",
        "ابي سواق", "ابغا سواق", "أبي سواق", "أبغا سواق", "ابغى سواق", "أبغى سواق", 
        "محتاج سواق", "محتاجة سواق", "محتاجه سواق", "مطلوب سواق",
        "ابي سواقة", "ابغا سواقة", "أبي سواقة", "أبغا سواقة", "ابغى سواقة", "أبغى سواقة", 
        "محتاجة سواقة", "محتاجه سواقه", "مطلوب سواقة", "مطلوب سواقه",
        "ابي توصيل", "ابغا توصيل", "أبي توصيل", "أبغا توصيل", "ابغى توصيل", "أبغى توصيل",
        "ابي مشوار", "ابغا مشوار", "أبي مشوار", "أبغا مشوار", "ابغى مشوار", "أبغى مشوار",
        "محتاج مشوار", "محتاجة مشوار", "محتاجه مشوار", "احتاج مشوار", "أحتاج مشوار",
        "محتاج توصيل", "محتاجة توصيل", "محتاجه توصيل", "محتاج توصيلة", "محتاجة توصيلة", "محتاجه توصيله",
        "محتاج سيارة", "محتاجة سيارة", "محتاجه سياره", "محتاج سياره",
        "في مندوب", "فيه مندوب", "في مندوبة", "فيه مندوبة", "في مندوبه", "فيه مندوبه",
        "في سواق", "فيه سواق", "في سواقة", "فيه سواقة", "في سواقه", "فيه سواقه",
        "في سائق", "فيه سائق", "في سائقة", "فيه سائقة",
        "هل فيه", "هل في", "فيه أحد", "في احد", "فيه احد", "هل يوجد",
        "في توصيل", "فيه توصيل", "في مشوار", "فيه مشوار",
        "مين يوديني", "من يوديني", "مين يوصلني", "من يوصلني", "مين توديني", "مين توصلني",
        "مين يوصل", "من يوصل", "مين يقدر", "من يقدر", "مين يساعدني", "من يساعدني",
        "مين فاضي", "من فاضي", "منهو فاضي", "منوه فاضي", "مين فاضية", "مين فاضيه",
        "مين يخلص", "من يخلص", "مين يقضي", "من يقضي", "مين يجيب", "من يجيب",
        "أدور توصيل", "ادور توصيل", "ابحث عن توصيل", "أبحث عن توصيل", 
        "ابحث عن سواق", "ابحث عن سواقة", "ابحث عن مندوب", "أدور سواق", "ادور سواق",
        "حد يوصل", "أحد يوصل", "احد يوصل", "حد يودي", "أحد يودي", "احد يودي",
        "حد يقدر", "أحد يقدر", "احد يقدر", "حد يخلص", "أحد يخلص", "احد يخلص",
        "توصيل من", "توصيله من", "مشوار من", "مشوار الى", "مشوار لـ", "مشوار ل",
        "توصيل لـ", "توصيل ل", "توصيل الى", "توصيلة لـ", "توصيله لـ",
        "أبغى أروح", "ابغى اروح", "ابي أروح", "ابي اروح", "ابغا أروح", "ابغا اروح",
        "محتاج أروح", "محتاج اروح", "محتاجة أروح", "محتاجة اروح",
        "مشوار سريع", "توصيل سريع", "مشوار ضروري", "توصوري ضروري",
        "مشوار للمطار", "توصيل للمطار", "رايح المطار", "ابغا المطار", "ابي المطار",
        "مشوار للجامعة", "توصيل للجامعة", "مشوار للكلية", "توصيل للكلية",
        "توصيل اغراض", "توصيل أغراض", "قضاء حوائج", "قضاء حاجة", "توصيل طلب",
        "مين يروح", "من يروح", "فيه احد يروح", "في احد يروح"
    ]

    if any(phrase in lower_clean for phrase in forced_phrases):
        print(f"⚡ [قبول سريع - طلب مؤكد]: '{clean[:35]}...'", flush=True)
        return True

    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت عقل ذكاء اصطناعي محترف وصارم جداً متخصص في فرز رسائل قروبات التوصيل والمشاوير بالسعودية (منطقة جازان والجنوب).

مهمتك: التمييز بدقة قاطعة بين (الزبون الطالب للخدمة) و(أي رسائل أخرى مثل نقاط، رموز، إعلانات، توفر سائقين):

[الصنف الأول: زبون/عميل يبحث أو يطلب توصيل أو مشوار لنفسه حصرياً -> أجب بـ YES]
قبول أي طلب أو استفسار شخصي واضح يطلبه صاحب الرسالة لنفسه فقط:
1. الأسئلة والاستفسارات: "في مندوب بالشقيق الحين؟", "مين فاضي لتوصيل مشوار؟".
2. طلبات المشاوير والمناديب المباشرة: "معايا وصفه ابغا اصرفها من صيدليه والموقع البيت صبيا", "ابغى سواق داخل أبوعريش يوصل مشاوير", "في مندوب يوصل من شورمر لكليه الطب؟".

[الصنف الثاني: رسائل رموز، نقاط، إعلانات سطحات، سائقين، معلمين -> أجب بـ NO قطعي]
رفض قاطع لأي رسالة قصيرة غير مفهومة مثل (..) أو رموز تعبيرية فقط، أو إعلانات السائقين المعروضة.

الرسالة المراد تحليل نيتها:
"{clean}"

الجواب كلمة واحدة فقط لا غير: (YES) أو (NO):"""

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
        res = requests.post(url, headers=headers, json=payload, timeout=2)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [تحليل الذكاء الاصطناعي]: '{clean[:35]}...' -> {answer}", flush=True)
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
        
        # 🛑 حد أدنى 4 أحرف لمنع سحب النقاط ".." والرموز
        if len(clean_text) < 4:
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

            print(f"✅ [طلب زبون مقبول]: {clean_text[:30]}...", flush=True)

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
# TARGETED GROUP HISTORY SCANNER (Safe & Smooth Polling)
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
                # تأخير آمن بين كل قروب وآخر لمنع قيود تليجرام
                await asyncio.sleep(0.5)
        
        # فاصل زمني آمن بين دورات الماسح الخلفي
        await asyncio.sleep(2.0)

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
    print("🚀 تم تشغيل النظام الماستر مع الحماية الكاملة من قيود الانتظار!", flush=True)

    asyncio.create_task(direct_chat_history_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
