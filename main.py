import os
import re
import asyncio
import hashlib
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import aiohttp
from cachetools import TTLCache
from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


# =========================
# الإعدادات
# =========================

API_ID = int(os.getenv("TELEGRAM_API_ID", "39120728"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
PORT = int(os.getenv("PORT", "10000"))

# المستلمون المعتمدون فقط
TARGET_USERS = [
    "@shaybq",
    "@abood1317",
]

CACHE_TTL = 10800
MAX_MESSAGE_LENGTH = 3500

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("Barq")


# =========================
# التحقق من الإعدادات
# =========================

required = {
    "TELEGRAM_API_HASH": API_HASH,
    "SESSION_STRING": SESSION_STRING,
    "BOT_TOKEN": BOT_TOKEN,
    "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
}

missing = [key for key, value in required.items() if not value]

if missing:
    raise RuntimeError(
        "متغيرات البيئة الناقصة: " + ", ".join(missing)
    )


# =========================
# العملاء
# =========================

userbot = Client(
    "barq_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
)

helper_bot = Client(
    "barq_helper_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)


# =========================
# الذاكرة ومنع التكرار
# =========================

seen_messages = TTLCache(maxsize=20000, ttl=CACHE_TTL)

ai_semaphore = asyncio.Semaphore(5)
send_semaphore = asyncio.Semaphore(10)

locks = {}
locks_guard = asyncio.Lock()

http_session = None


# =========================
# فحص Render
# =========================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )
        self.end_headers()
        self.wfile.write(
            "Barq Pure AI System Active!".encode("utf-8")
        )

    def log_message(self, format, *args):
        pass


def start_health_server():
    server = ThreadingHTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    threading.Thread(
        target=server.serve_forever,
        daemon=True
    ).start()

    logger.info("Health server running on port %s", PORT)


# =========================
# تعليمات الذكاء الاصطناعي
# =========================

SYSTEM_PROMPT = """
أنت نظام ذكاء اصطناعي متخصص في اكتشاف طلبات التوصيل
والمشاوير في جازان والمنطقة الجنوبية في السعودية.

مهمتك تحديد هل الرسالة تمثل شخصاً يبحث عن خدمة
أو مندوب أو سائق، أم أنها إعلان من شخص يعرض خدماته.

أجب برقم واحد فقط:

1 = طلب حقيقي من عميل يبحث عن:
- مندوب توصيل أو توصيل طلبات.
- سائق أو مشوار أو سيارة.
- شخص يوصل غرضاً أو طلباً.
- وسيلة نقل أو توصيلة إلى مكان.
- استفسار عن مندوب أو سائق متاح.
- طلب ترشيح أو رقم مندوب أو سائق.
- رد أو متابعة مرتبطة بطلب خدمة حقيقي.

0 = أي شيء آخر، ومنه:
- إعلان سائق أو مندوب يعرض خدماته.
- شخص يقول إنه متفرغ ويبحث عن زبائن.
- عروض وأسعار وتسويق للخدمات.
- إعلانات تجارية لا تبحث عن خدمة.
- دردشة عامة أو كلام غير متعلق بطلب خدمة.

افهم اللهجة السعودية والجازانية والمعنى المقصود،
ولا تعتمد على كلمات مفتاحية منفردة.

إذا كانت الرسالة رداً على رسالة سابقة،
افهم سياقها قدر الإمكان.

لا تخمّن وجود طلب إذا لم يكن واضحاً.
أخرج 1 أو 0 فقط دون أي شرح.
"""


# =========================
# تجهيز النص والبصمة
# =========================

def get_message_text(message):
    return (
        message.text or message.caption or ""
    ).strip()


def normalize_text(text):
    text = text.lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    text = re.sub(r"[ـ]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def make_fingerprint(text):
    normalized = normalize_text(text)

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


# =========================
# الذكاء الاصطناعي
# =========================

async def classify_message(text):
    global http_session

    if not http_session or http_session.closed:
        logger.error("HTTP session is not available")
        return None

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://barq-jazan.com",
        "X-Title": "Barq Jazan AI",
    }

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": text[:2500]
            },
        ],
        "temperature": 0,
        "max_tokens": 5,
        "stream": False,
    }

    for attempt in range(2):
        try:
            async with ai_semaphore:
                async with http_session.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as response:

                    if response.status != 200:
                        error_text = await response.text()

                        logger.error(
                            "OpenRouter error %s: %s",
                            response.status,
                            error_text[:500]
                        )
                        continue

                    data = await response.json()

            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )

            answer = str(content).strip()

            if answer.startswith("1"):
                return True

            if answer.startswith("0"):
                return False

            logger.warning(
                "Unexpected AI response: %s",
                answer[:100]
            )

        except asyncio.CancelledError:
            raise

        except Exception:
            logger.exception(
                "AI request failed (attempt %s)",
                attempt + 1
            )

            await asyncio.sleep(1)

    return None


