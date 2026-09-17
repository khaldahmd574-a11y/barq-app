import os
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
        self.wfile.write(b"Cerebras AI Engine Active!")

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
CEREBRAS_API_KEY = os.environ.get("CEREBRAS_API_KEY", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "fs_990"]

PROCESSED_KEYS = set()

# =========================================================
# ULTRA FAST CEREBRAS AI ENGINE (NO MORE 404 ERRORS)
# =========================================================

def analyze_with_cerebras(text: str) -> bool:
    if not CEREBRAS_API_KEY:
        print("❌ لم يتم ضبط CEREBRAS_API_KEY!", flush=True)
        return False

    prompt = f"""أنت نظام ذكاء اصطناعي متخصص في تصنيف رسائل التوصيل والمشاوير في السعودية بدقة متناهية.
مهمتك: التمييز بين "زبون يطلب توصيلاً/أغراضاً/سائقاً أو يشرح دوامه" وبين "سائق يعرض خدمته أو إعلانه".

قواعد التصنيف:
1. أجب بـ YES إذا كان الكاتب زبوناً:
   - يطلب توصيلاً أو مندوباً (مثل: ماك، مطعم، أغراض، صامطة، أبو حجر).
   - يشرح دوامه ويريد اتفاقاً (مثل: دوامي من الجهو والشقيري للجازان نتفق ع السعر).
   - يسأل عن سائق قريب أو فاضي (مثل: من قريب، مين فاضي، فيه أحد).

2. أجب بـ NO إذا كان الكاتب سائقاً:
   - يعرض سيارته أو يذكر أنه متواجد/فاضي للخدمة.
   - يضع رقماً أو إعلان نقل طالبات/موظفات.

الرسالة المراد تحليلها:
"{text}"

الجواب (أجب بكلمة YES أو NO فقط):"""

    url = "https://api.cerebras.ai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {CEREBRAS_API_KEY}",
        "Content-Type": "application/json"
    }

    # أسماء النماذج المعتمدة المتاحة حالياً على Cerebras
    active_models = ["llama3.1-70b", "llama3.1-8b"]

    for model in active_models:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise classifier that responds only with YES or NO."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 5
            }
            res = requests.post(url, headers=headers, json=payload, timeout=2.5)
            if res.status_code == 200:
                answer = res.json()['choices'][0]['message']['content'].strip().upper()
                print(f"⚡ [Cerebras AI ({model})]: '{text[:30]}...' -> {answer}", flush=True)
                return "YES" in answer
        except Exception:
            pass

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
        is_client_request = await loop.run_in_executor(None, analyze_with_cerebras, clean_text)

        if is_client_request:
            print(f"🎯 [طلب زبون مقبول بالذكاء الخارق]: {clean_text[:30]}...", flush=True)

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
                    except Exception:
                        pass

                if not sent:
                    try:
                        await userbot.send_message(
                            chat_id=user,
                            text=clean_text,
                            reply_markup=reply_markup,
                            disable_web_page_preview=True
                        )
                    except Exception:
                        pass
    except Exception as e:
        print(f"⚠️ خطأ أثناء معالجة الرسالة: {e}", flush=True)

# =========================================================
# FAST MULTI-GROUP SCANNER (مسح المجموعات الكبيرة)
# =========================================================

async def fast_dialog_poller(userbot: Client, bot: Client):
    await asyncio.sleep(5)
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=35):
                if dialog.top_message:
                    await process_live_message(userbot, bot, dialog.top_message)
        except Exception:
            pass
            
        await asyncio.sleep(8)

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
        except Exception:
            pass

    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        await process_live_message(client, bot, message)

    await userbot.start()
    print("🚀 تم تشغيل البوت بمحرك Cerebras AI المحدث بدون أخطاء!", flush=True)

    asyncio.create_task(fast_dialog_poller(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

