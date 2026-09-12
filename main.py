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

# قائمة المستلمين المعتمدة
TARGET_USERS = [
    "shaybq", 
    "Waaaaaaa33", 
    "abood1317"
]

# =========================
# القوائم الشاملة المحدثة للطلبات
# =========================

REQUEST_INTENTS = [
    # نية صريحة وطلب مباشر
    "ابغى", "ابغي", "أبغى", "ابغا", "أبغا", "تبغى", "تبغا", "يبغى", "يبغا",
    "ابي", "أبي", "تبي", "يبي", "نبي",
    "اريد", "أريد", "ارغب", "أرغب",
    "ودي", "ودّي",
    "احتاج", "أحتاج", "محتاج", "محتاجة", "نحتاج", "نبغى", "نشتي",

    # أسئلة واستفسارات البحث عن سائق/خدمة
    "مين", "من", "فيه", "فية", "شي", "موجود", "موجوده", "الي", "اللي", "احصل", "أحصل", "الاقي", "ألاقي",

    # أفعال التنقل والتوصيل المباشرة
    "يوصلني", "يوصل", "يوصلي", "يوصللي", "يوصل لي", "توصيلة", "توصيله", "يوصلنا",
    "يجيب", "يجيبلي", "يجيب لي", "يجيبني",
    "ياخذ", "ياخذلي", "ياخذ لي", "ياخذني",
    "ينقل", "ينقلني", "ينزلنا", "ينزلني",
    "يرجعنا", "يرجعني", "يوديني", "يودي", "يروح",
    "يعطينا", "يمر", "يمرني", "يشيلني", "يشيل", "يودينا", "يطوفني",

    # صيغ توجيه ومسميات الخدمة
    "سواق", "سواقه", "سواقة", "سائق", "سائقه", "سائقة", "سوقه", "سوقة",
    "مندوب", "مندوبة", "مندوبه", "كابتن", "مشوار", "مشاوير", "دفعات", "شهري", "شهريا"
]

DRIVER_PATTERNS = [
    "انا مندوب", "أنا مندوب", "مندوب فاضي", "مندوب ثقه", "مندوب ثقة", 
    "انا سواق", "أنا سواق", "انا سائق", "أنا سائق",
    "سواق فاضي", "سائق فاضي", "متوفر للتوصيل", "متاح للتوصيل", "متوفر للمشاوير",
    "متاح للمشاوير", "اللي يحتاج يتواصل", "اللي يحتاج يكلمني",
    "للتواصل خاص", "للتواصل واتس", "خدمات توصيل", "توصيل ومشاوير", "توصيل طلبات",
    "فاضي بصبيا", "فاضي بجيزان", "فاضي ببيش", "مين يبغى توصيل", "مين يبغى مشوار",
    "سيارة خاصة", "سياره خاصه", "حاضر للتوصيل", "جاهز للتوصيل", "وضواحيها", "وضواحي ه"
]

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = text.replace("ة", "ه")
    text = text.replace("ى", "ي")
    text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def contains_phrase(text, phrases):
    return any(normalize_text(phrase) in text for phrase in phrases)

def is_customer_request(text):
    norm_text = normalize_text(text)
    if not norm_text:
        return False

    # 1. استبعاد السائقين إذا كان المنشور يحتوي على رقم جوال سعودي (05xxxxxxx)
    if re.search(r"05\d{8}", text.replace(" ", "")):
        return False

    # 2. استبعاد منشورات السائقين المباشرة
    if contains_phrase(norm_text, DRIVER_PATTERNS):
        return False

    # 3. قبول نية الطلب الصريحة من العميل
    if contains_phrase(norm_text, REQUEST_INTENTS):
        return True

    # 4. قبول عبارات المشاوير والتوصيل المباشرة
    if any(k in norm_text for k in ["مشوار", "توصيل", "توصيله", "توصيلة"]):
        return True

    return False

# =========================
# بصمة ومنع التكرار
# =========================

PROCESSED_MESSAGES = set()
PROCESSED_REQUEST_HASHES = set()

def make_request_fingerprint(text):
    text = normalize_text(text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"\d+", "", text)
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

    # الفلترة الذكية للطلب
    if not is_customer_request(raw_text):
        return

    # بصمة الطلب لمنع التكرار عبر القنوات المزدوجة
    request_hash = make_request_fingerprint(raw_text)
    if request_hash in PROCESSED_REQUEST_HASHES:
        return

    PROCESSED_REQUEST_HASHES.add(request_hash)
    if len(PROCESSED_REQUEST_HASHES) > 10000:
        PROCESSED_REQUEST_HASHES.clear()

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

# =========================
# الماسح الدوري المستمر للقروبات والقنوات الكبيرة
# =========================

async def real_time_channel_and_group_scanner(userbot, bot):
    while True:
        try:
            # فحص أول 60 محادثة نشطة بانتظام
            async for dialog in userbot.get_dialogs(limit=60):
                try:
                    async for msg in userbot.get_chat_history(dialog.chat.id, limit=2):
                        await process_message(bot, msg)
                except Exception:
                    pass
                await asyncio.sleep(0.1)

        except Exception as e:
            print(f"⚠️ خطأ أثناء الفحص الدوري: {e}")
            
        # يعيد الفحص كاملاً كل 5 ثوانٍ
        await asyncio.sleep(5)

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

    # استماع لحظي لجميع الرسائل
    @userbot.on_message(filters.all)
    async def global_listener(client: Client, message: Message):
        await process_message(bot, message)

    await userbot.start()
    await bot.start()
    print("✅ تم التشغيل والربط بنجاح (استماع لحظي + ماسح دائم لكل القروبات القنوات).")

    # تشغيل الماسح الدوري في الخلفية لسحب القروبات الكبيرة والقنوات القاسية
    asyncio.create_task(real_time_channel_and_group_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

