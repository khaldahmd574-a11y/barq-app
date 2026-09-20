import os
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message
from groq import Groq
from aiohttp import web

# ----------------- الإعدادات والمتغيرات -----------------
API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

# المعرف المستهدف للتوجيه
FORWARD_TO = "@abood1317"

# قائمة مفاتيح Groq الثلاثة
GROQ_KEYS = [
    os.environ.get("GROQ_API_KEY_1"),
    os.environ.get("GROQ_API_KEY_2"),
    os.environ.get("GROQ_API_KEY_3")
]
current_key_index = 0

# ----------------- سيرفر خفيف لإبقاء Render شغالاً 24/7 -----------------
async def handle(request):
    return web.Response(text="Userbot with Groq AI is Active")

async def start_web_server():
    server = web.Application()
    server.router.add_get('/', handle)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))  # استخدام البورت 10000 الخاص بـ Render
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 تم تشغيل سيرفر الويب على البورت: {port}")

# ----------------- دالة الذكاء الاصطناعي Groq -----------------
def analyze_with_groq(text):
    global current_key_index
    
    prompt = f"""
أنت مساعد متخصص في تصنيف رسائل مجموعات التوصيل والمشاوير على التلجرام.

حلل النص التالي بذكاء واقرر نية الكاتب:
- إذا كان النص **طلب زبون حقيقي** يبحث عن توصيل (مثل: طلب توصيل أغراض، مشوار، توصيل طلب مطعم، طرد) -> أجب بـ: YES
- إذا كان النص **عروض أو إعلانات سائقين/مندوبين** يعلنون عن أنفسهم أو سياراتهم (مثل: "مستعد للتوصيل"، "سائق متاح"، "توصيل مشاوير خاص"، "سيارة مكيفة") -> أجب بـ: NO
- إذا كان النص كلاماً عاماً، إعلانات أخرى، أو سبام -> أجب بـ: NO

اجعل إجابتك كلمة واحدة فقط: إما YES أو NO.

النص:
\"\"\"
{text}
\"\"\"
"""

    for _ in range(len(GROQ_KEYS)):
        key = GROQ_KEYS[current_key_index]
        if not key:
            current_key_index = (current_key_index + 1) % len(GROQ_KEYS)
            continue
        try:
            client = Groq(api_key=key)
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            response = completion.choices[0].message.content.strip().upper()
            return "YES" in response
        except Exception as e:
            print(f"⚠️ فشل استخدام المفتاح رقم {current_key_index + 1}: {e}")
            current_key_index = (current_key_index + 1) % len(GROQ_KEYS)

    return False

# ----------------- تشغيل الحساب الوهمي -----------------
app = Client("userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)

@app.on_message(filters.group & ~filters.me)
async def process_group_messages(client: Client, message: Message):
    if not message.text:
        return
    
    # طباعة للاختبار وتأكيد وصول الرسالة لـ Render Logs
    print(f"📩 وصلت رسالة جديدة من: {message.chat.title or message.chat.id}")

    # تحليل النص بذكاء بواسطة Groq
    is_customer_request = await asyncio.to_thread(analyze_with_groq, message.text)
    
    if is_customer_request:
        try:
            await message.forward(FORWARD_TO)
            print(f"✅ [طلب زبون] تم التوجيه بنجاح إلى {FORWARD_TO}")
        except Exception as e:
            print(f"❌ خطأ أثناء توجيه الرسالة إلى {FORWARD_TO}: {e}")
    else:
        print("ℹ️ تم تجاهل الرسالة (ليست طلب زبون).")

# ----------------- نقطة البدء الصحيحة -----------------
async def main():
    await start_web_server()
    await app.start()
    print("🚀 تم تشغيل الحساب الوهمي ونظام Groq بنجاح وربطهم برندر!")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())  # التعديل الهام لمنع تعليق الكود

