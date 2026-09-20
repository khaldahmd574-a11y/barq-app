import os
import asyncio
import hashlib
import json
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
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
API_ID = int(os.environ.get("TELEGRAM_API_ID", os.environ.get("API_ID", 39120728)))
API_HASH = os.environ.get("TELEGRAM_API_HASH", os.environ.get("API_HASH", "1deec8393ce5aa05c54c0c7e280377d4")).strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

# مفاتيح الذكاء الاصطناعي
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
OPENROUTER_KEY = os.environ.get("OPENROUTER_API_KEY")

# القائمة المحدثة (بدون fs_990)
TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]
PROCESSED_KEYS = set()

# =========================================================
# MULTI-ENGINE AI ANALYSIS
# =========================================================

def analyze_with_pure_ai(text: str) -> bool:
    prompt = f"""أنت نظام ذكاء اصطناعي متخصص في تصنيف رسائل التوصيل والمشاوير بدقة متناهية.
مهمتك: التمييز بين "زبون يطلب توصيلاً أو يسأل عن سائق/مندوب" وبين "سائق يعرض خدمته أو إعلانه".

قواعد التمييز والتصنيف الصارمة:

1. أجب بـ YES إذا كان الكاتب زبوناً يسأل عن سائق، استلام طرد، توصيل أغراض، أو يستفسر عن شخص قريب منه للتوصيل:
   - أمثلة لطلب الزبون (YES):
     * "احتاج مندوب يستلم لي طرد من ارامكس"
     * "مين فاضي في جيزان؟" / "من قريب من الشواجرة؟"
     * "ابغى مشوار من جازان الى جامعة الطب"
     * "محتاجه مندوب داخل جازان"
     * "ابغى سواق" / "احتاج توصيل" / "مطلوب مندوب"

2. أجب بـ NO فوراً إذا كان الكاتب سائقاً يعرض سيارته، أو متواجداً لنقل الآخرين، أو يضع رقماً/إعلاناً:
   - أمثلة لعرض السائق (NO):
     * "أنا قريب من الشواجرة" / "متواجد في صبيا الي محتاج مشوار يتواصل خاص"
     * "موجود في جازان اي مشوار خاص" / "نوفر نقل الطالبات"

الرسالة المراد تحلیلها:
"{text}"

الجواب (أجب بكلمة YES أو NO فقط بدون أي إضافة):"""

    # 1. التجربة عبر Google Gemini (بأسماء النماذج الحالية والرسمية)
    if GEMINI_KEY:
        models = ["gemini-1.5-flash", "gemini-1.5-pro"]
        for model in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_KEY.strip()}"
                headers = {"Content-Type": "application/json"}
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "maxOutputTokens": 10}
                }
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
                with urllib.request.urlopen(req, timeout=5) as response:
                    if response.status == 200:
                        res_data = json.loads(response.read().decode('utf-8'))
                        answer = res_data['candidates'][0]['content']['parts'][0]['text'].strip().upper()
                        print(f"🤖 [تحليل Gemini ({model})]: '{text[:30]}...' -> {answer}", flush=True)
                        return "YES" in answer
            except Exception as e:
                print(f"⚠️ فشل Gemini ({model}): {e}", flush=True)

    # 2. التجربة عبر OpenRouter (خيار احتياطي ممتاز)
    if OPENROUTER_KEY:
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {OPENROUTER_KEY.strip()}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "qwen/qwen-2.5-7b-instruct",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
                "max_tokens": 5
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers, method='POST')
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    res_data = json.loads(response.read().decode('utf-8'))
                    answer = res_data['choices'][0]['message']['content'].strip().upper()
                    print(f"🤖 [تحليل OpenRouter]: '{text[:30]}...' -> {answer}", flush=True)
                    return "YES" in answer
        except Exception as e:
            print(f"⚠️ فشل OpenRouter: {e}", flush=True)

    print("❌ لم يتم العثور على أي مفتاح API صالح يعمل في متغيرات البيئة!", flush=True)
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

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
