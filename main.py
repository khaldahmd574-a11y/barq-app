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
        self.wfile.write(b"Barq Human-Level AI Active!")

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

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317"]

PROCESSED_KEYS = set()

# =========================================================
# HUMAN-LEVEL FULL POST INTENT ENGINE
# =========================================================

def analyze_post_like_a_human(text: str) -> bool:
    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""تخيل أنك إنسان بشري خبير يقرأ منشورات ومحادثات مجموعات المشاوير والتوصيل بالسعودية.
لا تنظر لكلمات منفردة بل اقرأ المنشور كاملاً وافهم نية كاتب المنشور الحقيقية بشكل كامل:

المنشور المراد تحليله:
"{text}"

قواعد التصنيف البشري:

1. أجب بـ (YES) فقط إذا كان صاحب المنشور شخصاً يبحث عن خدمة (زبون / عميل / ركاب / شخص يحتاج توصيل أغراض أو شحنة أو يريد سواق).
   - أمثلة صريحة للقبول (YES):
     * "من قريب من الراشد يوصلني السويس" (استفسار عن سائق قاطن قرب الراشد -> زبون)
     * "من يوصلني لصبيا" (طلب توصيلة -> زبون)
     * "ابغى سواقه شهري من بيش" (طلب سائق -> زبون)
     * "ابغا سطحه من الحقو لصبيا" (طلب نقل -> زبون)
     * "مين فاضي الحين ينفعني بمشوار" (استفسار زبون)

2. أجب بـ (NO) وبشكل قاطع إذا كان صاحب المنشور هو السائق/المندوب بنفسه يعلن عن توفره، أو يعلن عن سيارته، أو يذكر خط سيره للآخرين، أو يطلب من الناس التواصل معه للركوب معك.
   - أمثلة صريحة للرفض (NO):
     * "فاضي في أحد المسارحة وضواحيها وفاضي لتوصيل أي طلب" (إعلان سائق -> NO)
     * "اي طلب او مشوار صامطة خاص" (إعلان سائق -> NO)
     * "طالع من صامطه لين مستشفى الملك فهد" (سائق يذكر خط سيره -> NO)
     * "الي فاضي يرسل خاص" / "الي يبي مشوار يجي خاص" (سائق يطلب عملاء -> NO)

الجواب النهائي (أجب بكلمة YES أو كلمة NO فقط):"""

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
        res = requests.post(url, headers=headers, json=payload, timeout=6)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🧠 [فهم بشري كامل للنية]: '{text[:35]}...' -> {answer}", flush=True)
            return "YES" in answer
        else:
            print(f"⚠️ خطأ استجابة الذكاء الاصطناعي: {res.status_code}", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ في الاتصال بالذكاء الاصطناعي: {e}", flush=True)

    return False

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    if not message or not message.id:
        return

    # تجاهل رسائل الحساب المسجل به البوت نفسه
    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    clean_text = raw_text.strip()
    if len(clean_text) < 3:
        return

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
    print(f"📩 [رسالة التُقطت من {chat_title} بواسطة {sender_name}]: {clean_text[:40]}...", flush=True)

    loop = asyncio.get_running_loop()
    is_client_request = await loop.run_in_executor(None, analyze_post_like_a_human, clean_text)

    if is_client_request:
        print(f"✅ [طلب عميل حقيقي مقبول]: {clean_text[:30]}...", flush=True)

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
                    print(f"❌ فشل البوت لإرسال {user}: {e}", flush=True)

            if not sent:
                try:
                    await userbot.send_message(
                        chat_id=user,
                        text=clean_text,
                        reply_markup=reply_markup,
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    print(f"❌ فشل اليوزربوت لإرسال {user}: {e}", flush=True)

# =========================================================
# FAST MULTI-GROUP SCANNER (100 GROUPS)
# =========================================================

async def fast_dialog_poller(userbot: Client, bot: Client):
    await asyncio.sleep(2)
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=100):
                if dialog.top_message:
                    await process_live_message(userbot, bot, dialog.top_message)
        except Exception as e:
            print(f"⚠️ خطأ الفاحص الدائري: {e}", flush=True)
            
        await asyncio.sleep(3)

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
    print("🚀 تم تشغيل النظام المحدث بذكاء بشري كامل لنوايا المنشورات!", flush=True)

    asyncio.create_task(fast_dialog_poller(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
