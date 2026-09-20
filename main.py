import os
import asyncio
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import requests
from hydrogram import Client
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
# KEEP ALIVE SERVER 24/7 FOR RENDER
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq AI System Active!")

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
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]
PROCESSED_KEYS = set()

# =========================================================
# OPENROUTER PURE AI ANALYSIS ENGINE
# =========================================================

def analyze_with_pure_ai(text: str) -> bool:
    if not OPENROUTER_KEY:
        print("❌ لم يتم العثور على مفتاح OPENROUTER_API_KEY في متغيرات البيئة!", flush=True)
        return False

    prompt = f"""أنت نظام ذكاء اصطناعي متخصص في فهم وتصنيف طلبات التوصيل والمشاوير باللغة العربية واللهجات المحلية.
مهمتك الوحيدة: تحليل النص المرفق والتمييز الدقيق بين نوعين من الكتاب:

1. أجب بـ YES إذا كان الكاتب (زبوناً / عميلاً) يطلب توصيلاً أو يبحث عن سائق أو يسأل عن شخص يوصله أو يطلب استلام طرد/أغراض.
2. أجب بـ NO إذا كان الكاتب (سائقاً / مندوباً) يعرض سيارته، أو يعلن عن توفره ونقله للركاب أو يضع رقم تواصل للخدمات.

الرسالة المراد تحليلها:
"{text}"

الجواب (أجب فقط بكلمة YES أو NO بدون أي كلام آخر):"""

    # استخدام نموذج Llama 3.1 8B المباشر والسريع جداً
    model_name = "meta-llama/llama-3.1-8b-instruct"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_KEY}",
        "Content-Type": "application/json"
    }

    try:
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 10
        }
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=8)
        if response.status_code == 200:
            res_data = response.json()
            answer = res_data['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [تحليل الذكاء الاصطناعي]: '{text[:30]}...' -> {answer}", flush=True)
            return "YES" in answer
        else:
            print(f"⚠️ خطأ استجابة الذكاء الاصطناعي ({response.status_code}): {response.text}", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ أثناء الاتصال بالذكاء الاصطناعي: {e}", flush=True)

    return False

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    if not message or not message.id:
        return

    # تجاهل الرسائل الصادرة من نفس الحساب
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

    # تحويل عملية التحليل للذكاء الاصطناعي إلى مسار منفصل لمنع التجميد
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
    print("🚀 تم تشغيل النظام بنجاح!", flush=True)

    # جلب ومزامنة جميع المحادثات والمجموعات الكبيرة والقنوات التي ينتمي إليها الحساب
    try:
        print("🔄 جاري مزامنة وربط جميع المحادثات والمجموعات الكبيرة...", flush=True)
        dialogs_count = 0
        async for dialog in userbot.get_dialogs():
            dialogs_count += 1
        print(f"✅ تم ربط البوت بنجاح مع {dialogs_count} محادثة ومجموعة وقناة!", flush=True)
    except Exception as e:
        print(f"⚠️ تنبيه أثناء عملية المزامنة: {e}", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

