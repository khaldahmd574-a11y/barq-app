import os
import re
import time
import asyncio
import hashlib
import requests
from difflib import SequenceMatcher
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.enums import ChatType

# =========================================================
# KEEP ALIVE SERVER 24/7
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Direct System Active!")

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

TARGET_USER = "abood1317"
PROCESSED_KEYS = set()

# فلترة بالذكاء الاصطناعي
def analyze_intent_with_ai(text: str) -> bool:
    clean = " ".join(text.split()).strip()
    if not clean or len(clean) < 2 or not OPENROUTER_API_KEY:
        return True # لو مافي مفتاح ذكاء اصطناعي، مررها مؤقتاً للتأكد من السحب

    prompt = f"""أنت ذكاء اصطناعي مخصص لقروبات التوصيل والمشاوير. هل الرسالة من [زبون يبحث عن توصيل/سائق/مندوب] أم [سائق يعلن عن نفسه]؟
أجب بكلمة واحدة فقط: (YES) للزبون، أو (NO) للسائق الملعن.
الرسالة: "{clean}"
الجواب:"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        payload = {
            "model": "openai/gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 2
        }
        res = requests.post(url, headers=headers, json=payload, timeout=4)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [AI]: '{clean[:20]}...' -> {answer}", flush=True)
            return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ AI: {e}", flush=True)

    return True

# معالجة الرسائل المباشرة بدون شروط معقدة
async def process_message(userbot: Client, bot: Client, message: Message):
    try:
        if not message or not message.text:
            return
        
        # التأكد أنها مجموعة وليست محادثة خاصة
        if message.chat.type not in [ChatType.GROUP, ChatType.SUPERGROUP]:
            return

        text = message.text.strip()
        if len(text) < 2:
            return

        msg_key = f"{message.chat.id}_{message.id}"
        if msg_key in PROCESSED_KEYS:
            return
        PROCESSED_KEYS.add(msg_key)

        if len(PROCESSED_KEYS) > 5000:
            PROCESSED_KEYS.clear()

        # فحص الذكاء الاصطناعي
        loop = asyncio.get_running_loop()
        is_client = await loop.run_in_executor(None, analyze_intent_with_ai, text)

        if is_client:
            print(f"✅ [تم السحب بنجاح]: {text[:30]}", flush=True)

            # تجهيز الأزرار
            buttons = []
            if message.from_user and message.from_user.username:
                buttons.append([InlineKeyboardButton("💬 فتح المحادثة", url=f"https://t.me/{message.from_user.username}")])
            elif message.link:
                buttons.append([InlineKeyboardButton("📩 الرسالة الأصلية", url=message.link)])

            reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

            # الإرسال للبوت المساعد لكي يرسلها لك
            if bot:
                await bot.send_message(
                    chat_id=TARGET_USER,
                    text=f"📥 طلب جديد:\n\n{text}",
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
    except Exception as e:
        print(f"⚠️ خطأ معالجة: {e}", flush=True)

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "barq_simple_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING
    )

    bot = None
    if BOT_TOKEN:
        try:
            bot = Client(
                "barq_simple_helper",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN
            )
            await bot.start()
            print("🤖 [البوت المساعد متصل]", flush=True)
        except Exception as e:
            print(f"⚠️ خطأ البوت المساعد: {e}", flush=True)

    @userbot.on_message()
    async def listener(client: Client, message: Message):
        asyncio.create_task(process_message(client, bot, message))

    await userbot.start()
    print("🚀 [النظام المبسط يعمل الآن ويسحب من كل القروبات]...", flush=True)

    # مزامنة سريعة للقروبات لضمان استقبال الأحداث
    try:
        async for _ in userbot.get_dialogs(limit=30):
            pass
    except Exception:
        pass

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
