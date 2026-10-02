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

SESSION_STRING_1 = os.environ.get("SESSION_STRING", "").strip()
SESSION_STRING_2 = os.environ.get("SESSION_STRING_2", "").strip()

API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "Ndhhyfvvjkcd", "fs_990"]

PROCESSED_KEYS = set()

# =========================================================
# HARD REGEX FILTERS (فلترة سريعة فورية للإعلانات الصريحة)
# =========================================================

def is_hard_driver_advertisement(text: str) -> bool:
    """فلتر برمجي سريع جداً لمنع إعلانات السائقين الصريحة قبل استهلاك API الذكاء الاصطناعي"""
    
    has_phone = re.search(r'(05\d{8}|\+?9665\d{8}|05\d{2}\s?\d{3}\s?\d{3})', text)
    
    driver_keywords = [
        "متواجد", "كلموني", "تواصل معي", "تواصلوا", "اتصل", "رزقني", "يرزقكم", 
        "سيارتي", "جاهز للتحرك", "نوفر لكم", "خدمات توصيل", "حسابي", "خاص مفتوح", "متحرك العصر", "متحرك الظهر"
    ]
    
    if has_phone:
        for kw in driver_keywords:
            if kw in text:
                print(f"🚫 [فلتر سريع]: إعلان سائق برقم جوال: {text[:30]}...", flush=True)
                return True
                
    return False

# =========================================================
# ADVANCED INTENT AI ENGINE (عقل التمييز الفائق)
# =========================================================

def analyze_with_pure_ai(text: str) -> bool:
    if is_hard_driver_advertisement(text):
        return False

    if not OPENROUTER_API_KEY:
        return False

    # برومبت متطور وذكي جداً للتمييز بين الزبون والسائق في قروبات التوصيل
    prompt = f"""أنت نظام ذكاء اصطناعي فائق الدقة متخصص في تحليل نصوص مجموعات التوصيل والمشاوير في السعودية (منطقة جازان والجنوب).

مهمتك: تحديد نية الكاتب بصرامة عالية وهل هو (زبون يحتاج توصيلة) أم (سائق يعرض خدمته):

[✅ أجب بـ YES في الحالات التالية - طلبات الزبائن فقط]:
1. يبحث عن سائق أو يستفسر عن توفر توصيلة (مثل: "مين طالع من صبيا؟"، "فيه أحد رايح جازان؟"، "من قريب من ماك"، "فيه توصيل لضمد؟").
2. يطلب توصيل طرد أو أغراض أو ركاب (مثل: "ابغى مشوار"، "أبي سواق يوصل طرد"، "محتاج توصيلة ضروري"، "توصيل ضمد").
3. أسئلة المواعيد للزبائن (مثل: "مين يوصل الساعة 4؟"، "في أحد رايح أبي مشوار").
4. نصوص قصيرة جداً تحتوي اسم منطقة مع كلمة توصيل أو سواق (مثل: "توصيل بيش"، "أبي مندوب").

[❌ أجب بـ NO في الحالات التالية - إعلانات وعروض السائقين والسبام]:
1. السائق الذي يعلن عن توفره أو اتجاهه للعامة (مثل: "طالع جازان اللي يبي يكلمني"، "متواجد حالياً"، "متحرك العصر"، "أنا فاضي"، "جاهز للمشاوير").
2. ردود السائقين والمحادثات الجانبية (مثل: "تعال خاص"، "كم تدفع؟"، "تم"، "ابشر"، "تواصل معي").
3. عروض التوصيل الشهري والدوامات (مثل: "نوفر توصيل طالبات/موظفات"، "سيارة حديثة للتوصيل").
4. الإعلانات التجارية، الوظائف، والخدمات العامة.

الرسالة للمعاينة:
"{text}"

الجواب كلمة واحدة فقط: (YES) أو (NO):"""

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
        res = requests.post(url, headers=headers, json=payload, timeout=5)
        if res.status_code == 200:
            answer = res.json()['choices'][0]['message']['content'].strip().upper()
            print(f"🤖 [تحليل النية]: '{text[:35]}...' -> {answer}", flush=True)
            return "YES" in answer
        else:
            print(f"⚠️ خطأ API ({res.status_code}): {res.text}", flush=True)
    except Exception as e:
        print(f"⚠️ خطأ اتصالات الذكاء الاصطناعي: {e}", flush=True)

    return False

# =========================================================
# MESSAGE PROCESSOR (معالجة لحظية سريعة)
# =========================================================

async def process_live_message(active_userbot: Client, bot: Client, message: Message):
    try:
        if not message or not message.id or not message.chat:
            return

        # 1. استبعاد محادثات الخاص تماماً
        if message.chat.type == ChatType.PRIVATE:
            return

        # 2. استبعاد الردود (Replies) لمنع سحب الردود على المنشورات
        if message.reply_to_message_id or message.reply_to_message:
            return

        # 3. استبعاد رسائل الحساب نفسه
        if message.from_user and message.from_user.is_self:
            return

        raw_text = message.text or message.caption or ""
        clean_text = raw_text.strip()
        
        if len(clean_text) < 2:
            return

        # منع التكرار الفوري
        msg_key = f"{message.chat.id}_{message.id}"
        text_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest()
        
        if msg_key in PROCESSED_KEYS or text_hash in PROCESSED_KEYS:
            return
            
        PROCESSED_KEYS.add(msg_key)
        PROCESSED_KEYS.add(text_hash)

        if len(PROCESSED_KEYS) > 10000:
            PROCESSED_KEYS.clear()

        # إرسال النص للتحليل بالذكاء الاصطناعي
        loop = asyncio.get_running_loop()
        is_client_request = await loop.run_in_executor(None, analyze_with_pure_ai, clean_text)

        if is_client_request:
            print(f"⚡ [طلب زبون مؤكد تم لقطه بنجاح]: {clean_text[:30]}...", flush=True)

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

            # التوجيه للمستهدفين فوراً
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
                        await active_userbot.send_message(
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
# MAIN ENTRYPOINT
# =========================================================

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

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

    # تشغيل الحساب الوهمي الأول مع الاستماع اللحظي الفوري
    if SESSION_STRING_1:
        ub1 = Client("userbot_1", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING_1, in_memory=True)
        @ub1.on_message()
        async def handler1(client: Client, message: Message):
            asyncio.create_task(process_live_message(client, bot, message))
        await ub1.start()
        print("⚡ الحساب الوهمي 1 يعمل الآن بالاستماع اللحظي الفوري!", flush=True)

    # تشغيل الحساب الوهمي الثاني إذا توفر
    if SESSION_STRING_2:
        ub2 = Client("userbot_2", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING_2, in_memory=True)
        @ub2.on_message()
        async def handler2(client: Client, message: Message):
            asyncio.create_task(process_live_message(client, bot, message))
        await ub2.start()
        print("⚡ الحساب الوهمي 2 يعمل الآن بالاستماع اللحظي الفوري!", flush=True)

    print("🚀 تم التحديث: سرعة خاطفة + ذكاء يفصل بين الطلب والإعلان!", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
