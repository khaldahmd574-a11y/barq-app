import os
import asyncio
from aiohttp import web

# 1. إنشاء وتحديد الـ loop لتفادي أخطاء بايثون الحديثة
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from hydrogram import Client, filters
from hydrogram.types import Message
import google.generativeai as genai

# --- إعدادات البيئة والمفاتيح ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

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

# إعداد ذكاء Gemini المجاني
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

def analyze_with_ai(text):
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

    ai_decision = analyze_with_ai(message.text)

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
            print("[BOT ERROR] official_bot is not configured!")
    else:
        print(f"[SKIPPED] Rejected by AI.")

# --- سيرفر ويب وهمي لإرضاء منصة Render ومنع إغلاق الخدمة ---
async def handle_ping(request):
    return web.Response(text="Bot is Alive & Running 24/7!")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"[WEB SERVER] Listening on port {port}")

async def main():
    print("[SYSTEM] Starting Official Bot & Userbot with Gemini AI...")
    await start_web_server()
    if official_bot:
        await official_bot.start()
    await app.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())

