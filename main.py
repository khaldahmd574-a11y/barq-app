# -*- coding: utf-8 -*-
"""
بوت مراقبة طلبات التوصيل والمشاوير - جازان
- استماع فوري عبر on_message + نبضة حياة كل 2 ثانية (Hydrogram)
- تحليل الرسائل عبر OpenRouter
- إرسال الطلبات المقبولة للحسابات المستهدفة بأزرار تفاعلية
- DummyServer للتشغيل 24/7 على Render

المتطلبات (requirements.txt):
    hydrogram
    tgcrypto
    aiohttp

متغيرات البيئة:
    API_ID, API_HASH      : من my.telegram.org
    SESSION_STRING        : جلسة الحساب المراقب (يقرأ القروبات)
    BOT_TOKEN             : توكن بوت الإرسال (من @BotFather) - يرسل الأزرار
    OPENROUTER_API_KEY    : مفتاح OpenRouter
    OPENROUTER_MODEL      : (اختياري) الافتراضي google/gemini-3.1-flash-lite
    TARGET_USERS          : (اختياري) يوزرات المشتركين مفصولة بفواصل. الافتراضي: القائمة المضمّنة في الكود
    WATCH_CHATS           : (اختياري) آيدي القروبات للنبضة، مثال: -1001234,-1005678
                            إذا تُرك فارغاً: يستمع لكل القروبات عبر on_message فقط
    PORT                  : (يضبطه Render تلقائياً)

ملاحظة مهمة: كل مشترك لازم يكون ضغط /start على البوت (BOT_TOKEN) مرة واحدة
حتى يقدر البوت يرسل له. الأزرار (URL) لا تعمل من حساب مستخدم، لذلك الإرسال يتم عبر البوت.
"""

import asyncio
import hashlib
import html
import json
import logging
import os
import re
import time
from collections import OrderedDict

import aiohttp
from aiohttp import web
from hydrogram import Client, filters, idle
from hydrogram.errors import FloodWait, RPCError
from hydrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

# ───────────────────────── الإعدادات ─────────────────────────

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-3.1-flash-lite")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# ضع قائمة المشتركين هنا أو في متغير البيئة TARGET_IDS
DEFAULT_TARGET_IDS = [
    # 123456789,
    # 987654321,
]


def _parse_ids(raw: str) -> list[int]:
    return [int(x) for x in re.findall(r"-?\d+", raw or "")]


# قائمة المشتركين (يوزرات) من الكود القديم
DEFAULT_TARGET_USERS = [
    "abood1317",
    "Waaaaaaa33",
    "shaybq",
    "Ndhhyfvvjkcd",
    "fs_990",
    "Khaid3333",
    "anas14440",
]
_env_users = [u.strip().lstrip("@") for u in os.getenv("TARGET_USERS", "").split(",") if u.strip()]
TARGET_USERS: list[str] = _env_users or DEFAULT_TARGET_USERS
WATCH_CHATS: list[int] = _parse_ids(os.getenv("WATCH_CHATS", ""))
WATCH_SET = set(WATCH_CHATS)

HEARTBEAT_INTERVAL = 2.0     # ثواني
AI_CONCURRENCY = 5           # أقصى عدد طلبات AI بالتوازي
AI_TIMEOUT = 20              # ثواني
MIN_TEXT_LEN = 8
MAX_TEXT_LEN = 700
DEDUP_TTL = 120              # ثواني: منع تكرار نفس الطلب من نفس الشخص
SEEN_MAX = 5000              # حجم ذاكرة الرسائل المعالجة

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
log = logging.getLogger("jazan-bot")

# ───────────────────────── العملاء ─────────────────────────

user = Client(
    "watcher",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True,
)

bot = Client(
    "sender",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True,
)

http: aiohttp.ClientSession | None = None
ai_sem = asyncio.Semaphore(AI_CONCURRENCY)

# ───────────────────────── منع التكرار (بدون Queue) ─────────────────────────

