import os
import re
import time
import asyncio
import hashlib
import requests
import json
import base64
from collections import OrderedDict
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait, RPCError


# =========================================================
# KEEP ALIVE SERVER 24/7 - RENDER
# =========================================================

class DummyServer(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()

        self.wfile.write(
            b"Barq Pure AI System Active!"
        )

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()


def run_dummy_server():

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        DummyServer
    )

    server.serve_forever()


# =========================================================
# CONFIGURATION
# =========================================================

SESSION_STRING = os.environ.get(
    "SESSION_STRING",
    ""
).strip()


API_ID = int(
    os.environ.get(
        "TELEGRAM_API_ID",
        0
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
# TARGET SUBSCRIBERS
# =========================================================

TARGET_USERS = [
    "shaybq",
    "Waaaaaaa33",
    "abood1317",
    "Ndhhyfvvjkcd"
]


# =========================================================
# AI SETTINGS
# =========================================================

MAX_CONCURRENT_AI_REQUESTS = 10


# =========================================================
# DEDUPLICATION CACHE
# =========================================================

class TTLCache:

    def __init__(
        self,
        ttl_seconds=10800,
        max_size=20000
    ):

        self.ttl = ttl_seconds
        self.max_size = max_size

        self.cache = OrderedDict()

        self.lock = None


    def initialize_lock(self):

        if self.lock is None:
            self.lock = asyncio.Lock()


    async def add_if_not_exists(
        self,
        key: str
    ) -> bool:

        if self.lock is None:
            self.initialize_lock()


        async with self.lock:

            now = time.time()


            while self.cache:

                first_key = next(
                    iter(self.cache)
                )

                first_expiry = self.cache[
                    first_key
                ]

                if first_expiry < now:

                    self.cache.popitem(
                        last=False
                    )

                else:

                    break


            if key in self.cache:
                return False


            if len(self.cache) >= self.max_size:

                self.cache.popitem(
                    last=False
                )


            self.cache[key] = (
                now + self.ttl
            )

            return True


DEDUP_CACHE = TTLCache()


# =========================================================
# PROCESSING LOCK
# =========================================================

PROCESSING_LOCKS = set()

PROCESSING_LOCK = None


# =========================================================
# TEXT NORMALIZATION
# =========================================================

def normalize_text_for_hash(
    text: str
) -> str:

    text = text.lower()


    text = re.sub(
        r'[\u064B-\u0652]',
        '',
        text
    )


    text = re.sub(
        r'[^\w\s]',
        '',
        text
    )


    text = re.sub(
        r'\s+',
        ' ',
        text
    ).strip()


    return text


# =========================================================
# TEXT FINGERPRINT
# =========================================================

def generate_text_fingerprint(
    text: str
) -> str:

    normalized = (
        normalize_text_for_hash(
            text
        )
    )

    return hashlib.sha256(
        normalized.encode(
            "utf-8"
        )
    ).hexdigest()


# =========================================================
# OPENROUTER AI
# =========================================================

def analyze_with_pure_ai(
    text: str
) -> str:

    if not OPENROUTER_API_KEY:

        print(
            "⚠️ [OpenRouter]: "
            "OPENROUTER_API_KEY غير موجود.",
            flush=True
        )

        return "ERROR"


    prompt = f"""
أنت نظام ذكاء اصطناعي متخصص في تصنيف منشورات قروبات المشاوير والتوصيل في السعودية، وخاصة منطقة جازان والجنوب.

مهمتك فهم معنى المنشور كاملاً وتحديد هل الكاتب عميل يحتاج خدمة أم سائق/مندوب يعرض خدمة.

========================================
طلب عميل = YES
========================================

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

وجود رقم الجوال داخل طلب العميل لا يجعله إعلان سائق.

مثال:

"أحتاج سواق من صبيا لجيزان
05xxxxxxxx"

= YES

========================================
سائق أو مندوب يعرض خدمة = NO
========================================

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

========================================
محتوى غير متعلق = NO
========================================

الإعلانات العامة والسبام وعروض الوظائف والعملات الرقمية وأي محتوى غير متعلق بطلبات العملاء = NO.

لا تعتمد على كلمة واحدة.

افهم معنى الرسالة كاملة.

عميل يبحث عن خدمة = YES

سائق أو مندوب يعرض الخدمة = NO

سبام أو محتوى غير متعلق = NO

========================================
الرسالة:
========================================

{text}

========================================

أجب بكلمة واحدة فقط:

YES

أو

NO
"""


    url = (
        "https://openrouter.ai/"
        "api/v1/chat/completions"
    )


    headers = {

        "Authorization":
            f"Bearer {OPENROUTER_API_KEY}",

        "Content-Type":
            "application/json"
    }


    payload = {

        "model":
            "openai/gpt-4o-mini",

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


    for attempt in range(
        retries
    ):

        try:

            response = requests.post(

                url,

                headers=headers,

                json=payload,

                timeout=7
            )


            if response.status_code == 200:

                try:

                    data = (
                        response.json()
                    )

                    answer = (
                        data[
                            "choices"
                        ][0][
                            "message"
                        ][
                            "content"
                        ]
                        .strip()
                        .upper()
                    )

                except Exception as e:

                    print(
                        "⚠️ [OpenRouter]: "
                        f"خطأ قراءة الاستجابة -> {e}",
                        flush=True
                    )

                    return "ERROR"


                print(
                    "🤖 [OpenRouter AI]: "
                    f"{answer}",
                    flush=True
                )


                if answer == "YES":
                    return "YES"


                if answer == "NO":
                    return "NO"


                return "ERROR"


            elif response.status_code in [
                429,
                500,
                502,
                503,
                504
            ]:

                print(
                    "⚠️ [OpenRouter]: "
                    f"HTTP {response.status_code} "
                    f"محاولة {attempt + 1}/{retries}",
                    flush=True
                )

                time.sleep(1)


            else:

                print(
                    "⚠️ [OpenRouter]: "
                    f"HTTP {response.status_code} "
                    f"{response.text}",
                    flush=True
                )

                return "ERROR"


        except Exception as e:

            print(
                "⚠️ [OpenRouter]: "
                f"{e} "
                f"محاولة {attempt + 1}/{retries}",
                flush=True
            )

            time.sleep(1)


    return "ERROR"


# =========================================================
# CREATE INTERNAL PAYLOAD
# الحساب الوهمي -> البوت
# =========================================================

def create_bot_payload(
    text: str,
    sender_id,
    sender_username,
    sender_first_name,
    message_link
) -> str:

    data = {

        "type":
            "BARQ_CUSTOMER_REQUEST",

        "text":
            text,

        "sender_id":
            sender_id,

        "sender_username":
            sender_username,

        "sender_first_name":
            sender_first_name,

        "message_link":
            message_link
    }


    raw = json.dumps(
        data,
        ensure_ascii=False
    )


    encoded = base64.urlsafe_b64encode(
        raw.encode(
            "utf-8"
        )
    ).decode(
        "ascii"
    )


    return (
        "BARQ_INTERNAL:"
        + encoded
    )


# =========================================================
# SEND FROM USERBOT TO BOT
# =========================================================

async def send_request_to_bot(
    userbot: Client,
    bot_username: str,
    text: str,
    message: Message
):

    try:

        sender_id = None
        sender_username = None
        sender_first_name = "المستخدم"


        if message.from_user:

            sender_id = (
                message.from_user.id
            )

            sender_username = (
                message.from_user.username
            )

            sender_first_name = (
                message.from_user.first_name
                or "المستخدم"
            )


        message_link = None

        try:

            message_link = message.link

        except Exception:

            message_link = None


        payload = create_bot_payload(

            text=text,

            sender_id=sender_id,

            sender_username=sender_username,

            sender_first_name=sender_first_name,

            message_link=message_link
        )


        await userbot.send_message(

            chat_id=bot_username,

            text=payload,

            disable_web_page_preview=True
        )


        print(
            "📤 [Userbot → Bot]: "
            "تم تحويل طلب العميل إلى البوت.",
            flush=True
        )


        return True


    except FloodWait as e:

        print(
            "⏳ [Userbot → Bot]: "
            f"FloodWait {e.value} ثانية.",
            flush=True
        )

        await asyncio.sleep(
            e.value
        )


        try:

            await userbot.send_message(

                chat_id=bot_username,

                text=payload,

                disable_web_page_preview=True
            )

            print(
                "📤 [Userbot → Bot]: "
                "تم التحويل بعد الانتظار.",
                flush=True
            )

            return True


        except Exception as ex:

            print(
                "❌ [Userbot → Bot]: "
                f"فشل التحويل -> {ex}",
                flush=True
            )

            return False


    except Exception as e:

        print(
            "❌ [Userbot → Bot]: "
            f"فشل تحويل الطلب -> {e}",
            flush=True
        )

        return False


# =========================================================
# BOT -> SUBSCRIBERS
# =========================================================

async def send_to_subscriber(
    bot: Client,
    user: str,
    text: str,
    reply_markup
):

    try:

        await bot.send_message(

            chat_id=user,

            text=text,

            reply_markup=reply_markup,

            disable_web_page_preview=True
        )


        print(
            "✈️ [Bot → Subscriber]: "
            f"تم الإرسال إلى @{user}",
            flush=True
        )


    except FloodWait as e:

        print(
            "⏳ [Bot]: "
            f"FloodWait للمشترك @{user}: "
            f"{e.value} ثانية",
            flush=True
        )

        await asyncio.sleep(
            e.value
        )


        try:

            await bot.send_message(

                chat_id=user,

                text=text,

                reply_markup=reply_markup,

                disable_web_page_preview=True
            )


            print(
                "✈️ [Bot → Subscriber]: "
                f"تم الإرسال بعد الانتظار إلى @{user}",
                flush=True
            )


        except Exception as ex:

            print(
                "❌ [Bot → Subscriber]: "
                f"@{user} -> {ex}",
                flush=True
            )


    except Exception as e:

        print(
            "❌ [Bot → Subscriber]: "
            f"@{user} -> {e}",
            flush=True
        )


# =========================================================
# BOT BROADCAST
# =========================================================

async def bot_broadcast_to_subscribers(
    bot: Client,
    text: str,
    reply_markup
):

    tasks = []


    for user in TARGET_USERS:

        tasks.append(

            send_to_subscriber(

                bot,

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
# BOT INTERNAL MESSAGE HANDLER
# =========================================================

async def handle_bot_internal_message(
    bot: Client,
    message: Message
):

    if not message:
        return


    raw_text = (
        message.text
        or ""
    )


    if not raw_text.startswith(
        "BARQ_INTERNAL:"
    ):

        return


    try:

        encoded = raw_text[
            len("BARQ_INTERNAL:")
        :]


        decoded = (
            base64.urlsafe_b64decode(
                encoded
            )
            .decode(
                "utf-8"
            )
        )


        data = json.loads(
            decoded
        )


    except Exception as e:

        print(
            "❌ [Bot]: "
            f"فشل قراءة الطلب الداخلي -> {e}",
            flush=True
        )

        return


    if data.get("type") != (
        "BARQ_CUSTOMER_REQUEST"
    ):

        return


    text = (
        data.get("text")
        or ""
    ).strip()


    if len(text) < 4:

        return


    sender_id = (
        data.get("sender_id")
    )


    sender_username = (
        data.get("sender_username")
    )


    sender_first_name = (
        data.get("sender_first_name")
        or "المستخدم"
    )


    message_link = (
        data.get("message_link")
    )


    print(
        "📥 [Bot]: "
        "استلام طلب من الحساب الوهمي.",
        flush=True
    )


    # =====================================================
    # BUILD BUTTONS
    # =====================================================

    buttons = []

    row = []


    # زر فتح المحادثة
    if sender_username:

        user_url = (
            "https://t.me/"
            + sender_username
        )

        user_label = (
            "💬 فتح المحادثة "
            f"(@{sender_username})"
        )


        row.append(

            InlineKeyboardButton(

                user_label,

                url=user_url
            )
        )


    elif sender_id:

        user_url = (
            "tg://openmessage"
            "?user_id="
            f"{sender_id}"
        )

        user_label = (
            "💬 فتح المحادثة "
            f"({sender_first_name})"
        )


        row.append(

            InlineKeyboardButton(

                user_label,

                url=user_url
            )
        )


    # زر الرسالة الأصلية
    if message_link:

        row.append(

            InlineKeyboardButton(

                "📩 الرسالة الأصلية",

                url=message_link
            )
        )


    if row:

        buttons.append(row)


    reply_markup = (

        InlineKeyboardMarkup(
            buttons
        )

        if buttons

        else None
    )


    # =====================================================
    # BOT SENDS TO SUBSCRIBERS
    # =====================================================

    await bot_broadcast_to_subscribers(

        bot,

        text,

        reply_markup
    )


# =========================================================
# CORE USERBOT PROCESSOR
# =========================================================

async def process_live_message(
    userbot: Client,
    bot_username: str,
    message: Message,
    ai_semaphore
):

    if not message or not message.id:
        return


    # تجاهل رسائل الحساب نفسه
    if (
        message.from_user
        and message.from_user.is_self
    ):

        return


    raw_text = (
        message.text
        or message.caption
        or ""
    )


    clean_text = (
        raw_text.strip()
    )


    if len(clean_text) < 4:
        return


    unique_msg_id = (
        f"{message.chat.id}_"
        f"{message.id}"
    )


    text_fingerprint = (
        generate_text_fingerprint(
            clean_text
        )
    )


    async with PROCESSING_LOCK:

        if (
            unique_msg_id
            in PROCESSING_LOCKS
            or
            text_fingerprint
            in PROCESSING_LOCKS
        ):

            return


        PROCESSING_LOCKS.add(
            unique_msg_id
        )

        PROCESSING_LOCKS.add(
            text_fingerprint
        )


    try:

        print(
            "📩 [Userbot]: "
            f"رسالة جديدة -> "
            f"'{clean_text[:60]}...'",
            flush=True
        )


        # =================================================
        # AI ANALYSIS + RETRY
        # =================================================

        ai_result = "ERROR"

        max_ai_attempts = 3


        for ai_attempt in range(
            max_ai_attempts
        ):

            async with ai_semaphore:

                loop = (
                    asyncio.get_running_loop()
                )


                ai_result = (
                    await loop.run_in_executor(
                        None,
                        analyze_with_pure_ai,
                        clean_text
                    )
                )


            if ai_result in [
                "YES",
                "NO"
            ]:

                break


            if (
                ai_result == "ERROR"
                and
                ai_attempt
                < max_ai_attempts - 1
            ):

                print(
                    "🔄 [AI]: "
                    "إعادة تحليل الرسالة "
                    f"({ai_attempt + 2}/"
                    f"{max_ai_attempts})",
                    flush=True
                )


                await asyncio.sleep(
                    1
                )


        # =================================================
        # CUSTOMER REQUEST
        # =================================================

        if ai_result == "YES":


            # =================================================
            # DEDUP ONLY AFTER YES
            # =================================================

            if not await DEDUP_CACHE.add_if_not_exists(
                text_fingerprint
            ):

                print(
                    "🛑 [Dedup]: "
                    "الطلب مكرر، تم تجاهله.",
                    flush=True
                )

                return


            print(
                "✅ [AI]: "
                "طلب عميل مؤكد.",
                flush=True
            )


            # =================================================
            # USERBOT -> BOT
            # =================================================

            success = (
                await send_request_to_bot(

                    userbot=userbot,

                    bot_username=bot_username,

                    text=clean_text,

                    message=message
                )
            )


            if success:

                print(
                    "📤 [Userbot]: "
                    "تم تحويل الطلب إلى البوت "
                    "بدون إرسال مباشر للمشتركين.",
                    flush=True
                )


            else:

                print(
                    "⚠️ [Userbot]: "
                    "تعذر تحويل الطلب إلى البوت.",
                    flush=True
                )


        # =================================================
        # NO
        # =================================================

        elif ai_result == "NO":

            print(
                "🚫 [AI]: "
                "ليس طلب عميل، تم تجاهله.",
                flush=True
            )


        # =================================================
        # ERROR
        # =================================================

        else:

            print(
                "⚠️ [AI]: "
                "فشل التحليل بعد جميع المحاولات. "
                "لن يتم الإرسال ولن يسجل كتكرار.",
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
# BACKGROUND SCANNER
# =========================================================

async def background_dialog_poller(
    userbot: Client,
    bot_username: str,
    ai_semaphore
):

    await asyncio.sleep(15)


    while True:

        try:

            async for dialog in (
                userbot.get_dialogs()
            ):

                if (
                    dialog.chat
                    and
                    dialog.chat.type
                    in [
                        "group",
                        "supergroup"
                    ]
                ):

                    try:

                        async for msg in (
                            userbot.get_chat_history(
                                dialog.chat.id,
                                limit=1
                            )
                        ):

                            await process_live_message(

                                userbot,

                                bot_username,

                                msg,

                                ai_semaphore
                            )


                    except RPCError as e:

                        print(
                            "⚠️ [Scanner]: "
                            f"Telegram RPC Error -> {e}",
                            flush=True
                        )

                        await asyncio.sleep(
                            2
                        )


                    except Exception:

                        continue


                    await asyncio.sleep(
                        0.5
                    )


        except Exception as e:

            print(
                "⚠️ [Scanner]: "
                f"خطأ -> {e}",
                flush=True
            )


        await asyncio.sleep(
            30
        )


# =========================================================
# MAIN
# =========================================================

async def main():

    global PROCESSING_LOCK


    # =====================================================
    # LOCKS
    # =====================================================

    PROCESSING_LOCK = (
        asyncio.Lock()
    )


    DEDUP_CACHE.initialize_lock()


    # =====================================================
    # AI SEMAPHORE
    # =====================================================

    ai_semaphore = (
        asyncio.Semaphore(
            MAX_CONCURRENT_AI_REQUESTS
        )
    )


    # =====================================================
    # KEEP ALIVE
    # =====================================================

    threading.Thread(
        target=run_dummy_server,
        daemon=True
    ).start()


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
    # BOT
    # =====================================================

    if not BOT_TOKEN:

        print(
            "❌ [BOT]: "
            "BOT_TOKEN غير موجود في Render.",
            flush=True
        )

        return


    bot = Client(

        "helper_bot",

        api_id=API_ID,

        api_hash=API_HASH,

        bot_token=BOT_TOKEN,

        in_memory=True
    )


    # =====================================================
    # START BOT FIRST
    # =====================================================

    try:

        await bot.start()

        bot_me = (
            await bot.get_me()
        )


        bot_username = (
            bot_me.username
        )


        if not bot_username:

            print(
                "❌ [BOT]: "
                "البوت لا يملك username.",
                flush=True
            )

            return


        print(
            "🤖 [BOT]: "
            f"تم تشغيل البوت @{bot_username}",
            flush=True
        )


    except Exception as e:

        print(
            "❌ [BOT]: "
            f"فشل تشغيل البوت -> {e}",
            flush=True
        )

        return


    # =====================================================
    # BOT RECEIVER
    # =====================================================

    @bot.on_message(
        filters.private
    )
    async def bot_internal_receiver(
        client: Client,
        message: Message
    ):

        await handle_bot_internal_message(

            client,

            message
        )


    # =====================================================
    # USERBOT LISTENER
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

                bot_username,

                message,

                ai_semaphore
            )
        )


    # =====================================================
    # START USERBOT
    # =====================================================

    try:

        await userbot.start()

        print(
            "👤 [USERBOT]: "
            "تم تشغيل الحساب الوهمي.",
            flush=True
        )

    except Exception as e:

        print(
            "❌ [USERBOT]: "
            f"فشل التشغيل -> {e}",
            flush=True
        )

        await bot.stop()

        return


    # =====================================================
    # START BACKGROUND SCANNER
    # =====================================================

    asyncio.create_task(

        background_dialog_poller(

            userbot,

            bot_username,

            ai_semaphore
        )
    )


    print(
        "🚀 [BARQ]: "
        "النظام يعمل الآن:",
        flush=True
    )

    print(
        "📡 القروبات"
        " → 👤 الحساب الوهمي"
        " → 🤖 البوت"
        " → 👥 المشتركين",
        flush=True
    )


    # =====================================================
    # KEEP RUNNING
    # =====================================================

    await asyncio.Event().wait()


# =========================================================
# START
# =========================================================

if __name__ == "__main__":

    asyncio.run(
        main()
                    )
