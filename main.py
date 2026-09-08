import os
import asyncio
import re
import hashlib
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is alive 24/7!")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

SESSION_STRING = os.environ.get("SESSION_STRING")
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4")
BOT_TOKEN = "8782796916:AAEe9YRkzbfm3F5e9rj49iHfDS0wRTnVmmo"

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

RAW_KEYWORDS = [
    "افضل مكان", "ابغا مندوب", "ابغى مندوب", "ابغى سواق", "احتاج سواق",
    "نبغا سواق", "نحتاج سواق", "ابغى سواقه", "نبغا سواقه", "مين فاضي",
    "من فاضي", "احد فاضي", "فيه توصيل", "يوصل طلبي", "يوصل طلب",
    "ياخذ طلب", "ياخذ طلبي", "حي المطار", "حي السويس", "مخطط",
    "المخطط", "من جيزان", "من جازان", "مين موجود", "احد موجود",
    "ياخذ لي", "يوصل لي", "توصل لي", "يجيب لي", "تجيب لي",
    "يوصل من", "الي في", "ينفعني", "تنفعني", "ابي مندوب",
    "احتاج مندوب", "نبغى مندوب", "فيه مندوب", "مين طالع", "مين نازل",
    "مين طالعه", "الي بيطلع", "الي طالع", "لضمد", "من ضمد",
    "مين بحي", "الي قريب", "مين قريب", "معايه غرض", "معايه طلب",
    "اطلب", "بنطلب", "يرجعنا", "ترجعنا", "مندوب",
    "تبغى مندوب", "ابغى مشوار", "نبغى مشوار", "مندوب من", "مندوب قريب",
    "ابغى توصيل", "مشوار من", "ابغا مشوار", "مندوب ف", "من في",
    "مين في جازان", "مين في جيزان", "لين جيزان", "لين ابو عريش", "من صبيا",
    "الى صبيا", "في صبيا", "طالع صبيا", "ابو عريش", "ابغى من",
    "موقعي", "ضمد", "جيزان", "جازان", "مين عند",
    "مين قريب من", "من قريب", "مين راجع", "من يوصل", "يوصلي",
    "من يوصلي", "ياخذني", "يوديني"
]

BLOCKED_KEYWORDS = ["كتم", "سكليف", "صحتي", "توكلنا", "مؤسسه", "مرضيه"]

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = re.sub(r"ة", "ه", text)
    text = re.sub(r"ى", "ي", text)
    return text

NORMALIZED_KEYWORDS = {word: normalize_text(word) for word in set(RAW_KEYWORDS) if word.strip()}
NORMALIZED_BLOCKED = [normalize_text(word) for word in BLOCKED_KEYWORDS if word.strip()]

PROCESSED_MESSAGES = set()
PROCESSED_TEXT_HASHES = set()

async def process_message(bot, message: Message):
    if not message or not message.id:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MESSAGES:
        return
    
    PROCESSED_MESSAGES.add(msg_key)
    if len(PROCESSED_MESSAGES) > 5000:
        PROCESSED_MESSAGES.clear()

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    if not raw_text:
        return

    searchable_text = normalize_text(raw_text)

    # فحص الكلمات المحظورة أولاً (إذا وُجدت يتم تجاهل الرسالة مباشرة)
    if any(blocked in searchable_text for blocked in NORMALIZED_BLOCKED):
        return

    # إلغاء تكرار نفس الرسالة حتى لو نُشرت في أكثر من قروب
    text_hash = hashlib.md5(searchable_text.encode('utf-8')).hexdigest()
    if text_hash in PROCESSED_TEXT_HASHES:
        return

    for original_word, norm_word in NORMALIZED_KEYWORDS.items():
        if norm_word in searchable_text:
            PROCESSED_TEXT_HASHES.add(text_hash)
            if len(PROCESSED_TEXT_HASHES) > 3000:
                PROCESSED_TEXT_HASHES.clear()

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
                try:
                    await bot.send_message(
                        chat_id=user,
                        text=raw_text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                    await bot.send_message(
                        chat_id=user,
                        text=raw_text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"❌ خطأ توجيه: {e}")
            break

async def real_time_channel_and_group_scanner(userbot, bot):
    while True:
        try:
            # فحص أول 50 محادثة نشطة
            async for dialog in userbot.get_dialogs(limit=50):
                try:
                    async for msg in userbot.get_chat_history(dialog.chat.id, limit=2):
                        await process_message(bot, msg)
                except Exception:
                    pass
                await asyncio.sleep(0.1)

        except Exception as e:
            print(f"⚠️ خطأ أثناء الفحص: {e}")
            
        await asyncio.sleep(7)

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

    @userbot.on_message(filters.all)
    async def global_listener(client: Client, message: Message):
        await process_message(bot, message)

    await userbot.start()
    await bot.start()
    print("✅ تم التشغيل والربط بنجاح (فحص 50 محادثة كل 7 ثوانٍ بأمان تام ومع الكلمات المحظورة).")

    asyncio.create_task(real_time_channel_and_group_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

