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

API_ID = int(os.getenv("TELEGRAM_API_ID", "39120728"))
API_HASH = os.getenv("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4").strip()
SESSION_STRING = os.getenv("SESSION_STRING", "").strip()

PORT = int(os.getenv("PORT", "10000"))

# قائمة المستلمين (تم حذف @fs_990)
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
    GROQ_KEYS = ["gsk_dummy_key_for_deploy"]

GROQ_MODEL = "openai/gpt-oss-120b"

groq_clients = [Groq(api_key=key) for key in GROQ_KEYS]

current_groq_index = 0
groq_rotation_lock = asyncio.Lock()

# =========================================================
# منع الضغط والتحكم بالذاكرة
# =========================================================

AI_CONCURRENCY = 5
ai_semaphore = asyncio.Semaphore(AI_CONCURRENCY)

SEEN_LIMIT = 5000
seen_hashes = set()
seen_queue = deque(maxlen=SEEN_LIMIT)
seen_lock = asyncio.Lock()

# =========================================================
# Dummy HTTP Server
# =========================================================

class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Free Groq AI Active 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()

    def log_message(self, format, *args):
        return

def start_web_server():
    server = HTTPServer(("0.0.0.0", PORT), DummyHandler)
    print(f"[WEB] Server running on port {PORT}")
    server.serve_forever()

threading.Thread(target=start_web_server, daemon=True).start()

# =========================================================
# بصمة الرسالة ومنع التكرار
# =========================================================

def make_fingerprint(text):
    normalized = " ".join(text.strip().lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

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
        index = current_groq_index % len(groq_clients)
        return index, groq_clients[index]

async def rotate_groq():
    global current_groq_index
    async with groq_rotation_lock:
        current_groq_index = (current_groq_index + 1) % len(groq_clients)
        print(f"[GROQ] Rotated key -> {current_groq_index + 1}/{len(groq_clients)}")

# =========================================================
# الذكاء الاصطناعي
# =========================================================

AI_SYSTEM_PROMPT = """
أنت مصنف ذكي لرسائل مجموعات عامة.
المطلوب منك تحديد شيء واحد فقط:
هل الرسالة كتبها شخص يبحث فعلياً عن شخص آخر يقدم له خدمة نقل أو توصيل أو مشوار؟

اعتبر الرسالة YES عندما يكون المعنى العام أن صاحب الرسالة يريد الحصول على سائق أو مندوب أو وسيلة نقل.
اعتبر الرسالة NO عندما يكون صاحب الرسالة يقدم خدمة القيادة بنفسه، أو يعلن عن توفره، أو يبحث عن عملاء.

أخرج نتيجة واحدة فقط:
YES
أو
NO
ممنوع كتابة أي شرح أو مقدمات.
"""

async def ask_groq(text):
    if not text:
        return False

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
                            {"role": "system", "content": AI_SYSTEM_PROMPT},
                            {"role": "user", "content": text}
                        ],
                        temperature=0,
                        max_tokens=5,
                    )

                response = await asyncio.to_thread(request)
                answer = (response.choices[0].message.content or "").strip().upper()
                print(f"[AI] Key {index + 1} -> {answer}")

                if "YES" in answer:
                    return True
                if "NO" in answer:
                    return False

                return False

            except Exception as error:
                status = getattr(error, "status_code", None)
                error_text = str(error)
                print(f"[GROQ ERROR] key={index + 1} status={status} {error_text[:200]}")

                await rotate_groq()
                await asyncio.sleep(0.5)
                continue

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

def get_sender(message):
    user = getattr(message, "from_user", None)
    if not user:
        return None, None, None
    username = getattr(user, "username", None)
    user_id = getattr(user, "id", None)
    first_name = getattr(user, "first_name", None) or ""
    last_name = getattr(user, "last_name", None) or ""
    name = f"{first_name} {last_name}".strip()
    return username, user_id, name

def get_chat_name(message):
    chat = getattr(message, "chat", None)
    if not chat:
        return "غير معروف"
    title = getattr(chat, "title", None)
    if title:
        return title
    username = getattr(chat, "username", None)
    if username:
        return f"@{username}"
    return "غير معروف"

def get_user_link(username, user_id):
    if username:
        return f"https://t.me/{username}"
    if user_id:
        return f"tg://user?id={user_id}"
    return None

def get_message_link(message):
    try:
        link = getattr(message, "link", None)
        if link:
            return link
    except Exception:
        pass
    return None

def make_buttons(message):
    username, user_id, name = get_sender(message)
    buttons = []
    user_link = get_user_link(username, user_id)
    if user_link:
        buttons.append(InlineKeyboardButton("👤 محادثة العميل", url=user_link))

    message_link = get_message_link(message)
    if message_link:
        buttons.append(InlineKeyboardButton("🔗 الرسالة الأصلية", url=message_link))

    if not buttons:
        return None
    return InlineKeyboardMarkup([buttons])

def make_forward_text(message):
    text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
    username, user_id, name = get_sender(message)
    if username:
        sender = f"@{username}"
    elif name:
        sender = name
    elif user_id:
        sender = str(user_id)
    else:
        sender = "غير معروف"

    chat_name = get_chat_name(message)
    return (
        "🚕 طلب عميل\n"
        "━━━━━━━━━━━━━━\n"
        f"👤 العميل: {sender}\n"
        f"💬 المصدر: {chat_name}\n"
        "━━━━━━━━━━━━━━\n"
        f"{text}"
    )

async def send_one(target, text, buttons):
    try:
        await userbot.send_message(
            chat_id=target,
            text=text,
            reply_markup=buttons,
            disable_web_page_preview=True
        )
        print(f"[SENT] {target}")
        return True
    except FloodWait as error:
        seconds = int(getattr(error, "value", 5))
        await asyncio.sleep(seconds)
        try:
            await userbot.send_message(
                chat_id=target,
                text=text,
                reply_markup=buttons,
                disable_web_page_preview=True
            )
            return True
        except Exception:
            return False
    except Exception as error:
        print(f"[SEND ERROR] {target}: {error}")
        return False

async def send_to_targets(text, buttons):
    tasks = [send_one(target, text, buttons) for target in TARGET_USERS]
    await asyncio.gather(*tasks, return_exceptions=True)

# =========================================================
# المستمع المباشر
# =========================================================

@userbot.on_message()
async def on_new_message(client, message):
    try:
        if getattr(message, "outgoing", False) or getattr(message, "service", False):
            return

        text = (getattr(message, "text", None) or getattr(message, "caption", None) or "").strip()
        if not text or len(text) > 10000:
            return

        if await already_seen(text):
            return

        chat_name = get_chat_name(message)
        print(f"\n[NEW MESSAGE] [SOURCE: {chat_name}] -> {text[:100]}")

        is_request = await ask_groq(text)

        if is_request:
            print("[RESULT] YES -> SENDING TO TARGETS")
            forward_text = make_forward_text(message)
            buttons = make_buttons(message)
            await send_to_targets(forward_text, buttons)

    except Exception as error:
        print(f"[HANDLER ERROR]: {error}")

if __name__ == "__main__":
    print("[SYSTEM] Starting Hydrogram Engine...")
    userbot.run()

