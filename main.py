import os
import asyncio
from aiohttp import web
from hydrogram import Client, filters
from hydrogram.types import Message
import google.generativeai as genai

# --- 1. المفاتيح والمتغيرات ---
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("SESSION_STRING", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY", "")

# معرف المستهدف
TARGET_USER = "@abood1317"

# --- 2. إعداد العملاء ---
app = Client(
    "barq_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

official_bot = Client(
    "barq_official_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
) if BOT_TOKEN else None

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

def analyze_with_ai(text: str) -> str:
    if not ai_model:
        return "NO"
    prompt = f"""
أنت نظام ذكي لفلترة طلبات التوصيل.
إذا كانت الرسالة التالية طلب توصيل من زبون يبحث عن توصيل، أرجع كلمة: YES
إذا كانت غير ذلك، أرجع كلمة: NO

الرسالة:
"{text}"
    """
    try:
        response = ai_model.generate_content(prompt)
        res = response.text.strip().upper()
        print(f"🤖 [AI]: {res}")
        return res
    except Exception as e:
        print(f"❌ [AI Error]: {e}")
        return "NO"

# --- 3. دالة الاستماع للرسائل ---
@app.on_message(filters.group)
async def handle_group_messages(client: Client, message: Message):
    text = message.text or message.caption
    if not text:
        return

    chat_title = message.chat.title or "قروب"
    print(f"📥 [رسالة جديدة] [{chat_title}]: {text[:40]}")

    if "YES" in analyze_with_ai(text):
        user = message.from_user
        if user and user.username:
            contact = f"https://t.me/{user.username}"
            sender = f"[@{user.username}]({contact})"
        elif user:
            contact = f"tg://user?id={user.id}"
            sender = f"[{user.first_name or 'العميل'}]({contact})"
        else:
            contact = message.link or "خاص"
            sender = f"[فتح المحادثة]({contact})"

        msg = f"🚨 **طلب توصيل جديد**\n\n📝 **الرسالة:**\n{text}\n\n💬 **تواصل:** {sender}"

        if official_bot:
            try:
                await official_bot.send_message(chat_id=TARGET_USER, text=msg, disable_web_page_preview=True)
                print(f"✅ تم الإرسال إلى {TARGET_USER}")
            except Exception as e:
                print(f"❌ خطأ الإرسال: {e}")

# --- 4. سيرفر الويب وسير التشغيل الرئيسي ---
async def handle_ping(request):
    return web.Response(text="OK")

async def start_services():
    # تشغيل سيرفر الويب
    server = web.Application()
    server.router.add_get("/", handle_ping)
    runner = web.AppRunner(server)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 [Web Server Running on Port {port}]")

    # تشغيل البوتات
    if official_bot:
        await official_bot.start()
        print("🤖 [Official Bot Started]")
    
    await app.start()
    print("⚡ [Userbot Connected & Listening To Groups...]")

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(start_services())
    loop.run_forever()

