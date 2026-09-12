import os
import asyncio
import re
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

SESSION_STRING = os.environ.get("SESSION_STRING")
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4")
BOT_TOKEN = "8782796916:AAEe9YRkzbfm3F5e9rj49iHfDS0wRTnVmmo"

# قائمة المستلمين (تم استبعاد اليوزرات الثلاثة)
TARGET_USERS = [
    "shaybq", 
    "Waaaaaaa33", 
    "abood1317"
]

# =========================
# فلترة طلبات العملاء
# =========================

REQUEST_INTENTS = [
    # صريحة
    "ابغى", "ابغي", "أبغى", "ابغا", "أبغا",
    "ابي", "أبي", "اريد", "أريد", "ودي", "ودّي",
    "احتاج", "أحتاج", "محتاج", "محتاجة", "نحتاج", "نبغى", "نشتي",

    # تساؤلات واستفسار عن توفر خدمة
    "مين", "من", "فيه", "فية", "شي", "موجود", "الي", "اللي",

    # أفعال الطلب والتوصيل
    "يوصلني", "يوصل", "يوصلي", "يوصللي", "يوصل لي",
    "يجيب", "يجيبلي", "يجيب لي", "ياخذ", "ياخذلي", "ياخذ لي",
    "ينقل", "ينقلني", "ينزلنا", "يرجعنا", "يعطينا", "يمر",

    # صيغ موجهة للسائقين مباشرة
    "سواق", "سائقه", "سائقة", "سوقه", "سوقة", "سواقة",
    "مندوب", "مندوبة", "مندوبه", "كابتن", "مشوار", "مشاوير"
]

SERVICE_WORDS = [
    "مندوب", "سواق", "سواقه", "سائق", "سائقه",
    "توصيل", "يوصلني", "يوصل لي", "يوصللي", "يوصلي",
    "يجيب لي", "يجيبلي", "ياخذ لي", "ياخذلي",
    "مشوار", "مشاوير", "يروح", "ينقلني", "ينقل",
    "طلب", "طلبي", "غرض", "اغراض", "أغراض"
]

# عبارات تدل غالبًا أن الكاتب سائق/مندوب وليس عميل
DRIVER_PATTERNS = [
    "انا مندوب", "أنا مندوب", "مندوب فاضي", "مندوب متوفر", "مندوب متواجد",
    "مندوب ثقه", "مندوب ثقة", "انا سواق", "أنا سواق", "انا سائق", "أنا سائق",
    "سواق فاضي", "سواق متوفر", "سواق متواجد", "سائق فاضي", "سائق متوفر",
    "سائق متواجد", "متوفر للتوصيل", "متاح للتوصيل", "متوفر للمشاوير",
    "متاح للمشاوير", "اللي يحتاج يتواصل", "اللي يحتاج يكلمني",
    "للتواصل خاص", "للتواصل واتس", "خدمات توصيل", "توصيل ومشاوير",
    "فاضي بصبيا", "فاضي بجيزان", "فاضي ببيش", "مين يبغى توصيل"
]

LOCATION_WORDS = [
    "جيزان", "جازان", "صبيا", "ضمد", "بيش", "الدرب", "ابو عريش", "أبو عريش",
    "العارضة", "صامطة", "الطوال", "فيفاء", "الداير", "الدائر", "المطار",
    "الجامعة", "السويس", "المجمع", "النخيل", "الاسكان", "الإسكان", "مخطط", "حي"
]

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = text.replace("ة", "ه")
    text = text.replace("ى", "ي")
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def contains_phrase(text, phrases):
    return any(normalize_text(phrase) in text for phrase in phrases)

def is_customer_request(text):
    norm_text = normalize_text(text)
    if not norm_text:
        return False

    # 1. استبعاد منشورات السائقين
    if contains_phrase(norm_text, DRIVER_PATTERNS):
        return False

    # 2. نية طلب
    has_intent = contains_phrase(norm_text, REQUEST_INTENTS)
    if not has_intent:
        return False

    # 3. نوع الخدمة
    has_service = contains_phrase(norm_text, SERVICE_WORDS)
    if not has_service:
        return False

    return True

# =========================
# بصمة أولى للطلب
# =========================

PROCESSED_MESSAGES = set()
PROCESSED_REQUEST_HASHES = set()

def make_request_fingerprint(text):
    text = normalize_text(text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"\d+", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return hashlib.md5(text.encode("utf-8")).hexdigest()

async def process_message(bot, message: Message):
    if not message or not message.id:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MESSAGES:
        return

    PROCESSED_MESSAGES.add(msg_key)
    if len(PROCESSED_MESSAGES) > 10000:
        PROCESSED_MESSAGES.clear()

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    if not raw_text:
        return

    # فلترة طلب العميل
    if not is_customer_request(raw_text):
        return

    # بصمة الطلب لمنع التكرار
    request_hash = make_request_fingerprint(raw_text)
    if request_hash in PROCESSED_REQUEST_HASHES:
        return

    PROCESSED_REQUEST_HASHES.add(request_hash)
    if len(PROCESSED_REQUEST_HASHES) > 10000:
        PROCESSED_REQUEST_HASHES.clear()

    # أزرار التواصل
    buttons = []
    row = []

    if message.from_user:
        if message.from_user.username:
            user_url = f"https://t.me/{message.from_user.username}"
            user_label = f"💬 فتح المحادثة (@{message.from_user.username})"
        else:
            user_url = f"tg://openmessage?user_id={message.from_user.id}"
            user_label = f"💬 فتح المحادثة ({message.from_user.first_name or 'المستخدم'})"
        row.append(InlineKeyboardButton(user_label, url=user_url))

    if message.link:
        row.append(InlineKeyboardButton("📩 الرسالة الأصلية", url=message.link))

    if row:
        buttons.append(row)

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

    # إرسال الطلب للمشتركين
    for user in TARGET_USERS:
        try:
            await bot.send_message(
                chat_id=user,
                text=raw_text,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await bot.send_message(
                chat_id=user,
                text=raw_text,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except Exception as e:
            print(f"❌ خطأ توجيه: {e}")

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "my_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    bot = Client(
        "helper_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True
    )

    @userbot.on_message(filters.all)
    async def global_listener(client: Client, message: Message):
        await process_message(bot, message)

    await userbot.start()
    await bot.start()
    print("✅ تم التشغيل بنجاح مع الفلترة الذكية المحدثة.")

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

