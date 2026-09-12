import os
import asyncio
import re
import hashlib
import json
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Barq System Active 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

SESSION_STRING = os.environ.get("SESSION_STRING")
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4")
BOT_TOKEN = "8782796916:AAEe9YRkzbfm3F5e9rj49iHfDS0wRTnVmmo"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

def analyze_with_ai(text: str) -> bool:
    if not GROQ_API_KEY:
        print("⚠️ تنبيه: مفتاح GROQ_API_KEY غير مضاف في Render!")
        return False

    prompt = f"""
أنت خبير في تصفية رسائل التوصيل والتاكسي.
المطلوب: هل صاحب هذه الرسالة (زبون حقيقي) يبحث عن توصيله أو سائق أو مندوب لنفسه؟

قواعد الرفض الصارمة جداً (أجب بـ NO فوراً إذا تحققت):
1. عروض السائقين والمندوبين (مثل: فاضي، متوفر، نوصل، جاهز للمشاوير، سواق موجود، تواصل معي خاص).
2. إعلانات الإجازات المرضية، المعاملات، الخدمات الحكومية، السكني، الوظائف، والروابط.
3. الترحيب والقوانين والأسئلة العامة (مثل: كم من صامطة لجيزان، كم من فين لافين).

الشرط الوحيد للقبول (أجب بـ YES):
- زبون يطلب لنفسه حصراً (مثل: مين يوديني، ابغى سواق، نحتاج سيارة، من يرّجعني).

الرسالة:
"{text}"

أجب بكلمة واحدة فقط: YES أو NO.
"""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=3) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            answer = res_data["choices"][0]["message"]["content"].strip().upper()
            
            if "YES" in answer:
                print(f"✅ [AI PASS] طلب زبون مقبول: {text[:30]}...")
                return True
            else:
                print(f"🚫 [AI REJECT] تم رفض الرسالة (سائق/إعلان): {text[:30]}...")
                return False
    except Exception as e:
        print(f"❌ خطأ اتصالات Groq AI: {e}")
        return False

PROCESSED_MESSAGES = set()

async def process_message(bot, message: Message):
    if not message or not message.id:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MESSAGES:
        return
    PROCESSED_MESSAGES.add(msg_key)

    if len(PROCESSED_MESSAGES) > 20000:
        PROCESSED_MESSAGES.clear()

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    if not raw_text or len(raw_text) < 4:
        return

    # التقييم بواسطة الذكاء الاصطناعي
    is_valid = await asyncio.to_thread(analyze_with_ai, raw_text)
    if not is_valid:
        return

    buttons = []
    row = []

    if message.from_user:
        if message.from_user.username:
            user_url = f"https://t.me/{message.from_user.username}"
            user_label = f"💬 المحادثة (@{message.from_user.username})"
        else:
            user_url = f"tg://openmessage?user_id={message.from_user.id}"
            user_label = f"💬 المحادثة ({message.from_user.first_name or 'زبون'})"
        row.append(InlineKeyboardButton(user_label, url=user_url))

    if message.link:
        row.append(InlineKeyboardButton("📩 الرابط الأصلي", url=message.link))

    reply_markup = InlineKeyboardMarkup([row]) if row else None

    for user in TARGET_USERS:
        try:
            await bot.send_message(
                chat_id=user,
                text=raw_text,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await bot.send_message(chat_id=user, text=raw_text, reply_markup=reply_markup, disable_web_page_preview=True)
        except Exception as e:
            print(f"❌ خطأ توجيه: {e}")

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "my_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    bot = Client(
        "helper_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True
    )

    # الاستماع لجميع أنواع المجموعات والقنوات بدون استثناء
    @userbot.on_message(filters.group | filters.supergroup | filters.channel)
    async def global_listener(client: Client, message: Message):
        await process_message(bot, message)

    await userbot.start()
    await bot.start()
    print("🚀 تم التحديث: الذكاء الاصطناعي شغال 100% والسحب شامل ولحظي.")

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

