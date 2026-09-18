import os
import re
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message
from openai import OpenAI

# --- 1. إعدادات البيئة والمفاتيح ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
OPENAI_KEY = os.environ.get("OPENAI_API_KEY", "")

# قائمة المشتركين المستهدفين للإرسال
SUBSCRIBERS = [
    "abood1317",
]

env_dest = os.environ.get("DESTINATION_CHAT_ID")
if env_dest and env_dest not in SUBSCRIBERS:
    SUBSCRIBERS.append(env_dest)

# تشغيل الحساب الشخصي (Userbot)
app = Client(
    "barq_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# إعداد عميل OpenAI
ai_client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

def analyze_with_ai(text):
    """تحليل الرسالة بواسطة الذكاء الاصطناعي OpenAI"""
    if not ai_client:
        print("[AI ERROR] OPENAI_API_KEY is missing!")
        return "NO"

    prompt = f"""
أنت نظام ذكي لفلترة طلبات التوصيل.
حدد ما إذا كانت الرسالة التالية عبارة عن "طلب توصيل من زبون/عميل" يبحث عن مندوب لتوصيل شحنة أو مشوار.
إذا كانت طلب توصيل حقيقي من زبون، أرجع كلمة: YES
إذا كانت إعلان من مندوب، أو استفسار، أو غير متعلقة بطلب توصيل، أرجع كلمة: NO

الرسالة:
"{text}"
    """
    try:
        response = ai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=10
        )
        result = response.choices[0].message.content.strip().upper()
        print(f"[AI RESULT] -> '{result}'")
        return result
    except Exception as e:
        print(f"[AI EXCEPTION] -> {e}")
        return "NO"

@app.on_message(filters.group & ~filters.me)
async def handle_incoming_messages(client: Client, message: Message):
    if not message.text:
        return

    chat_title = message.chat.title or "قروب"
    print(f"[NEW MSG] [{chat_title}] -> {message.text[:40]}...")

    # 1. التحليل بالذكاء الاصطناعي
    ai_decision = analyze_with_ai(message.text)

    # 2. التوجيه في حال القبول
    if "YES" in ai_decision:
        sender_username = message.from_user.username if message.from_user and message.from_user.username else ""
        sender_info = f"@{sender_username}" if sender_username else (message.from_user.mention if message.from_user else "خاص")
        
        formatted_text = (
            f"🚚 **طلب توصيل جديد!**\n\n"
            f"📝 **التفاصيل:**\n{message.text}\n\n"
            f"👤 **المرسل:** {sender_info}\n"
            f"📍 **المصدر:** {chat_title}"
        )

        for target in SUBSCRIBERS:
            try:
                await client.send_message(chat_id=target, text=formatted_text)
                print(f"[SUCCESS] Forwarded to subscriber: {target}")
            except Exception as e:
                print(f"[SEND ERROR] Could not send to {target}: {e}")
    else:
        print(f"[SKIPPED] Rejected by AI.")

if __name__ == "__main__":
    print("[SYSTEM] Starting Userbot with OpenAI Engine...")
    app.run()
