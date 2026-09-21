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
# 1. KEEP ALIVE SERVER (مضاد لخطأ 503 و 404 لمنع نوم Render)
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq System Online 24/7 - Max AI Engine Active!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        return

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    try:
        server = HTTPServer(("0.0.0.0", port), DummyServer)
        server.serve_forever()
    except Exception as e:
        print(f"⚠️ تنبيه السيرفر الداخلي: {e}", flush=True)

# =========================================================
# 2. CONFIGURATION & VARIABLES
# =========================================================

SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

PROCESSED_KEYS = set()

# =========================================================
# 3. HARD DENY PATTERNS (تصفية أولية سريعة لإعلانات المناديب)
# =========================================================

DRIVER_DENY_PATTERNS = [
    r"يتوصل معي", r"يتواصل معي", r"تواصل معي", r"تواصلوا معي",
    r"يتواصلون معي", r"يتواصل خاص", r"تواصل خاص", r"يجي خاص",
    r"يجيني خاص", r"يراسلني خاص", r"فاضي لتوصيل", r"متواجد لتوصيل",
    r"على أتم الاستعداد", r"الي يبغى.*يتوصل", r"الي يبغى.*يتواصل",
    r"اللي يبي.*يجي", r"مين تبي سواق", r"مين يبغى سواق", r"مستعد لتوصيل"
]

def contains_driver_offer(text: str) -> bool:
    for pattern in DRIVER_DENY_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False

# =========================================================
# 4. MAXIMUM AI INTENT ENGINE (محرك الذكاء الاصطناعي الفائق)
# =========================================================

def analyze_post_strictly(text: str) -> bool:
    clean_text = text.strip()

    # فحص الكلمات الصريحة لطلبات الزبائن
    is_explicit_request = any(clean_text.startswith(w) for w in ["ابغى", "أبغى", "ابغا", "أبغا", "احتاج", "أحتاج", "مطلوب", "مين", "من يوصل", "من يوديني"])

    if not is_explicit_request and contains_driver_offer(clean_text):
        print(f"🚫 [فلترة سريعة - إعلان مندوب]: '{clean_text[:35]}...'", flush=True)
        return False

    if not OPENROUTER_API_KEY:
        print("⚠️ مفتاح OpenRouter غير موجود!", flush=True)
        return False

    # برومبت احترافي فائق الدقة
    prompt = f"""أنت خبير محترف جداً في تحليل نية نصوص طلبات التوصيل بالسعودية.
حلل المنشور التالي بدقة متناهية لمعرفة نية كاتبه الحقيقية:
"{clean_text}"

هل كاتب هذا المنشور هو عميل / زبون يحتاج خدمة (توصيل, نقل, مشوار, مندوب) بنفسه؟
- أجب بـ (YES) إذا كان الكاتب زبون يطلب خدمة (مثال: ابغى سواق, محتاجه مندوب, من يوصلني, ابغى مندوب يتواصل معي).
- أجب بـ (NO) إذا كان الكاتب سواق أو مندوب يعلن عن توفره أو يضع خدماته ورقمه للناس.

اجابتك يجب أن تكون كلمة واحدة فقط لا غير: (YES) أو (NO)."""

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    try:
        # استخدام موديل GPT-4o بالطاقة القصوى لفهم المعنى
        payload = {
            "model": "openai/gpt-4o",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": 3
        }
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🧠 [تحليل الذكاء الاصطناعي GPT-4o]: '{clean_text[:35]}...' -> {answer}", flush=True)
            return "YES" in answer
        else:
            print(f"⚠️ استجابة API خاطئة ({res.status_code}): {res.text}", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ في اتصال الذكاء الاصطناعي: {e}", flush=True)

    return False

# =========================================================
# 5. LIVE MESSAGE PROCESSOR (معالج الرسائل الحية)
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    if not message or not message.id:
        return

    # تجاهل رسائل الحساب نفسه
    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    clean_text = raw_text.strip()
    if len(clean_text) < 3:
        return

    # منع تكرار المعالجة
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
    print(f"📥 [وصلت رسالة من {chat_title} - {sender_name}]: {clean_text[:30]}...", flush=True)

    # تشغيل الفلترة والذكاء الاصطناعي
    loop = asyncio.get_running_loop()
    is_client_request = await loop.run_in_executor(None, analyze_post_strictly, clean_text)

    if is_client_request:
        print(f"✅ [طلب عميل حقيقي مقبول - جارٍ التحويل]: {clean_text[:30]}...", flush=True)

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
                    print(f"❌ فشل البوت للإرسال إلى {user}: {e}", flush=True)

            if not sent:
                try:
                    await userbot.send_message(
                        chat_id=user,
                        text=clean_text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"❌ فشل اليوزربوت للإرسال إلى {user}: {e}", flush=True)

# =========================================================
# 6. MAIN ENTRYPOINT
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

    # استماع لحظي لكل المجموعات والقنوات التي يوجد بها الحساب
    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        await process_live_message(client, bot, message)

    await userbot.start()
    print("🚀 تم تشغيل البوت بأقصى طاقة للذكاء الاصطناعي والاستماع اللحظي الشامل!", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

