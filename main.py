import os
import asyncio
from hydrogram import Client, filters
from hydrogram.types import Message
import google.generativeai as genai

# --- 1. إعدادات البيئة والمفاتيح ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

# قائمة المشتركين المستهدفين للإرسال بواسطة البوت الرسمي
SUBSCRIBERS = [
    "abood1317",
]

env_dest = os.environ.get("DESTINATION_CHAT_ID")
if env_dest and env_dest not in SUBSCRIBERS:
    SUBSCRIBERS.append(env_dest)

# الحساب الوهمي (Userbot) لسحب الرسائل من القروبات
app = Client(
    "barq_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# البوت الرسمي لإعادة الإرسال للمشتركين
official_bot = Client(
    "barq_official_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
) if BOT_TOKEN else None

# إعداد ذكاء Google Gemini المجاني
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

def analyze_with_ai(text):
    """تحليل الرسالة بواسطة ذكاء Gemini المجاني والسريع"""
    if not ai_model:
        print("[AI ERROR] GEMINI_API_KEY is missing!")
        return "NO"

    prompt = f"""
أنت نظام ذكي لفلترة طلبات التوصيل.
حدد ما إذا كانت الرسالة التالية عبارة عن "طلب توصيل من زبون/عميل" يبحث عن مندوب لتوصيل شحنة أو مشوار أو أغراض.
إذا كانت طلب توصيل حقيقي من زبون، أرجع كلمة: YES
إذا كانت إعلان من مندوب، أو عرض خدمة، أو استفسار، أو غير متعلقة بطلب توصيل، أرجع كلمة: NO

الرسالة:
"{text}"
    """
    try:
        response = ai_model.generate_content(prompt)
        result = response.text.strip().upper()
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
    print(f"[FETCHED] [{chat_title}] -> {message.text[:40]}...")

    # 1. تحليل الرسالة بالذكاء الاصطناعي (Gemini)
    ai_decision = analyze_with_ai(message.text)

    # 2. التوجيه عبر البوت الرسمي في حال كانت طلب توصيل
    if "YES" in ai_decision:
        user = message.from_user
        
        if user:
            if user.username:
                contact_link = f"https://t.me/{user.username}"
                sender_display = f"[@{user.username}]({contact_link})"
            else:
                contact_link = f"tg://user?id={user.id}"
                sender_display = f"[{user.first_name or 'صاحب الطلب'}]({contact_link})"
        else:
            contact_link = message.link or "خاص"
            sender_display = f"[فتح المحادثة]({contact_link})"

        formatted_text = (
            f"🚨 **طلب توصيل جديد**\n\n"
            f"📝 **الرسالة:**\n{message.text}\n\n"
            f"💬 **تواصل مع العميل:** {sender_display}\n"
            f"🔗 **رابط مباشر:** {contact_link}"
        )

        # الإرسال عبر البوت الرسمي
        if official_bot:
            for target in SUBSCRIBERS:
                try:
                    await official_bot.send_message(
                        chat_id=target,
                        text=formatted_text,
                        disable_web_page_preview=True
                    )
                    print(f"[BOT SUCCESS] Sent via official bot to {target}")
                except Exception as e:
                    print(f"[BOT ERROR] Could not send to {target}: {e}")
        else:
            print("[BOT ERROR] official_bot is not configured! Check BOT_TOKEN.")
    else:
        print(f"[SKIPPED] Rejected by AI.")

async def main():
    print("[SYSTEM] Starting Official Bot & Userbot with Gemini AI...")
    if official_bot:
        await official_bot.start()
    await app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    # حل مشكلة asyncio في بايثون الحديث
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(main())

