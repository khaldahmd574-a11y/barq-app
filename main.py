import os
import re
import time
import asyncio
import hashlib
import requests
from collections import OrderedDict
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait, RPCError


# =========================================================
# KEEP ALIVE SERVER 24/7 (RENDER PORT)
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Pure AI System Active!")

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

API_ID = int(
    os.environ.get(
        "TELEGRAM_API_ID",
        39120728
    )
)

API_HASH = os.environ.get(
    "TELEGRAM_API_HASH",
    ""
).strip()

BOT_TOKEN = os.environ.get(
    "BOT_TOKEN",
    ""
).strip()

OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    ""
).strip()


# =========================================================
# TARGET USERS
# =========================================================

TARGET_USERS = [
    "shaybq",
    "Waaaaaaa33",
    "abood1317",
    "Ndhhyfvvjkcd"
]


# =========================================================
# THREAD-SAFE ADVANCED DEDUPLICATION CACHE
# =========================================================

class TTLCache:
    """
    ذاكرة مؤقتة لمنع تكرار نفس الطلب.
    صلاحية البصمة 3 ساعات.
    """

    def __init__(self, ttl_seconds=10800, max_size=20000):
        self.ttl = ttl_seconds
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = None

    def initialize_lock(self):
        if self.lock is None:
            self.lock = asyncio.Lock()

    async def add_if_not_exists(self, key: str) -> bool:
        if self.lock is None:
            self.initialize_lock()

        async with self.lock:
            now = time.time()

            # تنظيف العناصر المنتهية
            while self.cache:
                first_key = next(iter(self.cache))
                first_expiry = self.cache[first_key]

                if first_expiry < now:
                    self.cache.popitem(last=False)
                else:
                    break

            # إذا كانت البصمة موجودة مسبقاً
            if key in self.cache:
                return False

            # حماية الذاكرة من التضخم
            if len(self.cache) >= self.max_size:
                self.cache.popitem(last=False)

            self.cache[key] = now + self.ttl

            return True


DEDUP_CACHE = TTLCache()

PROCESSING_LOCKS = set()
PROCESSING_LOCK = None


# =========================================================
# TEXT NORMALIZATION / FINGERPRINT
# =========================================================

def normalize_text_for_hash(text: str) -> str:
    """
    تطبيع النص لمنع التكرار الناتج عن اختلاف:
    - التشكيل
    - علامات الترقيم
    - المسافات
    - الأسطر
    """

    text = text.lower()

    # إزالة التشكيل العربي
    text = re.sub(r'[\u064B-\u0652]', '', text)

    # إزالة علامات الترقيم والرموز
    text = re.sub(r'[^\w\s]', '', text)

    # توحيد المسافات
    text = re.sub(r'\s+', ' ', text).strip()

    return text


def generate_text_fingerprint(text: str) -> str:
    normalized = normalize_text_for_hash(text)

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


# =========================================================
# OPENROUTER AI ANALYSIS ENGINE
# =========================================================

