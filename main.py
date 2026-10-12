import os
import re
import asyncio
import hashlib
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.enums import ChatType

# =========================================================
# KEEP ALIVE SERVER 24/7 (للعمل المستمر على ريندر)
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Ultra Smart AI System Active!")

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
# INTENT ENGINE + LOCAL FALLBACK
# =========================================================

def analyze_intent_with_ai(text: str) -> bool:
    clean = " ".join(text.split()).strip()
    
    if not clean or len(clean) < 2:
        return False

    # الفلتر الاحتياطي المحلي المباشر (يعمل حتى لو انقطع رصيد أو توقف OpenRouter)
    local_keywords = [
        "ابغى", "أبغى", "ابي", "أبي", "محتاج", "محتاجه", "مين يوصل", "من يوصل", 
        "أحد رايح", "احد رايح", "في حد", "فيه احد", "توصيلة", "توصيله", 
        "سواق", "مشوار", "دوام", "منداوب", "مندوب", "ضروري"
    ]
    
    # إذا لم يكن هناك مفتاح أو فشل الاتصال، نعتمد على الكلمات المفتاحية فوراً
    is_local_match = any(k in clean for k in local_keywords)

    if not OPENROUTER_API_KEY:
        return is_local_match

    prompt = f"""أنت عقل ذكاء اصطناعي محترف لمهمة تصنيف نصوص قروبات المشاوير والتوصيل بالسعودية (جازان والجنوب).
حدد هل الكاتب (زبون يطلب خدمة توصيل/مشوار شخصي) أم (سائق يعرض خدمة):

[طلب عميل/زبون -> YES]
- أسئلة واستفسارات عن توفر سائق أو خط سير (مثل: "في حد في ضمد؟"، "مين طالع صبيا؟"، "أحد رايح جازان؟").
- طلبات الاحتياج (مثل: "ابغى سواق"، "محتاج توصيلة", "مين يوصلني").

[إعلان سائق أو غير ذلك -> NO]
- إعلانات السائقين، المندوبين، أرقام الجوال للتوصيل، أو أي مواضيع أخرى.

الرسالة:
"{clean}"

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
            "max_tokens": 2
        }
        res = requests.post(url, headers=headers, json=payload, timeout=3)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            return "YES" in answer
    except Exception:
        pass

    # في حال حدوث أي خطأ في اتصال الـ API، نعود للفلتر المحلي لضمان عدم ضياع أي طلب
    return is_local_match

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    try:
        if not message or not message.id or not message.chat:
            return

        if message.chat.type == ChatType.PRIVATE:
            return

        if message.reply_to_message_id or message.reply_to_message:
            return

        if message.from_user and message.from_user.is_self:
            return

        raw_text = message.text or message.caption or ""
        clean_text = raw_text.strip()
        
        if len(clean_text) < 2:
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
        is_client_request = await loop.run_in_executor(None, analyze_intent_with_ai, clean_text)

        if is_client_request:
            print(f"✅ [تم التقاط وسحب الطلب]: {clean_text[:30]}...", flush=True)

            buttons = []
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
        asyncio.create_task(process_live_message(client, bot, message))

    await userbot.start()
    print("🚀 نظام برق يعمل الآن بقوة (الذكاء الاصطناعي + نظام الحماية الاحتياطي المحلي)!", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
