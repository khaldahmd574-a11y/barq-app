import os
import asyncio
import hashlib
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from groq import Groq
from hydrogram import Client
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
# KEEP ALIVE SERVER 24/7
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Multi-Key Engine Active!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# =========================================================
# CONFIGURATION & MULTI-KEY ROTATION
# =========================================================

SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

GROQ_KEYS = [
    os.environ.get("GROQ_API_KEY_1", "").strip(),
    os.environ.get("GROQ_API_KEY_2", "").strip(),
    os.environ.get("GROQ_API_KEY_3", "").strip(),
    os.environ.get("GROQ_API_KEY", "").strip()
]

GROQ_KEYS = [k for k in GROQ_KEYS if k]
CURRENT_KEY_INDEX = 0

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "fs_990"]

PROCESSED_KEYS = set()

# =========================================================
# GROQ AI ANALYSIS ENGINE
# =========================================================

def analyze_with_groq(text: str) -> bool:
    global CURRENT_KEY_INDEX

    if not GROQ_KEYS:
        print("❌ لا توجد مفاتيح Groq مضافة!", flush=True)
        return False

    if re.search(r'(05\d{8}|\+?9665\d{8}|05\d\s?\d{3}\s?\d{4})', text):
        return False

    prompt = f"""أنت نظام تصنيف لطلبات التوصيل والمشاوير.
حدد هل النص هو "طلب توصيل من زبون يبحث عن سائق" أم "إعلان/عرض خدمة من سائق".

أجب بـ YES فقط إذا كانت الرسالة:
- زبون يطلب توصيل أو يسأل عن سواق (مثل: "من فاضي؟"، "حد قريب؟"، "ابغى سواق"، "هل يوجد سواق؟"، "مين يوصل؟"، "احتاج توصيل").

أجب بـ NO فقط إذا كانت الرسالة:
- سائق يعرض خدمته (مثل: "أنا فاضي"، "متواجد للتوصيل"، "سيارة لنقل"، "توصيل خاص").
- إعلان أو كلام غير متعلق بطلب مشوار.

الرسالة: "{text}"
الجواب (YES أو NO فقط):"""

    for _ in range(len(GROQ_KEYS)):
        active_key = GROQ_KEYS[CURRENT_KEY_INDEX]
        try:
            client = Groq(api_key=active_key)
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model="openai/gpt-oss-120b",
                temperature=0.0,
                max_tokens=5,
            )
            answer = response.choices[0].message.content.strip().upper()
            print(f"🤖 [Groq المفتاح #{CURRENT_KEY_INDEX + 1}]: '{text[:30]}...' -> {answer}", flush=True)
            return "YES" in answer
        except Exception as e:
            print(f"⚠️ المفتاح #{CURRENT_KEY_INDEX + 1} واجه مشكلة ({e})، جاري التبديل...", flush=True)
            CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(GROQ_KEYS)

    return False

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    try:
        if not message or not message.id:
            return

        if message.from_user and message.from_user.is_self:
            return

        raw_text = message.text or message.caption or ""
        clean_text = raw_text.strip()
        if len(clean_text) < 4:
            return

        msg_key = f"{message.chat.id}_{message.id}"
        text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
        
        if msg_key in PROCESSED_KEYS or text_hash in PROCESSED_KEYS:
            return
            
        PROCESSED_KEYS.add(msg_key)
        PROCESSED_KEYS.add(text_hash)

        if len(PROCESSED_KEYS) > 10000:
            PROCESSED_KEYS.clear()

        loop = asyncio.get_event_loop()
        is_client_request = await loop.run_in_executor(None, analyze_with_groq, clean_text)

        if is_client_request:
            print(f"✅ [تم قبول الرسالة وإرسالها للمشتركين]: {clean_text[:30]}...", flush=True)

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

            for user in TARGET_USERS:
                sent = False
                if bot:
                    try:
                        await bot.send_message(
                            chat_id=user,
                            text=clean_text,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )
                        sent = True
                    except Exception as e:
                        print(f"❌ خطأ إرسال البوت لـ {user}: {e}", flush=True)

                if not sent:
                    try:
                        await userbot.send_message(
                            chat_id=user,
                            text=clean_text,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )
                        print(f"✅ تم الإرسال عبر اليوزر بوت لـ {user}", flush=True)
                    except Exception as e:
                        print(f"❌ خطأ إرسال اليوزر بوت لـ {user}: {e}", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ معالجة: {e}", flush=True)

# =========================================================
# MAIN ENTRYPOINT (LIVE LISTENER ONLY)
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
        except Exception:
            pass

    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        await process_live_message(client, bot, message)

    await userbot.start()
    print("🚀 تم التشغيل عبر الاستماع اللحظي الفوري المباشر بطلب خفيف دون حظر!", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

