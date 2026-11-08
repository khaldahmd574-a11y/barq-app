import os
import asyncio
import aiohttp
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# =========================================================
# KEEP ALIVE SERVER 24/7 (لمنع انقطاع الاتصال على Render)
# =========================================================
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Supreme Engine Active 24/7!")

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
TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "Ndhhyfvvjkcd", "fs_990"]

API_ID = 39120728
API_HASH = "1deec8393ce5aa05c54c0c7e280377d4"
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()
SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "").strip()

GROUP_TITLE_KEYWORDS = []  # فارغ لمراقبة جميع القروبات المكتشفة

msg_queue = asyncio.Queue(maxsize=500)
send_queue = asyncio.Queue()
seen_ids = set()
ai_sem = asyncio.Semaphore(3)
AUTO_GROUP_IDS = set()

# =========================================================
# AI CHECK (محصن بمهلة 20 ثانية وفلترة مسبقة سريعة)
# =========================================================
async def ai_check(session, text):
    if not text or len(text) < 5:
        return False

    keywords = ["مشوار", "توصيل", "مندوب", "وديني", "سواق", "يوصلني", "فاضي", "ابغا", "ابي", "احتاج", "مين يودي", "فيه احد"]
    if not any(k in text for k in keywords):
        return False

    async with ai_sem:
        try:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                json={
                    "model": "google/gemini-3.1-flash-lite",
                    "messages": [{"role": "user", "content": f"هل هذه رسالة زبون يطلب مشوار/توصيل في جازان؟ أجب YES أو NO فقط. الرسالة: {text}"}],
                    "temperature": 0, "max_tokens": 2
                },
                timeout=20
            ) as res:
                if res.status == 200:
                    data = await res.json()
                    if 'choices' in data and len(data['choices']) > 0:
                        msg_obj = data['choices'][0].get('message')
                        if msg_obj and msg_obj.get('content'):
                            ans = msg_obj.get('content').strip().upper()
                            return "YES" in ans
        except Exception:
            pass
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
            tasks = [bot.send_message(chat_id=u, text=text, reply_markup=markup, disable_web_page_preview=True) for u in TARGET_USERS]
            await asyncio.gather(*tasks, return_exceptions=True)
            print(f"✅ تم الإرسال بنجاح للمستهدفين: {text[:30]}", flush=True)
        except Exception as e:
            print(f"Send error: {e}", flush=True)
        finally:
            send_queue.task_done()

# =========================================================
# DISCOVER GROUPS
# =========================================================
async def discover_groups(userbot):
    print("🔍 جاري اكتشاف القروبات تلقائياً...", flush=True)
    try:
        async for dialog in userbot.get_dialogs(limit=200):
            chat = dialog.chat
            if chat.type not in ["group", "supergroup"]:
                continue
            if GROUP_TITLE_KEYWORDS:
                title = (chat.title or "").lower()
                if not any(k.lower() in title for k in GROUP_TITLE_KEYWORDS):
                    continue
            AUTO_GROUP_IDS.add(chat.id)
        print(f"✅ تم اكتشاف {len(AUTO_GROUP_IDS)} قروب بنجاح!", flush=True)
    except Exception as e:
        print(f"Discover error: {e}", flush=True)

# =========================================================
# MAIN
# =========================================================
async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    bot = Client(
        "helper_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True
    )
    userbot = Client(
        "my_userbot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING,
        in_memory=True
    )

    @userbot.on_message()
    async def listener(_, message):
        if message.chat.id not in AUTO_GROUP_IDS:
            return
        if message.from_user and message.from_user.is_self:
            return
        try:
            msg_queue.put_nowait(message)
        except Exception:
            pass

    await bot.start()
    await userbot.start()

    await discover_groups(userbot)

    async with aiohttp.ClientSession() as session:
        workers = [asyncio.create_task(worker(session)) for _ in range(3)]
        asyncio.create_task(sender(bot))
        print("🚀 النظام يعمل بأقصى سرعة وثبات تام 24/7!", flush=True)
        await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
