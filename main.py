import os
import re
import json
import time
import asyncio
import hashlib
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

import aiohttp

from hydrogram import Client, filters
from hydrogram.types import Message
from hydrogram.errors import FloodWait


# ============================================================
#                    إعدادات Environment
# ============================================================

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

PORT = int(os.getenv("PORT", "10000"))

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "qwen/qwen-2.5-7b-instruct"
)

OPENROUTER_FALLBACK_MODEL = os.getenv(
    "OPENROUTER_FALLBACK_MODEL",
    "meta-llama/llama-3.1-8b-instruct"
)


# ============================================================
#                  المستهدفون بالطلبات
# ============================================================

TARGET_USERS = [
    "@abood1317",
    "@shaybq",
]


# ============================================================
#                       إعدادات عامة
# ============================================================

AI_RETRIES = 2
AI_TIMEOUT = 15

DEDUP_TTL = 60 * 60 * 24

MAX_MESSAGE_LENGTH = 6000

MAX_CONCURRENT_AI = 8


# ============================================================
#                       Logging
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("BARQ")


# ============================================================
#                  التحقق من Environment
# ============================================================

required_env = {
    "TELEGRAM_API_ID": API_ID,
    "TELEGRAM_API_HASH": API_HASH,
    "SESSION_STRING": SESSION_STRING,
    "BOT_TOKEN": BOT_TOKEN,
    "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
}

missing = [
    name
    for name, value in required_env.items()
    if not value
]

if missing:
    raise RuntimeError(
        "Environment Variables ناقصة: "
        + ", ".join(missing)
    )


# ============================================================
#                     Keep Alive
# ============================================================

class KeepAliveHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        try:

            self.send_response(200)

            self.send_header(
                "Content-Type",
                "text/plain; charset=utf-8"
            )

            self.end_headers()

            self.wfile.write(
                b"Barq AI Userbot Active 24/7!"
            )

        except Exception:
            pass

    def log_message(self, format, *args):
        return


def run_keep_alive():

    try:

        server = HTTPServer(
            ("0.0.0.0", PORT),
            KeepAliveHandler
        )

        logger.info(
            f"Keep Alive started on port {PORT}"
        )

        server.serve_forever()

    except Exception as e:

        logger.exception(
            f"Keep Alive Error: {e}"
        )


threading.Thread(
    target=run_keep_alive,
    daemon=True
).start()


# ============================================================
#                    Hydrogram Userbot
# ============================================================

app = Client(
    "barq_userbot",

    api_id=int(API_ID),

    api_hash=API_HASH,

    session_string=SESSION_STRING,

    in_memory=True,
)


# ============================================================
#                  Telegram Bot API
# ============================================================

BOT_API = (
    f"https://api.telegram.org/"
    f"bot{BOT_TOKEN}"
)


# ============================================================
#                    OpenRouter API
# ============================================================

OPENROUTER_URL = (
    "https://openrouter.ai/api/v1/chat/completions"
)


# ============================================================
#                 منع الرسائل المكررة
# ============================================================

processed_messages = {}

processed_lock = asyncio.Lock()


async def cleanup_processed_messages():

    while True:

        try:

            now = time.time()

            async with processed_lock:

                expired = [
                    key
                    for key, timestamp
                    in processed_messages.items()
                    if now - timestamp > DEDUP_TTL
                ]

                for key in expired:

                    processed_messages.pop(
                        key,
                        None
                    )

        except Exception as e:

            logger.exception(
                f"Dedup cleanup error: {e}"
            )

        await asyncio.sleep(600)


async def is_duplicate(
    message: Message,
    text: str
) -> bool:

    try:

        chat_id = getattr(
            message.chat,
            "id",
            0
        )

        sender_id = 0

        if message.from_user:

            sender_id = getattr(
                message.from_user,
                "id",
                0
            )

        normalized = text.strip().lower()

        raw = (
            f"{chat_id}|"
            f"{sender_id}|"
            f"{normalized}"
        )

        fingerprint = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

        async with processed_lock:

            if fingerprint in processed_messages:

                return True

            processed_messages[
                fingerprint
            ] = time.time()

        return False

    except Exception as e:

        logger.exception(
            f"Duplicate check error: {e}"
        )

        return False


