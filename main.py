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
        self.wfile.write(b"Barq Pure AI System Active!")

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

PROCESSED_KEYS = set()

# =========================================================
# HARDCODE FILTER (فلترة فورية لاستبعاد إعلانات السائقين)
# =========================================================

DRIVER_EXCLUDE_KEYWORDS = [
    "يتواصل معي", "تتواصل معي", "تواصل معي", "تواصل خاص", "خاص معي",
    "اللي يبغى", "اللي تبي", "اللي يحتاج", "اللي تحتاجه", "اللي تبي توصيل",
    "الي يبغى", "الي تبي", "الي يحتاج", "الي تبي توصيل",
    "متواجد", "متواجدين", "موجود في", "موجود بـ", "موجودين",
    "فاضي", "فاضيه", "فاضيين",
    "نوفر", "نوفر لكم", "خدمة توصيل", "خدمات توصيل", "للتوصيل", "جامعه او دوام",
    "سواق خاص", "سواقة خاص", "سائق خاص", "مندوب توصيل", "مندوب الداير"
]

def contains_driver_keywords(text: str) -> bool:
    t = text.lower()
    for kw in DRIVER_EXCLUDE_KEYWORDS:
        if kw in t:
            # استثناء بسيط: إذا كان العميل يطلب "ابغى سواق" أو "ابي سواق" فلا نستبعدها
            if ("ابغى" in t or "ابي" in t or "مطلوب" in t or "مين" in t or "حد" in t or "احتاج" in t) and ("فاضي" not in t and "يتواصل" not in t and "اللي تبي" not in t and "الي تبي" not in t):
                continue
            return True
    return False

# =========================================================
# STRICT AI ANALYSIS ENGINE (محرك ذكاء اصطناعي صارم جداً)
# =========================================================

def analyze_with_pure_ai(text: str) -> bool:
    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت نظام فلترة صارم جداً لطلبات التوصيل.
مهمتك: تحديد هل الرسالة صادرة من "زبون يطلب توصيلاً لنفسه" أم من "سائق/مندوب يعرض خدمته".

قواعد الحظر الصارمة (أجب بـ NO فوراً إذا انطبقت أي منها):
1. إذا كان الكاتب سائقاً أو مندوباً يعرض خدماته للآخرين (أمثلة: "مندوب فاضي"، "الي تبي سواق يتواصل معي"، "موجود في جازان"، "اللي يبغى توصيل"، "فاضي للطلبات").
2. إذا احتوت الرسالة على عبارات مثل "يتواصل معي"، "تواصل خاص"، "فاضي"، "متواجد".
3. الإعلانات العامة والتسويق.

أجب بـ YES فقط وفقط إذا كان الكاتب زبوناً يبحث عن توصيل بنفسه (أمثلة: "ابغى سواق شهر"، "احتاج توصيل للكلية"، "مين يوصلني صبيا"، "ابغى سواقة").

الرسالة:
"{text}"

الجواب (YES أو NO فقط):"""

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
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [قرار الذكاء الاصطناعي]: '{text[:35]}...' -> {answer}", flush=True)
            return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ في الاتصال بالذكاء الاصطناعي: {e}", flush=True)

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

    msg_key = f"{message.chat.id}_{message.id}"
    text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
    
    if msg_key in PROCESSED_KEYS or text_hash in PROCESSED_KEYS:
        return
        
    PROCESSED_KEYS.add(msg_key)
    PROCESSED_KEYS.add(text_hash)

    if len(PROCESSED_KEYS) > 10000:
        PROCESSED_KEYS.clear()

    # 1. التصفية المباشرة أولاً بالكلمات المفتاحية للسائقين
    if contains_driver_keywords(clean_text):
        print(f"🚫 [استبعاد مباشر - عرض سائق/مندوب]: {clean_text[:35]}...", flush=True)
        return

    # 2. الفحص عن طريق الذكاء الاصطناعي إذا تجاوزت الفلتر المباشر
    loop = asyncio.get_running_loop()
    is_client_request = await loop.run_in_executor(None, analyze_with_pure_ai, clean_text)

    if is_client_request:
        print(f"✅ [طلب عميل حقيقي مقبول]: {clean_text[:30]}...", flush=True)

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
# FAST MULTI-GROUP SCANNER
# =========================================================

async def fast_dialog_poller(userbot: Client, bot: Client):
    await asyncio.sleep(5)
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=30):
                if dialog.top_message:
                    await process_live_message(userbot, bot, dialog.top_message)
        except Exception as e:
            print(f"⚠️ خطأ في الفاحص الدائري: {e}", flush=True)
            
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
        except Exception as e:
            print(f"⚠️ لم يتم بدء البوت المساعد: {e}", flush=True)

    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        await process_live_message(client, bot, message)

    await userbot.start()
    print("🚀 تم تشغيل النظام المحدث بالفلاتر الصارمة!", flush=True)

    asyncio.create_task(fast_dialog_poller(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

