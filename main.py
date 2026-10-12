import os
import re
import asyncio
import hashlib
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
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
        self.wfile.write(b"Barq Test System Active!")

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
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

TARGET_USERS = ["abood1317"]
PROCESSED_KEYS = set()

def analyze_with_pure_ai(text: str) -> bool:
    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت ذكاء اصطناعي لقروبات التوصيل والمشاوير بجازان. هل الرسالة من زبون يبحث عن توصيل/سواق (YES) أم سائق يعلن عن خدماته (NO)؟
الرسالة: "{text}"
الجواب بكلمة واحدة فقط: (YES) أو (NO):"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        payload = {
            "model": "openai/gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 3
        }
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            return "YES" in answer
    except Exception:
        pass
    return False

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "my_userbot_test",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    bot = None
    if BOT_TOKEN:
        try:
            bot = Client(
                "helper_bot_test",
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
        if not message or not message.id:
            return

        raw_text = message.text or message.caption or ""
        clean_text = raw_text.strip()

        # أمر اختبار فوري: لو كتبت /test في أي قروب، سيرد عليك البوت ليؤكد أنه متصل
        if clean_text == "/test":
            try:
                await message.reply("✅ نظام برق شغال ويسحب الرسائل الحية بنجاح!")
                print("🛠️ [اختبار ناجح]: استجابة لأمر /test في مجموعة", flush=True)
            except Exception as e:
                print(f"⚠️ خطأ في الرد على أمر الاختبار: {e}", flush=True)
            return

        if message.from_user and message.from_user.is_self:
            return

        if len(clean_text) < 3:
            return

        msg_key = f"{message.chat.id}_{message.id}"
        if msg_key in PROCESSED_KEYS:
            return
        PROCESSED_KEYS.add(msg_key)

        is_client_request = await asyncio.get_running_loop().run_in_executor(
            None, analyze_with_pure_ai, clean_text
        )

        if is_client_request:
            print(f"✅ [طلب عميل مقبول]: {clean_text[:30]}...", flush=True)

            row = []
            if message.from_user:
                if message.from_user.username:
                    user_url = f"https://t.me/{message.from_user.username}"
                    user_label = f"💬 فتح المحادثة (@{message.from_user.username})"
                else:
                    user_url = f"tg://openmessage?user_id={message.from_user.id}"
                    user_label = "💬 فتح المحادثة"
                row.append(InlineKeyboardButton(user_label, url=user_url))

            if message.link:
                row.append(InlineKeyboardButton("📩 الرسالة الأصلية", url=message.link))

            reply_markup = InlineKeyboardMarkup([row]) if row else None

            for user in TARGET_USERS:
                try:
                    if bot:
                        await bot.send_message(chat_id=user, text=f"📥 طلب جديد:\n\n{clean_text}", reply_markup=reply_markup, disable_web_page_preview=True)
                    else:
                        await userbot.send_message(chat_id=user, text=f"📥 طلب جديد:\n\n{clean_text}", reply_markup=reply_markup, disable_web_page_preview=True)
                except Exception:
                    pass

    await userbot.start()
    print("🚀 [نظام الفحص والتبريد يعمل الآن على رندر]...", flush=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
