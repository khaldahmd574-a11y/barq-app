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
# KEEP ALIVE - RENDER
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
            b"Barq OpenRouter AI System Active!"
        )

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()


def run_dummy_server():

    port = int(
        os.environ.get(
            "PORT",
            "10000"
        )
    )

    server = HTTPServer(
        ("0.0.0.0", port),
        DummyServer
    )

    server.serve_forever()


# =========================================================
# CONFIG
# =========================================================

SESSION_STRING = os.environ.get(
    "SESSION_STRING",
    ""
).strip()

API_ID_RAW = os.environ.get(
    "TELEGRAM_API_ID",
    ""
).strip()

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


try:
    API_ID = int(API_ID_RAW)
except Exception:
    API_ID = 0


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
# AI SETTINGS
# =========================================================

MAX_CONCURRENT_AI_REQUESTS = 10


# =========================================================
# DEDUP CACHE
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
# PROCESSING
# =========================================================

PROCESSING_LOCKS = set()
PROCESSING_LOCK = None


# =========================================================
# NORMALIZE TEXT
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
# FINGERPRINT
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
        normalized.encode("utf-8")
    ).hexdigest()


# =========================================================
# OPENROUTER AI
# =========================================================

def analyze_with_pure_ai(
    text: str
) -> str:

    if not OPENROUTER_API_KEY:

        print(
            "❌ [OpenRouter]: "
            "OPENROUTER_API_KEY غير موجود.",
            flush=True
        )

        return "ERROR"


    prompt = f"""
أنت نظام ذكاء اصطناعي متخصص في تصنيف منشورات قروبات المشاوير والتوصيل في السعودية، وخاصة جازان والمنطقة الجنوبية.

حلل معنى المنشور كاملاً.

المطلوب:

YES = عميل يبحث عن سائق أو مندوب أو توصيل أو مشوار.

NO = سائق أو مندوب يعرض خدماته، أو إعلان، أو سبام، أو محتوى غير متعلق.

========================================
أمثلة YES
========================================

"مين رايح من صبيا لجيزان؟"

"فيه أحد رايح أبو عريش؟"

"مين فاضي يوصلني الآن؟"

"أحتاج سواق للجامعة"

"محتاج أحد يوصل لي طلب"

"أبي مندوب يجيب لي غرض"

"مطلوب سواق دوامات"

"أحتاج أحد يوصلني من جيزان لصبيا"

"مين عنده مشوار من صامطة إلى جيزان؟"

وجود رقم جوال في طلب العميل لا يجعله سائقاً.

مثال:

"أحتاج سواق من صبيا لجيزان
05xxxxxxxx"

= YES

========================================
أمثلة NO
========================================

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
مهم
========================================

لا تعتمد على كلمة واحدة.

افهم نية صاحب المنشور.

إذا كان يبحث عن شخص يقدم له الخدمة:
YES

إذا كان هو الشخص الذي يقدم الخدمة:
NO

الإعلانات والوظائف والعملات الرقمية والمحتوى غير المتعلق:
NO

========================================
المنشور:
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
            "application/json",

        "HTTP-Referer":
            "https://barq.local",

        "X-Title":
            "Barq Jazan AI"
    }


    payload = {

        "model":
            "openai/gpt-4o-mini",

        "messages": [

            {
                "role":
                    "user",

                "content":
                    prompt
            }
        ],

        "temperature":
            0,

        "max_tokens":
            5
    }


    for attempt in range(3):

        try:

            response = requests.post(

                url,

                headers=headers,

                json=payload,

                timeout=15
            )


            if response.status_code == 200:

                data = response.json()

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


                print(
                    "🤖 [OpenRouter]: "
                    f"{answer}",
                    flush=True
                )


                if answer == "YES":
                    return "YES"

                if answer == "NO":
                    return "NO"

                return "ERROR"


            if response.status_code in (
                429,
                500,
                502,
                503,
                504
            ):

                print(
                    "⚠️ [OpenRouter]: "
                    f"HTTP {response.status_code} "
                    f"محاولة {attempt + 1}/3",
                    flush=True
                )

                time.sleep(1)

                continue


            print(
                "❌ [OpenRouter]: "
                f"HTTP {response.status_code} "
                f"{response.text[:500]}",
                flush=True
            )

            return "ERROR"


        except Exception as e:

            print(
                "⚠️ [OpenRouter]: "
                f"{e} "
                f"محاولة {attempt + 1}/3",
                flush=True
            )

            time.sleep(1)


    return "ERROR"


# =========================================================
# CREATE INTERNAL MESSAGE
# =========================================================

def create_bot_payload(
    text,
    sender_id,
    sender_username,
    sender_first_name,
    message_link
):

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


    encoded = (
        base64.urlsafe_b64encode(
            raw.encode("utf-8")
        )
        .decode("ascii")
    )


    return (
        "BARQ_INTERNAL:"
        + encoded
    )


# =========================================================
# USERBOT -> BOT
# =========================================================

async def send_request_to_bot(
    userbot,
    bot_username,
    text,
    message
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

            text,

            sender_id,

            sender_username,

            sender_first_name,

            message_link
        )


        await userbot.send_message(

            chat_id=bot_username,

            text=payload,

            disable_web_page_preview=True
        )


        print(
            "📤 [USERBOT → BOT]: "
            "تم إرسال الطلب إلى البوت.",
            flush=True
        )

        return True


    except FloodWait as e:

        print(
            "⏳ [USERBOT → BOT]: "
            f"FloodWait {e.value}",
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
                "📤 [USERBOT → BOT]: "
                "تم الإرسال بعد الانتظار.",
                flush=True
            )

            return True

        except Exception as ex:

            print(
                "❌ [USERBOT → BOT]: "
                f"{ex}",
                flush=True
            )

            return False


    except Exception as e:

        print(
            "❌ [USERBOT → BOT]: "
            f"فشل إرسال الطلب -> {e}",
            flush=True
        )

        return False


# =========================================================
# BOT -> ONE SUBSCRIBER
# =========================================================

async def send_to_subscriber(
    bot,
    username,
    text,
    reply_markup
):

    try:

        await bot.send_message(

            chat_id=username,

            text=text,

            reply_markup=reply_markup,

            disable_web_page_preview=True
        )


        print(
            "✅ [BOT → SUBSCRIBER]: "
            f"تم الإرسال إلى @{username}",
            flush=True
        )


    except FloodWait as e:

        print(
            "⏳ [BOT]: "
            f"@{username} FloodWait "
            f"{e.value}",
            flush=True
        )

        await asyncio.sleep(
            e.value
        )


        try:

            await bot.send_message(

                chat_id=username,

                text=text,

                reply_markup=reply_markup,

                disable_web_page_preview=True
            )


            print(
                "✅ [BOT → SUBSCRIBER]: "
                f"تم الإرسال بعد الانتظار إلى "
                f"@{username}",
                flush=True
            )


        except Exception as ex:

            print(
                "❌ [BOT → SUBSCRIBER]: "
                f"@{username} -> {ex}",
                flush=True
            )


    except Exception as e:

        print(
            "❌ [BOT → SUBSCRIBER]: "
            f"@{username} -> {e}",
            flush=True
        )


# =========================================================
# BOT BROADCAST
# =========================================================

async def bot_broadcast_to_subscribers(
    bot,
    text,
    reply_markup
):

    print(
        "📢 [BOT]: "
        "بدء إرسال الطلب للمشتركين...",
        flush=True
    )


    for username in TARGET_USERS:

        await send_to_subscriber(

            bot,

            username,

            text,

            reply_markup
        )

        await asyncio.sleep(
            0.2
        )


    print(
        "🏁 [BOT]: "
        "انتهى إرسال الطلب للمشتركين.",
        flush=True
    )


# =========================================================
# BOT INTERNAL RECEIVER
# =========================================================

async def handle_bot_internal_message(
    bot,
    message
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


    print(
        "📥 [BOT]: "
        "استلام رسالة داخلية من الحساب الوهمي.",
        flush=True
    )


    try:

        encoded = raw_text[
            len("BARQ_INTERNAL:")
        :]


        decoded = (
            base64.urlsafe_b64decode(
                encoded
            )
            .decode("utf-8")
        )


        data = json.loads(
            decoded
        )


    except Exception as e:

        print(
            "❌ [BOT]: "
            f"فشل فك الرسالة -> {e}",
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


    sender_id = data.get(
        "sender_id"
    )

    sender_username = data.get(
        "sender_username"
    )

    sender_first_name = (
        data.get(
            "sender_first_name"
        )
        or "المستخدم"
    )

    message_link = data.get(
        "message_link"
    )


    print(
        "✅ [BOT]: "
        "تم التعرف على طلب عميل.",
        flush=True
    )


    # =====================================================
    # BUTTONS
    # =====================================================

    buttons = []

    row = []


    # فتح المحادثة
    if sender_username:

        user_url = (
            "https://t.me/"
            + str(sender_username)
        )

        row.append(

            InlineKeyboardButton(

                "💬 فتح المحادثة "
                f"(@{sender_username})",

                url=user_url
            )
        )


    elif sender_id:

        user_url = (
            "tg://openmessage"
            "?user_id="
            + str(sender_id)
        )

        row.append(

            InlineKeyboardButton(

                "💬 فتح المحادثة "
                f"({sender_first_name})",

                url=user_url
            )
        )


    # الرسالة الأصلية
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
    # BOT SENDS
    # =====================================================

    await bot_broadcast_to_subscribers(

        bot,

        text,

        reply_markup
    )


# =========================================================
# PROCESS USERBOT MESSAGE
# =========================================================

async def process_live_message(
    userbot,
    bot_username,
    message,
    ai_semaphore
):

    if not message or not message.id:
        return


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


    clean_text = raw_text.strip()


    if len(clean_text) < 4:
        return


    unique_msg_id = (
        f"{message.chat.id}:"
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
            "📩 [USERBOT]: "
            f"{clean_text[:80]}",
            flush=True
        )


        ai_result = "ERROR"


        for attempt in range(3):

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


            if ai_result in (
                "YES",
                "NO"
            ):

                break


            if attempt < 2:

                await asyncio.sleep(1)


        # =================================================
        # YES
        # =================================================

        if ai_result == "YES":

            if not await DEDUP_CACHE.add_if_not_exists(
                text_fingerprint
            ):

                print(
                    "🛑 [DEDUP]: "
                    "طلب مكرر.",
                    flush=True
                )

                return


            print(
                "✅ [AI]: "
                "طلب عميل مؤكد.",
                flush=True
            )


            success = (
                await send_request_to_bot(

                    userbot,

                    bot_username,

                    clean_text,

                    message
                )
            )


            if not success:

                print(
                    "❌ [FLOW]: "
                    "الحساب الوهمي لم يستطع "
                    "إرسال الطلب إلى البوت.",
                    flush=True
                )


        elif ai_result == "NO":

            print(
                "🚫 [AI]: "
                "ليس طلب عميل.",
                flush=True
            )


        else:

            print(
                "⚠️ [AI]: "
                "فشل التحليل.",
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
    userbot,
    bot_username,
    ai_semaphore
):

    await asyncio.sleep(15)


    while True:

        try:

            async for dialog in (
                userbot.get_dialogs()
            ):

                if not dialog.chat:
                    continue


                if dialog.chat.type not in (
                    "group",
                    "supergroup"
                ):

                    continue


                try:

                    async for msg in (
                        userbot.get_chat_history(
                            dialog.chat.id,
                            limit=1
                        )
                    ):

                        asyncio.create_task(

                            process_live_message(

                                userbot,

                                bot_username,

                                msg,

                                ai_semaphore
                            )
                        )

                        break


                except RPCError as e:

                    print(
                        "⚠️ [SCANNER]: "
                        f"{e}",
                        flush=True
                    )

                except Exception as e:

                    print(
                        "⚠️ [SCANNER]: "
                        f"{e}",
                        flush=True
                    )


                await asyncio.sleep(
                    0.5
                )


        except Exception as e:

            print(
                "⚠️ [SCANNER]: "
                f"خطأ عام -> {e}",
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
    # CHECK ENV
    # =====================================================

    print(
        "🔧 [CONFIG]: فحص الإعدادات...",
        flush=True
    )


    if not API_ID:

        print(
            "❌ [CONFIG]: "
            "TELEGRAM_API_ID غير موجود أو غير صحيح.",
            flush=True
        )

        return


    if not API_HASH:

        print(
            "❌ [CONFIG]: "
            "TELEGRAM_API_HASH غير موجود.",
            flush=True
        )

        return


    if not BOT_TOKEN:

        print(
            "❌ [CONFIG]: "
            "BOT_TOKEN غير موجود.",
            flush=True
        )

        return


    if not SESSION_STRING:

        print(
            "❌ [CONFIG]: "
            "SESSION_STRING غير موجود.",
            flush=True
        )

        return


    if not OPENROUTER_API_KEY:

        print(
            "❌ [CONFIG]: "
            "OPENROUTER_API_KEY غير موجود.",
            flush=True
        )

        return


    print(
        "✅ [CONFIG]: "
        "جميع المتغيرات الأساسية موجودة.",
        flush=True
    )


    # =====================================================
    # LOCK
    # =====================================================

    PROCESSING_LOCK = asyncio.Lock()

    DEDUP_CACHE.initialize_lock()


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

    bot = Client(

        "barq_bot",

        api_id=API_ID,

        api_hash=API_HASH,

        bot_token=BOT_TOKEN
    )


    # =====================================================
    # BOT HANDLER
    # =====================================================

    @bot.on_message(
        filters.private
    )
    async def bot_internal_receiver(
        client,
        message
    ):

        await handle_bot_internal_message(

            client,

            message
        )


    # =====================================================
    # START BOT
    # =====================================================

    try:

        print(
            "🤖 [BOT]: "
            "جاري تشغيل البوت...",
            flush=True
        )


        await bot.start()


        bot_me = await bot.get_me()


        bot_username = (
            bot_me.username
        )


        if not bot_username:

            print(
                "❌ [BOT]: "
                "البوت لا يملك username.",
                flush=True
            )

            await bot.stop()

            return


        print(
            "✅ [BOT]: "
            f"تم تشغيل @{bot_username}",
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
    # USERBOT LISTENER
    # =====================================================

    @userbot.on_message(
        filters.group | filters.channel
    )
    async def global_live_listener(
        client,
        message
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

        print(
            "👤 [USERBOT]: "
            "جاري تشغيل الحساب الوهمي...",
            flush=True
        )


        await userbot.start()


        print(
            "✅ [USERBOT]: "
            "تم تشغيل الحساب الوهمي.",
            flush=True
        )


    except Exception as e:

        print(
            "❌ [USERBOT]: "
            f"فشل تشغيل الحساب الوهمي -> {e}",
            flush=True
        )

        try:
            await bot.stop()
        except Exception:
            pass

        return


    # =====================================================
    # START SCANNER
    # =====================================================

    asyncio.create_task(

        background_dialog_poller(

            userbot,

            bot_username,

            ai_semaphore
        )
    )


    # =====================================================
    # FINAL STATUS
    # =====================================================

    print(
        "",
        flush=True
    )

    print(
        "🚀 [BARQ]: النظام يعمل الآن",
        flush=True
    )

    print(
        "📡 القروبات"
        " → 👤 الحساب الوهمي"
        " → 🤖 البوت"
        " → 👥 المشتركين",
        flush=True
    )

    print(
        "🤖 OpenRouter: ACTIVE",
        flush=True
    )

    print(
        "👥 المشتركين:",
        ", ".join(
            "@" + x
            for x in TARGET_USERS
        ),
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

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "🛑 تم إيقاف النظام.",
            flush=True
        )

    except Exception as e:

        print(
            "💥 [FATAL]: "
            f"{e}",
            flush=True
    )
