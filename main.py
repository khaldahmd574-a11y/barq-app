import os
import asyncio
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from groq import Groq
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

# =========================================================
# KEEP ALIVE SERVER 24/7
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Smart AI Bot Active 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# =========================================================
# CONFIGURATION & CONFIG RECOVERY
# =========================================================

SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

groq_client = None
if GROQ_API_KEY:
    try:
        groq_client = Groq(api_key=GROQ_API_KEY)
        print("✅ تم الاتصال بمكتبة Groq بنجاح", flush=True)
    except Exception as e:
        print(f"❌ [Groq Init Error] {e}", flush=True)

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]
PROCESSED_MESSAGES = set()
AI_CACHE = {}

# =========================================================
# ADVANCED GROQ AI DECISION ENGINE
# =========================================================

def analyze_with_groq(text: str) -> bool:
    # 1. استبعاد أرقام الجوال فوراً (عروض سائقين أو إعلانات)
    if re.search(r'(05\d{8}|\+?9665\d{8})', text):
        return False

    # 2. فحص الذاكرة المؤقتة لمنع تكرار الاستهلاك
    if text in AI_CACHE:
        return AI_CACHE[text]

    if not GROQ_API_KEY or not groq_client:
        return False

    prompt = f"""أنت ذكاء اصطناعي لتصنيف رسائل مجموعات تليجرام في السعودية.
حدد هل الرسالة التالية هي "طلب توصيل / مشوار / بحث عن سواق أو مندوب" قادم من زبون فقط؟
أجب بكلمة واحدة فقط: YES أو NO.

الرسالة: "{text}"
الجواب:"""

    models = ["llama-3.1-8b-instant", "llama3-8b-8192", "mixtral-8x7b-32768"]

    for model_name in models:
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                temperature=0,
                max_tokens=2
            )
            raw_res = response.choices[0].message.content.strip().upper()
            is_valid = "YES" in raw_res
            
            AI_CACHE[text] = is_valid
            if len(AI_CACHE) > 1000:
                AI_CACHE.clear()

            return is_valid
        except Exception:
            continue

    return False

# =========================================================
# MESSAGE PROCESSING & FORWARDING
# =========================================================

async def process_message(userbot: Client, bot: Client, message: Message):
    if not message or not message.id:
        return

    # تجاهل المحادثات الخاصة المباشرة
    if message.chat and message.chat.type.value not in ["group", "supergroup", "channel"]:
        return

    # تجاهل رسائل الحساب نفسه
    if message.from_user and message.from_user.is_self:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MESSAGES:
        return
    
    PROCESSED_MESSAGES.add(msg_key)
    if len(PROCESSED_MESSAGES) > 10000:
        PROCESSED_MESSAGES.clear()

    raw_text = message.text or message.caption or ""
    if len(raw_text.strip()) < 3:
        return

    if analyze_with_groq(raw_text):
        buttons = []
        row = []
        
        if message.from_user:
            if message.from_user.username:
                user_url = f"https://t.me/{message.from_user.username}"
                user_label = f"💬 فتح المحادثة (@{message.from_user.username})"
            else:
                user_url = f"tg://openmessage?user_id={message.from_user.id}"
                user_label = f"💬 فتح المحادثة ({message.from_user.first_name or 'المستخدم'})"
            row.append(InlineKeyboardButton(user_label, url=user_url))

        if message.link:
            row.append(InlineKeyboardButton("📩 الرسالة الأصلية", url=message.link))
        
        if row:
            buttons.append(row)
            
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        chat_title = message.chat.title or "مجموعة"
        text_to_send = f"📌 من: {chat_title}\n\n{raw_text}"

        for user in TARGET_USERS:
            sent = False
            if bot:
                try:
                    await bot.send_message(
                        chat_id=user,
                        text=text_to_send,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                    sent = True
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    try:
                        await bot.send_message(
                            chat_id=user,
                            text=text_to_send,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )
                        sent = True
                    except Exception:
                        pass
                except Exception:
                    pass

            if not sent:
                try:
                    await userbot.send_message(
                        chat_id=user,
                        text=text_to_send,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"❌ خطأ توجيه بالحساب: {e}", flush=True)

# =========================================================
# REAL TIME SCANNER (المحرك التكراري لسحب جميع القروبات)
# =========================================================

async def real_time_channel_and_group_scanner(userbot: Client, bot: Client):
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=50):
                if dialog.chat.type.value in ["group", "supergroup", "channel"]:
                    try:
                        async for msg in userbot.get_chat_history(dialog.chat.id, limit=2):
                            await process_message(userbot, bot, msg)
                    except Exception:
                        pass
                    await asyncio.sleep(0.1)
        except Exception as e:
            print(f"⚠️ خطأ أثناء الفحص: {e}", flush=True)
            
        await asyncio.sleep(7)

# =========================================================
# MAIN ENTRYPOINT
# =========================================================

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "my_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    bot = None
    if BOT_TOKEN:
        try:
            bot = Client(
                "helper_bot",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                in_memory=True
            )
            await bot.start()
            print("✅ تم اتصال وتشغيل البوت المساعد بالتوافق مع التوكن الجديد!", flush=True)
        except Exception as e:
            print(f"⚠️ خطأ تشغيل البوت: {e}", flush=True)

    @userbot.on_message(filters.group | filters.channel)
    async def global_listener(client: Client, message: Message):
        await process_message(client, bot, message)

    await userbot.start()
    print("✅ تم تشغيل الحساب وربط جميع القروبات 100% بنجاح!", flush=True)

    asyncio.create_task(real_time_channel_and_group_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

