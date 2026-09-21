import os
import asyncio
import hashlib
import requests
import re
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
        self.wfile.write(b"Barq System Online & Smart Filtered!")

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
# HARD RULES (قواعد استبعاد السائقين والمناديب برمجياً)
# =========================================================

DRIVER_DENY_PATTERNS = [
    r"يتوصل معي",
    r"يتواصل معي",
    r"تواصل معي",
    r"تواصلوا معي",
    r"يتواصلون معي",
    r"يتواصل خاص",
    r"تواصل خاص",
    r"يجي خاص",
    r"يجيني خاص",
    r"يراسلني خاص",
    r"فاضي لتوصيل",
    r"متواجد لتوصيل",
    r"على أتم الاستعداد",
    r"الي يبغى.*يتوصل",
    r"الي يبغى.*يتواصل",
    r"اللي يبي.*يجي",
    r"مين تبي سواق",
    r"مين يبغى سواق",
]

def contains_driver_offer(text: str) -> bool:
    for pattern in DRIVER_DENY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

# =========================================================
# HYBRID INTENT ENGINE (الفلتر الذكي)
# =========================================================

def analyze_post_strictly(text: str) -> bool:
    clean_text = text.strip()

    # كلمات صريحة واضحة لطلبات الزبائن
    is_explicit_request = any(clean_text.startswith(w) for w in ["ابغى", "أبغى", "ابغا", "أبغا", "احتاج", "أحتاج", "مطلوب", "مين", "من يوصل", "من يوديني"])

    # 1. الاستبعاد البرمجي المباشر لإعلانات المناديب
    if not is_explicit_request and contains_driver_offer(clean_text):
        print(f"🚫 [استبعاد برمجي - إعلان مندوب/سائق]: '{clean_text[:35]}...'", flush=True)
        return False

    if not OPENROUTER_API_KEY:
        return False

    # 2. الفحص بالذكاء الاصطناعي للتحقق من النية
    prompt = f"""أنت نظام فلترة صارم جداً لطلبات التوصيل والمشاوير بالسعودية.
اقرأ هذا المنشور بتركيز شديد وافهم النية الحقيقية لكاتبه:
"{clean_text}"

هل كاتب هذا المنشور هو عميل/زبون يبحث عن توصيلة أو سواق/مندوب لنفسه؟
- أجب بـ (YES) فقط إذا كان الكاتب زبون يحتاج خدمة (مثل: ابغى سواق, محتاجه مندوب, من يوصلني, ابغى مندوب فاضي يتواصل معاي).
- أجب بـ (NO) إذا كان الكاتب هو السائق أو المندوب بنفسه يعلن عن توفره أو يضع رقمه أو يطلب من الناس التواصل معه.

الجواب كلمة واحدة فقط (YES أو NO):"""

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
        res = requests.post(url, headers=headers, json=payload, timeout=6)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🧠 [تحليل الذكاء الاصطناعي]: '{clean_text[:35]}...' -> {answer}", flush=True)
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

    # استثناء رسائل الحساب نفسه
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

    chat_title = message.chat.title or str(message.chat.id)
    sender_name = message.from_user.first_name if message.from_user else "مجهول"
    print(f"📥 [رسالة جديدة من {chat_title} - {sender_name}]: {clean_text[:30]}...", flush=True)

    loop = asyncio.get_running_loop()
    is_client_request = await loop.run_in_executor(None, analyze_post_strictly, clean_text)

    if is_client_request:
        print(f"✅ [طلب عميل مقبول - جارٍ الإرسال]: {clean_text[:30]}...", flush=True)

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
                except Exception as e:
                    print(f"❌ فشل البوت لإرسال {user}: {e}", flush=True)

            if not sent:
                try:
                    await userbot.send_message(
                        chat_id=user,
                        text=clean_text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"❌ فشل اليوزربوت لإرسال {user}: {e}", flush=True)

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

    # الاستماع اللحظي المباشر السريع
    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        await process_live_message(client, bot, message)

    await userbot.start()
    print("🚀 تم تشغيل النظام بالاستماع المباشر والفلترة الذكية!", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

