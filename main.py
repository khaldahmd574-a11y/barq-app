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
        self.wfile.write(b"Strict AI Active - No Duplicates!")

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
# HARD FILTERS & STRICT AI CLASSIFIER
# =========================================================

def analyze_with_openrouter(text: str) -> bool:
    # 1. تصفية أولية فورية: إن كان النص يحتوي على أرقام هواتف أو روابط تواصل فهو إعلان سائق/خدمة 100%
    phone_pattern = r"(05\d{8}|\+9665\d{8}|05\d{1}[\s\-]\d{3}[\s\-]\d{4})"
    if re.search(phone_pattern, text):
        print(f"🛑 [إعلان مرفوض وجود رقم جوال]: {text[:30]}...", flush=True)
        return False

    if not OPENROUTER_KEY:
        print("❌ خطأ: مفتاح OpenRouter غير موجود!", flush=True)
        return False

    prompt = f"""أنت نظام ذكاء اصطناعي صارم جداً لتصنيف رسائل التلغرام.
مهمتك: السماح فقط لطلبات الزبائن والعملاء الذين يبحثون عن توصيل أو سائق أو اغراض، ومنع أي إعلان سائق أو توصيل أو نقل أو بيع وشراء.

قواعد صارمة جداً:
- أجب بـ YES فقط إذا كانت الرسالة من زبون/عميل يسأل أو يطلب توصيل/سائق/مشوار/أكل/طلب (مثل: "ابي مندوب"، "مين فاضي يوصلني"، "اريد توصيل ل صامطه"، "فيه سواق"، "احتاج توصيل").
- أجب بـ NO فوراً إذا كانت الرسالة إعلان سائق، توفر باصات/نقل، عروض توصيل، بيع أثاث/أغراض، أو أكواد برمجية وروابط.

النص المراد تحليله:
"{text}"

الجواب (أجب فقط إما YES أو NO):"""

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
        response = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=6)
        if response.status_code == 200:
            res_data = response.json()
            answer = res_data['choices'][0]['message']['content'].strip().upper()
            return "YES" in answer
        else:
            print(f"⚠️ خطأ AI Status ({response.status_code}): {response.text}", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ اتصال بالذكاء الاصطناعي: {e}", flush=True)

    return False

# =========================================================
# CORE MESSAGE PROCESSOR
# =========================================================

async def process_message(bot, message: Message):
    if not message or not message.id:
        return

    # منع التكرار تماماً باستخدام معرف الشات والرسالة
    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MESSAGES:
        return
    
    PROCESSED_MESSAGES.add(msg_key)
    if len(PROCESSED_MESSAGES) > 20000:
        PROCESSED_MESSAGES.clear()

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    clean_text = raw_text.strip()
    if len(clean_text) < 2:
        return

    # الفحص الصارم بالذكاء الاصطناعي
    loop = asyncio.get_event_loop()
    is_client_request = await loop.run_in_executor(None, analyze_with_openrouter, clean_text)

    if is_client_request:
        print(f"✅ [طلب زبون حقيقي مقبول]: {clean_text[:40]}...", flush=True)

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

    # الاستماع المباشر الحقيقي اللحظي (بدون حلقات تكرارية لمنع التكرار)
    @userbot.on_message(~filters.me & ~filters.private)
    async def global_listener(client: Client, message: Message):
        await process_message(bot, message)

    await userbot.start()
    await bot.start()

    # تحمئة ومزامنة جميع المحادثات والقروبات الكبيرة مرة واحدة فقط عند التشغيل
    print("🔄 جاري مزامنة القروبات لضمان استقبال الرسائل الحية...", flush=True)
    try:
        async for dialog in userbot.get_dialogs(limit=200):
            pass
        print("✅ تم المزامنة وتفعيل القروبات بنجاح!", flush=True)
    except Exception as e:
        print(f"⚠️ تنبيه أثناء المزامنة: {e}", flush=True)

    print("🚀 تم تشغيل البوت الذكي بنجاح بدون تكرار وبفلترة صارمة 100%!", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

