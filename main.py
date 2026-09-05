import asyncio
import os
import json
import urllib.request
from hydrogram import Client

API_ID = 39120728
API_HASH = os.environ.get("TELEGRAM_API_HASH")
BOT_TOKEN = "8782796916:AAFloRFjgcxsiZ4Y50VAeyJpjOiJXriWl9g"

CHAT_IDS = [
    8554351423
]

KEYWORDS = [
    "جيزان", "الدرب", "بيش", "العارضة", "صامطة", "أحد", "صياغة", "محايل", 
    "صبيا", "ابوعريش", "المجاردة", "الشقيق", "القنفذة", "بارق", "محايل", 
    "المظيلف", "القوز", "توصيل", "يوصل", "توصيل", "توصيلات", "توصيلي", 
    "يركبها", "شحن", "على طريقه", "ادور عن", "ابحث عن", "معلم", "مقاول", 
    "شغال", "مندوب", "دباب", "سطحة", "تاكسي", "مشوار", "مطعم", "حلاق", 
    "مطبخ", "غسيل", "مطابخ", "المنيوم", "تكييف", "سباك", "كهربائي", 
    "نقل عوائل", "دهان", "مبلط", "حداد", "سطحه", "نقل الهارات", "مصنع", 
    "عمالة", "مغسلة", "شركة", "دوام"
]

app = Client("userbot_session", api_id=API_ID, api_hash=API_HASH)
processed_message_ids = set()

def send_via_bot(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    for chat_id in CHAT_IDS:
        payload = {"chat_id": chat_id, "text": text}
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json; charset=utf-8'})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                print(f"--> [Bot API] Sent to {chat_id} (Status: {response.status})", flush=True)
        except Exception as e:
            print(f"--> [Bot API Error]: {e}", flush=True)

async def poll_messages(client: Client):
    print("--> تم بدء مراقبة المجموعات والقنوات بنجاح...", flush=True)
    while True:
        try:
            async for dialog in client.get_dialogs():
                chat = dialog.chat
                if not chat or chat.type.value not in ["group", "supergroup", "channel"]:
                    continue

                try:
                    async for message in client.get_chat_history(chat.id, limit=5):
                        message_key = (chat.id, message.id)
                        if message_key in processed_message_ids:
                            continue

                        processed_message_ids.add(message_key)
                        text = message.text or message.caption or ""
                        chat_title = message.chat.title or "Group"

                        if text:
                            for word in KEYWORDS:
                                if word in text:
                                    alert_text = f"🔔 تنبيه كلمة ({word})\nالمجموعة: {chat_title}\n\n{text}"
                                    send_via_bot(alert_text)
                                    await client.send_message("me", alert_text)
                                    print(f"--> [SUCCESS] Match: {word}", flush=True)
                                    break
                except Exception as e:
                    pass

            await asyncio.sleep(3)
        except Exception as e:
            await asyncio.sleep(5)

async def main():
    await app.start()
    print("الحساب يعمل الآن...", flush=True)
    await poll_messages(app)

if __name__ == "__main__":
    asyncio.run(main())
