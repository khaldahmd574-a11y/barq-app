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

# =========================================================
# HARD REGEX FILTERS (فلترة الأرقام والإعلانات الصريحة أولاً)
# =========================================================

def is_hard_driver_advertisement(text: str) -> bool:
    """يفحص الرسالة برمجياً لمنع إعلانات السائقين التي تحتوي على أرقام أو كلمات صريحة قبل الذكاء الاصطناعي"""
    
    # البحث عن أرقام هواتف
    has_phone = re.search(r'(05\d{8}|\+?9665\d{8}|05\d{2}\s?\d{3}\s?\d{3})', text)
    
    # كلمات إعلانات السائقين والمناديب
    driver_keywords = [
        "متواجد", "كلموني", "تواصل معي", "تواصلوا", "اتصل", "رزقني", "يرزقكم", 
        "فاضي", "سيارتي", "جاهز", "نوفر لكم", "خدمات توصيل", "حسابي", "خاص مفتوح"
    ]
    
    # إذا كان النص يحتوي على رقم جوال وإحدى كلمات السائقين -> رفض فوري
    if has_phone:
        for kw in driver_keywords:
            if kw in text:
                print(f"🚫 [فلتر الأرقام]: تم رفض إعلان سائق يحتوي على رقم هاتف: {text[:30]}...", flush=True)
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

    prompt = f"""أنت عقل ذكاء اصطناعي محترف لمهمة تصنيف نصوص قروبات المشاوير والتوصيل بالسعودية (خاصة منطقة جازان والجنوب).

مهمتك الأساسية: تحديد "دور الكاتب" بدقة متناهية هل هو (زبون يطلب خدمة/توصيلة/طرد) أم (سائق يعرض خدمة):

[الصنف الأول: طلب عميل/زبون -> أجب بـ YES]
يكون الكاتب زبوناً ويجب قبول رسالته (YES) إذا كان يُعبر عن احتياجه أو يبحث عن سواق/مندوب لنقل طرد/مشوار/ركاب:
1. الأسئلة والاستفسارات عن توفر سائق أو خط سير (مثل: "مين طالع من صبيا؟"، "فيه أحد رايح جازان؟"، "مين فاضي يوصل؟"، "من قريب من ماك").
2. طلبات الاحتياج والتوصيل المباشرة أو القليلة الكلمات (مثل: "توصيل ضمد"، "توصيل ضمد من فاضي"، "ابغى سواق"، "أبي مندوب"، "محتاج توصيلة").
3. السلام والتحية المتبوعة بطلب أو استفسار عن توصيلة (مثل: "السلام عليكم ورحمة الله وبركاته صباح الخير من قريب من ماك").
* قاعدة حاسمة: أي رسالة قصيرة تشير إلى اسم مكان مع كلمة "توصيل" أو "مين" أو "فاضي" أو "قريب" تعتبر (YES) فوراً.

[الصنف الثاني: إعلان سائق/مندوب أو سبام -> أجب بـ NO]
يكون الكاتب سائقاً/معلناً ويجب رفض رسالته (NO) إذا كان يُعلن صراحةً عن توفره الشخصي أو سيارته أو خدماته للجمهور:
1. أي نص يحتوي على "رقم جوال" للسائق للاتصال والتواصل (مثل: "متواجد كلموني 055xxx", "تواصل خاص 050xxx").
2. التصريح بالتحرك أو الجاهزية الشخصية للعامة (مثل: "متحرك من صبياء"، "مشي العصر"، "أنا فاضي"، "متواجد حالياً"، "طالع جازان اللي يبي يكلمني"، "الله يرزقنا ويرزقكم").
3. السائق الذي يعرض خدمة التوصيل للدوامات أو المجموعات ويتلقى الطلبات.
4. إعلانات قوائم الخدمات المكررة، والوظائف والعملات الرقمية.

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
        res = requests.post(url, headers=headers, json=payload, timeout=6)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [تحليل النية والفلترة]: '{text[:35]}...' -> {answer}", flush=True)
            return "YES" in answer
        else:
            print(f"⚠️ خطأ API ({res.status_code}): {res.text}", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ في الاتصال بالذكاء الاصطناعي: {e}", flush=True)

    return False

# =========================================================
# MESSAGE PROCESSOR
# =========================================================

async def process_live_message(userbot: Client, bot: Client, message: Message):
    if not message or not message.id or not message.chat:
        return

    # 1. التجاهل التام لرسائل الخاص للحساب الوهمي (تفاعل في المجموعة فقط)
    if message.chat.type == ChatType.PRIVATE:
        return

    # 2. التجاهل التام لأي ردود على رسائل أخرى (Reply) لمنع سحب ردود السائقين
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
        print(f"✅ [طلب عميل مقبول بناءً على النية]: {clean_text[:30]}...", flush=True)

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

# =========================================================
# FAST MULTI-GROUP SCANNER (تغطية 100% لجميع القروبات)
# =========================================================

async def fast_dialog_poller(userbot: Client, bot: Client):
    await asyncio.sleep(2)
    while True:
        try:
            async for dialog in userbot.get_dialogs(limit=150):
                # قراءة المجموعات والقنوات فقط في الفاحص الدائري
                if dialog.chat and dialog.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP, ChatType.CHANNEL]:
                    if dialog.top_message:
                        asyncio.create_task(process_live_message(userbot, bot, dialog.top_message))
        except Exception as e:
            print(f"⚠️ خطأ في الفاحص الدائري: {e}", flush=True)
            
        await asyncio.sleep(2)

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
        except Exception as e:
            print(f"⚠️ لم يتم بدء البوت المساعد: {e}", flush=True)

    @userbot.on_message()
    async def global_live_listener(client: Client, message: Message):
        asyncio.create_task(process_live_message(client, bot, message))

    await userbot.start()
    print("🚀 تم تشغيل النظام: تصفية الردود (Replies) واستبعاد الخاص نهائياً!", flush=True)

    asyncio.create_task(fast_dialog_poller(userbot, bot))

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())

