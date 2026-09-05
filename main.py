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

def escape_html(text: str) -> str:
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

NORMALIZED_KEYWORDS = {word: normalize_text(word) for word in KEYWORDS}
PROCESSED_MESSAGES = set()

async def process_and_send(bot, message: Message):
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
            
            # تنظيف النص الأساسي حتى لا يتداخل مع وسوم HTML
            clean_raw_text = escape_html(raw_text)
            user_header = ""
            
            if message.from_user:
                sender_id = message.from_user.id
                sender_name = escape_html(message.from_user.first_name or "صاحب الرسالة")
                
                # رابط المنشن الفعال المباشر بداخل النص
                user_header = f"👤 <b>المرسل:</b> <a href=\"tg://user?id={sender_id}\">{sender_name}</a>\n\n"
                
                # إبقاء أزرار التوجيه للأزرار المتاحة فقط
                if message.from_user.username:
                    row.append(InlineKeyboardButton("💬 فتح المحادثة", url=f"https://t.me/{message.from_user.username}"))

            if message.link:
                row.append(InlineKeyboardButton("📩 فتح الرسالة بالأصل", url=message.link))
            
            if row:
                buttons.append(row)
                
            reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
            
            # النص النهائي مدمجاً معه رابط الحساب باللون الأزرق المباشر
            final_text = f"{user_header}{clean_raw_text}"

            for user in TARGET_USERS:
                try:
                    await bot.send_message(
                        chat_id=user,
                        text=final_text,
                        parse_mode=filters.enums.ParseMode.HTML,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await bot.send_message(
                        chat_id=user,
                        text=final_text,
                        parse_mode=filters.enums.ParseMode.HTML,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"❌ خطأ توجيه: {e}")
            break

async def full_coverage_scanner(userbot, bot):
    while True:
        try:
            async for dialog in userbot.get_dialogs():
                try:
                    if dialog.top_message:
                        await process_and_send(bot, dialog.top_message)
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
        await process_and_send(bot, message)

    await userbot.start()
    await bot.start()
    print("⚡ تم تشغيل النظام المحدث بتركيب المنشن المباشر.")

    asyncio.create_task(full_coverage_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

