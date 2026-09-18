import os
import re
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message
from groq import Groq

# --- 1. إعدادات البيئة ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

GROQ_KEYS = [
    os.environ.get("GROQ_API_KEY_1"),
    os.environ.get("GROQ_API_KEY_2"),
    os.environ.get("GROQ_API_KEY_3")
]
GROQ_KEYS = [k for k in GROQ_KEYS if k]

# قائمة المشتركين (يمكن وضع المعرفات أو معرف القناة/المجموعة)
SUBSCRIBERS = [
    "abood1317",
]

env_dest = os.environ.get("DESTINATION_CHAT_ID")
if env_dest and env_dest not in SUBSCRIBERS:
    SUBSCRIBERS.append(env_dest)

app = Client(
    "barq_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

def analyze_with_groq(text):
    prompt = f"""
أنت مساعد ذكي لفلترة طلبات التوصيل.
حدد ما إذا كانت الرسالة التالية عبارة عن "طلب توصيل من زبون/عميل" يبحث عن مندوب.
إذا كانت طلب توصيل حقيقي، أرجع كلمة: YES
إذا كانت إعلان مندوب أو غير ذلك، أرجع كلمة: NO

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
            print(f"[AI] Key {idx + 1} Raw Result: '{result}'")
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

    ai_decision = analyze_with_groq(message.text)

    # مرونة الفحص للتأكد من وجود كلمة YES
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
                await client.send_message(
                    chat_id=target,
                    text=formatted_text
                )
                print(f"[SUCCESS] Sent request to target: {target}")
            except Exception as e:
                print(f"[ERROR] Could not send to {target}: {e}")
    else:
        print(f"[SKIPPED] Rejected by AI. Decision was: {ai_decision}")

if __name__ == "__main__":
    print("[SYSTEM] Starting Hydrogram Engine...")
    app.run()