# ============================================================
#                  فلتر أرقام الجوال
# ============================================================

PHONE_PATTERNS = [

    # 05xxxxxxxx
    r"(?<!\d)05\d{8}(?!\d)",

    # 5xxxxxxxx
    r"(?<!\d)5\d{8}(?!\d)",

    # +9665xxxxxxxx
    r"(?<!\d)\+9665\d{8}(?!\d)",

    # 009665xxxxxxxx
    r"(?<!\d)009665\d{8}(?!\d)",

    # 9665xxxxxxxx
    r"(?<!\d)9665\d{8}(?!\d)",

    # 05x xxx xxxx
    r"(?<!\d)05\d[\s\-]?\d{3}[\s\-]?\d{4}(?!\d)",
]

PHONE_REGEX = re.compile(
    "|".join(PHONE_PATTERNS)
)


def normalize_arabic_digits(
    text: str
) -> str:

    translation = str.maketrans(
        "٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹",
        "01234567890123456789"
    )

    return text.translate(translation)


def contains_phone_number(
    text: str
) -> bool:

    try:

        normalized = normalize_arabic_digits(
            text
        )

        return bool(
            PHONE_REGEX.search(
                normalized
            )
        )

    except Exception as e:

        logger.exception(
            f"Phone regex error: {e}"
        )

        return False


# ============================================================
#                       تنظيف النص
# ============================================================

def clean_text(text: str) -> str:

    if not text:
        return ""

    text = text.strip()

    if len(text) > MAX_MESSAGE_LENGTH:

        text = text[
            :MAX_MESSAGE_LENGTH
        ]

    return text


# ============================================================
#                    AI SYSTEM PROMPT
# ============================================================

AI_SYSTEM_PROMPT = r"""
أنت فلتر ذكاء اصطناعي لطلبات التوصيل والمشاوير في السعودية.

مهمتك تصنيف الرسالة إلى:

allow=true
أو
allow=false

أخرج JSON فقط:

{
  "allow": true
}

أو:

{
  "allow": false
}


السماح يكون فقط عندما تكون الرسالة من عميل أو زبون
يبحث عن:

- سائق
- سائقة
- مندوب
- توصيل
- مشوار
- استلام طلب
- إحضار غرض
- توصيل شخص
- توصيل طلب
- شراء أو إحضار شيء له


أمثلة على طلبات العملاء:

"ابغى سواق من جيزان لصبيا"

"محتاجة أحد يوصلني للجامعة"

"مين فاضي يجيب لي غرض من المطار؟"

"أحتاج مندوب يستلم لي طلب"

"فيه أحد يوصلني للدوام؟"

"أبغى أحد يجيب لي طلب من المطعم"

"مين يقدر يسوي لي مشوار؟"


ارفض:

- إعلانات السائقين
- إعلانات المناديب
- مناديب متوفرين
- سائق متوفر
- عروض التوصيل
- عروض النقل
- إعلان خدمة
- إعلان متجر
- إعلان تجاري
- رقم مندوب
- رقم سائق
- خدمات عامة
- بيع وشراء
- وظائف
- رسائل عامة
- تحيات
- دردشة
- رسائل غير مرتبطة بالتوصيل والمشاوير


مهم جدًا:

لا تعتمد على كلمات ثابتة.

افهم معنى الرسالة كاملة.

إذا كان الكاتب يعرض نفسه كسائق أو مندوب
فهي false.

إذا كان الكاتب يبحث عن شخص يقوم بالمشوار أو التوصيل
فهي true.

إذا كانت الرسالة غير واضحة
اجعلها false.

أخرج JSON فقط بدون أي شرح.
"""


# ============================================================
#                  OpenRouter AI
# ============================================================

ai_semaphore = asyncio.Semaphore(
    MAX_CONCURRENT_AI
)