def analyze_with_pure_ai(text: str) -> str:
    """
    تحليل النص بواسطة OpenRouter.

    النتائج:
    YES   = طلب عميل
    NO    = ليس طلب عميل
    ERROR = فشل التحليل
    """

    if not OPENROUTER_API_KEY:
        print(
            "⚠️ [OpenRouter]: لم يتم ضبط OPENROUTER_API_KEY في Render!",
            flush=True
        )

        return "ERROR"

    prompt = f"""
أنت نظام ذكاء اصطناعي متخصص في تصنيف منشورات قروبات المشاوير والتوصيل في السعودية، وخاصة منطقة جازان والجنوب.

مهمتك هي فهم معنى المنشور وسياقه بالكامل، وتحديد هل كاتب الرسالة:

1. عميل أو زبون يبحث عن سائق أو مندوب أو توصيلة.
2. سائق أو مندوب يعرض خدماته.
3. رسالة سبام أو إعلان أو محتوى غير متعلق بطلبات العملاء.

========================================
إذا كان المنشور طلب عميل حقيقي:
========================================

أجب YES.

أمثلة:

"مين رايح من صبيا لجيزان؟"

"فيه أحد رايح أبو عريش؟"

"مين فاضي يوصلني الآن؟"

"أحتاج سواق للجامعة"

"محتاج أحد يوصل لي طلب"

"أبي مندوب يجيب لي غرض"

"مطلوب سواق دوامات"

"أحتاج أحد يوصلني من جيزان لصبيا"

"مين عنده مشوار من صامطة إلى جيزان؟"

وجود رقم جوال داخل رسالة العميل لا يجعلها إعلان سائق.

مثال:

"أحتاج سواق من صبيا لجيزان
05xxxxxxxx"

هذه رسالة عميل ويجب أن تكون YES.

========================================
إذا كان المنشور إعلان سائق أو مندوب:
========================================

أجب NO.

أمثلة:

"أنا متواجد في جيزان واللي يحتاج توصيل يكلمني"

"فاضي من صبيا إلى جيزان"

"متواجد 24 ساعة للتوصيل"

"عندي سيارة وأوصل مشاوير"

"طالع جازان اللي يبي يكلمني"

"أنا مندوب ومتواجد الآن"

"أي أحد يحتاج مشوار يكلمني"

"متوفر للتوصيل"

"الله يرزقنا ويرزقكم"

أي إعلان لخدمة السائق أو المندوب للجمهور = NO.

========================================
أيضاً:
========================================

الإعلانات العامة والسبام وعروض الوظائف والعملات الرقمية والمحتوى غير المرتبط بطلبات العملاء = NO.

لا تعتمد على كلمة واحدة فقط.

افهم معنى الرسالة كاملة وسياقها.

المطلوب تحديد دور كاتب الرسالة:

عميل يبحث عن خدمة = YES

سائق أو مندوب يعرض الخدمة = NO

سبام أو محتوى غير متعلق = NO

========================================
الرسالة المراد تحليلها:
========================================

{text}

========================================

أجب بكلمة واحدة فقط:

YES

أو

NO
"""

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0,
        "max_tokens": 5
    }

    retries = 3

    for attempt in range(retries):

        try:

            response = requests.post(
                url,
                headers=headers,
                json=payload,
                timeout=7
            )

            if response.status_code == 200:

                try:
                    data = response.json()

                    answer = (
                        data["choices"][0]["message"]["content"]
                        .strip()
                        .upper()
                    )

                except Exception as parse_error:

                    print(
                        f"⚠️ [OpenRouter]: تعذر قراءة الاستجابة -> {parse_error}",
                        flush=True
                    )

                    return "ERROR"

                print(
                    f"🤖 [OpenRouter AI]: نتيجة التحليل -> {answer}",
                    flush=True
                )

                if answer == "YES":
                    return "YES"

                elif answer == "NO":
                    return "NO"

                else:
                    print(
                        f"⚠️ [OpenRouter AI]: استجابة غير متوقعة -> {answer}",
                        flush=True
                    )

                    return "ERROR"

            elif response.status_code in [
                429,
                500,
                502,
                503,
                504
            ]:

                print(
                    f"⚠️ [OpenRouter AI]: خطأ مؤقت HTTP "
                    f"{response.status_code} "
                    f"- إعادة المحاولة "
                    f"({attempt + 1}/{retries})...",
                    flush=True
                )

                time.sleep(1)

            else:

                print(
                    f"⚠️ [OpenRouter AI]: خطأ HTTP "
                    f"{response.status_code}: "
                    f"{response.text}",
                    flush=True
                )

                return "ERROR"

        except Exception as e:

            print(
                f"⚠️ [OpenRouter AI]: استثناء أثناء الاتصال: "
                f"{e} "
                f"- محاولة ({attempt + 1}/{retries})",
                flush=True
            )

            time.sleep(1)

    return "ERROR"


# =========================================================
# SEND TO SUBSCRIBER
# =========================================================

async def send_to_subscriber(
    client_app: Client,
    user: str,
    text: str,
    reply_markup
):

    try:

        await client_app.send_message(
            chat_id=user,
            text=text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )

        print(
            f"✈️ [إرسال ناجح]: "
            f"تم إرسال الطلب للمشترك -> @{user}",
            flush=True
        )

    except FloodWait as e:

        print(
            f"⏳ [FloodWait]: "
            f"انتظار {e.value} ثانية للمشترك @{user}",
            flush=True
        )

        await asyncio.sleep(e.value)

        try:

            await client_app.send_message(
                chat_id=user,
                text=text,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )

            print(
                f"✈️ [إرسال ناجح بعد الانتظار]: @{user}",
                flush=True
            )

        except Exception as ex:

            print(
                f"❌ [فشل الإرسال بعد الانتظار]: "
                f"@{user} -> {ex}",
                flush=True
            )

    except Exception as e:

        print(
            f"❌ [فشل الإرسال]: "
            f"@{user} -> {e}",
            flush=True
        )


# =========================================================
# BROADCAST
# =========================================================

