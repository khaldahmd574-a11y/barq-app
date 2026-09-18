import os
import asyncio
import hashlib
import threading
from collections import deque
from http.server import HTTPServer, BaseHTTPRequestHandler

from groq import Groq
from hydrogram import Client
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait


# =========================================================
# الإعدادات
# =========================================================

API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()

PORT = int(os.getenv("PORT", "10000"))

TARGET_USERS = [
    "@shaybq",
    "@Waaaaaaa33",
    "@abood1317",
]

# =========================================================
# مفاتيح Groq
# =========================================================

GROQ_KEYS = []

for name in [
    "GROQ_API_KEY_1",
    "GROQ_API_KEY_2",
    "GROQ_API_KEY_3",
    "GROQ_API_KEY",
]:
    value = os.getenv(name, "").strip()

    if value and value not in GROQ_KEYS:
        GROQ_KEYS.append(value)

if not GROQ_KEYS:
    raise RuntimeError(
        "لم يتم العثور على أي Groq API Key."
    )

# موديل سريع للتصنيف
GROQ_MODEL = "openai/gpt-oss-20b"

groq_clients = [
    Groq(api_key=key)
    for key in GROQ_KEYS
]

current_groq_index = 0
groq_rotation_lock = asyncio.Lock()

# =========================================================
# منع الضغط على Groq
# =========================================================

AI_CONCURRENCY = 5

ai_semaphore = asyncio.Semaphore(
    AI_CONCURRENCY
)

# =========================================================
# منع التكرار
# =========================================================

SEEN_LIMIT = 5000

seen_hashes = set()
seen_queue = deque(maxlen=SEEN_LIMIT)

seen_lock = asyncio.Lock()


# =========================================================
# التحقق من الإعدادات
# =========================================================

if not API_ID:
    raise RuntimeError(
        "TELEGRAM_API_ID غير موجود."
    )

if not API_HASH:
    raise RuntimeError(
        "TELEGRAM_API_HASH غير موجود."
    )

if not SESSION_STRING:
    raise RuntimeError(
        "SESSION_STRING غير موجود."
    )


# =========================================================
# Dummy HTTP Server
# =========================================================

class DummyHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )

        self.end_headers()

        self.wfile.write(
            b"Barq Free Groq AI Active 24/7!"
        )

    def do_HEAD(self):
        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8"
        )

        self.end_headers()

    def log_message(self, format, *args):
        return


def start_web_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        DummyHandler
    )

    print(
        f"[WEB] Server running on port {PORT}"
    )

    server.serve_forever()


threading.Thread(
    target=start_web_server,
    daemon=True
).start()


# =========================================================
# بصمة الرسالة
# =========================================================

def make_fingerprint(text):

    normalized = " ".join(
        text.strip().lower().split()
    )

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


async def already_seen(text):

    fingerprint = make_fingerprint(text)

    async with seen_lock:

        if fingerprint in seen_hashes:
            return True

        if len(seen_queue) >= SEEN_LIMIT:

            old = seen_queue.popleft()

            seen_hashes.discard(old)

        seen_queue.append(fingerprint)

        seen_hashes.add(fingerprint)

        return False


# =========================================================
# تدوير مفاتيح Groq
# =========================================================

async def get_groq_client():

    global current_groq_index

    async with groq_rotation_lock:

        index = (
            current_groq_index
            % len(groq_clients)
        )

        return (
            index,
            groq_clients[index]
        )


async def rotate_groq():

    global current_groq_index

    async with groq_rotation_lock:

        current_groq_index = (
            current_groq_index + 1
        ) % len(groq_clients)

        print(
            "[GROQ] Rotated key -> "
            f"{current_groq_index + 1}/"
            f"{len(groq_clients)}"
        )


# =========================================================
# الذكاء الاصطناعي
# =========================================================

