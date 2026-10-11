import os
import time
import asyncio
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
from hydrogram import Client
from hydrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.enums import ChatType

# Keep Alive Server
class DummyServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Barq Active!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), DummyServer)
    server.serve_forever()

SESSION_STRING = os.environ.get("SESSION_STRING", "").strip()
API_ID = int(os.environ.get("TELEGRAM_API_ID", 39120728))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "1deec8393ce5aa05c54c0c7e280377d4").strip()
BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

TARGET_USERS = ["shaybq", "Waaaaaaa33", "abood1317", "Ndhhyfvvjkcd", "fs_990"]
PROCESSED_KEYS = set()

async def handle_new_message(userbot: Client, bot: Client, message: Message):
    try:
        if not message or not message.chat or message.chat.type == ChatType.PRIVATE:
            return

        if message.from_user and message.from_user.is_self:
            return

        text = (message.text or message.caption or "").strip()
        if len(text) < 1:
            return

        msg_key = f"{message.chat.id}_{message.id}"
        if msg_key in PROCESSED_KEYS:
            return
        PROCESSED_KEYS.add(msg_key)

        print(f"🔥 [تم رصد رسالة وسحبها فوراً]: {text}", flush=True)

        buttons = []
        if message.from_user:
            if message.from_user.username:
                user_url = f"https://t.me/{message.from_user.username}"
                user_label = f"💬 فتح المحادثة (@{message.from_user.username})"
            else:
                user_url = f"tg://openmessage?user_id={message.from_user.id}"
                user_label = f"💬 فتح المحادثة ({message.from_user.first_name or 'العميل'})"
            buttons.append([InlineKeyboardButton(user_label, url=user_url)])

        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None

        for target in TARGET_USERS:
            sent = False
            if bot:
                try:
                    await bot.send_message(chat_id=target, text=f"📥 وصل طلب جديد:\n\n{text}", reply_markup=reply_markup, disable_web_page_preview=True)
                    sent = True
                except Exception:
                    pass
            if not sent:
                try:
                    await userbot.send_message(chat_id=target, text=f"📥 وصل طلب جديد:\n\n{text}", reply_markup=reply_markup, disable_web_page_preview=True)
                except Exception:
                    pass
    except Exception as e:
        print(f"⚠️ خطأ: {e}", flush=True)

async def main():
    threading.Thread(target=run_dummy_server, daemon=True).start()

    userbot = Client("barq_userbot", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING, in_memory=True)
    bot = None
    if BOT_TOKEN:
        try:
            bot = Client("barq_helper_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN, in_memory=True)
            await bot.start()
        except Exception:
            pass

    @userbot.on_message()
    async def on_live_message(client: Client, message: Message):
        asyncio.create_task(handle_new_message(client, bot, message))

    await userbot.start()
    print("🚀 [برق يعمل الآن بوضع السحب الفوري المباشر بدون شروط!]", flush=True)

    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
