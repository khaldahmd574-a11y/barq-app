import os
import asyncio
import re
import hashlib
import json
import urllib.request
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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

def analyze_with_ai(text: str) -> bool:
    if not GROQ_API_KEY:
        return False

    prompt = f"""
أنت مساعد ذكي متخصص في التمييز بين طلبات التوصيل الإعلان والتنبيهات.
حدد هل النص التالي عبارة عن "طلب توصيل مشوار/بضائع/سائق من زبون حقيقي" أم لا؟

قواعد الاستبعاد الصارمة (أجب بـ NO فوراً إذا تحققت):
1. إعلانات الخدمات الحكومية أو المعاملات مثل (إجازات مرضية، سكني، ترفيع، توثيق، منصة صحتي، إنجاز).
2. إعلانات التوظيف، التعارف، المسيار، والربح أو التسويق.
3. التنبيهات الإدارية وقوانين المجموعات.
4. منشورات السائقين الذين يعرضون التوصيل (مثل: طالع من...، متوفر توصيل).

الشرط الوحيد للقبول (أجب بـ YES):
- أن يكون صاحب الرسالة (زبون) يطلب سائقاً، مشواراً، أو توصيل طلبات لنفسه بوضوح.

الرسالة:
"{text}"

أجب بكلمة واحدة فقط: YES أو NO.
"""
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        data = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0
        }).encode("utf-8")

        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=3) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            result = res_data["choices"][0]["message"]["content"].strip().upper()
            return "YES" in result
    except Exception as e:
        print(f"⚠️ خطأ الذكاء الاصطناعي: {e}")
    
    return False

PROCESSED_MESSAGES = set()
PROCESSED_REQUEST_HASHES = set()

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[أإآ]", "ا", text)
    text = text.replace("ة", "ه").replace("ى", "ي")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def make_request_fingerprint(text):
    text = normalize_text(text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"@\w+", "", text)
    text = re.sub(r"\d+", "", text)
    return hashlib.md5(text.encode("utf-8")).hexdigest()

async def process_message(bot, message: Message):
    if not message or not message.id:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    if msg_key in PROCESSED_MESSAGES:
        return

    PROCESSED_MESSAGES.add(msg_key)
    if len(PROCESSED_MESSAGES) > 15000:
        PROCESSED_MESSAGES.clear()

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    if not raw_text or len(raw_text) < 5:
        return

    is_customer = await asyncio.to_thread(analyze_with_ai, raw_text)
    if not is_customer:
        return

    request_hash = make_request_fingerprint(raw_text)
    if request_hash in PROCESSED_REQUEST_HASHES:
        return

    PROCESSED_REQUEST_HASHES.add(request_hash)
    if len(PROCESSED_REQUEST_HASHES) > 15000:
        PROCESSED_REQUEST_HASHES.clear()

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

async def real_time_channel_and_group_scanner(userbot, bot):
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=60):
                try:
                    async for msg in userbot.get_chat_history(dialog.chat.id, limit=3):
                        await process_message(bot, msg)
                except Exception:
                    pass
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"⚠️ خطأ الفحص الدوري: {e}")
            
        await asyncio.sleep(5)

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
    print("✅ تم التشغيل: تفعيل الذكاء الاصطناعي بنجاح.")

    asyncio.create_task(real_time_channel_and_group_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