async def broadcast_to_subscribers(
    userbot: Client,
    bot: Client,
    text: str,
    reply_markup
):

    active_client = bot if bot else userbot

    tasks = []

    for user in TARGET_USERS:

        tasks.append(
            send_to_subscriber(
                active_client,
                user,
                text,
                reply_markup
            )
        )

    await asyncio.gather(
        *tasks,
        return_exceptions=True
    )


# =========================================================
# CORE MESSAGE PROCESSOR
# =========================================================

async def process_live_message(
    userbot: Client,
    bot: Client,
    message: Message,
    ai_semaphore
):

    if not message or not message.id:
        return

    # تجاهل رسائل الحساب نفسه
    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""

    clean_text = raw_text.strip()

    if len(clean_text) < 4:
        return

    # المفتاح الخاص بالرسالة
    unique_msg_id = (
        f"{message.chat.id}_{message.id}"
    )

    # بصمة النص
    text_fingerprint = generate_text_fingerprint(
        clean_text
    )

    # منع معالجة نفس الرسالة مرتين في نفس اللحظة
    async with PROCESSING_LOCK:

        if (
            unique_msg_id in PROCESSING_LOCKS
            or text_fingerprint in PROCESSING_LOCKS
        ):
            return

        PROCESSING_LOCKS.add(unique_msg_id)
        PROCESSING_LOCKS.add(text_fingerprint)

    try:

        sender_info = (
            f"@{message.from_user.username}"
            if (
                message.from_user
                and message.from_user.username
            )
            else (
                f"ID: {message.from_user.id}"
                if message.from_user
                else "مجهول"
            )
        )

        print(
            f"📩 [رسالة جديدة]: "
            f"من ({sender_info}) | "
            f"النص: '{clean_text[:60]}...'",
            flush=True
        )

        # =================================================
        # AI RETRY SYSTEM
        # =================================================

        ai_result = "ERROR"

        max_ai_attempts = 3

        for ai_attempt in range(max_ai_attempts):

            async with ai_semaphore:

                loop = asyncio.get_running_loop()

                ai_result = await loop.run_in_executor(
                    None,
                    analyze_with_pure_ai,
                    clean_text
                )

            if ai_result in ["YES", "NO"]:
                break

            if ai_result == "ERROR":

                if ai_attempt < max_ai_attempts - 1:

                    print(
                        f"🔄 [إعادة تحليل]: "
                        f"فشل تحليل الرسالة، "
                        f"إعادة المحاولة "
                        f"({ai_attempt + 2}/{max_ai_attempts})...",
                        flush=True
                    )

                    await asyncio.sleep(1)

        # =================================================
        # YES
        # =================================================

        if ai_result == "YES":

            # التكرار يسجل فقط بعد YES
            if not await DEDUP_CACHE.add_if_not_exists(
                text_fingerprint
            ):

                print(
                    "🛑 [منع التكرار]: "
                    "الطلب مقبول لكنه مكرر، تم تجاهله.",
                    flush=True
                )

                return

            print(
                "✅ [قبول الطلب]: "
                "تم التعرف على طلب عميل -> "
                "جاري الإرسال للمشتركين...",
                flush=True
            )

            buttons = []
            row = []

            # =================================================
            # BUTTON 1: OPEN CHAT
            # =================================================

            if message.from_user:

                if message.from_user.username:

                    user_url = (
                        f"https://t.me/"
                        f"{message.from_user.username}"
                    )

                    user_label = (
                        "💬 فتح المحادثة "
                        f"(@{message.from_user.username})"
                    )

                else:

                    user_url = (
                        "tg://openmessage?user_id="
                        f"{message.from_user.id}"
                    )

                    user_label = (
                        "💬 فتح المحادثة "
                        f"({message.from_user.first_name or 'المستخدم'})"
                    )

                row.append(
                    InlineKeyboardButton(
                        user_label,
                        url=user_url
                    )
                )

            # =================================================
            # BUTTON 2: ORIGINAL MESSAGE
            # =================================================

            if message.link:

                row.append(
                    InlineKeyboardButton(
                        "📩 الرسالة الأصلية",
                        url=message.link
                    )
                )

            if row:

                buttons.append(row)

            reply_markup = (
                InlineKeyboardMarkup(buttons)
                if buttons
                else None
            )

            # =================================================
            # إرسال النص الأصلي فقط
            # بدون اسم القروب
            # بدون المصدر
            # =================================================

            await broadcast_to_subscribers(
                userbot,
                bot,
                clean_text,
                reply_markup
            )

        # =================================================
        # NO
        # =================================================

        elif ai_result == "NO":

            print(
                "🚫 [رفض الطلب]: "
                "تم التصنيف كسائق/مندوب/سبام/غير متعلق.",
                flush=True
            )

        # =================================================
        # ERROR AFTER ALL RETRIES
        # =================================================

        else:

            print(
                "⚠️ [فشل التحليل]: "
                "تعذر تحليل الرسالة بعد جميع المحاولات. "
                "لن يتم إرسالها ولن تسجل كتكرار.",
                flush=True
            )

    finally:

        async with PROCESSING_LOCK:

            PROCESSING_LOCKS.discard(
                unique_msg_id
            )

            PROCESSING_LOCKS.discard(
                text_fingerprint
            )