async def ask_openrouter(
    text: str
) -> bool:

    async with ai_semaphore:

        headers = {

            "Authorization":
                f"Bearer {OPENROUTER_API_KEY}",

            "Content-Type":
                "application/json",

            "HTTP-Referer":
                "https://render.com/",

            "X-Title":
                "Barq Jazan AI Filter",
        }

        payload = {

            "models": [

                OPENROUTER_MODEL,

                OPENROUTER_FALLBACK_MODEL

            ],

            "messages": [

                {
                    "role": "system",
                    "content": AI_SYSTEM_PROMPT
                },

                {
                    "role": "user",
                    "content": text
                }

            ],

            "temperature": 0,

            "max_tokens": 30,

            "response_format": {
                "type": "json_object"
            }
        }

        timeout = aiohttp.ClientTimeout(
            total=AI_TIMEOUT
        )

        for attempt in range(
            AI_RETRIES + 1
        ):

            try:

                async with aiohttp.ClientSession(
                    timeout=timeout
                ) as session:

                    async with session.post(
                        OPENROUTER_URL,
                        headers=headers,
                        json=payload
                    ) as response:

                        raw = await response.text()

                        if response.status != 200:

                            logger.warning(
                                "OpenRouter HTTP "
                                f"{response.status}: "
                                f"{raw[:300]}"
                            )

                            if attempt < AI_RETRIES:

                                await asyncio.sleep(
                                    1.5 * (attempt + 1)
                                )

                                continue

                            return False

                        data = json.loads(
                            raw
                        )

                        choices = data.get(
                            "choices",
                            []
                        )

                        if not choices:

                            return False

                        content = (
                            choices[0]
                            .get("message", {})
                            .get("content", "")
                        )

                        if not content:

                            return False

                        content = (
                            content
                            .replace(
                                "```json",
                                ""
                            )
                            .replace(
                                "```",
                                ""
                            )
                            .strip()
                        )

                        result = json.loads(
                            content
                        )

                        return bool(
                            result.get(
                                "allow",
                                False
                            )
                        )

            except asyncio.TimeoutError:

                logger.warning(
                    "OpenRouter timeout"
                )

            except json.JSONDecodeError:

                logger.warning(
                    "Invalid AI JSON"
                )

            except Exception as e:

                logger.exception(
                    f"OpenRouter error: {e}"
                )

            if attempt < AI_RETRIES:

                await asyncio.sleep(
                    1.5 * (attempt + 1)
                )

        return False


# ============================================================
#                  رابط محادثة العميل
# ============================================================

def get_user_link(
    message: Message
) -> Optional[str]:

    try:

        user = message.from_user

        if not user:
            return None

        username = getattr(
            user,
            "username",
            None
        )

        if username:

            return (
                f"https://t.me/"
                f"{username}"
            )

        user_id = getattr(
            user,
            "id",
            None
        )

        if user_id:

            return (
                f"tg://user?id="
                f"{user_id}"
            )

    except Exception as e:

        logger.exception(
            f"User link error: {e}"
        )

    return None


# ============================================================
#                  رابط الرسالة الأصلية
# ============================================================

def get_message_link(
    message: Message
) -> Optional[str]:

    try:

        chat = message.chat

        username = getattr(
            chat,
            "username",
            None
        )

        message_id = getattr(
            message,
            "id",
            None
        )

        if not message_id:
            return None

        # قروب/قناة عامة
        if username:

            return (
                f"https://t.me/"
                f"{username}/"
                f"{message_id}"
            )

        # قروب/قناة خاصة
        chat_id = getattr(
            chat,
            "id",
            None
        )

        if (
            chat_id
            and str(chat_id).startswith("-100")
        ):

            internal_id = str(
                chat_id
            )[4:]

            return (
                f"https://t.me/c/"
                f"{internal_id}/"
                f"{message_id}"
            )

    except Exception as e:

        logger.exception(
            f"Message link error: {e}"
        )

    return None


# ============================================================
#                    اسم المصدر
# ============================================================

def get_chat_name(
    message: Message
) -> str:

    try:

        chat = message.chat

        title = getattr(
            chat,
            "title",
            None
        )

        if title:
            return title

        first_name = getattr(
            chat,
            "first_name",
            None
        )

        if first_name:
            return first_name

        username = getattr(
            chat,
            "username",
            None
        )

        if username:
            return "@" + username

    except Exception:
        pass

    return "غير معروف"


# ============================================================
#                    اسم العميل
# ============================================================

