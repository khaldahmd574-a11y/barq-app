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
# KEEP ALIVE SERVER 24/7
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
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "Ndhhyfvvjkcd", "fs_990"]

PROCESSED_KEYS = set()
KNOWN_CHAT_IDS = set()

# =========================================================
# HARD REGEX FILTERS (فلترة الأرقام وإعلانات السائقين)
# =========================================================

def is_hard_driver_advertisement(text: str) -> bool:
    clean = text.strip()
    
    # فلتر صريح لاستبعاد عروض توفر السائقين (مع التعامل مع الأخطاء الإملائية مثل موحود / مشور)
    driver_availabilities = ["موجود", "موحود", "فاضي", "جاهز", "متواجد", "سيارتي", "خدمات توصيل"]
    trip_keywords = ["مشوار", "مشور", "خاص", "اي مشوار", "اي مشور", "تواصل خاص", "خاص مفتوح"]
    
    if any(a in clean for a in driver_availabilities) and any(t in clean for t in trip_keywords):
        print(f"🚫 [فلتر عرض سائق]: تم رفض إعلان سائق متوفر: {clean[:30]}...", flush=True)
        return True

    # فلتر أرقام الجوال المصحوبة بعبارات سائقين
    has_phone = re.search(r'(05\d{8}|\+?9665\d{8}|05\d{2}\s?\d{3}\s?\d{3})', clean)
    if has_phone:
        driver_keywords = ["كلموني", "تواصل معي", "تواصلوا", "اتصل", "رزقني", "يرزقكم", "حسابي", "خاص مفتوح"]
        for kw in driver_keywords:
            if kw in clean:
                print(f"🚫 [فلتر الأرقام]: تم رفض إعلان سائق مع رقم: {clean[:30]}...", flush=True)
                return True

    return False

# =========================================================
# PURE INTENT AI ANALYSIS ENGINE
# =========================================================

def analyze_with_pure_ai(text: str) -> bool:
    clean = text.strip()
    
    # 1. منع التحيات المجردة والكلمات القصيرة جداً (مثل: سلام، مرحبا)
    greetings = ["سلام", "السلام عليكم", "مرحبا", "هلا", "صباح الخير", "مساء الخير", "الو"]
    if clean.lower() in greetings or len(clean) < 8:
        keywords = ["توصيل", "مشوار", "مشور", "سواق", "سواقه", "باص", "رايح", "طالع", "مندوب", "ابي", "ابغى", "احتاج"]
        if not any(kw in clean for kw in keywords):
            print(f"🚫 [منع تحية/كلمة قصيرة]: {clean}", flush=True)
            return False

    # 2. تطبيق الفلتر السريع
    if is_hard_driver_advertisement(clean):
        return False

    if not OPENROUTER_API_KEY:
        return False

    prompt = f"""أنت عقل ذكاء اصطناعي محترف لمهمة تصنيف نصوص قروبات المشاوير والتوصيل بالسعودية (خاصة منطقة جازان والجنوب).

مهمتك الأساسية: تحديد "دور الكاتب" بدقة متناهية هل هو (زبون يطلب خدمة/توصيلة/طرد) أم (سائق يعرض خدمة):

[الصنف الأول: طلب عميل/زبون -> أجب بـ YES]
يكون الكاتب زبوناً ويجب قبول رسالته (YES) فقط إذا كان يُعبر عن احتياجه الشخصي لنقل أو توصيلة:
1. طلبات التوصيل والاحتياج المباشرة (مثل: "ابغا مشوار من الخميس لين صبيا"، "احتاج سواقه او سواق لمدرسة...", "ابي سواق يوصل من كليه التمريض"، "ابي مندوب").
2. الأسئلة والاستفسارات عن توفر سائق لخدمته (مثل: "مين طالع من صبيا؟"، "فيه أحد رايح جازان؟"، "مين فاضي يوصل؟").

[الصنف الثاني: إعلان سائق/عرض توفر أو تحية مجردة -> أجب بـ NO]
1. أي شخص يعرض توفره الشخصي أو سيارته لخدمة الناس (مثل: "موجود في صامطه اي مشوار خاص"، "متحرك من صبياء"، "أنا فاضي"، "متواجد حالياً").
2. التحيات المباشرة التي لا تتبعها تفاصيل طلب.
3. إعلانات الأرقام المكررة والخدمات والتسويق.

الرسالة المراد تحليلها:
"{clean}"

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
            "max_tokens": 2
        }
        res = requests.post(url, headers=headers, json=payload, timeout=3)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [تحليل النية]: '{clean[:35]}...' -> {answer}", flush=True)
            return "YES" in answer
    except Exception:
        pass

    return False

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    try:
        if not message or not message.id or not message.chat:
            return

        if message.chat.type == ChatType.PRIVATE:
            return

        if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            KNOWN_CHAT_IDS.add(message.chat.id)

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
        is_client_request = await loop.run_in_executor(None, analyze_with_pure_ai, clean_text)

        if is_client_request:
            print(f"✅ [طلب عميل مقبول]: {clean_text[:30]}...", flush=True)

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
    except Exception:
        pass

# =========================================================
# TARGETED GROUP HISTORY SCANNER (0.5s Fast Polling)
# =========================================================

async def direct_chat_history_scanner(userbot: Client, bot: Client):
    await asyncio.sleep(2)
    
    try:
        async for dialog in userbot.get_dialogs(limit=50):
            if dialog.chat and dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
                KNOWN_CHAT_IDS.add(dialog.chat.id)
    except Exception:
        pass

    while True:
        if KNOWN_CHAT_IDS:
            for chat_id in list(KNOWN_CHAT_IDS):
                try:
                    async for msg in userbot.get_chat_history(chat_id=chat_id, limit=2):
                        asyncio.create_task(process_live_message(userbot, bot, msg))
                except Exception:
                    continue
        await asyncio.sleep(0.5)

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
    print("🚀 تم تشغيل النظام بأقصى سرعة مسح وآلية فلترة متطورة!", flush=True)

    asyncio.create_task(direct_chat_history_scanner(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