# =========================================================
# BACKGROUND COMPREHENSIVE SCANNER
# =========================================================

async def background_dialog_poller(
    userbot: Client,
    bot: Client,
    ai_semaphore
):

    await asyncio.sleep(15)

    while True:

        try:

            async for dialog in userbot.get_dialogs():

                if (
                    dialog.chat
                    and dialog.chat.type
                    in ["group", "supergroup"]
                ):

                    try:

                        async for msg in userbot.get_chat_history(
                            dialog.chat.id,
                            limit=1
                        ):

                            await process_live_message(
                                userbot,
                                bot,
                                msg,
                                ai_semaphore
                            )

                    except RPCError as e:

                        print(
                            f"⚠️ [الفاحص الاحتياطي]: "
                            f"Telegram RPC Error -> {e}",
                            flush=True
                        )

                        await asyncio.sleep(2)

                    except Exception:
                        continue

                    # تخفيف الضغط على Telegram
                    await asyncio.sleep(0.5)

        except Exception as e:

            print(
                f"⚠️ [الفاحص الاحتياطي]: "
                f"خطأ أثناء الفحص -> {e}",
                flush=True
            )

        # دورة احتياطية كل 30 ثانية
        await asyncio.sleep(30)


# =========================================================
# MAIN
# =========================================================

async def main():

    global PROCESSING_LOCK

    # =====================================================
    # إنشاء الـ Locks داخل حلقة asyncio
    # =====================================================

    PROCESSING_LOCK = asyncio.Lock()

    DEDUP_CACHE.initialize_lock()

    # =====================================================
    # Semaphore داخل event loop
    # =====================================================

    MAX_CONCURRENT_AI_REQUESTS = 10

    ai_semaphore = asyncio.Semaphore(
        MAX_CONCURRENT_AI_REQUESTS
    )

    # =====================================================
    # KEEP ALIVE
    # =====================================================

    threading.Thread(
        target=run_dummy_server,
        daemon=True
    ).start()

    print(
        "🌐 [Keep Alive]: "
        "تم تشغيل خادم Render بنجاح.",
        flush=True
    )

    # =====================================================
    # USERBOT
    # =====================================================

    userbot = Client(
        "my_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    # =====================================================
    # HELPER BOT
    # =====================================================

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

            print(
                "🤖 [البوت المساعد]: "
                "تم التشغيل بنجاح للإرسال.",
                flush=True
            )

        except Exception as e:

            print(
                "⚠️ [البوت المساعد]: "
                f"تعذر التشغيل، سيتم استخدام Userbot -> {e}",
                flush=True
            )

            bot = None

    # =====================================================
    # LIVE LISTENER
    # =====================================================

    @userbot.on_message(
        filters.group | filters.channel
    )
    async def global_live_listener(
        client: Client,
        message: Message
    ):

        asyncio.create_task(
            process_live_message(
                client,
                bot,
                message,
                ai_semaphore
            )
        )

    # =====================================================
    # START USERBOT
    # =====================================================

    await userbot.start()

    print(
        "🚀 [نظام برق الذكي]: "
        "تم بدء المراقبة اللحظية الشاملة "
        "للقروبات بنجاح!",
        flush=True
    )

    # =====================================================
    # BACKGROUND SCANNER
    # =====================================================

    asyncio.create_task(
        background_dialog_poller(
            userbot,
            bot,
            ai_semaphore
        )
    )

    print(
        "🔎 [الفاحص الاحتياطي]: "
        "تم تشغيل الفحص الاحتياطي كل 30 ثانية.",
        flush=True
    )

    # =====================================================
    # KEEP APPLICATION ALIVE
    # =====================================================

    await asyncio.Event().wait()


# =========================================================
# START APPLICATION
# =========================================================

if __name__ == "__main__":
    asyncio.run(main())
