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

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

RAW_KEYWORDS = [
    "فيه", "احتاج", "مين", "يجيب", "بنات", "من", "اذا", "مشوار", "سواق", "ابحث", 
    "ادور", "ابغى", "ابغا", "احد", "حد", "طلبي", "الي", "يوصل", "الى", "توصلنا", 
    "يوصلني", "توصلني", "رايحه", "رايح", "ابي", "يعرف", "تكرمتو", "مندوبه", "حتى", 
    "ابغاه", "خاصه", "عندي", "بيطلع", "طالع", "مندوب", "كنت", "للعارضه", "لجيزان", 
    "لضمد", "لدرب", "للمطار", "لصبيا", "بسألكم", "السلام عليكم", "للمجمع", "لمحليه", 
    "هنا", "بالموسم", "بصامطه", "بحتاج", "بيروحني", "بروح", "يجيني", "تجيني", 
    "نوصل", "شباب", "يوصلي", "توصيل", "ذحين", "للكربوس", "لأبوعريش", "ماك", 
    "البيك", "قهوه", "حلا", "نمشي", "جيزان", "جازان", "شهري", "يلتزم", "سعره", 
    "كوفي", "روحه", "ورجعه", "إسكان", "ينفعني", "مشاوير", "الدرب", "للدرب", 
    "لين", "لأبها", "لابها", "صبيا", "يوصله", "بيش", "لبيش", "فالشقيري", 
    "الشقيري", "يرجعني", "بالضاحيه", "وجبه", "الظبيه", "للبرج", "البرج", "حي", 
    "مخطط", "موجود", "ابوعريش", "نازل", "مستشفى", "قصر", "شعب", "الذيب", "وجاي", 
    "صيدليه", "للمجنه", "اشاره", "الشاشه", "ماشي", "يأخذ", "قرى", "حاكمه", "الاهل", 
    "يستلم", "سمسا", "ارامكس", "نفسها", "بجيزان", "بجازان", "بضمد", "بالشقيق", 
    "طلبيه", "ابغاها", "معتمد", "يفتح", "المطاعم", "بشارع", "العارضه", "يروح", 
    "داخل", "ضروري", "محطه", "معي", "معايه", "معانا", "الحين", "يقدر", "تقدر", 
    "يجيبها", "قطه", "قط", "الصوارمه", "المضايا", "مزهره", "هاف", "في", "حوض"
]

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    return text

NORMALIZED_KEYWORDS = set(normalize_text(word) for word in RAW_KEYWORDS if word.strip())
PROCESSED_MESSAGES = set()
PROCESSED_TEXT_HASHES = set()

async def process_message(bot, message: Message):
    if not message or not message.id:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MESSAGES:
        return
    
    PROCESSED_MESSAGES.add(msg_key)
    if len(PROCESSED_MESSAGES) > 5000:
        PROCESSED_MESSAGES.clear()

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    if not raw_text.strip():
        return

    searchable_text = normalize_text(raw_text)

    # 1. تصفية الكلمات المفتاحية الصارمة (إلغاء المعالجة فوراً إن لم توجد أي كلمة)
    words_in_message = set(re.findall(r'\w+', searchable_text))
    has_keyword = False

    if NORMALIZED_KEYWORDS.intersection(words_in_message):
        has_keyword = True
    else:
        for kw in NORMALIZED_KEYWORDS:
            if kw in searchable_text:
                has_keyword = True
                break

    if not has_keyword:
        return

    # 2. منع تكرار النشر المماثل عبر القروبات المختلفة باستخدام بصمة النص
    text_hash = hashlib.md5(searchable_text.encode('utf-8')).hexdigest()
    if text_hash in PROCESSED_TEXT_HASHES:
        return

    PROCESSED_TEXT_HASHES.add(text_hash)
    if len(PROCESSED_TEXT_HASHES) > 3000:
        PROCESSED_TEXT_HASHES.clear()

    # بناء الأزرار
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

    # توجيه التنبيه للمستقبلين
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

async def real_time_channel_and_group_scanner(userbot, bot):
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=50):
                try:
                    async for msg in userbot.get_chat_history(dialog.chat.id, limit=2):
                        await process_message(bot, msg)
                except Exception:
                    pass
                await asyncio.sleep(0.1)

        except Exception as e:
            print(f"⚠️ خطأ أثناء الفحص: {e}")
            
        await asyncio.sleep(7)

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

    @userbot.on_message(filters.text | filters.caption)
    async def global_listener(client: Client, message: Message):
        await process_message(bot, message)

    await userbot.start()
    await bot.start()
    print("✅ تم التحديث بنجاح: كلمات جديدة + تصفية دقيقة + منع التكرار عبر القروبات.")

    asyncio.create_task(real_time_channel_and_group_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