_seen: "OrderedDict[tuple, float]" = OrderedDict()
_recent_text: dict[str, float] = {}
_last_seen_id: dict[int, int] = {}


def mark_seen(chat_id: int, msg_id: int) -> bool:
    """يرجع True إذا الرسالة جديدة (وتسجلها)، False إذا سبق معالجتها."""
    key = (chat_id, msg_id)
    if key in _seen:
        return False
    _seen[key] = time.time()
    while len(_seen) > SEEN_MAX:
        _seen.popitem(last=False)
    return True


def is_duplicate_text(sender_id: int, text: str) -> bool:
    now = time.time()
    for k in [k for k, t in _recent_text.items() if now - t > DEDUP_TTL]:
        _recent_text.pop(k, None)
    digest = hashlib.md5(f"{sender_id}:{text.strip()}".encode("utf-8")).hexdigest()
    if digest in _recent_text:
        return True
    _recent_text[digest] = now
    return False


# ───────────────────────── تحليل الذكاء الاصطناعي ─────────────────────────

SYSTEM_PROMPT = """أنت مصنّف رسائل لقروبات التوصيل والمشاوير في منطقة جازان (السعودية).
مهمتك: تحديد هل الرسالة هي طلب حقيقي من زبون يبحث عن سائق/توصيل/مشوار، أم لا.

اعتبرها طلب زبون (is_request = true) إذا كان كاتبها يطلب خدمة: توصيلة، مشوار، مشوار طلبات،
توصيل من وإلى مكان، مشوار مطار/مستشفى/جامعة/سوق، أو يسأل عن سائق متاح الآن.
افهم اللهجة الجازانية والعامية، مثل: "أبغى مشوار"، "مين فاضي"، "ودي توصيلة"، "محتاج سواق".

اعتبرها غير طلب (is_request = false) إذا كانت:
- إعلان سائق يعرض خدماته ("متواجد للتوصيل"، "اتصل بي"، "أسعار مناسبة").
- إعلان تجاري أو ترويج أو رابط أو دعوة قروب.
- سلام أو دردشة أو رد على أحد أو نقاش عام أو شكوى.
- رسالة غير مفهومة أو ليس فيها طلب خدمة.

أجب بصيغة JSON فقط وبدون أي نص إضافي:
{"is_request": true/false, "from_area": "نقطة الانطلاق أو فارغ", "to_area": "الوجهة أو فارغ", "reason": "سبب قصير جداً"}"""


def _extract_json(raw: str) -> dict | None:
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


async def classify(text: str) -> dict | None:
    """يرجع dict بنتيجة التحليل أو None عند الفشل."""
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": 200,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    async with ai_sem:
        for attempt in (1, 2):
            try:
                async with http.post(
                    OPENROUTER_URL,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=AI_TIMEOUT),
                ) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(1.5 * attempt)
                        continue
                    if resp.status != 200:
                        log.warning("OpenRouter HTTP %s: %s", resp.status, (await resp.text())[:200])
                        return None
                    data = await resp.json()
                    content = data["choices"][0]["message"]["content"]
                    result = _extract_json(content)
                    if isinstance(result, dict):
                        return result
                    log.warning("رد AI غير صالح: %s", str(content)[:150])
                    return None
            except asyncio.TimeoutError:
                log.warning("انتهت مهلة OpenRouter (محاولة %s)", attempt)
            except Exception as e:  # noqa: BLE001
                log.warning("خطأ OpenRouter: %s", e)
                return None
    return None


# ───────────────────────── الإرسال للمشتركين ─────────────────────────

def build_keyboard(message: Message) -> InlineKeyboardMarkup | None:
    rows = []
    sender = message.from_user
    if sender:
        if sender.username:
            chat_url = f"https://t.me/{sender.username}"
        else:
            chat_url = f"tg://user?id={sender.id}"
        rows.append([InlineKeyboardButton("💬 محادثة الزبون", url=chat_url)])
    try:
        link = message.link
        if link:
            rows.append([InlineKeyboardButton("📩 الرسالة الأصلية", url=link)])
    except Exception:  # noqa: BLE001
        pass
    return InlineKeyboardMarkup(rows) if rows else None


