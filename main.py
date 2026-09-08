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

BLOCKED_KEYWORDS = ["سكليف", "كتم", "مرحبا", "صحتي", "عذر طبي"]

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
    "الاثله", "حي", "النور", "المعبوج", "الصفا", "الراشد", "الكادي", "هاف", "مليون", 
    "ايت", "دونتس", "هرفي", "البيك", "يوصلني", "يوصلي", "يجيب", "يمر", "يجي", 
    "يوصلنا", "يرجعنا", "يعطينا", "ينزلنا", "يداوم", "يلتزم", "دوز", "فندق", 
    "دوار", "الحناوي", "الصناعيه", "معاه", "هايلوكس", "الشامل", "مضغوط", "ماك", 
    "ماكدونالدز", "بيشه", "المقاريه", "الروابي", "شاكس", "تسالي", "دجى", "صيدليه", 
    "مطعم", "طعميه", "ارجع", "بوفيه", "ابتسام", "التخصصي", "الثانويه", "الروضه", 
    "صفوه", "المهيدب", "بوجا", "تويوتا", "الشقيري", "الجهو", "الرحاب", "البدر", 
    "الوحله", "العقده", "الحوامضه", "المرابي", "الكبرى", "مغشيه", "السفلى", "رماده", 
    "فهد", "المهدج", "قمبوره", "حاكمه", "فلس", "المجصص", "المدينه", "العيدابي", 
    "بصبيا", "هايبر", "بنده", "حله", "الحسيني", "النهضه", "حرجه", "الحرجه", "الحمى", 
    "جريبه", "الزرقاء", "النسيم", "مشاوي", "الزاكي", "قهوه", "حلا", "حلى", "اكل", 
    "قاعه", "السوق", "الداخلي", "البلد", "محمصه", "مننا", "الطاهريه", "القعاريه", 
    "العميريه", "مشوار", "الضاحيه", "جرير", "الحصمه", "الحصامه", "الحياه", "صبيحه", 
    "كيان", "النجاميه", "العكره", "ابو المض", "دوامي", "سواقه", "سواق", "شهري", 
    "الشهر", "ابها", "نازل", "ينزل", "طالع", "يطلع", "مندوب", "قريب", "قريه", 
    "قرى", "البحر", "بحر", "ابو حجر", "حجر", "القصبه", "طلب", "وادي", "الرباح", 
    "بعد", "اللقيه", "اللّقيه", "الوزاره", "كبري", "عند", "لجيزان", "ابي", "ابغا", "اريد", 
    "لالمجمع", "ينقل", "يعرف", "يوصل", "الكلية", "الخارش", "العسيليه",
    "فيه", "احتاج", "مين", "بنات", "من", "اذا", "ابحث", "ادور", "ابغى", "احد", 
    "حد", "طلبي", "الي", "الى", "توصلنا", "توصلني", "رايحه", "رايح", "تكرمتو", 
    "مندوبه", "حتى", "ابغاه", "خاصه", "عندي", "بيطلع", "كنت", "للعارضه", "لدرب", 
    "لالمطار", "لصبيا", "بسألكم", "السلام عليكم", "لمحليه", "هنا", "بالموسم", 
    "بصامطه", "بحتاج", "بيروحني", "بروح", "يجيني", "تجيني", "نوصل", "شباب", 
    "توصيل", "ذحين", "للكربوس", "لأبوعريش", "نمشي", "سعره", "كوفي", "روحه", 
    "ورجعه", "ينفعني", "مشاوير", "للدرب", "لين", "لأبها", "لابها", "يوصله", 
    "لبيش", "فالشقيري", "يرجعني", "بالضاحيه", "وجبه", "للبرج", "موجود", 
    "شعب", "الذيب", "وجاي", "لالمجنه", "اشاره", "الشاشه", "ماشي", "يأخذ", 
    "الاهل", "يستلم", "سمسا", "ارامكس", "نفسها", "بجيزان", "بجازان", "بضمد", 
    "بالشقيق", "طلبيه", "ابغاها", "معتمد", "يفتح", "المطاعم", "بشارع", "يروح", 
    "داخل", "ضروري", "محطه", "معي", "معايه", "معانا", "الحين", "يقدر", "تقدر", 
    "يجيبها", "قطه", "قط", "الصوارمه", "في", "حوض", "نخلان", "اولاد", 
    "دومات", "تداوم", "الكورنيش", "ابو السلع", "سيارته", "كبيره", "صغيره", "نلتزم", "اقل"
]

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    return text

NORMALIZED_KEYWORDS = [normalize_text(word) for word in set(RAW_KEYWORDS) if word.strip()]
NORMALIZED_BLOCKED = [normalize_text(word) for word in BLOCKED_KEYWORDS if word.strip()]

KEYWORD_PATTERN = re.compile(r"|".join(map(re.escape, NORMALIZED_KEYWORDS)))
BLOCKED_PATTERN = re.compile(r"|".join(map(re.escape, NORMALIZED_BLOCKED)))

PROCESSED_MESSAGES = set()
PROCESSED_TEXT_HASHES = set()

async def send_to_user(bot, user, raw_text, reply_markup):
    try:
        await bot.send_message(
            chat_id=user,
            text=raw_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        print(f"✅ تم الإرسال بنجاح إلى: {user}")
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await bot.send_message(
            chat_id=user,
            text=raw_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
    except Exception as e:
        print(f"❌ خطأ في الإرسال لـ {user}: {e}")

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

    if BLOCKED_PATTERN.search(searchable_text):
        return

    text_hash = hashlib.md5(searchable_text.encode('utf-8')).hexdigest()
    if text_hash in PROCESSED_TEXT_HASHES:
        return

    if KEYWORD_PATTERN.search(searchable_text):
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

        # إرسال متوازي لجميع المستخدمين المحددين
        tasks = [send_to_user(bot, user, raw_text, reply_markup) for user in TARGET_USERS]
        await asyncio.gather(*tasks)

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
        chat_name = message.chat.title or message.chat.first_name or "خاص"
        print(f"📩 تم استلام رسالة جديدة من [{chat_name}]")
        await process_message(bot, message)

    await userbot.start()
    await bot.start()
    
    me = await userbot.get_me()
    print(f"🚀 تم تشغيل الخدمة بنجاح للحساب: {me.first_name} (@{me.username})")
    print("⚡️ يمتلك البوت القدرة الآن على معالجة الرسائل فور وصولها...")

    # حل مشكلة الإيقاف والتنبيه (تم إضافة await)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

