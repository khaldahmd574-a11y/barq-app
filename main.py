import os
import asyncio
import hashlib
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
        self.wfile.write(b"Barq Supreme Lightning Engine Active!")

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

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "Ndhhyfvvjkcd", "fs_990"]

PROCESSED_KEYS = set()

# =========================================================
# ULTRA SMART & FAST AI ENGINE (Gemini Flash-Lite)
# =========================================================

def analyze_message_smart(text: str) -> bool:
    clean = text.strip()
    if not clean or len(clean) < 3:
        return False

    # تصفية سريعة للتحيات العابرة
    if clean.lower() in ["سلام", "السلام عليكم", "مرحبا", "هلا", "صباح الخير", "مساء الخير", "الو"]:
        return False

    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت عقل ذكاء اصطناعي خارق وواعي تماماً، ومختص حصرياً بتحليل نية الرسائل في قروبات التوصيل والمشاوير والمناديب بمنطقة جازان بالمملكة العربية السعودية.

مهمتك الجوهرية قراءة الرسالة التالية بدقة واكتشاف هل صاحب الرسالة يطلب خدمة (مشوار، توصيل، مندوب، نقل) أم لا:

[أجب بـ (YES) فقط في هذه الحالات:]
- زبون يبحث عن توصيلة، مشوار، نقل، أو مندوب لنفسه أو لغيره (مثل: "مين يوديني"، "ابي مشوار"، "احتاج سواق"، "فيه أحد فاضي يوصلني").
- استفسار عن توفر شخص أو سائق في أي مدينة أو قرية بجازان (مثل: "من فاضي في صامطة"، "احد موجود في أبو عريش أبغا مشوار").

[أجب بـ (NO) في أي حالة أخرى:]
- إعلانات السائقين الذين يعرضون خدماتهم أو رحلاتهم أو أرقام جوالاتهم.
- قوائم الثقة، أسماء الكباتن، أو تنبيهات الإدارة.
- الإعلانات التجارية العامة، القروض، أو الخدمات الأخرى.

الرسالة: "{text}"
الجواب كلمة واحدة فقط (YES) أو (NO):"""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        payload = {
            "model": "google/gemini-3.1-flash-lite",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 2
        }
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        if res.status_code == 200:
            data = res.json()
            if 'choices' in data and len(data['choices']) > 0:
                answer = data['choices'][0]['message']['content'].strip().upper()
                print(f"🧠 [Gemini Super Fast]: '{clean[:25]}...' -> {answer}", flush=True)
                return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ الذكاء الاصطناعي: {e}", flush=True)

    return False

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_live_message(bot: Client, message: Message):
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

    loop = asyncio.get_running_loop()
    is_client_request = await loop.run_in_executor(None, analyze_message_smart, clean_text)

    if is_client_request:
        print(f"✅ [تم اعتماد الطلب - البوت يرسل فورا]: {clean_text[:30]}...", flush=True)

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

        if bot:
            for user in TARGET_USERS:
                try:
                    await bot.send_message(
                        chat_id=user,
                        text=clean_text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"⚠️ خطأ في الإرسال للمستخدم {user}: {e}", flush=True)

# =========================================================
# LIGHTNING FAST POLLER (فحص سريع جداً كل 5 ثواني)
# =========================================================

async def lightning_dialog_poller(userbot: Client, bot: Client):
    await asyncio.sleep(2)
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=46):
                if dialog.top_message:
                    asyncio.create_task(process_live_message(bot, dialog.top_message))
                await asyncio.sleep(0.1)
        except Exception:
            pass
            
        await asyncio.sleep(5) # فحص خاطف كل 5 ثواني لضمان السرعة الصاروخية

# =========================================================
# MAIN ENTRYPOINT
# =========================================================

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

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
            print("🤖 تم تفعيل البوت الرسمي بنجاح للإرسال الصاروخي!", flush=True)
        except Exception as e:
            print(f"❌ فشل تشغيل البوت: {e}", flush=True)

    userbot = Client(
        "my_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        if bot:
            asyncio.create_task(process_live_message(bot, message))

    await userbot.start()
    print("🚀 النظام يعمل الآن بأقصى سرعة صاروخية (Gemini Flash-Lite + فوري + فحص كل 5 ثواني)!", flush=True)

    if bot:
        asyncio.create_task(lightning_dialog_poller(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
