import os
import re
import asyncio
import hashlib
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
# KEEP ALIVE SERVER 24/7 (Render Binding)
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq System Active!")

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

TARGET_USERS = ["abood1317"]
PROCESSED_KEYS = set()

# =========================================================
# HARD REGEX FILTERS (فلترة الأرقام والإعلانات الصريحة)
# =========================================================

def is_hard_driver_advertisement(text: str) -> bool:
    has_phone = re.search(r'(05\d{8}|\+?9665\d{8}|05\d{2}\s?\d{3}\s?\d{3})', text)
    driver_keywords = [
        "متواجد", "كلموني", "تواصل معي", "تواصلوا", "اتصل", "رزقني", "يرزقكم", 
        "فاضي", "سيارتي", "جاهز", "نوفر لكم", "خدمات توصيل", "حسابي", "خاص مفتوح"
    ]
    if has_phone:
        for kw in driver_keywords:
            if kw in text:
                print(f"🚫 [فلتر الأرقام]: تم رفض إعلان سائق: {text[:30]}...", flush=True)
                return True
    return False

# =========================================================
# PURE INTENT AI ANALYSIS ENGINE
# =========================================================

def analyze_with_pure_ai(text: str) -> bool:
    if is_hard_driver_advertisement(text):
        return False

    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت عقل ذكاء اصطناعي محترف لمهمة تصنيف نصوص قروبات المشاوير والتوصيل بالسعودية (جازان والجنوب).
حدد هل الكاتب (زبون يطلب خدمة توصيل/مشوار) أم (سائق يعرض خدمة):

[طلب عميل/زبون -> YES]
- أسئلة واستفسارات عن توفر سائق أو خط سير (مثل: "مين طالع من صبيا؟"، "فيه أحد رايح جازان؟").
- طلبات الاحتياج (مثل: "ابغى سواق"، "محتاج توصيلة"، "مين يوصلني").

[إعلان سائق/مندوب أو سبام -> NO]
- يحتوي على رقم جوال أو عرض خدمة شخصية أو جاهزية للتحرك.

الرسالة:
"{text}"

الجواب بكلمة واحدة فقط: (YES) أو (NO):"""

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
        res = requests.post(url, headers=headers, json=payload, timeout=8)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [الذكاء الاصطناعي]: '{text[:30]}...' -> {answer}", flush=True)
            return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ الاتصال بالذكاء الاصطناعي: {e}", flush=True)

    return False

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_and_send(userbot: Client, bot: Client, message: Message):
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

    loop = asyncio.get_running_loop()
    is_client_request = await loop.run_in_executor(None, analyze_with_pure_ai, clean_text)

    if is_client_request:
        print(f"✅ [طلب زبون مقبول]: {clean_text[:30]}...", flush=True)

        row = []
        if message.from_user:
            if message.from_user.username:
                user_url = f"https://t.me/{message.from_user.username}"
                user_label = f"💬 فتح المحادثة (@{message.from_user.username})"
            else:
                user_url = f"tg://openmessage?user_id={message.from_user.id}"
                user_label = "💬 فتح المحادثة"
            row.append(InlineKeyboardButton(user_label, url=user_url))

        if message.link:
            row.append(InlineKeyboardButton("📩 الرسالة الأصلية", url=message.link))

        reply_markup = InlineKeyboardMarkup([row]) if row else None

        for user in TARGET_USERS:
            sent = False
            if bot:
                try:
                    await bot.send_message(
                        chat_id=user,
                        text=f"📥 طلب جديد:\n\n{clean_text}",
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
                        text=f"📥 طلب جديد:\n\n{clean_text}",
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except Exception:
                    pass

# =========================================================
# SMART POLLING ENGINE
# =========================================================

async def smart_polling_loop(userbot: Client, bot: Client):
    await asyncio.sleep(8)
    print("🔄 [محرك السحب النشط يعمل الآن]...", flush=True)
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=30):
                if dialog.chat and dialog.chat.type in ["group", "supergroup"]:
                    try:
                        async for msg in userbot.get_chat_history(chat_id=dialog.chat.id, limit=3):
                            await process_and_send(userbot, bot, msg)
                    except Exception:
                        pass
                await asyncio.sleep(0.3)
        except Exception as e:
            print(f"⚠️ خطأ في حلقة السحب: {e}", flush=True)
            
        await asyncio.sleep(12)

# =========================================================
# MAIN ENTRYPOINT
# =========================================================

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client(
        "barq_final_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    bot = None
    if BOT_TOKEN:
        try:
            bot = Client(
                "barq_final_helper",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                in_memory=True
            )
            await bot.start()
        except Exception as e:
            print(f"⚠️ البوت المساعد لم يبدأ: {e}", flush=True)

    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        await process_and_send(client, bot, message)

    await userbot.start()
    print("🚀 [نظام برق جاهز ومرتبط بالحساب الجديد ويراقب المجموعات]...", flush=True)

    asyncio.create_task(smart_polling_loop(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