AI_SYSTEM_PROMPT = """
أنت مصنف ذكي لرسائل مجموعات عامة.

اقرأ الرسالة كاملة وافهم معناها وسياقها، ولا تعتمد على البحث عن كلمات محددة أو قائمة كلمات.

المطلوب منك تحديد شيء واحد فقط:

هل الرسالة كتبها شخص يبحث فعلياً عن شخص آخر يقدم له خدمة نقل أو توصيل أو مشوار؟

اعتبر الرسالة YES عندما يكون المعنى العام أن صاحب الرسالة يريد الحصول على سائق أو مندوب أو وسيلة نقل أو شخص ينفذ له توصيلاً أو مشواراً، حتى لو استخدم أسلوباً غير مباشر أو عامياً أو مختصراً أو احتوى النص على أخطاء إملائية.

اعتبر الرسالة NO عندما يكون صاحب الرسالة يقدم خدمة القيادة أو التوصيل بنفسه، أو يعلن عن توفره، أو يبحث عن عملاء، أو ينشر إعلاناً تجارياً، أو يتحدث مع الآخرين، أو يرسل تحية، أو يسأل سؤالاً عاماً، أو تكون الرسالة غير مرتبطة بطلب خدمة نقل أو توصيل.

لا تعتمد على وجود كلمة معينة.
لا تستخدم قائمة كلمات.
لا تستخدم أسماء مدن أو أحياء كشرط.
افهم النية من السياق والمعنى.

إذا كان من الواضح أن الشخص يريد الخدمة من شخص آخر:
YES

إذا كان من الواضح أنه يقدم الخدمة أو أن الرسالة ليست طلب عميل:
NO

إذا لم تكن متأكداً وكان النص لا يوضح وجود طلب خدمة حقيقي:
NO

أخرج نتيجة واحدة فقط.

YES
أو
NO

ممنوع كتابة أي شرح.
ممنوع كتابة أي مقدمات.
ممنوع JSON.
ممنوع علامات إضافية.
"""


async def ask_groq(text):

    if not text:
        return False

    # حد أقصى لحجم النص المرسل للذكاء الاصطناعي
    if len(text) > 6000:
        text = text[:6000]

    async with ai_semaphore:

        total_attempts = len(groq_clients)

        for attempt in range(total_attempts):

            index, client = await get_groq_client()

            try:

                def request():

                    return client.chat.completions.create(

                        model=GROQ_MODEL,

                        messages=[
                            {
                                "role": "system",
                                "content": AI_SYSTEM_PROMPT
                            },
                            {
                                "role": "user",
                                "content": text
                            }
                        ],

                        temperature=0,

                        max_completion_tokens=5,

                        reasoning_effort="low",

                        reasoning_format="hidden"
                    )

                response = await asyncio.to_thread(
                    request
                )

                answer = (
                    response
                    .choices[0]
                    .message
                    .content
                    or ""
                )

                answer = answer.strip().upper()

                print(
                    f"[AI] Key {index + 1} -> "
                    f"{answer}"
                )

                if answer == "YES":
                    return True

                if answer == "NO":
                    return False

                # لو رجع مثلاً:
                # YES\n
                # نأخذ أول جزء
                first = answer.split()[0] if answer else ""

                if first == "YES":
                    return True

                if first == "NO":
                    return False

                print(
                    "[AI] Invalid response -> NO"
                )

                return False

            except Exception as error:

                status = getattr(
                    error,
                    "status_code",
                    None
                )

                error_text = str(error)

                print(
                    "[GROQ ERROR]"
                    f" key={index + 1}"
                    f" status={status}"
                    f" {error_text[:300]}"
                )

                # Rate Limit
                if (
                    status == 429
                    or "rate limit"
                    in error_text.lower()
                    or "429" in error_text
                ):

                    await rotate_groq()

                    await asyncio.sleep(0.5)

                    continue

                # أخطاء مؤقتة
                if (
                    status in [500, 502, 503, 504]
                    or "timeout"
                    in error_text.lower()
                    or "connection"
                    in error_text.lower()
                ):

                    await rotate_groq()

                    await asyncio.sleep(0.5)

                    continue

                # أي خطأ آخر
                return False

        print(
            "[GROQ] All API keys failed."
        )

        return False


