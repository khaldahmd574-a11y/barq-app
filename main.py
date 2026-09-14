import os
import asyncio
import re
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
        self.wfile.write(b"Barq OpenRouter Active 24/7!")

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

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

PROCESSED_MSG_IDS = set()

# الكلمات المفتاحية الشاملة
EXPRESS_KEYWORDS = [
    "مشوار", "توصيل", "سائق", "سواق", "سواقة", "سواقه", 
    "مندوب", "فاضي", "من فاضي", "مين فاضي", "أبغى", "ابغى", 
    "نوصل", "ويرجعني", "يرجعني", "الشاخر", "رديس", "مزهره", "مزهرة", "صبيا", "جازان", "ابوعريش"
]

# =========================================================
# AI & KEYWORD ANALYSIS
# =========================================================

def analyze_message(text: str) -> bool:
    # 1. استبعاد أرقام الجوال (عروض سائقين)
    if re.search(r'(05\d{8}|\+?9665\d{8})', text):
        return False

    clean = text.lower()

    # 2. مطابقة فورية للكلمات
    for kw in EXPRESS_KEYWORDS:
        if kw in clean:
            print(f"⚡ [مطابقة فورية]: {kw}", flush=True)
            return True

    # 3. فحص الذكاء الاصطناعي
    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""هل هذه الرسالة طلب توصيل/مشوار/مندوب/سائق؟ أجب بـ YES أو NO فقط.
الرسالة: "{text}"
الجواب:"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        payload = {
            "model": "qwen/qwen-2.5-7b-instruct",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 5
        }
        res = requests.post(url, headers=headers, json=payload, timeout=3)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            return "YES" in answer
    except Exception:
        pass

    return False

# =========================================================
# LIVE MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    if not message or not message.id:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MSG_IDS:
        return
    PROCESSED_MSG_IDS.add(msg_key)

    # عدم معالجة الرسائل القديمة جداً عند التشغيل الأول
    if len(PROCESSED_MSG_IDS) > 5000:
        PROCESSED_MSG_IDS.clear()

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    clean_text = raw_text.strip()
    if len(clean_text) < 2:
        return

    chat_title = getattr(message.chat, 'title', str(message.chat.id))

    loop = asyncio.get_event_loop()
    is_valid = await loop.run_in_executor(None, analyze_message, clean_text)

    if is_valid:
        print(f"✅ [صيد رسالة من {chat_title}]: {clean_text[:30]}", flush=True)

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

# =========================================================
# HARDWARE SCANNER LOOP (حل مشكلة القروبات الكبيرة)
# =========================================================

async def active_chat_scanner(userbot: Client, bot: Client):
    """حلقة مسح دورية تجبر تلغرام على إعطاء السكربت آخر الرسائل من كافة المحادثات"""
    await asyncio.sleep(10)
    print("🔄 [تفعيل الماسح المباشر للقروبات الكبيرة والقنوات]...", flush=True)
    
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=100):
                if dialog.chat.type.name in ["GROUP", "SUPERGROUP", "CHANNEL"]:
                    try:
                        async for msg in userbot.get_chat_history(dialog.chat.id, limit=3):
                            await process_live_message(userbot, bot, msg)
                    except Exception:
                        continue
        except Exception as e:
            print(f"⚠️ خطأ في حلقة المسح: {e}", flush=True)
            
        await asyncio.sleep(7)  # يفحص كل القروبات كل 7 ثوانٍ مجدداً

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
    print("🚀 تم تشغيل البوت + حلقة السحب الدورية الشاملة!", flush=True)

    # تشغيل حلقة الفحص النشط للقروبات الكبيرة في الخلفية
    asyncio.create_task(active_chat_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