def get_sender_name(
    message: Message
) -> str:

    try:

        user = message.from_user

        if not user:
            return "غير معروف"

        first = getattr(
            user,
            "first_name",
            ""
        ) or ""

        last = getattr(
            user,
            "last_name",
            ""
        ) or ""

        name = (
            f"{first} {last}"
        ).strip()

        if name:
            return name

        username = getattr(
            user,
            "username",
            None
        )

        if username:
            return "@" + username

    except Exception:
        pass

    return "غير معروف"


# ============================================================
#                 تجهيز الرسالة النهائية
# ============================================================

def build_output_message(
    message: Message,
    text: str
) -> str:

    chat_name = get_chat_name(
        message
    )

    sender_name = get_sender_name(
        message
    )

    return (
        "📦 <b>طلب عميل جديد</b>\n"
        "\n"
        f"👤 <b>العميل:</b> "
        f"{sender_name}\n"
        f"📍 <b>المصدر:</b> "
        f"{chat_name}\n"
        "\n"
        "💬 <b>الطلب:</b>\n"
        f"{text}"
    )


# ============================================================
#                    Telegram Bot API
# ============================================================

async def bot_api_request(
    method: str,
    payload: dict
):

    url = (
        f"{BOT_API}/"
        f"{method}"
    )

    timeout = aiohttp.ClientTimeout(
        total=20
    )

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:

        async with session.post(
            url,
            json=payload
        ) as response:

            raw = await response.text()

            try:

                data = json.loads(
                    raw
                )

            except Exception:

                data = {
                    "ok": False,
                    "description": raw
                }

            if not data.get("ok"):

                raise RuntimeError(
                    data.get(
                        "description",
                        f"HTTP {response.status}"
                    )
                )

            return data


# ============================================================
#                 إرسال لمستلم واحد
# ============================================================

async def send_to_one_target(
    target,
    text,
    keyboard
):

    # ========================================================
    # مهم جدًا:
    # هذا try-except خاص بهذا المستلم فقط.
    # ========================================================

    try:

        payload = {

            "chat_id":
                target,

            "text":
                text,

            "parse_mode":
                "HTML",

            "disable_web_page_preview":
                True,
        }

        if keyboard:

            payload[
                "reply_markup"
            ] = keyboard

        await bot_api_request(
            "sendMessage",
            payload
        )

        logger.info(
            f"SUCCESS -> {target}"
        )

        return True

    except Exception as e:

        logger.error(
            f"FAILED -> {target} | {e}"
        )

        return False


# ============================================================
#                 إرسال لكل المستهدفين
# ============================================================

async def send_to_all_targets(
    message: Message,
    text: str
):

    try:

        user_link = get_user_link(
            message
        )

        message_link = get_message_link(
            message
        )

        buttons = []

        if user_link:

            buttons.append({
                "text":
                    "👤 محادثة العميل",

                "url":
                    user_link
            })

        if message_link:

            buttons.append({
                "text":
                    "🔗 الرسالة الأصلية",

                "url":
                    message_link
            })

        keyboard = None

        if buttons:

            keyboard = {
                "inline_keyboard": [
                    buttons
                ]
            }

        output = build_output_message(
            message,
            text
        )

        # كل مستلم مستقل
        tasks = []

        for target in TARGET_USERS:

            tasks.append(
                send_to_one_target(
                    target,
                    output,
                    keyboard
                )
            )

        if not tasks:

            logger.warning(
                "TARGET_USERS فارغة"
            )

            return

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True
        )

        success = 0
        failed = 0

        for result in results:

            if result is True:

                success += 1

            else:

                failed += 1

        logger.info(
            "Distribution finished | "
            f"Success={success} | "
            f"Failed={failed}"
        )

    except Exception as e:

        logger.exception(
            f"Distribution error: {e}"
        )


# ============================================================
#                  معالجة الرسالة
# ============================================================

processing_semaphore = asyncio.Semaphore(
    20
)


