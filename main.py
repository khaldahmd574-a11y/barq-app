import os
import re
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message
from groq import Groq

# --- 1. بيانات الحساب والذكاء الاصطناعي من Railway ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# قائمة مفاتيح Groq
GROQ_KEYS = [
    os.environ.get("GROQ_API_KEY_1"),
    os.environ.get("GROQ_API_KEY_2"),
    os.environ.get("GROQ_API_KEY_3")
]
GROQ_KEYS = [k for k in GROQ_KEYS if k]

# --- 2. قائمة معرفات المشتركين المستهدفين (بدون fs_990) ---
SUBSCRIBERS = [
    "abood1317",  # المشترك الأول
    # ضع معرف المشترك الثاني هنا بين التنصيص (مثال: "user2")
    # ضع معرف المشترك الثالث هنا بين التنصيص (مثال: "user3")
]

# إضافة أي قناة أو مستلم من متغيرات البيئة إن وجد
env_dest = os.environ.get("DESTINATION_CHAT_ID")
if env_dest and env_dest not in SUBSCRIBERS:
    SUBSCRIBERS.append(env_dest)

# --- 3. تشغيل الـ Userbot ---
app = Client(
    "barq_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

def analyze_with_groq(text):
    """تحليل النص عبر الذكاء الاصطناعي (Groq Llama-3) لفلترة طلبات التوصيل"""
    prompt = f"""
أنت مساعد ذكي لفلترة طلبات التوصيل والمناديب.
المطلوب منك تحديد ما إذا كانت الرسالة التالية عبارة عن "طلب توصيل من زبون/عميل" يبحث عن مندوب لتوصيل شحنة أو مشوار.
إذا كانت الرسالة طلب توصيل حقيقي من زبون، أرجع كلمة: YES
إذا كانت إعلان من مندوب يعرض خدماته، أو استفسار عام، أرجع كلمة: NO

الرسالة:
"{text}"
    """
    
    for idx, key in enumerate(GROQ_KEYS):
        try:
            client = Groq(api_key=key)
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=10
            )
            result = response.choices[0].message.content.strip().upper()
            print(f"[AI] Key {idx + 1} -> Result: {result}")
            return result
        except Exception as e:
            print(f"[AI] Key {idx + 1} Error: {e}")
            continue
            
    return "NO"

@app.on_message(filters.group & ~filters.me)
async def handle_incoming_messages(client: Client, message: Message):
    if not message.text:
        return

    chat_title = message.chat.title or "قروب"
    print(f"[NEW MESSAGE] [SOURCE: {chat_title}] -> {message.text[:50]}...")

    # تحليل الرسالة بواسطة الذكاء الاصطناعي
    ai_decision = analyze_with_groq(message.text)

    # الإرسال للمشتركين عند الموافقة والفلترة
    if "YES" in ai_decision:
        sender_username = message.from_user.username if message.from_user and message.from_user.username else ""
        sender_info = f"@{sender_username}" if sender_username else (message.from_user.mention if message.from_user else "خاص")
        
        formatted_text = (
            f"🚚 **طلب توصيل جديد!**\n\n"
            f"📝 **التفاصيل:**\n{message.text}\n\n"
            f"👤 **المرسل:** {sender_info}\n"
            f"📍 **المصدر:** {chat_title}"
        )

        # تحويل الرسالة إلى جميع المشتركين الموجودين في القائمة
        for target in SUBSCRIBERS:
            try:
                await client.send_message(
                    chat_id=target,
                    text=formatted_text
                )
                print(f"[SUCCESS] Sent request to subscriber: {target}")
            except Exception as e:
                print(f"[ERROR] Failed to send to subscriber {target}: {e}")
    else:
        print(f"[SKIPPED] Message classified as NO.")

if __name__ == "__main__":
    print("[SYSTEM] Starting Hydrogram Engine...")
    app.run()