# =========================================================
# Userbot
# =========================================================

userbot = Client(

    name="barq_userbot",

    api_id=API_ID,

    api_hash=API_HASH,

    session_string=SESSION_STRING
)


# =========================================================
# معلومات صاحب الرسالة
# =========================================================

def get_sender(message):

    user = getattr(
        message,
        "from_user",
        None
    )

    if not user:
        return None, None, None

    username = getattr(
        user,
        "username",
        None
    )

    user_id = getattr(
        user,
        "id",
        None
    )

    first_name = (
        getattr(
            user,
            "first_name",
            None
        )
        or ""
    )

    last_name = (
        getattr(
            user,
            "last_name",
            None
        )
        or ""
    )

    name = (
        f"{first_name} {last_name}"
    ).strip()

    return (
        username,
        user_id,
        name
    )


# =========================================================
# اسم المجموعة
# =========================================================

def get_chat_name(message):

    chat = getattr(
        message,
        "chat",
        None
    )

    if not chat:
        return "غير معروف"

    title = getattr(
        chat,
        "title",
        None
    )

    if title:
        return title

    username = getattr(
        chat,
        "username",
        None
    )

    if username:
        return f"@{username}"

    return "غير معروف"


# =========================================================
# رابط حساب العميل
# =========================================================

def get_user_link(
    username,
    user_id
):

    if username:

        return (
            f"https://t.me/{username}"
        )

    if user_id:

        return (
            f"tg://user?id={user_id}"
        )

    return None


# =========================================================
# رابط الرسالة الأصلية
# =========================================================

def get_message_link(message):

    try:

        link = getattr(
            message,
            "link",
            None
        )

        if link:
            return link

    except Exception:
        pass

    return None


# =========================================================
# أزرار الرسالة
# =========================================================

def make_buttons(message):

    username, user_id, name = get_sender(
        message
    )

    buttons = []

    user_link = get_user_link(
        username,
        user_id
    )

    if user_link:

        buttons.append(
            InlineKeyboardButton(
                "👤 محادثة العميل",
                url=user_link
            )
        )

    message_link = get_message_link(
        message
    )

    if message_link:

        buttons.append(
            InlineKeyboardButton(
                "🔗 الرسالة الأصلية",
                url=message_link
            )
        )

    if not buttons:
        return None

    return InlineKeyboardMarkup(
        [
            buttons
        ]
    )


# =========================================================
# الرسالة التي تصل للمستلمين
# =========================================================

def make_forward_text(message):

    text = (
        getattr(
            message,
            "text",
            None
        )
        or getattr(
            message,
            "caption",
            None
        )
        or ""
    ).strip()

    username, user_id, name = get_sender(
        message
    )

    if username:

        sender = f"@{username}"

    elif name:

        sender = name

    elif user_id:

        sender = str(user_id)

    else:

        sender = "غير معروف"

    chat_name = get_chat_name(
        message
    )

    return (
        "🚕 طلب عميل\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 العميل: {sender}\n"
        f"💬 المصدر: {chat_name}\n"
        "━━━━━━━━━━━━━━\n"
        f"{text}"
    )


# =========================================================
# إرسال لمستلم واحد
# =========================================================

async def send_one(
    target,
    text,
    buttons
):

    try:

        await userbot.send_message(

            chat_id=target,

            text=text,

            reply_markup=buttons,

            disable_web_page_preview=True
        )

        print(
            f"[SENT] {target}"
        )

        return True

    except FloodWait as error:

        seconds = int(
            getattr(
                error,
                "value",
                5
            )
        )

        print(
            f"[FLOODWAIT] "
            f"{target} -> {seconds}s"
        )

        await asyncio.sleep(
            seconds
        )

        try:

            await userbot.send_message(

                chat_id=target,

                text=text,

                reply_markup=buttons,

                disable_web_page_preview=True
            )

            print(
                f"[SENT] {target} after wait"
            )

            return True

        except Exception as retry_error:

            print(
                f"[SEND ERROR] "
                f"{target}: {retry_error}"
            )

            return False

    except Exception as error:

        print(
            f"[SEND ERROR] "
            f"{target}: {error}"
        )

        return False


