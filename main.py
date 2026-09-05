import os
import asyncio
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

SESSION_STRING = os.environ.get("SESSION_STRING")
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4")
BOT_TOKEN = "8782796916:AAFloRFjgcxsiZ4Y50VAeyJpjOiJXriWl9g"

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

KEYWORDS = [
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
    "العميريه", "مشوار", "الضاحيه"
]

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    return text

NORMALIZED_KEYWORDS = {word: normalize_text(word) for word in KEYWORDS}

if not SESSION_STRING:
    raise ValueError("خطأ: لم يتم العثور على SESSION_STRING!")

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

    # رصد جميع الرسائل الواردة لليوزر بوت في القروبات العامة والخاصة والمواضيع
    @userbot.on_message(filters.group, group=-1)
    async def monitor_messages(client: Client, message: Message):
        if message.from_user and message.from_user.is_self:
            return

        raw_text = message.text or message.caption or ""
        if not raw_text:
            return

        searchable_text = normalize_text(raw_text)
        
        for original_word, norm_word in NORMALIZED_KEYWORDS.items():
            if norm_word in searchable_text:
                user_info = ""
                buttons = []
                row = []
                
                # المعالجة الدقيقة لرابط الخاص المستهدف
                if message.from_user:
                    if message.from_user.username:
                        user_url = f"https://t.me/{message.from_user.username}"
                        row.append(InlineKeyboardButton("💬 فتح المحادثة", url=user_url))
                    else:
                        # إضافة منشن للمستخدم بالرسالة يتيح لك الدخول لخاصه مباشرة بالنقر عليه
                        user_info = f"\n\n👤 **صاحب الطلب:** [{message.from_user.first_name}](tg://user?id={message.from_user.id})"

                # زر التوجه لموقع الرسالة بالقروب
                if message.link:
                    row.append(InlineKeyboardButton("📩 فتح الرسالة", url=message.link))
                
                if row:
                    buttons.append(row)
                    
                reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
                formatted_message = f"{raw_text}{user_info}"

                for user in TARGET_USERS:
                    try:
                        await bot.send_message(
                            chat_id=user,
                            text=formatted_message,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )
                    except Exception as e:
                        print(f"❌ خطأ عند التوجيه إلى @{user}: {e}")
                break

    await userbot.start()
    await bot.start()
    print("✅ تم البدء بنجاح! الرصد يعمل في كافة القروبات بلا استثناء.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