def build_text(message: Message, result: dict) -> str:
    sender = message.from_user
    name = html.escape(sender.first_name or "زبون") if sender else "زبون"
    group = html.escape(message.chat.title or "قروب")
    body = html.escape(message.text or "")

    lines = ["🚖 <b>طلب جديد</b>", ""]
    lines.append(f"👤 <b>الزبون:</b> {name}")
    lines.append(f"👥 <b>القروب:</b> {group}")
    from_area = (result.get("from_area") or "").strip()
    to_area = (result.get("to_area") or "").strip()
    if from_area:
        lines.append(f"📍 <b>من:</b> {html.escape(from_area)}")
    if to_area:
        lines.append(f"🏁 <b>إلى:</b> {html.escape(to_area)}")
    lines += ["", f"📝 {body}"]
    return "\n".join(lines)


def build_links_footer(message: Message) -> str:
    """روابط نصية تُستخدم عند الإرسال من حساب المستخدم (الأزرار غير مدعومة فيه)."""
    parts = []
    sender = message.from_user
    if sender:
        url = f"https://t.me/{sender.username}" if sender.username else f"tg://user?id={sender.id}"
        parts.append(f'<a href="{url}">💬 فتح المحادثة</a>')
    try:
        if message.link:
            parts.append(f'<a href="{message.link}">📩 الرسالة الأصلية</a>')
    except Exception:  # noqa: BLE001
        pass
    return "\n\n" + " | ".join(parts) if parts else ""


async def _try_send(client: Client, username: str, text: str, markup) -> bool:
    for _ in range(2):
        try:
            await client.send_message(
                username,
                text,
                reply_markup=markup,
                disable_web_page_preview=True,
            )
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value + 1)
        except RPCError as e:
            log.debug("تعذر الإرسال إلى @%s: %s", username, e)
            return False
        except Exception as e:  # noqa: BLE001
            log.debug("خطأ إرسال إلى @%s: %s", username, e)
            return False
    return False


async def send_to_target(username: str, text: str, markup, footer: str) -> None:
    # 1) عبر البوت مع الأزرار  2) إن فشل: عبر حساب المستخدم مع روابط نصية
    if await _try_send(bot, username, text, markup):
        return
    if await _try_send(user, username, text + footer, None):
        return
    log.warning("فشل الإرسال إلى @%s (تأكد أنه ضغط /start على البوت)", username)


async def broadcast(message: Message, result: dict) -> None:
    if not TARGET_USERS:
        log.warning("قائمة المشتركين فارغة!")
        return
    text = build_text(message, result)
    markup = build_keyboard(message)
    footer = build_links_footer(message)
    await asyncio.gather(*(send_to_target(u, text, markup, footer) for u in TARGET_USERS))
    log.info("تم إرسال الطلب إلى %s مشترك", len(TARGET_USERS))


# ───────────────────────── معالجة الرسائل ─────────────────────────

async def process_message(message: Message) -> None:
    try:
        if not message or not message.text or not message.chat:
            return
        if WATCH_SET and message.chat.id not in WATCH_SET:
            return
        sender = message.from_user
        if not sender or sender.is_bot or sender.is_self:
            return
        if message.reply_to_message_id:
            return
        if not mark_seen(message.chat.id, message.id):
            return

        text = message.text.strip()
        if not (MIN_TEXT_LEN <= len(text) <= MAX_TEXT_LEN):
            return
        if is_duplicate_text(sender.id, text):
            return

        result = await classify(text)
        if not result or not result.get("is_request"):
            return

        log.info("طلب مقبول من %s في %s", sender.id, message.chat.title)
        await broadcast(message, result)
    except Exception:  # noqa: BLE001
        log.exception("خطأ أثناء معالجة الرسالة")


