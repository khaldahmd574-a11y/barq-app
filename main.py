import os
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message

# قراءة جلسة العمل والمتغيرات من بيئة Render
SESSION_STRING = os.environ.get("SESSION_STRING")
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4")

if not SESSION_STRING:
    raise ValueError("شديد الأهمية: لم يتم العثور على SESSION_STRING في متغيرات البيئة!")

# إنشاء عميل Hydrogram مع تمرير الـ session_string لمنع طلب رقم الهاتف
app = Client(
    "my_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)

# قائمة الكلمات المفتاحية المراد مراقبتها (عدّلها حسب حاجتك)
KEYWORDS = ["برق", "طلب", "تصميم", "تطبيق", "شراء"]

@app.on_message(filters.text & ~filters.me)
async def monitor_keywords(client: Client, message: Message):
    """الاستماع للرسائل الواردة وفحص وجود الكلمات المفتاحية"""
    text = message.text.lower()
    
    for word in KEYWORDS:
        if word in text:
            print(f" تم العثور على كلمة مفتاحية: '{word}' في المجموعة/القناة: {message.chat.title or message.chat.id}")
            # يمكنك إضافة كود هنا لإرسال تنبيه لنفسك أو لإعادة توجيه الرسالة
            break

async def main():
    print(" جاري تشغيل اليوزر بوت على Render...")
    await app.start()
    print(" تم تشغيل البوت بنجاح! يتم الآن مراقبة الكلمات المفتاحية على مدار 24 ساعة.")
    await asyncio.Event().wait()  # الإبقاء على البوت يعملاً دائماً

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
