
import os
import asyncio
import logging
import hashlib
import time
import json
from collections import OrderedDict
from urllib.parse import quote

import aiohttp
from hydrogram import Client, filters, idle
from hydrogram.enums import ChatType
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait, RPCError

# =====================================================
# BARQ JAZAN - Hydrogram + OpenRouter
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("BARQ")

def env_required(*names):
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    raise RuntimeError("Missing environment variable: " + " / ".join(names))

API_ID = int(env_required("TELEGRAM_API_ID", "API_ID"))
API_HASH = env_required("TELEGRAM_API_HASH", "API_HASH")
SESSION_STRING = env_required("SESSION_STRING")
BOT_TOKEN = env_required("BOT_TOKEN")
OPENROUTER_API_KEY = env_required("OPENROUTER_API_KEY")

TARGET = os.getenv("TARGET_USERNAME", "abood1317").lstrip("@")
MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

# ضع WORKER فقط في Render Background Worker.
# لا تستخدم نسختين من هذا البرنامج في الوقت نفسه بنفس الجلسة.

userbot = Client(
    "barq_user",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    no_updates=False,
    workers=8,
)

bot = Client(
    "barq_helper",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    no_updates=False,
    workers=4,
)

# =====================================================
# Deduplication
# =====================================================

seen = OrderedDict()
SEEN_TTL = 6 * 60 * 60
SEEN_MAX = 30000

def seen_before(key):
    now = time.time()

    while seen:
        _, ts = next(iter(seen.items()))
        if now - ts < SEEN_TTL:
            break
        seen.popitem(last=False)

    if key in seen:
        return True

    seen[key] = now

    while len(seen) > SEEN_MAX:
        seen.popitem(last=False)

    return False

def message_key(message):
    # هوية الرسالة الأصلية: تمنع التكرار عند ظهورها
    # في أكثر من مجموعة إذا كانت الرسالة معاد توجيهها.
    if message.forward_date and message.forward_from_chat:
        return (
            f"fwd:{message.forward_from_chat.id}:"
            f"{message.forward_from_message_id}"
        )

    text = (message.text or message.caption or "").strip()
    if not text:
        return None

    # النص المتطابق يُعالج مرة واحدة خلال مدة الاحتفاظ.
    normalized = " ".join(text.lower().split())
    digest = hashlib.sha256(normalized.encode()).hexdigest()
    return "text:" + digest

# =====================================================
# Message queue
# =====================================================

queue = asyncio.Queue(maxsize=1000)
http_session = None

# =====================================================
# Original message link
# =====================================================

def original_url(message):
    chat = message.chat
    msg_id = message.id

    if chat.username:
        return f"https://t.me/{chat.username}/{msg_id}"

    # روابط المجموعات الخاصة قد تعمل فقط للأعضاء
    # الذين يملكون صلاحية الوصول إلى المجموعة.
    chat_id = str(chat.id)
    if chat_id.startswith("-100"):
        internal_id = chat_id[4:]
        return f"https://t.me/c/{internal_id}/{msg_id}"

    return None

# =====================================================
# OpenRouter classification
# =====================================================

async def classify(text):
    global http_session

    payload = {
        "model": MODEL,
        "temperature": 0,
        "max_tokens": 8,
        "messages": [
            {
                "role": "system",
                "content": (
                    "صنّف الرسالة إلى طلب عميل حقيقي أو غير ذلك. "
                    "YES فقط إذا كان شخص يطلب توصيلًا أو مشوارًا "
                    "أو مندوبًا لنقل شيء. يشمل الطلبات باللهجة "
                    "السعودية وجازان. "
                    "NO للإعلانات التي ينشرها السائقون أو المناديب "
                    "للبحث عن عمل، والعروض التجارية، والمحادثات "
                    "العادية، والرسائل غير الواضحة. "
                    "لا تعتبر وجود رقم هاتف وحده دليلًا على طلب. "
                    "أخرج YES أو NO فقط."
                ),
            },
            {"role": "user", "content": text[:6000]},
        ],
    }

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "X-Title": "Barq Jazan",
    }

    async with http_session.post(
        url, headers=headers, json=payload
    ) as response:
        raw = await response.text()

        if response.status != 200:
            log.error("OpenRouter HTTP %s: %s", response.status, raw[:700])
            return False

        try:
            data = json.loads(raw)
            answer = data["choices"][0]["message"]["content"]
            answer = answer.strip().upper()
            log.info("AI result: %s", answer[:30])
            return answer.startswith("YES")
        except (ValueError, KeyError, IndexError, TypeError):
            log.exception("Invalid OpenRouter response")
            return False

