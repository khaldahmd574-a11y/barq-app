import os
import re
import asyncio
import hashlib
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
        self.wfile.write(b"Local High-Precision Engine Active 24/7!")

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

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "fs_990"]

PROCESSED_KEYS = set()

# =========================================================
# ADVANCED LOCAL CONTEXT FILTERING ENGINE (NO API - 100% STABLE)
# =========================================================

# أنماط إعلانات السائقين والشركات (استبعاد فوري)
DRIVER_EXCLUSIONS = [
    r"متوفر", r"متواجد", r"أنا فاضي", r"جاهز للتوصيل", r"نوصل", r"نوفر لكم", 
    r"خدمة توصيل", r"مشاوير خاصة", r"نقل طالبات", r"نقل موظفات", r"سطحة", 
    r"باص", r"دينا", r"تواصل واتس", r"للتواصل", r"05\d{8}", r"سائق خاص", 
    r"سيارة حديثة", r"إعلان", r"توصيل طلبات", r"عروض", r"خصم"
]

# أنماط طلبات الزبائن الصريحة (قبول)
PASSENGER_PATTERNS = [
    r"أبغى", r"ابغى", r"محتاج", r"محتاجة", r"أبي", r"ابي", r"فيه أحد", r"فيه احد",
    r"مين يوصل", r"من يوصل", r"من يوديني", r"مين يوديني", r"اريد", r"أريد",
    r"يقدر يوصل", r"تقدر توصل", r"توصلون", r"تطلعون", r"يبحث عن توصيل",
    r"مطلوب سائق", r"سائق للضرورة", r"من\s+.*\s+إلى", r"من\s+.*\s+الي"
]

def analyze_message_context(text: str) -> bool:
    clean_text = text.lower()

    # 1. إذا كان النص يحتوي على أي نمط إعلان كابتن/شركة -> استبعاد فوري
    for pattern in DRIVER_EXCLUSIONS:
        if re.search(pattern, clean_text):
            return False

    # 2. إذا كان النص يحتوي على صيغة طلب زبون مؤكدة -> قبول
    for pattern in PASSENGER_PATTERNS:
        if re.search(pattern, clean_text):
            return True

    # 3. إذا كانت الرسالة قصيرة وتستفسر بعلامة استفهام بدون إعلانات -> قبول
    if ("?" in clean_text or "؟" in clean_text) and len(clean_text) < 100:
        return True

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

        # الفلترة المحلية الفائقة
        is_client_request = analyze_message_context(clean_text)

        if is_client_request:
            print(f"🎯 [طلب زبون مؤكد محلياً]: {clean_text[:30]}...", flush=True)

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
    except Exception as e:
        print(f"⚠️ خطأ أثناء معالجة الرسالة: {e}", flush=True)

# =========================================================
# FAST MULTI-GROUP SCANNER (80 DIALOGS)
# =========================================================

async def fast_dialog_poller(userbot: Client, bot: Client):
    await asyncio.sleep(3)
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=80):
                if dialog.top_message:
                    await process_live_message(userbot, bot, dialog.top_message)
        except Exception:
            pass
            
        await asyncio.sleep(5)

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
    print("🚀 تم تشغيل البوت بمحرك الفلترة المحلي الدائم 100%!", flush=True)

    asyncio.create_task(fast_dialog_poller(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