async def process_message(
    message: Message
):

    async with processing_semaphore:

        try:

            # ------------------------------------------------
            # النص أو الكابشن
            # ------------------------------------------------

            text = getattr(
                message,
                "text",
                None
            )

            if not text:

                text = getattr(
                    message,
                    "caption",
                    None
                )

            if not text:

                return

            text = clean_text(
                text
            )

            if not text:

                return

            # ------------------------------------------------
            # تجاهل رسائل الحساب نفسه
            # ------------------------------------------------

            try:

                me = await app.get_me()

                if (
                    message.from_user
                    and
                    message.from_user.id
                    == me.id
                ):

                    return

            except Exception:

                pass

            # ------------------------------------------------
            # منع التكرار
            # ------------------------------------------------

            if await is_duplicate(
                message,
                text
            ):

                logger.info(
                    "DUPLICATE -> SKIP"
                )

                return

            # ------------------------------------------------
            # Regex أرقام الجوال
            # ------------------------------------------------

            if contains_phone_number(
                text
            ):

                logger.info(
                    "PHONE NUMBER -> SKIP"
                )

                return

            # ------------------------------------------------
            # OpenRouter
            # ------------------------------------------------

            logger.info(
                "AI CHECK -> "
                f"{text[:100]}"
            )

            allowed = await ask_openrouter(
                text
            )

            if not allowed:

                logger.info(
                    "AI REJECTED"
                )

                return

            logger.info(
                "AI ACCEPTED"
            )

            # ------------------------------------------------
            # إرسال للمستهدفين
            # ------------------------------------------------

            await send_to_all_targets(
                message,
                text
            )

        except FloodWait as e:

            wait_seconds = getattr(
                e,
                "value",
                5
            )

            logger.warning(
                f"FloodWait -> "
                f"{wait_seconds}s"
            )

            await asyncio.sleep(
                wait_seconds
            )

        except Exception as e:

            logger.exception(
                f"PROCESS ERROR: {e}"
            )


# ============================================================
#               استقبال جميع الرسائل الجديدة
# ============================================================

@app.on_message(
    filters.incoming
)
async def new_message_handler(
    client,
    message
):

    try:

        # لا نعالج إلا الرسائل التي تحتوي نصًا
        if not (
            getattr(
                message,
                "text",
                None
            )
            or
            getattr(
                message,
                "caption",
                None
            )
        ):

            return

        # تشغيل المعالجة في Task منفصل
        asyncio.create_task(
            process_message(
                message
            )
        )

    except Exception as e:

        logger.exception(
            f"HANDLER ERROR: {e}"
        )


# ============================================================
#                 فحص Telegram Bot
# ============================================================

async def check_bot():

    try:

        data = await bot_api_request(
            "getMe",
            {}
        )

        bot = data.get(
            "result",
            {}
        )

        username = bot.get(
            "username",
            "unknown"
        )

        logger.info(
            f"BOT CONNECTED -> @{username}"
        )

    except Exception as e:

        raise RuntimeError(
            "BOT_TOKEN غير صحيح أو البوت غير متاح: "
            f"{e}"
        )


# ============================================================
#                       التشغيل
# ============================================================

async def main():

    logger.info(
        "======================================"
    )

    logger.info(
        "BARQ AI USERBOT STARTING..."
    )

    logger.info(
        "======================================"
    )

    # فحص Bot API
    await check_bot()

    # تنظيف ذاكرة التكرار
    asyncio.create_task(
        cleanup_processed_messages()
    )

    # تشغيل الحساب الوهمي
    await app.start()

    try:

        me = await app.get_me()

        logger.info(
            "USERBOT CONNECTED"
        )

        logger.info(
            f"ACCOUNT ID -> {me.id}"
        )

        if me.username:

            logger.info(
                f"ACCOUNT -> @{me.username}"
            )

        # محاولة معرفة عدد المحادثات
        try:

            count = await app.get_dialogs_count()

            logger.info(
                f"DIALOGS -> {count}"
            )

        except Exception as e:

            logger.warning(
                f"Could not get dialogs count: {e}"
            )

        logger.info(
            "LISTENING TO ALL AVAILABLE "
            "INCOMING CHATS..."
        )

        logger.info(
            "TARGET 1 -> @abood1317"
        )

        logger.info(
            "TARGET 2 -> @shaybq"
        )

        # إبقاء البرنامج يعمل
        await asyncio.Event().wait()

    finally:

        try:

            await app.stop()

        except Exception:

            pass


# ============================================================
#                         START
# ============================================================

if __name__ == "__main__":

    try:

        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        logger.info(
            "STOPPED"
        )

    except Exception as e:

        logger.exception(
            f"FATAL ERROR -> {e}"
                    )
