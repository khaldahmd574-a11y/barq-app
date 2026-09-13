import os
import asyncio
import re
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from groq import Groq
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

# =========================================================
# SERVER TO KEEP ALIVE 24/7
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Super Fast AI Active 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# =========================================================
# CONFIGURATION
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

# ذاكرة حماية لمنع التكرار الشامل (بالـ ID وبالنص)
PROCESSED_MSG_IDS = set()
PROCESSED_TEXT_HASHES = set()

# =========================================================
# GROQ AI DECISION ENGINE (MODEL FIXED)
# =========================================================

def analyze_with_groq_fast(text: str) -> bool:
    # 1. استبعاد أرقام الجوال فوراً (إعلانات أو عروض سائقين)
    if re.search(r'(05\d{8}|\+?9665\d{8})', text):
        return False

    if not GROQ_API_KEY or not groq_client:
        return False

    prompt = f"""أنت ذكاء اصطناعي محترف لتصنيف الطلبات.
هل الرسالة التالية عبارة عن طلب توصيل / مشوار / طلب سواق / طلب مندوب من قبل زبون يبحث عن خدمة؟
أجب بكلمة واحدة فقط: YES أو NO.

الرسالة: "{text}"
الجواب:"""

    # استخدام النماذج المعتمدة الحالية في Groq لمنع خطأ 404
    active_models = [
        "llama-3.3-70b-versatile",
        "llama3-8b-8192",
        "mixtral-8x7b-32768"
    ]

    for model_name in active_models:
        try:
            response = groq_client.chat.completions.create(
                messages=[{"role": "user", "content": prompt}],
                model=model_name,
                temperature=0,
                max_tokens=2
            )
            raw_res = response.choices[0].message.content.strip().upper()
            return "YES" in raw_res
        except Exception:
            continue

    return False

# =========================================================
# REAL-TIME INSTANT PROCESSING (بدون بطء وبدون تكرار)
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    if not message or not message.id:
        return

    # 1. منع تكرار معرف الرسالة
    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MSG_IDS:
        return
    PROCESSED_MSG_IDS.add(msg_key)

    if len(PROCESSED_MSG_IDS) > 20000:
        PROCESSED_MSG_IDS.clear()

    # 2. استبعاد رسائل الحساب نفسه
    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    clean_text = raw_text.strip()
    if len(clean_text) < 3:
        return

    # 3. منع تكرار نفس النص إذا نُشر في عدة قروبات بنفس اللحظة
    text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    if text_hash in PROCESSED_TEXT_HASHES:
        return

    # 4. التقييم بالذكاء الاصطناعي
    if analyze_with_groq_fast(clean_text):
        PROCESSED_TEXT_HASHES.add(text_hash)
        if len(PROCESSED_TEXT_HASHES) > 10000:
            PROCESSED_TEXT_HASHES.clear()

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
        
        # إرسال نص الرسالة الصافي فقط بدون اسم القروب
        text_to_send = clean_text

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
                    print(f"❌ خطأ توجيه: {e}", flush=True)

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
            print("✅ تم تشغيل البوت المساعد بنجاح!", flush=True)
        except Exception as e:
            print(f"⚠️ خطأ البوت: {e}", flush=True)

    # الاستماع المباشر واللحظي لجميع القروبات القنوات
    @userbot.on_message(filters.group | filters.channel)
    async def global_live_listener(client: Client, message: Message):
        await process_live_message(client, bot, message)

    await userbot.start()
    print("⚡ تم التفعيل الفوري! السحب يعمل بأقصى سرعة وبذكاء اصطناعي بدون تكرار.", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

