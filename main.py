
import os
import asyncio
import logging
import hashlib
import time
import json

from collections import OrderedDict

import aiohttp
from hydrogram import Client, filters, idle
from hydrogram.enums import ChatType
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait, RPCError

# =========================
# Logging
# =========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("Barq")

# =========================
# Environment
# =========================

def required_env(name):
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"متغير البيئة مفقود: {name}")
    return value


API_ID = int(required_env("API_ID"))
API_HASH = required_env("API_HASH")
SESSION_STRING = required_env("SESSION_STRING")
BOT_TOKEN = required_env("BOT_TOKEN")
OPENROUTER_API_KEY = required_env("OPENROUTER_API_KEY")

# معرّف حساب المستلم
TARGET_USERNAME = "abood1317"

MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openai/gpt-4o-mini"
)

# =========================
# Clients
# =========================

userbot = Client(
    name="barq_user",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    no_updates=False,
)

bot = Client(
    name="barq_helper",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
)

# =========================
# Deduplication
# =========================

seen = OrderedDict()
SEEN_TTL = 6 * 60 * 60
MAX_SEEN = 20000


def is_duplicate(key):
    now = time.time()

    while seen:
        first_key, first_time = next(iter(seen.items()))
        if now - first_time <= SEEN_TTL:
            break
        seen.pop(first_key, None)

    if key in seen:
        seen.move_to_end(key)
        return True

    seen[key] = now

    while len(seen) > MAX_SEEN:
        seen.popitem(last=False)

    return False


def fingerprint(message):
    # إزالة التكرار عبر المجموعات اعتمادًا على نص الرسالة
    text = (message.text or message.caption or "").strip()
    if not text:
        return None

    normalized = " ".join(text.lower().split())
    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


# =========================
# AI classification
# =========================

async def classify_request(text):
    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://barq.example",
        "X-Title": "Barq Jazan Requests",
    }

    payload = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": 10,
        "messages": [
            {
                "role": "system",
                "content": (
                    "أنت مصنف رسائل لمجموعة طلبات توصيل ومشاوير "
                    "في جازان وجنوب السعودية. "
                    "أجب YES فقط إذا كانت الرسالة من عميل يطلب "
                    "توصيلة أو مشواراً أو مندوب توصيل لطلب فعلي. "
                    "أجب NO إذا كانت إعلان سائق أو مندوب يبحث عن "
                    "عمل، أو إعلاناً تجارياً، أو رسالة عادية، "
                    "أو إعادة نشر لطلب غير واضح. "
                    "افهم المعنى والسياق، ولا تعتمد على وجود "
                    "رقم هاتف وحده. أجب بكلمة YES أو NO فقط."
                ),
            },
            {"role": "user", "content": text[:6000]},
        ],
    }

    timeout = aiohttp.ClientTimeout(total=35)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            url, headers=headers, json=payload
        ) as response:
            body = await response.text()

            if response.status != 200:
                log.error(
                    "OpenRouter HTTP %s: %s",
                    response.status, body[:500]
                )
                return False

            data = json.loads(body)
            result = (
                data["choices"][0]["message"]["content"]
                .strip()
                .upper()
            )

            log.info("AI classification: %s", result[:30])
            return result.startswith("YES")


# =========================
# Receive messages
# =========================

@userbot.on_message(filters.group)
async def monitor_groups(client, message):
    try:
        chat = message.chat

        if chat.type not in (
            ChatType.GROUP,
            ChatType.SUPERGROUP,
        ):
            return

        text = (message.text or message.caption or "").strip()
        if not text:
            return

        # لا تعالج رسائل المجموعات الفارغة
        log.info(
            "MESSAGE RECEIVED | chat_id=%s | type=%s | chars=%s",
            chat.id, chat.type, len(text)
        )

        key = fingerprint(message)
        if not key:
            return

        if is_duplicate(key):
            log.info("Duplicate skipped")
            return

        try:
            matched = await classify_request(text)
        except asyncio.TimeoutError:
            log.warning("OpenRouter request timed out")
            return
        except Exception:
            log.exception("AI classification failed")
            return

        if not matched:
            log.info("Not a customer request")
            return

        # لا تعرض اسم المجموعة أو رابطها في الرسالة المرسلة
        original = text[:3900]

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "💬 فتح المحادثة",
                    url="https://t.me/" + TARGET_USERNAME
                )
            ]
        ])

        await bot.send_message(
            chat_id=TARGET_USERNAME,
            text="📦 طلب توصيل أو مشوار جديد\n\n" + original,
            reply_markup=keyboard,
            disable_web_page_preview=True,
        )

        log.info("Forwarded to @%s", TARGET_USERNAME)

    except FloodWait as e:
        log.warning("FloodWait: %s seconds", e.value)
        await asyncio.sleep(e.value)
    except RPCError:
        log.exception("Telegram RPC error")
    except Exception:
        log.exception("Unhandled message handler error")


# =========================
# Startup
# =========================

async def main():
    log.info("Starting Barq clients...")

    await userbot.start()
    log.info("USERBOT STARTED")

    try:
        me = await userbot.get_me()
        log.info(
            "USERBOT AUTHENTICATED | id=%s | username=%s",
            me.id, me.username
        )

        await bot.start()
        log.info("HELPER BOT STARTED")

        bot_me = await bot.get_me()
        log.info("HELPER BOT ID=%s", bot_me.id)

        # اختبار إمكانية إرسال رسالة إلى المستلم
        try:
            await bot.send_message(
                TARGET_USERNAME,
                "✅ برق: اختبار تشغيل البوت المساعد. "
                "إذا وصلتك هذه الرسالة، فالإرسال يعمل."
            )
            log.info("Recipient test message sent")
        except Exception:
            log.exception(
                "Cannot message recipient. "
                "Make sure @abood1317 has opened the helper bot."
            )

        log.info(
            "MONITOR READY: waiting for group messages"
        )

        await idle()

    finally:
        await bot.stop()
        await userbot.stop()
        log.info("Clients stopped")


if __name__ == "__main__":
    asyncio.run(main())