# =========================================================
# إرسال للجميع
# =========================================================

async def send_to_targets(
    text,
    buttons
):

    tasks = []

    for target in TARGET_USERS:

        tasks.append(
            send_one(
                target,
                text,
                buttons
            )
        )

    results = await asyncio.gather(
        *tasks,
        return_exceptions=True
    )

    successful = sum(
        1
        for result in results
        if result is True
    )

    print(
        f"[DELIVERY] "
        f"{successful}/{len(TARGET_USERS)}"
    )


# =========================================================
# المستمع المباشر
# =========================================================

@userbot.on_message()
async def on_new_message(
    client,
    message
):

    try:

        # ---------------------------------------------
        # تجاهل رسائل الحساب نفسه
        # ---------------------------------------------

        if getattr(
            message,
            "outgoing",
            False
        ):
            return

        # ---------------------------------------------
        # تجاهل رسائل الخدمة
        # ---------------------------------------------

        if getattr(
            message,
            "service",
            False
        ):
            return

        # ---------------------------------------------
        # استخراج النص
        # ---------------------------------------------

        text = (
            getattr(
                message,
                "text",
                None
            )
            or getattr(
                message,
                "caption",
                None
            )
            or ""
        ).strip()

        if not text:
            return

        # ---------------------------------------------
        # منع النصوص العملاقة
        # ---------------------------------------------

        if len(text) > 10000:

            print(
                "[SKIP] Message too long"
            )

            return

        # ---------------------------------------------
        # منع التكرار
        # ---------------------------------------------

        if await already_seen(text):

            print(
                "[DUPLICATE] Skipped"
            )

            return

        # ---------------------------------------------
        # تسجيل الرسالة
        # ---------------------------------------------

        chat_name = get_chat_name(
            message
        )

        print(
            "\n[NEW MESSAGE]"
        )

        print(
            f"[SOURCE] {chat_name}"
        )

        print(
            f"[TEXT] {text[:300]}"
        )

        # ---------------------------------------------
        # AI
        # ---------------------------------------------

        is_request = await ask_groq(
            text
        )

        # ---------------------------------------------
        # NO
        # ---------------------------------------------

        if not is_request:

            print(
                "[RESULT] NO"
            )

            return

        # ---------------------------------------------
        # YES
        # ---------------------------------------------

        print(
            "[RESULT] YES -> SEND"
        )

        forward_text = make_forward_text(
            message
        )

        buttons = make_buttons(
            message
        )

        await send_to_targets(
            forward_text,
            buttons
        )

    except Exception as error:

        print(
            "[HANDLER ERROR]"
            f" {type(error).__name__}: "
            f"{error}"
        )


# =========================================================
# بدء التشغيل
# =========================================================

async def startup():

    print()
    print("=" * 60)
    print("🚕 BARQ AI TELEGRAM USERBOT")
    print("=" * 60)

    print(
        f"🤖 Groq Model: {GROQ_MODEL}"
    )

    print(
        f"🔑 Groq Keys: {len(GROQ_KEYS)}"
    )

    print(
        "🧠 AI Classification: ENABLED"
    )

    print(
        "🔤 Keyword Filtering: DISABLED"
    )

    print(
        "📍 Location Keywords: DISABLED"
    )

    print(
        "🔎 Periodic Group Scanning: DISABLED"
    )

    print(
        "📡 Direct on_message Listener: ENABLED"
    )

    print(
        "👥 Targets:"
    )

    for user in TARGET_USERS:

        print(
            f"   - {user}"
        )

    print("=" * 60)
    print()


# =========================================================
# تشغيل Userbot
# =========================================================

if __name__ == "__main__":

    asyncio.run(
        startup()
    )

    print(
        "[SYSTEM] Starting Hydrogram..."
    )

    userbot.run()