@user.on_message(filters.group & filters.text & ~filters.me)
async def on_group_message(_, message: Message):
    # تشغيل المعالجة كمهمة مستقلة حتى لا يتأخر استقبال الرسائل التالية
    asyncio.create_task(process_message(message))


# ───────────────────────── نبضة الحياة ─────────────────────────

async def heartbeat() -> None:
    """
    كل 2 ثانية:
      1) ping خفيف للحفاظ على الاتصال حياً.
      2) إذا حددت WATCH_CHATS: يفحص آخر رسائل كل قروب لالتقاط أي رسالة
         فاتت على on_message (المنع من التكرار مضمون عبر mark_seen).
    """
    log.info("نبضة الحياة تعمل كل %.1f ثانية", HEARTBEAT_INTERVAL)
    while True:
        try:
            await user.get_me()

            for chat_id in WATCH_CHATS:
                msgs = []
                async for m in user.get_chat_history(chat_id, limit=5):
                    msgs.append(m)
                if not msgs:
                    continue
                msgs.sort(key=lambda m: m.id)
                last = _last_seen_id.get(chat_id)
                if last is None:
                    # أول مرة: نسجل آخر رسالة فقط بدون معالجة القديم
                    _last_seen_id[chat_id] = msgs[-1].id
                    for m in msgs:
                        mark_seen(chat_id, m.id)
                    continue
                for m in msgs:
                    if m.id > last:
                        asyncio.create_task(process_message(m))
                _last_seen_id[chat_id] = max(last, msgs[-1].id)

        except FloodWait as e:
            log.warning("FloodWait في النبضة: انتظار %s ثانية", e.value)
            await asyncio.sleep(e.value + 1)
        except Exception as e:  # noqa: BLE001
            log.warning("خطأ في النبضة: %s", e)
        await asyncio.sleep(HEARTBEAT_INTERVAL)


# ───────────────────────── DummyServer لـ Render ─────────────────────────

class DummyServer:
    def __init__(self, port: int):
        self.port = port
        self.runner: web.AppRunner | None = None

    async def _handle(self, _request: web.Request) -> web.Response:
        return web.Response(text="Bot is running ✅")

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/", self._handle)
        app.router.add_get("/health", self._handle)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await site.start()
        log.info("DummyServer يعمل على المنفذ %s", self.port)

    async def stop(self) -> None:
        if self.runner:
            await self.runner.cleanup()


# ───────────────────────── التشغيل ─────────────────────────

def check_config() -> None:
    missing = [
        n for n, v in {
            "API_ID": API_ID,
            "API_HASH": API_HASH,
            "SESSION_STRING": SESSION_STRING,
            "BOT_TOKEN": BOT_TOKEN,
            "OPENROUTER_API_KEY": OPENROUTER_API_KEY,
        }.items() if not v
    ]
    if missing:
        raise SystemExit(f"متغيرات ناقصة: {', '.join(missing)}")
    if not TARGET_USERS:
        log.warning("تنبيه: لا يوجد مشتركين في TARGET_USERS")


async def main() -> None:
    global http
    check_config()

    server = DummyServer(int(os.getenv("PORT", "8080")))
    await server.start()

    http = aiohttp.ClientSession()
    hb_task = None
    try:
        await user.start()
        await bot.start()
        me = await user.get_me()
        log.info("الحساب المراقب: %s (%s)", me.first_name, me.id)
        log.info("النموذج: %s | المشتركين: %s", OPENROUTER_MODEL, len(TARGET_USERS))

        hb_task = asyncio.create_task(heartbeat())
        await idle()
    finally:
        if hb_task:
            hb_task.cancel()
        for c in (user, bot):
            try:
                await c.stop()
            except Exception:  # noqa: BLE001
                pass
        await http.close()
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())
