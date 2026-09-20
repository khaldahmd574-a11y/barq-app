import os
import asyncio
import hashlib
import re
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
# KEEP ALIVE SERVER 24/7 FOR RENDER
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Strict Filtering Active - Bot Forwarder Only!")

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
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

PROCESSED_KEYS = set()

# =========================================================
# STRICT HYBRID FILTERING ENGINE (تصفية صارمة)
# =========================================================

def analyze_message_strict(text: str) -> bool:
    clean = text.lower()

    # 1. رفض فوري لأي رسالة تحتوي على رقم جوال (إعلانات السواقين والمندوبين)
    if re.search(r'(05\d{8}|\+?9665\d{8}|05\d\s?\d{3}\s?\d{4})', text):
        print(f"🛑 [استبعاد فوري - رقم جوال]: {text[:30]}...", flush=True)
        return False

    # 2. رفض فوري لكلمات تقديم الخدمات والإعلانات
    driver_offer_triggers = [
        "نقل من", "نوفر", "توصيل طلبات", "سائق للمشاوير", "سيارة لنقل", 
        "تواصل مع", "للتواصل", "خدماتنا", "على الرقم", "واتساب", "تواصل خاص"
    ]
    for trigger in driver_offer_triggers:
        if trigger in clean and not any(req in clean for req in ["احتاج", "أحتاج", "ابي", "ابغى", "مطلوب"]):
            print(f"🛑 [استبعاد فوري - إعلان سائق]: {text[:30]}...", flush=True)
            return False

    # 3. التحليل بالذكاء الاصطناعي مع أوامر صارمة
    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت نظام تصفية صارم جداً. مهمتك تحديد هل النص هو "طلب زبون يبحث عن توصيل" أم "إعلان سائق/مندوب يقدم خدمة".

قواعد التصنيف:
- أجب بـ YES فقط إذا كان كاتب الرسالة زبوناً أو عميلاً يطلب مشوار، توصيل، سائق، أو مندوب (مثل: "احتاج سواق"، "مين فاضي يوصلني"، "ابي مشوار").
- أجب بـ NO فوراً إذا كانت الرسالة إعلاناً لسائق يقدم خدمة نقل، عرض توصيل، رقم جوال سائق، أو تنبيهاً.

الرسالة: "{text}"
الجواب (أجب بـ YES أو NO فقط):"""

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
            "max_tokens": 3
        }
        res = requests.post(url, headers=headers, json=payload, timeout=3.0)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [قرار الذكاء الاصطناعي]: '{text[:25]}...' -> {answer}", flush=True)
            return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ الذكاء الاصطناعي: {e}", flush=True)

    return False

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    if not message or not message.id:
        return

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    clean_text = raw_text.strip()
    if len(clean_text) < 4:
        return

    # منع التكرار الصارم
    msg_key = f"{message.chat.id}_{message.id}"
    text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    
    if msg_key in PROCESSED_KEYS or text_hash in PROCESSED_KEYS:
        return
        
    PROCESSED_KEYS.add(msg_key)
    PROCESSED_KEYS.add(text_hash)

    if len(PROCESSED_KEYS) > 10000:
        PROCESSED_KEYS.clear()

    # التصفية الصارمة
    loop = asyncio.get_event_loop()
    is_client_request = await loop.run_in_executor(None, analyze_message_strict, clean_text)

    if is_client_request:
        print(f"✅ [تم اعتماد طلب زبون حقيقي]: {clean_text[:30]}...", flush=True)

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

        # الإرسال عبر البوت فقط إلى المستهدفين
        for user in TARGET_USERS:
            if bot:
                try:
                    await bot.send_message(
                        chat_id=user,
                        text=clean_text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                    print(f"🚀 تم إرسال الطلب عبر البوت إلى: {user}", flush=True)
                except Exception as err:
                    print(f"⚠️ فشل الإرسال للبوت لدى المستهدف ({user}): {err}", flush=True)

# =========================================================
# FAST & LIGHTWEIGHT MULTI-GROUP SCANNER
# =========================================================

async def fast_dialog_poller(userbot: Client, bot: Client):
    await asyncio.sleep(3)
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=50):
                if dialog.top_message:
                    await process_live_message(userbot, bot, dialog.top_message)
        except Exception:
            pass
            
        await asyncio.sleep(3)

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
            print("🤖 تم تشغيل البوت المساعد للإرسال بنجاح!", flush=True)
        except Exception as e:
            print(f"❌ فشل تشغيل البوت المساعد: {e}", flush=True)

    @userbot.on_message(~filters.me & ~filters.private)
    async def global_live_listener(client: Client, message: Message):
        await process_live_message(client, bot, message)

    await userbot.start()
    print("🚀 تم التحديث: تصفية صارمة + السحب والإرسال من البوت المساعد فقط!", flush=True)

    asyncio.create_task(fast_dialog_poller(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

