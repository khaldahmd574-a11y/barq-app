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

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "fs_990"]

PROCESSED_KEYS = set()

# =========================================================
# PURE AI ANALYSIS ENGINE
# =========================================================

def analyze_with_pure_ai(text: str) -> bool:
    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت نظام ذكاء اصطناعي متخصص في تصنيف رسائل التوصيل والمشاوير بدقة متناهية.
مهمتك: التمييز بين "زبون يطلب توصيلاً أو يسأل عن سائق" وبين "سائق يعرض خدمته أو إعلانه".

أجب بـ YES فقط إذا كان الكاتب زبوناً يطلب توصيلة أو سائقاً.
أجب بـ NO إذا كان الكاتب سائقاً يعرض خدماته أو إعلاناً.

[قواعد وتوجيهات صارمة للتصنيف بـ YES]:
1. أجب بـ YES إذا احتوت الرسالة على طلب توصيل، نقل، شحن، أو دباب من زبون.
2. أجب بـ YES إذا احتوت على استفسار أو بحث عن سائق/سائقة مثل: ("ابي سواق"، "مطلوب سائقة"، "حد يراني"، "من قريب من"، "مين يوصل"، "محتاج توصيله"، "حد فاضي").
3. أجب بـ YES إذا ذكر الزبون ميزانية أو سعراً محدد للمشوار (مثال: "المشوار بـ 10"، "معي 15"، "من الحصمة للحصمة بـ 10"). تحديد السعر من الكاتب لا يعني أنه سائق بل زبون يحدد ميزانيته.
4. أجب بـ YES لطلبات العقود والدوامات الشهرية إذا كان الكاتب يبحث عن توصيل (مثال: "ابي سواق/ه دوامي يوميا من...").

[قواعد التصفية بـ NO]:
1. أجب بـ NO إذا كان الكاتب سائقاً يعرض سيارته أو خدماته (مثال: "أنا قريب"، "متوفر توصيل"، "سائق خاص جاهز"، "فاضي الحين"، "نوفر نقل طالبات").
2. أجب بـ NO للإعلانات، الروابط، والرسائل العادية.

الرسالة المراد تحليلها:
"{text}"

الجواب (أجب بكلمة YES أو NO فقط بدون أي إضافة):"""

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
        res = requests.post(url, headers=headers, json=payload, timeout=2.5)
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

    loop = asyncio.get_event_loop()
    is_client_request = await loop.run_in_executor(None, analyze_with_pure_ai, clean_text)

    if is_client_request:
        print(f"✅ [طلب عميل مقبول بالذكاء الاصطناعي]: {clean_text[:30]}...", flush=True)

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
            async for dialog in userbot.get_dialogs(limit=15):
                if dialog.top_message:
                    await process_live_message(userbot, bot, dialog.top_message)
        except Exception:
            pass
            
        await asyncio.sleep(10)

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
    print("🚀 تم تشغيل النظام المحدث شاملاً الرسائل الاستفسارية القريبة!", flush=True)

    asyncio.create_task(fast_dialog_poller(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

