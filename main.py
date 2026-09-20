import os
import asyncio
import hashlib
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import requests
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

# =========================================================
# KEEP ALIVE SERVER 24/7 FOR RENDER
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Merged AI & Deep Scanner Active!")

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
API_ID = int(os.environ.get("TELEGRAM_API_ID", os.environ.get("API_ID", 39120728)))
API_HASH = os.environ.get("TELEGRAM_API_HASH", os.environ.get("API_HASH", "1deec8393ce5aa05c54c0c7e280377d4")).strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8782796916:AAEe9YRkzbfm3F5e9rj49iHfDS0wRTnVmmo").strip()

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]
PROCESSED_MESSAGES = set()

# =========================================================
# PURE AI CLASSIFIER (NO KEYWORDS)
# =========================================================

def analyze_with_openrouter(text: str) -> bool:
    if not OPENROUTER_KEY:
        print("❌ خطأ: لا يوجد مفتاح OpenRouter API Key!", flush=True)
        return False

    prompt = f"""You are an expert AI classifier analyzing raw Telegram chat messages from delivery/transportation groups.

Determine if the author is a CLIENT/CUSTOMER seeking a service, or a DRIVER/COURIER offering a service.

Rules:
- Respond YES if the message is written by a client looking for a ride, food delivery, package transfer, driver, courier, or asking if someone is available.
- Respond NO if the message is written by a driver/courier offering their availability, services, or posting contact details.

Message:
"{text}"

Output ONLY "YES" or "NO":"""

    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }

    try:
        payload = {
            "model": "meta-llama/llama-3.1-8b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 5
        }
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            res_data = response.json()
            answer = res_data['choices'][0]['message']['content'].strip().upper()
            return "YES" in answer
        else:
            print(f"⚠️ خطأ استجابة الذكاء الاصطناعي ({response.status_code}): {response.text}", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ اتصال بالذكاء الاصطناعي: {e}", flush=True)

    return False

# =========================================================
# CORE MESSAGE PROCESSOR
# =========================================================

async def process_message(bot, message: Message):
    if not message or not message.id:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MESSAGES:
        return
    
    PROCESSED_MESSAGES.add(msg_key)
    if len(PROCESSED_MESSAGES) > 10000:
        PROCESSED_MESSAGES.clear()

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    clean_text = raw_text.strip()
    if len(clean_text) < 2:
        return

    # الفحص بالذكاء الاصطناعي الخالص
    loop = asyncio.get_event_loop()
    is_client_request = await loop.run_in_executor(None, analyze_with_openrouter, clean_text)

    if is_client_request:
        print(f"✅ [تمت الموافقة بالذكاء الاصطناعي]: {clean_text[:40]}...", flush=True)

        buttons = []
        row = []
        
        if message.from_user:
            if message.from_user.username:
                user_url = f"https://t.me/{message.from_user.username}"
                user_label = f"💬 المحادثة (@{message.from_user.username})"
            else:
                user_url = f"tg://openmessage?user_id={message.from_user.id}"
                user_label = f"💬 المحادثة ({message.from_user.first_name or 'المستخدم'})"
            row.append(InlineKeyboardButton(user_label, url=user_url))

        if message.link:
            row.append(InlineKeyboardButton("📩 الرسالة الأصلية", url=message.link))
        
        if row:
            buttons.append(row)
            
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

        for user in TARGET_USERS:
            try:
                await bot.send_message(
                    chat_id=user,
                    text=clean_text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await bot.send_message(
                    chat_id=user,
                    text=clean_text,
                    reply_markup=reply_markup,
                    disable_web_page_preview=True
                )
            except Exception as e:
                print(f"❌ خطأ توجيه: {e}", flush=True)

# =========================================================
# REAL-TIME DEEP SCANNER (من كودك القديم لجلب كل القروبات)
# =========================================================

async def real_time_channel_and_group_scanner(userbot, bot):
    while True:
        try:
            # جلب آخر 100 محادثة ونشاط بانتظام لضمان تغطية كامل القروبات الكبيرة
            async for dialog in userbot.get_dialogs(limit=100):
                try:
                    async for msg in userbot.get_chat_history(dialog.chat.id, limit=3):
                        await process_message(bot, msg)
                except Exception:
                    pass
                await asyncio.sleep(0.05)

        except Exception as e:
            print(f"⚠️ خطأ أثناء الفحص العميق: {e}", flush=True)
            
        # إعادة الفحص الشامل والسريع كل 5 ثوانٍ
        await asyncio.sleep(5)

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

    bot = Client(
        "helper_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True
    )

    # الاستماع الحي الفوري
    @userbot.on_message(~filters.me & ~filters.private)
    async def global_listener(client: Client, message: Message):
        await process_message(bot, message)

    await userbot.start()
    await bot.start()
    print("🚀 تم تشغيل النظام المدمج (فحص عميق للقروبات الكبيرة + ذكاء اصطناعي خالص)!", flush=True)

    # تشغيل الفاحص المباشر في الخلفية
    asyncio.create_task(real_time_channel_and_group_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

