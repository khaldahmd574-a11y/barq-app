import os
import re
import json
import time
import asyncio
import hashlib
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp
from hydrogram import Client, filters
from hydrogram.types import Message


# ============================================================
#                    إعدادات Environment
# ============================================================

API_ID = os.getenv("API_ID") or os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("API_HASH") or os.getenv("TELEGRAM_API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

PORT = int(os.getenv("PORT", "10000"))

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "qwen/qwen-2.5-7b-instruct"
)

env_targets = os.getenv("TARGET_USERS", "")
if env_targets:
    TARGET_USERS = [t.strip() for t in env_targets.split(",") if t.strip()]
else:
    TARGET_USERS = [
        "@abood1317",
        "@shaybq",
    ]


# ============================================================
#                       Logging الشامل
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("BARQ_DEBUG")


# ============================================================
#                     Keep Alive Server
# ============================================================

class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Barq Debug Userbot Active")
        except Exception:
            pass

    def log_message(self, format, *args):
        return

threading.Thread(target=lambda: HTTPServer(("0.0.0.0", PORT), KeepAliveHandler).serve_forever(), daemon=True).start()


# ============================================================
#                    Hydrogram Client
# ============================================================

app = Client(
    "barq_userbot",
    api_id=int(API_ID),
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True,
)

BOT_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# ============================================================
#                 منع الرسائل المكررة
# ============================================================

processed_messages = {}
processed_lock = asyncio.Lock()

async def is_duplicate(message: Message, text: str) -> bool:
    try:
        chat_id = getattr(message.chat, "id", 0)
        sender_id = getattr(message.from_user, "id", 0) if message.from_user else 0
        normalized = text.strip().lower()
        raw = f"{chat_id}|{sender_id}|{normalized}"
        fingerprint = hashlib.sha256(raw.encode("utf-8")).hexdigest()

        async with processed_lock:
            if fingerprint in processed_messages:
                return True
            processed_messages[fingerprint] = time.time()
        return False
    except Exception:
        return False


# ============================================================
#             AI SYSTEM PROMPT (فحص نية الزبون)
# ============================================================

AI_SYSTEM_PROMPT = """أنت نظام ذكاء اصطناعي مخصص لفلترة طلبات التوصيل.
مهمتك: تحديد هل الرسالة صادرة من زبون يحتاج توصيل أم من سائق يعرض خدمته.

أخرج كائن JSON فقط:
{"allow": true} أو {"allow": false}

1. {"allow": true}: إذا كان الكاتب زبوناً يطلب توصيل أو مشوار (مثال: "مين يوصلني"، "احتاج سواق"، "مطلوب توصيل اغراض").
2. {"allow": false}: إذا كان الكاتب سائقاً/مندوباً يعرض خدماته أو يتواجد في مكان أو أرقام جوال وإعلانات.
"""

async def ask_openrouter(text: str) -> bool:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": AI_SYSTEM_PROMPT},
            {"role": "user", "content": f"حلل النية: \"{text}\""}
        ],
        "temperature": 0.0,
        "max_tokens": 20
    }
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.post(OPENROUTER_URL, headers=headers, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    content = data["choices"][0]["message"]["content"].strip()
                    content_clean = re.sub(r"```json|

