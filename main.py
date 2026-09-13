import os
import asyncio
import hashlib
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler

from groq import Groq
from hydrogram import Client, filters
from hydrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from hydrogram.errors import FloodWait


# =========================================================
# إعدادات Render - السيرفر الوهمي
# =========================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"Bot is alive 24/7")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


def start_health_server():
    port = int(os.getenv("PORT", "10000"))

    server = HTTPServer(
        ("0.0.0.0", port),
        HealthHandler
    )

    print(f"🌐 Health server started on port {port}", flush=True)

    server.serve_forever()


# =========================================================
# المتغيرات
# =========================================================

SESSION_STRING = os.getenv("SESSION_STRING", "").strip()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

API_ID = int(
    os.getenv(
        "TELEGRAM_API_ID",
        "39120728"
    )
)

API_HASH = os.getenv(
    "TELEGRAM_API_HASH",
    "1deec8393ce5aa05c54c0c7e280377d4"
).strip()


# =========================================================
# الأشخاص الذين يستقبلون الطلبات
# =========================================================

TARGET_USERS = [
    "@abood1317",
    "@Waaaaaaa33",
    "@shaybq"
]


# =========================================================
# نموذج Groq سريع
# =========================================================

AI_MODEL = "openai/gpt-oss-20b"


if not SESSION_STRING:
    raise RuntimeError(
        "❌ SESSION_STRING غير موجود في Render"
    )

if not GROQ_API_KEY:
    raise RuntimeError(
        "❌ GROQ_API_KEY غير موجود في Render"
    )


# =========================================================
# Groq
# =========================================================

groq_client = Groq(
    api_key=GROQ_API_KEY
)

print("✅ Groq جاهز", flush=True)


# =========================================================
# Telegram Userbot
# =========================================================

userbot = Client(
    "jazan_listener",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    in_memory=True
)


# =========================================================
# منع التكرار
# =========================================================

processed_messages = set()

processed_requests = {}

dedupe_lock = asyncio.Lock()


# مدة منع تكرار نفس طلب الشخص
# 6 ساعات
DEDUP_SECONDS = 6 * 60 * 60


# =========================================================
# تنظيف النص
# =========================================================

def clean_text(text):

    if not text:
        return ""

    text = text.replace("\n", " ")
    text = " ".join(text.split())

    return text.strip()


# =========================================================
# بص
