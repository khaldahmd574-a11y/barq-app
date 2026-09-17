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
        self.wfile.write(b"Groq AI System Active!")

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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "fs_990"]

PROCESSED_KEYS = set()

# =========================================================
# GROQ PURE AI ANALYSIS ENGINE
# =========================================================

def analyze_with_pure_ai(text: str) -> bool:
    if not GROQ_API_KEY:
        print("❌ خطأ: لم يتم ضبط GROQ_API_KEY في متغيرات البيئة!", flush=True)
        return False

    prompt = f"""أنت نظام ذكاء اصطناعي متخصص في تصنيف رسائل التوصيل والمشاوير بدقة متناهية.
مهمتك: التمييز بين "زبون يطلب توصيلاً أو يسأل عن سائق قريب" وبين "سائق يعرض خدمته أو إعلانه".

قواعد التمييز والتصنيف الصارمة:

1. أجب بـ YES إذا كان الكاتب زبوناً يسأل عن سائق، أو يستفسر عن شخص قريب منه للتوصيل، أو يشرح جدول دوامه:
   - أمثلة صريحة لطلب الزبون (YES):
     * "من قريب من الشواجرة؟" / "حد قريب من صبيا؟" / "مين القريب من جازان؟"
     * "مين فاضي في جيزان؟" / "حد فاضي؟" / "فيه احد فاضي؟"
     * "انا دوامي من الجهو والشقيري الي جازان... اللي يناسبه يجي نتفق ع السعر"
     * "ابغى جازان اذ احد من احد المسارحة يوصل"
     * "ابغى سواق" / "احتاج توصيل" / "مطلوب مندوب"

2. أجب بـ NO فوراً إذا كان الكاتب سائقاً يعرض سيارته، أو متواجداً لنقل الآخرين، أو يضع رقماً/إعلاناً:
   - أمثلة صريحة لعرض السائق (NO):
     * "أنا قريب من الشواجرة" / "متواجد بالقرب من الشواجرة"
     * "أنا فاضي في جيزان" / "فاضي الحين" / "فاضي في جازان تبغى شيء"
     * "متواجد في صبيا الي محتاج مشوار يتواصل خاص"
     * "موجود في جازان اي مشوار خاص"
     * "فاضيه في جازان الي تبغى مشوار" / "او سواقات"
     * "نوفر نقل الطالبات" / "نقل موظفات" / "للتواصل خاص"

الرسالة المراد تحليلها:
"{text}"

الجواب (أجب بكلمة YES أو NO فقط بدون أي إضافة):"""

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # المحاولة مع النموذج الأساسي ثم النموذج الاحتياطي الخفيف
    models_to_try = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

    for model in models_to_try:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise classifier that responds only with YES or NO."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.0,
                "max_tokens": 5
            }
            res = requests.post(url, headers=headers, json=payload, timeout=4)
            if res.status_code == 200:
                answer = res.json()['choices'][0]['message']['content'].strip().upper()
                print(f"🤖 [قرار Groq AI ({model})]: '{text[:30]}...' -> {answer}", flush=True)
                return "YES" in answer
            else:
                print(f"⚠️ استجابة Groq ({model}): {res.status_code} - {res.text}", flush=True)
        except Exception as e:
            print(f"⚠️ خطأ الاتصال بـ Groq ({model}): {e}", flush=True)

    return False

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    try:
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
            print(f"🎯 [طلب مقبوض عبر Groq!]: {clean_text[:30]}...", flush=True)

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
                        print(f"✅ تم الإرسال إلى @{user} عبر البوت", flush=True)
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
                        print(f"✅ تم الإرسال إلى @{user} عبر الحساب الوهمي", flush=True)
                    except Exception as e:
                        print(f"❌ فشل الإرسال لـ @{user}: {e}", flush=True)

    except Exception as e:
        print(f"⚠️ خطأ عام في معالجة الرسالة: {e}", flush=True)

# =========================================================
# MAIN ENTRYPOINT
# =========================================================

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "my_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING
    )

    bot = None
    if BOT_TOKEN:
        try:
            bot = Client(
                "helper_bot",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN
            )
            await bot.start()
            print("🤖 تم تشغيل بوت التوجيه بنجاح!", flush=True)
        except Exception as e:
            print(f"⚠️ فشل تشغيل البوت المساعد: {e}", flush=True)

    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        await process_live_message(client, bot, message)

    await userbot.start()
    print("🚀 تم تشغيل البوت بنجاح واعتماد Groq AI معالجة مجانية 100%!", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

