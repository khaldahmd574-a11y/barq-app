import os
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client, filters
from hydrogram.types import Message

# خادم وهمي لمنع Render من إغلاق الخدمة
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running 24/7!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# 1. إعدادات الحساب الوهمي من Render
SESSION_STRING = os.environ.get("SESSION_STRING")
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4")

# 2. توكن البوت الخاص بك
BOT_TOKEN = "8782796916:AAFloRFjgcxsiZ4Y50VAeyJpjOiJXriWl9g"

# 3. قائمة يوزرات الأعضاء
TARGET_USERS = [
    "shaybq",
    "Waaaaaaa33",
    "abood1317"
]

# 4. الكلمات المفتاحية الـ 52 كاملة
KEYWORDS = [
    "جيزان", "الدرب", "بيش", "العارضة", "صامطة", "أحد", "صياغة", "محايل",
    "صبيا", "ابوعريش", "المجاردة", "الشقيق", "القنفذة", "بارق", "المظيلف",
    "القوز", "توصيل", "يوصل", "توصيلات", "توصيلي", "يركبها", "شحن",
    "على طريقه", "ادور عن", "ابحث عن", "معلم", "مقاول", "شغال", "مندوب",
    "دباب", "سطحة", "تاكسي", "مشوار", "مطعم", "حلاق", "مطبخ", "غسيل",
    "مطابخ", "المنيوم", "تكييف", "سباك", "كهربائي", "نقل عوائل", "دهان",
    "مبلط", "حداد", "سطحه", "نقل الهارات", "مصنع"
]

if not SESSION_STRING:
    raise ValueError("خطأ: لم يتم العثور على SESSION_STRING!")

async def main():
    # تشغيل الخادم الوهمي في مسار خلفي
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    print("🚀 جاري تشغيل الحساب الوهمي والبوت...")
    
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

    @userbot.on_message(filters.text & ~filters.me)
    async def monitor_messages(client: Client, message: Message):
        text = message.text.lower()
        
        for word in KEYWORDS:
            if word in text:
                alert_text = (
                    f"🚨 **تم رصد كلمة مفتاحية:** `{word}`\n\n"
                    f"👤 **المرسل:** {message.from_user.mention if message.from_user else 'مجهول'}\n"
                    f"💬 **المجموعة:** {message.chat.title or 'محادثة خاصة'}\n"
                    f"📝 **الرسالة:**\n{message.text}\n\n"
                    f"🔗 **رابط الرسالة:** {message.link if message.link else 'لا يوجد رابط مباشر'}"
                )
                
                for user in TARGET_USERS:
                    try:
                        await bot.send_message(chat_id=user, text=alert_text)
                        print(f"✅ تم توجيه التنبيه عبر البوت إلى: @{user}")
                    except Exception as e:
                        print(f"❌ تعذر إرسال التنبيه إلى @{user}: {e}")
                break

    await userbot.start()
    await bot.start()
    print("✅ تم التشغيل بنجاح! السيرفر والبوت يعملان الآن 24/7.")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
