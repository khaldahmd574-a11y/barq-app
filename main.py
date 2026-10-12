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
        self.wfile.write(b"Barq Smart Polling Render Active!")

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

# =========================================================
# AI ANALYSIS ENGINE
# =========================================================

def analyze_with_pure_ai(text: str) -> bool:
    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت ذكاء اصطناعي لقروبات التوصيل والمشاوير بجازان. هل هذه الرسالة من زبون يبحث عن توصيل/مشوار/سواق (YES) أم سائق يعلن عن خدماته أو شخص آخر (NO)؟
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

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_and_send(userbot: Client, bot: Client, message: Message):
    if not message or not message.id:
        return

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    clean_text = raw_text.strip()
    if len(clean_text) < 3:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    
    if msg_key in PROCESSED_KEYS or text_hash in PROCESSED_KEYS:
        return
        
    PROCESSED_KEYS.add(msg_key)
    PROCESSED_KEYS.add(text_hash)
    if len(PROCESSED_KEYS) > 10000:
        PROCESSED_KEYS.clear()

    is_client_request = await asyncio.get_running_loop().run_in_executor(
        None, analyze_with_pure_ai, clean_text
    )

    if is_client_request:
        print(f"✅ [تم رصد طلب زبون على رندر]: {clean_text[:30]}...", flush=True)

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

# =========================================================
# SMART POLLING ENGINE (الحل البديل لضمان السحب على رندر)
# =========================================================

async def smart_polling_loop(userbot: Client, bot: Client):
    await asyncio.sleep(10)
    print("🔄 [بدء محرك السحب الذكي المخصص لـ Render]...", flush=True)
    
    while True:
        try:
            # فحص أحدث الحوارات والمجموعات المشترك فيها الحساب
            async for dialog in userbot.get_dialogs(limit=25):
                if dialog.chat and dialog.chat.type in ["group", "supergroup"]:
                    try:
                        async for msg in userbot.get_chat_history(chat_id=dialog.chat.id, limit=3):
                            await process_and_send(userbot, bot, msg)
                    except Exception:
                        pass
                await asyncio.sleep(0.5)
        except Exception as e:
            print(f"⚠️ تنبيه في حلقة السحب: {e}", flush=True)
            
        # الانتظار قليلًا قبل دورة الفحص التالية لتجنب أي حظر
        await asyncio.sleep(15)

# =========================================================
# MAIN ENTRYPOINT
# =========================================================

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "barq_render_polling",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    bot = None
    if BOT_TOKEN:
        try:
            bot = Client(
                "barq_render_helper_polling",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                in_memory=True
            )
            await bot.start()
        except Exception:
            pass

    await userbot.start()
    print("🚀 [نظام برق يعمل الآن بوضع الفحص الذكي على Render]...", flush=True)

    # تشغيل محرك السحب الذكي في الخلفية
    asyncio.create_task(smart_polling_loop(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
