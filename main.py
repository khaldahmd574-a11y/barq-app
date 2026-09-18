import os
import re
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message

# --- 1. إعدادات الحساب من Railway ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")

# قائمة المشتركين المستقبلين
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

# كلمات تعبر عن وجود طلب توصيل زبون
REQUEST_KEYWORDS = [
    "ابغى", "أبغى", "مطلوب", "احتاج", "أحتاج", "وصل", "توصيل", 
    "مين يوصل", "من يوصل", "ابي", "أبي", "مشوار", "طلب", "مندوب"
]

# كلمات تعبر عن إعلانات المناديب (لتجاهلها)
EXCLUDE_KEYWORDS = [
    "متواجد", "متواجدين", "جاهز", "نوصل", "نخدمكم", "خدمة توصيل", "حسابي", "تابعوني"
]

def is_order_request(text):
    """فلترة فورية وسريعة جداً للطلبات"""
    text_lower = text.lower()
    
    # إذا كان إعلان مندوب اتجاهله
    if any(ex in text_lower for ex in EXCLUDE_KEYWORDS):
        return False
        
    # إذا يحتوي على كلمات الطلب اعتبره طلب حقيقي
    if any(kw in text_lower for kw in REQUEST_KEYWORDS):
        return True
        
    return False

@app.on_message(filters.group & ~filters.me)
async def handle_incoming_messages(client: Client, message: Message):
    if not message.text:
        return

    chat_title = message.chat.title or "قروب"
    print(f"[NEW MESSAGE] [SOURCE: {chat_title}] -> {message.text[:50]}...")

    # فحص الطلب فورياً
    if is_order_request(message.text):
        print(f"[MATCHED] Order detected! Sending to subscribers...")
        
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
        print(f"[SKIPPED] Not a delivery request.")

if __name__ == "__main__":
    print("[SYSTEM] Starting Fast Engine...")
    app.run()
