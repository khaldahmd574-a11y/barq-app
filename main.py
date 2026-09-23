import os
import re
import time
import asyncio
import hashlib
import requests
import json
import base64
from collections import OrderedDict
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

from hydrogram import Client, filters
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait, RPCError

# =========================================================
# KEEP ALIVE SERVER 24/7
# =========================================================

class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq AI System Active!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", "10000"))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

# =========================================================
# CONFIGURATION
# =========================================================

API_ID_RAW = os.environ.get("API_ID", os.environ.get("TELEGRAM_API_ID", "39120728")).strip()
API_HASH = os.environ.get("API_HASH", os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4")).strip()
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

try:
    API_ID = int(API_ID_RAW)
except Exception:
    API_ID = 0

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "Ndhhyfvvjkcd"]

# =========================================================
# DEDUPLICATION & LOCKS
# =========================================================

PROCESSED_KEYS = set()
PROCESSED_LOCK = asyncio.Lock()

def get_text_hash(text: str) -> str:
    clean = re.sub(r'\s+', ' ', text.strip().lower())
    return hashlib.md5(clean.encode('utf-8')).hexdigest()

# =========================================================
# HARD REGEX PRE-FILTER (فلتر صريح للسائقين لتقليل الضغط)
# =========================================================

def is_hard_driver_advertisement(text: str) -> bool:
    has_phone = re.search(r'(05\d{8}|\+?9665\d{8}|05\d{2}\s?\d{3}\s?\d{3})', text)
    driver_keywords = [
        "متواجد", "كلموني", "تواصل معي", "تواصلوا", "اتصل", "رزقني", "يرزقكم", 
        "فاضي", "سيارتي", "جاهز", "نوفر لكم", "خدمات توصيل", "خاص مفتوح"
    ]
    if has_phone:
        for kw in driver_keywords:
            if kw in text:
                return True
    return False

# =========================================================
# FLEXIBLE AI ENGINE
# =========================================================

def analyze_with_pure_ai(text: str) -> bool:
    if is_hard_driver_advertisement(text):
        return False

    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت عقل ذكاء اصطناعي محترف لمهمة تصنيف نصوص قروبات المشاوير والتوصيل بالسعودية (خاصة منطقة جازان والجنوب).

مهمتك الأساسية: تحديد "دور الكاتب" بدقة متناهية هل هو (زبون يطلب خدمة/طرد/توصيلة) أم (سائق يعرض خدمة):

[الصنف الأول: طلب عميل/زبون -> أجب بـ YES]
يكون الكاتب زبوناً ويجب قبول رسالته (YES) إذا كان يُعبر عن احتياجه أو يبحث عن سواق/مندوب لنقل طرد/مشوار/ركاب:
1. الأسئلة والاستفسارات عن توفر سائق أو خط سير (مثل: "مين طالع من صبيا؟"، "فيه أحد رايح جازان؟"، "مين فاضي يوصل؟").
2. طلبات الاحتياج والمبادرة بجميع صيغ العامية سواء كانت سؤالاً أو إخباراً (مثل: "ابغى سواق"، "أبي مندوب"، "محتاج توصيلة"، "مطلوب سواق"، "مشوار الآن ابي سيارة.."، "مندوب من صبيا جاي صامطة يستلم طلبية..").
3. أي طلب لنقل أغراض، طرود، ركاب، هدايا، طلبات مطاعم، أو استلام شحنات من مواقع مثل (ريد بوكس، سمسا، جرير... إلخ).

[الصنف الثاني: إعلان سائق/مندوب أو سبام -> أجب بـ NO]
يكون الكاتب سائقاً/معلناً ويجب رفض رسالته (NO) إذا كان يُعلن صراحةً عن توفره الشخصي أو سيارته أو خدماته للجمهور:
1. أي نص يحتوي على "رقم جوال" للسائق مع عبارات التوفر (مثل: "متواجد كلموني 055xxx", "تواصل خاص 050xxx").
2. التصريح بالتحرك أو الجاهزية الشخصية للعامة (مثل: "متحرك من صبياء"، "مشي العصر"، "أنا فاضي"، "متواجد حالياً"، "طالع جازان اللي يبي يكلمني"، "الله يرزقنا ويرزقكم").
3. إعلانات قوائم الخدمات المكررة، والوظائف والتسويق.

الرسالة المراد تحليلها:
"{text}"

