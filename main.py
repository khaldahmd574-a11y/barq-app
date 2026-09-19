import os
import asyncio
from aiohttp import web

# 1. تهيئة الـ Event Loop لمنع أي تعارض في Render
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

from hydrogram import Client, filters
from hydrogram.types import Message
import google.generativeai as genai

# --- جلب المفاتيح الأساسية من متغيرات البيئة ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

# 🎯 معرف الحساب المستهدف بإضافة @ مباشرة
TARGET_USER = "@abood1317"

# 2. إعداد الحساب الوهمي (Userbot) لسحب الرسائل
app = Client(
    "barq_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

# 3. إعداد البوت الرسمي لإعادة الإرسال
official_bot = Client(
    "barq_official_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
) if BOT_TOKEN else None

# 4. إعداد ذكاء Gemini الاصطناعي
if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

def analyze_with_ai(text: str) -> str:
    """تحليل نص الرسالة بواسطة Gemini AI"""
    if not ai_model:
        print("⚠️ [AI WARNING] GEMINI_API_KEY is not configured!")
        return "NO"

    prompt = f"""
أنت نظام ذكي متخصص في فلترة طلبات التوصيل.
حلل الرسالة التالية وأجب بـ YES فقط إذا كانت عبارة عن "طلب توصيل من زبون/عميل" يبحث عن مندوب لتوصيل شحنة أو أغراض أو مشوار.
أجب بـ NO إذا كانت إعلان من مندوب، أو عرض خدمة، أو استفسار عام، أو غير متعلقة بطلب توصيل.

الرسالة:
"{text}"
    """
    try:
        response = ai_model.generate_content(prompt)
        result = response.text.strip().upper()
        print(f"🤖 [AI DECISION] -> {result}")
        return result
    except Exception as e:
        print(f"❌ [AI ERROR] {e}")
        return "NO"

@app.on_message(filters.group)
async def handle_group_messages(client: Client, message: Message):
    """الاستماع لكافة الرسائل الجديدة الواردة في القروبات"""
    text = message.text or message.caption
    if not text:
        return

    chat_title = message.chat.title or "قروب"
    print(f"📥 [NEW MESSAGE] [{chat_title}] -> {text[:50]}...")

    # التحليل الذكي
    decision = analyze_with_ai(text)

    if "YES" in decision:
        user = message.from_user
        if user:
            if user.username:
                contact_link = f"https://t.me/{user.username}"
                sender_display = f"[@{user.username}]({contact_link})"
            else:
                contact_link = f"tg://user?id={user.id}"
                sender_display = f"[{user.first_name or 'صاحب الطلب'}]({contact_link})"
        else:
            contact_link = message.link or "رابط غير متوفر"
            sender_display = f"[فتح المحادثة]({contact_link})"

        formatted_text = (
            f"🚨 **طلب توصيل جديد**\n\n"
            f"📝 **الرسالة:**\n{text}\n\n"
            f"💬 **تواصل مع العميل:** {sender_display}\n"
            f"🔗 **الرابط:** {contact_link}"
        )

        if official_bot:
            try:
                await official_bot.send_message(
                    chat_id=TARGET_USER,
                    text=formatted_text,
                    disable_web_page_preview=True
                )
                print(f"✅ [SUCCESS] Sent directly to {TARGET_USER}")
            except Exception as e:
                print(f"❌ [SEND ERROR] Could not send to {TARGET_USER}: {e}")
        else:
            print("⚠️ [CONFIG ERROR] official_bot is missing!")
    else:
        print("⏭️ [SKIPPED] Not a delivery request.")

# --- سيرفر ويب لمنع إيقاف Render ---
async def handle_ping(request):
    return web.Response(text="Bot is running perfectly 24/7!")

async def start_web_server():
    server = web.Application()
    server.router.add_get("/", handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 [WEB SERVER] Active on port {port}")

async def main():
    print(f"🚀 [SYSTEM] Starting Userbot & Official Bot (Target: {TARGET_USER})...")
    await start_web_server()
    if official_bot:
        await official_bot.start()
    await app.start()
    print("✨ [SYSTEM] All services active and listening to messages...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    loop.run_until_complete(main())

