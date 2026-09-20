import os
import asyncio
from threading import Thread
from flask import Flask
from hydrogram import Client, filters
from hydrogram.types import Message
from groq import Groq

# ----------------- الإعدادات والمتغيرات -----------------
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

# المعرف المستهدف للتوجيه
FORWARD_TO = "@abood1317"

# مفتاح API من متغيرات البيئة
GROQ_KEY = os.environ.get("GROQ_API_KEY_1")

# الأسماء الرسمية الصحيحة لموديلات Groq الحالية
GROQ_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

# ----------------- سيرفر خفيف لإبقاء Render شغالاً 24/7 -----------------
web_app = Flask('')

@web_app.route('/')
def home():
    return "Userbot with Groq AI is Active"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    web_app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_web)
    t.daemon = True
    t.start()

# ----------------- دالة الذكاء الاصطناعي -----------------
def analyze_with_groq(text):
    if not GROQ_KEY:
        print("⚠️ لم يتم العثور على GROQ_API_KEY_1")
        return False

    prompt = f"""
أنت مساعد متخصص في تصنيف رسائل مجموعات التوصيل والمشاوير على التلجرام.

حلل النص التالي بذكاء واقرر نية الكاتب:
- إذا كان النص **طلب زبون حقيقي** يبحث عن توصيل (مثل: طلب توصيل، يبغى توصيل، طرد، مشوار، توصيل طلب) -> أجب بـ: YES
- إذا كان النص **عروض سائقين** يعلنون عن أنفسهم (مثل: مستعد للتوصيل، سائق متاح، سيارة مكيفة) -> أجب بـ: NO
- إذا كان النص غير ذلك -> أجب بـ: NO

اجعل إجابتك كلمة واحدة فقط: إما YES أو NO.

النص:
\"\"\"
{text}
\"\"\"
"""

    client = Groq(api_key=GROQ_KEY)

    for model_name in GROQ_MODELS:
        try:
            completion = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            response = completion.choices[0].message.content.strip().upper()
            print(f"🤖 تحليل الذكاء الاصطناعي بواسطة ({model_name}): {response}")
            return "YES" in response
        except Exception as e:
            print(f"⚠️ فشل النموذج {model_name}: {e}")
            continue

    print("⚠️ فشل جميع النماذج، جاري استخدام الفحص البديل...")
    keywords = ["ابغى توصيل", "يبغى توصيل", "مطلوب توصيل", "محتاج توصيل", "توصيل من", "نوصل"]
    return any(k in text for k in keywords)

# ----------------- تشغيل الحساب -----------------
app = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

@app.on_message(filters.group & ~filters.me)
async def process_group_messages(client: Client, message: Message):
    text = message.text or message.caption
    if not text:
        return
    
    print(f"📩 تم استقبال رسالة جديدة: {text}")

    # تحليل النص بواسطة الذكاء الاصطناعي
    is_customer_request = await asyncio.to_thread(analyze_with_groq, text)
    
    if is_customer_request:
        try:
            await message.forward(FORWARD_TO)
            print(f"✅ تم توجيه طلب زبون بنجاح إلى {FORWARD_TO}")
        except Exception as e:
            print(f"❌ خطأ أثناء توجيه الرسالة إلى {FORWARD_TO}: {e}")
    else:
        print("ℹ️ ليست طلب زبون حقيقي.")

if __name__ == "__main__":
    keep_alive()
    print("🚀 جاري تشغيل الحساب الوهمي ونظام الذكاء الاصطناعي...")
    app.run()

