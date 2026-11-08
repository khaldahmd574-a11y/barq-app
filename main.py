import os
import asyncio
import aiohttp
from hydrogram import Client
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
# CONFIG - بدون أي آيدي
# =========================================================
TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "Ndhhyfvvjkcd", "fs_990"]

# إذا تبي تراقب كل القروبات خله فاضي []
# إذا تبي قروبات معينة بس، حط كلمات من اسمها هنا
# مثال: ["توصيل", "مشاوير", "جازان", "صامطة"]
GROUP_TITLE_KEYWORDS = []  # فاضي = راقب كل القروبات

msg_queue = asyncio.Queue(maxsize=500)
send_queue = asyncio.Queue()
seen_ids = set()
ai_sem = asyncio.Semaphore(3)

# هنا البوت بيحفظ القروبات تلقائياً
AUTO_GROUP_IDS = set()

# =========================================================
# AI - سريع مع فلتر قبل ما يرسل لـ Gemini
# =========================================================
async def ai_check(session, text):
    if len(text) < 5:
        return False

    # فلتر سريع يوفر 80% من طلبات AI
    keywords = ["مشوار", "توصيل", "مندوب", "وديني", "سواق", "يوصلني", "فاضي", "ابغا", "ابي", "احتاج", "مين يودي", "فيه احد"]
    if not any(k in text for k in keywords):
        return False

    async with ai_sem:
        try:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.environ.get('OPENROUTER_API_KEY')}"},
                json={
                    "model": "google/gemini-3.1-flash-lite",
                    "messages": [{"role": "user", "content": f"هل هذه رسالة زبون يطلب مشوار/توصيل في جازان؟ أجب YES أو NO فقط. الرسالة: {text}"}],
                    "temperature": 0, "max_tokens": 2
                },
                timeout=8
            ) as res:
                data = await res.json()
                ans = data['choices'][0]['message']['content'].strip().upper()
                return "YES" in ans
        except Exception:
            return False

# =========================================================
# WORKERS
# =========================================================
async def worker(session):
    while True:
        msg = await msg_queue.get()
        try:
            key = f"{msg.chat.id}_{msg.id}"
            if key in seen_ids:
                continue
            seen_ids.add(key)
            if len(seen_ids) > 5000:
                seen_ids.clear()

            text = (msg.text or msg.caption or "").strip()
            if await ai_check(session, text):
                await send_queue.put((msg, text))
        except Exception as e:
            print(f"Worker error: {e}", flush=True)
        finally:
            msg_queue.task_done()

async def sender(bot):
    while True:
        msg, text = await send_queue.get()
        try:
            buttons = []
            row = []
            if msg.from_user:
                if msg.from_user.username:
                    row.append(InlineKeyboardButton(f"💬 فتح المحادثة (@{msg.from_user.username})", url=f"https://t.me/{msg.from_user.username}"))
                else:
                    row.append(InlineKeyboardButton(f"💬 فتح المحادثة", url=f"tg://openmessage?user_id={msg.from_user.id}"))
            if msg.link:
                row.append(InlineKeyboardButton("📩 الرسالة الأصلية", url=msg.link))
            if row:
                buttons.append(row)

            markup = InlineKeyboardMarkup(buttons) if buttons else None
            # إرسال للـ 5 بنفس الوقت، مو واحد ورا الثاني
            tasks = [bot.send_message(chat_id=u, text=text, reply_markup=markup, disable_web_page_preview=True) for u in TARGET_USERS]
            await asyncio.gather(*tasks, return_exceptions=True)
            print(f"✅ تم الإرسال: {text[:30]}", flush=True)
        except Exception as e:
            print(f"Send error: {e}", flush=True)
        finally:
            send_queue.task_done()

# =========================================================
# اكتشاف القروبات تلقائياً - مرة واحدة فقط
# =========================================================
async def discover_groups(userbot):
    print("🔍 جاري اكتشاف القروبات تلقائياً...", flush=True)
    try:
        async for dialog in userbot.get_dialogs(limit=200):
            chat = dialog.chat
            if chat.type not in ["group", "supergroup"]:
                continue
            # لو حاط كلمات فلترة، يطبقها. لو فاضي، ياخذ الكل
            if GROUP_TITLE_KEYWORDS:
                title = (chat.title or "").lower()
                if not any(k.lower() in title for k in GROUP_TITLE_KEYWORDS):
                    continue
            AUTO_GROUP_IDS.add(chat.id)
        print(f"✅ تم اكتشاف {len(AUTO_GROUP_IDS)} قروب، والبوت جاهز", flush=True)
    except Exception as e:
        print(f"Discover error: {e}", flush=True)

# =========================================================
# MAIN
# =========================================================
async def main():
    bot = Client(
        "helper_bot",
        api_id=int(os.environ.get("TELEGRAM_API_ID")),
        api_hash=os.environ.get("TELEGRAM_API_HASH"),
        bot_token=os.environ.get("BOT_TOKEN"),
        in_memory=True
    )
    userbot = Client(
        "my_userbot",
        api_id=int(os.environ.get("TELEGRAM_API_ID")),
        api_hash=os.environ.get("TELEGRAM_API_HASH"),
        session_string=os.environ.get("SESSION_STRING"),
        in_memory=True
    )

    @userbot.on_message()
    async def listener(_, message):
        # تجاهل الخاص والقنوات، راقب القروبات المكتشفة فقط
        if message.chat.id not in AUTO_GROUP_IDS:
            return
        if message.from_user and message.from_user.is_self:
            return
        # خفيف فقط: حط في الطابور وامش
        try:
            msg_queue.put_nowait(message)
        except asyncio.QueueFull:
            pass

    await bot.start()
    await userbot.start()

    # اكتشاف مرة واحدة، وبعدها خلاص
    await discover_groups(userbot)

    async with aiohttp.ClientSession() as session:
        workers = [asyncio.create_task(worker(session)) for _ in range(3)]
        asyncio.create_task(sender(bot))
        print("🚀 النظام شغال بدون آيديات وبدون Poller", flush=True)
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
