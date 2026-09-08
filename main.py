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

CUSTOMER_INDICATORS = [
    "ابغى", "ابغا", "ابي", "اريد", "ابغى سواق", "ابي سواق", "محتاج", "محتاجه", 
    "مين", "من", "حد", "احد", "يوصلني", "يوصلنا", "يرجعنا", "يرجعني", "يجيبلي", 
    "يروحني", "تودي", "توديني", "من يوصل", "مين يوصل", "مين يروح", "من يروح", 
    "فيه احد", "في احد", "ابي مندوب", "محتاج مندوب", "محتاج موصل", "مين يمر", 
    "مين طالع", "مين نازل", "بكم يوصل", "ابي مشوار", "بسألكم", "ادور", "ابحث"
]

RAW_KEYWORDS = [
    "جيزان", "جازان", "بيش", "الدرب", "صبيا", "ضمد", "الضبيه", "الظبيه", "مزهره", 
    "ابو عريش", "العارضه", "مسليه", "رديس", "الخضراء", "فيفاء", "الداير", "الدائر", 
    "المضايا", "الخمس", "الخميسين", "الأحد", "الدغارير", "صامطه", "الطوال", "السويس", 
    "سويس", "الجامعه", "محليه", "البرج", "المجمع", "النخيل", "مخطط", "خمسه", "سته", 
    "سبعه", "ثمانيه", "الاسكان", "اسكان", "إسكان", "الملك", "عبدالله", "العريش", 
    "المخابشه", "الكربوس", "المطار", "الشواجره", "الشاطئ", "الواصلي", "الريان", 
    "الخشابيه", "العسيله", "العسيلة", "الاسامله", "البديع", "القرفي", "خضير", 
    "خضيره", "الغريب", "خبت سعيد", "الكوامله", "الكواملة", "الفقهاء", "العشوه", 
    "صنبه", "مستشفى", "العام", "الأمير", "السبخه", "الحقاويه", "ام العرش", "الحرف", 
    "الجديين", "الحجرين", "العرضه", "العدايا", "الطب", "الجنوبي", "الشمالي", 
    "الاثله", "حي", "النور", "المعبوج", "الصفا", "الراشد", "الكادي", "المقاريه", 
    "الروابي", "الشقيري", "الجهو", "الرحاب", "البدر", "الوحله", "العقده", "الحوامضه", 
    "المرابي", "الكبرى", "مغشيه", "السفلى", "رماده", "فهد", "المهدج", "قمبوره", 
    "حاكمه", "فلس", "المجصص", "المدينه", "العيدابي", "بصبيا", "حله", "الحسيني", 
    "النهضه", "حرجه", "الحرجه", "الحمى", "جريبه", "الزرقاء", "النسيم", "الطاهريه", 
    "القعاريه", "العميريه", "الضاحيه", "الحصمه", "الحصامه", "صبيحه", "النجاميه", 
    "العكره", "ابو المض", "ابها", "البحر", "بحر", "ابو حجر", "حجر", "القصبه", 
    "وادي", "الرباح", "اللقيه", "اللّقيه", "الوزاره", "الكلية", "الخارش", "العسيليه", 
    "بالموسم", "بصامطه", "لمحليه", "للكربوس", "لأبوعريش", "للعارضه", "لدرب", "للمطار", 
    "لصبيا", "للدرب", "لأبها", "لابها", "لبيش", "فالشقيري", "بالضاحيه", "للبرج", 
    "للمجنه", "شعب", "الذيب", "بجيزان", "بجازان", "بضمد", "بالشقيق", "الصوارمه", 
    "نخلان", "الكورنيش", "ابو السلع", "الكورنيش الشمالي", "الكورنيش الجنوبي", "جامعة جيزان", "مجمع صبيا",
    "هاف", "مليون", "ايت", "دونتس", "هرفي", "البيك", "دوز", "فندق", "دوار", 
    "الحناوي", "الصناعيه", "الشامل", "ماك", "ماكدونالدز", "شاكس", "تسالي", "دجى", 
    "صيدليه", "مطعم", "طعميه", "بوفيه", "ابتسام", "التخصصي", "الثانويه", "الروضه", 
    "صفوه", "المهيدب", "بوجا", "تويوتا", "هايبر", "بنده", "مشاوي", "الزاكي", 
    "قهوه", "حلا", "حلى", "اكل", "قاعه", "السوق", "الداخلي", "البلد", "محمصه", 
    "جرير", "الحياه", "كيان", "سمسا", "ارامكس", "المطاعم", "محطه", "كوفي", "وجبه"
]

BLOCKED_KEYWORDS = [
    "متوفر توصيل", "موجود للتوصيل", "جاهز للتوصيل", "توصيل طلبات وشحنات", 
    "مستعد للنقل", "سيارة نظيفة", "توصيل مشاوير", "تواصل واتس", "اتصال", 
    "للتواصل واتس", "نوصل طلبات", "متوفر سواق", "موجود سواق", "خدمة توصيل",
    "سكليف", "كتم", "مرحبا", "صحتي", "عذر طبي", "إجازة", "اجازة", 
    "مرضي", "مرضية", "استفسار", "مين يعرف", "شاي", "كرك", "اعلان", "إعلان"
]

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    return text

NORMALIZED_KEYWORDS = {word: normalize_text(word) for word in set(RAW_KEYWORDS) if word.strip()}
NORMALIZED_BLOCKED = [normalize_text(word) for word in BLOCKED_KEYWORDS if word.strip()]
NORMALIZED_CUSTOMERS = [normalize_text(word) for word in CUSTOMER_INDICATORS if word.strip()]

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

    # 1. حظر الرسالة فوراً إذا احتوت على أي كلمة ممنوعة أو عبارة إعلان للمندوب
    for blocked_word in NORMALIZED_BLOCKED:
        if blocked_word in searchable_text:
            return

    # 2. التأكد من أن الرسالة من زبون (تحتوي على صيغة طلب)
    is_customer = any(cust_word in searchable_text for cust_word in NORMALIZED_CUSTOMERS)
    if not is_customer:
        return

    # 3. منع التكرار بالنص عبر كافة القروبات
    text_hash = hashlib.md5(searchable_text.encode('utf-8')).hexdigest()
    if text_hash in PROCESSED_TEXT_HASHES:
        return

    # 4. مطابقة موقع أو خدمة مطلوبة
    for original_word, norm_word in NORMALIZED_KEYWORDS.items():
        if norm_word in searchable_text:
            PROCESSED_TEXT_HASHES.add(text_hash)
            if len(PROCESSED_TEXT_HASHES) > 3000:
                PROCESSED_TEXT_HASHES.clear()

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
            break

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

    @userbot.on_message(filters.all)
    async def global_listener(client: Client, message: Message):
        await process_message(bot, message)

    await userbot.start()
    await bot.start()
    print("✅ تم التشغيل والربط بنجاح (فلترة الزبائن فقط وحظر عروض المندوبين والتكرار).")

    asyncio.create_task(real_time_channel_and_group_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