الجواب كلمة واحدة فقط لا غير: (YES) أو (NO):"""

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
            print(f"🤖 [الذكاء الاصطناعي]: '{text[:35]}...' -> {answer}", flush=True)
            return "YES" in answer
    except Exception as e:
        print(f"⚠️ خطأ API: {e}", flush=True)

    return False

# =========================================================
# INTERNAL PAYLOAD CREATOR
# =========================================================

def create_bot_payload(text, sender_id, sender_username, sender_first_name, message_link):
    data = {
        "type": "BARQ_CUSTOMER_REQUEST",
        "text": text,
        "sender_id": sender_id,
        "sender_username": sender_username,
        "sender_first_name": sender_first_name,
        "message_link": message_link
    }
    raw = json.dumps(data, ensure_ascii=False)
    encoded = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")
    return "BARQ_INTERNAL:" + encoded

# =========================================================
# BOT INTERNAL HANDLER
# =========================================================

async def handle_bot_internal_message(bot: Client, message: Message):
    if not message or not message.text or not message.text.startswith("BARQ_INTERNAL:"):
        return

    try:
        encoded = message.text[len("BARQ_INTERNAL:"):]
        decoded = base64.urlsafe_b64decode(encoded).decode("utf-8")
        data = json.loads(decoded)
    except Exception:
        return

    text = data.get("text", "").strip()
    sender_id = data.get("sender_id")
    sender_username = data.get("sender_username")
    sender_first_name = data.get("sender_first_name", "المستخدم")
    message_link = data.get("message_link")

    buttons = []
    row = []

    if sender_username:
        row.append(InlineKeyboardButton(f"💬 فتح المحادثة (@{sender_username})", url=f"https://t.me/{sender_username}"))
    elif sender_id:
        row.append(InlineKeyboardButton(f"💬 فتح المحادثة ({sender_first_name})", url=f"tg://openmessage?user_id={sender_id}"))

    if message_link:
        row.append(InlineKeyboardButton("📩 الرسالة الأصلية", url=message_link))

    if row:
        buttons.append(row)

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

    for user in TARGET_USERS:
        try:
            await bot.send_message(chat_id=user, text=text, reply_markup=reply_markup, disable_web_page_preview=True)
            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"❌ فشل إرسال إلى {user}: {e}", flush=True)

# =========================================================
# PROCESSOR FOR LIVE MESSAGES
# =========================================================

async def process_live_message(userbot: Client, bot_username: str, message: Message):
    if not message or not message.id:
        return

    if message.from_user and message.from_user.is_self:
        return

    raw_text = message.text or message.caption or ""
    clean_text = raw_text.strip()
    if len(clean_text) < 4:
        return

    msg_key = f"{message.chat.id}_{message.id}"
    text_hash = get_text_hash(clean_text)

    async with PROCESSED_LOCK:
        if msg_key in PROCESSED_KEYS or text_hash in PROCESSED_KEYS:
            return
        PROCESSED_KEYS.add(msg_key)
        PROCESSED_KEYS.add(text_hash)
        if len(PROCESSED_KEYS) > 15000:
            PROCESSED_KEYS.clear()

    loop = asyncio.get_running_loop()
    is_client_request = await loop.run_in_executor(None, analyze_with_pure_ai, clean_text)

    if is_client_request:
        print(f"✅ [طلب عميل مقبول]: {clean_text[:30]}...", flush=True)

        sender_id = message.from_user.id if message.from_user else None
        sender_username = message.from_user.username if message.from_user else None
        sender_first_name = message.from_user.first_name if message.from_user else "المستخدم"
        message_link = message.link

        payload = create_bot_payload(clean_text, sender_id, sender_username, sender_first_name, message_link)

        try:
            await userbot.send_message(chat_id=bot_username, text=payload, disable_web_page_preview=True)
        except Exception as e:
            print(f"❌ خطأ عند تحويل الطلب للبوت: {e}", flush=True)

# =========================================================
# FAST SCANNER FOR LARGE GROUPS
# =========================================================

async def fast_dialog_poller(userbot: Client, bot_username: str):
    await asyncio.sleep(5)
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=50):
                if dialog.top_message:
                    await process_live_message(userbot, bot_username, dialog.top_message)
        except Exception as e:
            print(f"⚠️ خطأ الفاحص: {e}", flush=True)
        await asyncio.sleep(4)

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
        "barq_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True
    )

    @bot.on_message(filters.private)
    async def bot_receiver(client: Client, message: Message):
        await handle_bot_internal_message(client, message)

    await bot.start()
    bot_me = await bot.get_me()
    bot_username = bot_me.username

    # تم إلغاء الفلاتر المقيدة لضمان التقاط كل المجموعات الكبيرة والقنوات الملحقة
    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        await process_live_message(client, bot_username, message)

    await userbot.start()
    print(f"🚀 تم تشغيل النظام بنجاح! البوت: @{bot_username}", flush=True)

    asyncio.create_task(fast_dialog_poller(userbot, bot_username))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
