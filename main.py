import os
import asyncio
import re
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
    "العميريه", "مشوار", "الضاحيه", "جرير", "الحصمه", "الحصامه", "الحياه", "صبيحه", 
    "كيان", "النجاميه", "العكره", "ابو المض", "دوامي", "سواقه", "سواق", "شهري", 
    "الشهر", "ابها", "نازل", "ينزل", "طالع", "يطلع"
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
PROCESSED_MESSAGES = set()

async def process_and_send(userbot, bot, message: Message):
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
    if not raw_text:
        return

    searchable_text = normalize_text(raw_text)
    
    for original_word, norm_word in NORMALIZED_KEYWORDS.items():
        if norm_word in searchable_text:
            buttons = []
            row = []
            sender_info = "غير معروف"
            
            if message.from_user:
                sender_name = message.from_user.first_name or "المرسل"
                if message.from_user.username:
                    # فتح المحادثة والصفحة مباشرة إذا كان يملك اسم مستخدم
                    row.append(InlineKeyboardButton(f"👤 {sender_name}", url=f"https://t.me/{message.from_user.username}"))
                    sender_info = f"@{message.from_user.username}"
                else:
                    sender_info = f"{sender_name} (لا يملك يوزر)"

            if message.link:
                row.append(InlineKeyboardButton("📩 فتح الرسالة بالأصل", url=message.link))
            
            if row:
                buttons.append(row)
                
            reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
            formatted_text = f"👤 **المرسل:** {sender_info}\n\n{raw_text}"

            for user in TARGET_USERS:
                try:
                    # إرسال الرسالة المعالجة عبر البوت
                    await bot.send_message(
                        chat_id=user,
                        text=formatted_text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                    
                    # إذا لم يكن للحساب يوزر، نقوم بتحويل الرسالة الأصلية فوراً عبر الحساب الوهمي 
                    # ليتمكن المستقبل من الضغط على اسم صاحب الرسالة مباشرة بفتح بروفايله
                    if message.from_user and not message.from_user.username:
                        await userbot.forward_messages(
                            chat_id=user,
                            from_chat_id=message.chat.id,
                            message_ids=message.id
                        )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception as e:
                    print(f"❌ خطأ إرسال: {e}")
            break

async def full_coverage_scanner(userbot, bot):
    while True:
        try:
            async for dialog in userbot.get_dialogs():
                try:
                    if dialog.top_message:
                        await process_and_send(userbot, bot, dialog.top_message)
                except Exception:
                    pass
        except Exception as e:
            print(f"⚠️ خطأ فحص: {e}")
        await asyncio.sleep(1)

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
        await process_and_send(userbot, bot, message)

    await userbot.start()
    await bot.start()
    print("⚡ تم تشغيل النظام المحدث مع الحل النهائي لفتح البروفايل.")

    asyncio.create_task(full_coverage_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