# =========================
# منع تكرار الطلبات
# =========================

async def check_request(text, context=None):
    fingerprint = make_fingerprint(text)

    async with locks_guard:
        lock = locks.setdefault(
            fingerprint,
            asyncio.Lock()
        )

    try:
        async with lock:

            if fingerprint in seen_messages:
                logger.info("Duplicate message skipped")
                return False

            result = await classify_message(
                context or text
            )

            if result is None:
                return False

            seen_messages[fingerprint] = result

            return result

    finally:
        async with locks_guard:
            if not lock.locked():
                locks.pop(fingerprint, None)


# =========================
# أزرار الرسالة
# =========================

def build_buttons(message):
    buttons = []

    sender = message.from_user

    if sender:
        if sender.username:
            user_url = (
                f"https://t.me/{sender.username}"
            )
        else:
            user_url = f"tg://user?id={sender.id}"

        buttons.append(
            InlineKeyboardButton(
                "💬 فتح المحادثة",
                url=user_url
            )
        )

    try:
        original_link = message.link
    except Exception:
        original_link = None

    if original_link:
        buttons.append(
            InlineKeyboardButton(
                "📩 الرسالة الأصلية",
                url=original_link
            )
        )

    if not buttons:
        return None

    return InlineKeyboardMarkup([buttons])


# =========================
# إرسال الطلبات
# =========================

async def send_to_one(target, text, keyboard):

    async with send_semaphore:

        try:
            await helper_bot.send_message(
                chat_id=target,
                text=text,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

            logger.info(
                "Sent to %s using helper bot",
                target
            )

            return True

        except Exception as bot_error:

            logger.warning(
                "Helper bot could not send to %s: %s",
                target,
                str(bot_error)[:200]
            )

        try:
            await userbot.send_message(
                chat_id=target,
                text=text,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

            logger.info(
                "Sent to %s using userbot",
                target
            )

            return True

        except Exception as user_error:

            logger.error(
                "Both sending methods failed for %s: %s",
                target,
                str(user_error)[:200]
            )

            return False


async def forward_to_subscribers(message, text):

    keyboard = build_buttons(message)

    outgoing_text = text[:MAX_MESSAGE_LENGTH]

    tasks = [
        send_to_one(target, outgoing_text, keyboard)
        for target in TARGET_USERS
    ]

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True
    )

    successful = sum(
        result is True for result in results
    )

    logger.info(
        "Forwarding completed: %s/%s recipients",
        successful,
        len(TARGET_USERS)
    )


# =========================
# مراقبة المجموعات والردود
# =========================

@userbot.on_message(
    filters.group & (filters.text | filters.caption)
)
async def monitor_groups(client, message):

    try:

        if message.outgoing:
            return

        text = get_message_text(message)

        if not text or len(text.strip()) < 3:
            return

        # تحليل الرد مع الرسالة الأصلية
        context = text

        try:
            replied = message.reply_to_message

            if replied:
                parent_text = get_message_text(replied)

                if parent_text:
                    context = (
                        f"الرسالة الأصلية:\n"
                        f"{parent_text}\n\n"
                        f"الرد عليها:\n{text}"
                    )

        except Exception:
            pass

        is_request = await check_request(
            text,
            context
        )

        if not is_request:
            return

        logger.info(
            "Genuine customer request detected"
        )

        await forward_to_subscribers(
            message,
            text
        )

    except asyncio.CancelledError:
        raise

    except Exception:
        logger.exception(
            "Error while processing a message"
        )


# =========================
# التشغيل والإغلاق
# =========================

async def main():

    global http_session

    start_health_server()

    http_session = aiohttp.ClientSession()

    try:

        logger.info("Starting Barq userbot...")
        await userbot.start()

        logger.info("Starting Barq helper bot...")
        await helper_bot.start()

        logger.info("Barq Pure AI System Active!")
        logger.info("AI Model: %s", MODEL)
        logger.info("Reply analysis: ENABLED")
        logger.info(
            "Subscribers: %s",
            len(TARGET_USERS)
        )

        await asyncio.Event().wait()

    finally:

        if http_session and not http_session.closed:
            await http_session.close()

        try:
            if helper_bot.is_connected:
                await helper_bot.stop()
        except Exception:
            logger.exception(
                "Error stopping helper bot"
            )

        try:
            if userbot.is_connected:
                await userbot.stop()
        except Exception:
            logger.exception(
                "Error stopping userbot"
            )


if __name__ == "__main__":
    asyncio.run(main())