# =====================================================
# Listener: log immediately, then enqueue
# =====================================================

@userbot.on_message(filters.group, group=0)
async def group_listener(client, message):
    try:
        chat = message.chat

        if chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
            return

        text = (message.text or message.caption or "").strip()
        if not text:
            log.info(
                "GROUP MESSAGE WITHOUT TEXT | chat_id=%s | message_id=%s",
                chat.id, message.id
            )
            return

        log.info(
            "MESSAGE RECEIVED | chat_id=%s | type=%s | message_id=%s",
            chat.id, chat.type, message.id
        )

        key = message_key(message)
        if not key:
            return

        if seen_before(key):
            log.info("DUPLICATE SKIPPED | message_id=%s", message.id)
            return

        item = {
            "text": text,
            "key": key,
            "message": message,
        }

        try:
            queue.put_nowait(item)
            log.info("QUEUED | queue_size=%s", queue.qsize())
        except asyncio.QueueFull:
            log.error("QUEUE FULL: message not queued")

    except Exception:
        log.exception("GROUP LISTENER FAILED")

# =====================================================
# Worker: AI + delivery
# =====================================================

async def process_queue():
    while True:
        item = await queue.get()

        try:
            text = item["text"]
            message = item["message"]

            log.info("AI START | message_id=%s", message.id)

            try:
                matched = await asyncio.wait_for(
                    classify(text), timeout=45
                )
            except asyncio.TimeoutError:
                log.error("AI TIMEOUT | message_id=%s", message.id)
                continue
            except Exception:
                log.exception("AI REQUEST FAILED")
                continue

            if not matched:
                log.info("IGNORED BY AI | message_id=%s", message.id)
                continue

            buttons = []
            url = original_url(message)

            if url:
                buttons.append(
                    InlineKeyboardButton(
                        "📩 الرسالة الأصلية",
                        url=url,
                    )
                )

            buttons.append(
                InlineKeyboardButton(
                    "💬 فتح المحادثة",
                    url=f"https://t.me/{TARGET}",
                )
            )

            keyboard = InlineKeyboardMarkup([buttons])

            await bot.send_message(
                chat_id=TARGET,
                text="📦 طلب توصيل أو مشوار جديد\n\n" + text[:3800],
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )

            log.info(
                "DELIVERED | target=@%s | message_id=%s",
                TARGET, message.id
            )

        except FloodWait as e:
            delay = int(getattr(e, "value", 10))
            log.warning("FloodWait: waiting %s seconds", delay)
            await asyncio.sleep(delay)

        except RPCError:
            log.exception("TELEGRAM RPC ERROR")

        except Exception:
            log.exception("QUEUE PROCESSING FAILED")

        finally:
            queue.task_done()

# =====================================================
# Startup
# =====================================================

async def main():
    global http_session

    log.info("Starting Barq...")

    timeout = aiohttp.ClientTimeout(total=40)
    http_session = aiohttp.ClientSession(timeout=timeout)

    await userbot.start()
    log.info("USERBOT STARTED")

    me = await userbot.get_me()
    log.info(
        "USERBOT AUTHENTICATED | id=%s | username=%s",
        me.id, me.username
    )

    await bot.start()
    log.info("HELPER BOT STARTED")

    bot_me = await bot.get_me()
    log.info("HELPER BOT AUTHENTICATED | id=%s", bot_me.id)

    # فحص الإرسال للمستلم
    try:
        await bot.send_message(
            TARGET,
            "✅ برق جازان: اختبار تشغيل البوت المساعد."
        )
        log.info("RECIPIENT TEST SENT")
    except Exception:
        log.exception(
            "RECIPIENT TEST FAILED: open the helper bot first "
            "and press Start"
        )

    worker_task = asyncio.create_task(process_queue())

    log.info(
        "MONITOR READY | groups=%s | AI=%s",
        "GROUP + SUPERGROUP", MODEL
    )

    try:
        await idle()
    finally:
        worker_task.cancel()
        await asyncio.gather(worker_task, return_exceptions=True)

        if http_session and not http_session.closed:
            await http_session.close()

        await bot.stop()
        await userbot.stop()
        log.info("BARQ STOPPED")

if __name__ == "__main__":
    asyncio.run(main())
