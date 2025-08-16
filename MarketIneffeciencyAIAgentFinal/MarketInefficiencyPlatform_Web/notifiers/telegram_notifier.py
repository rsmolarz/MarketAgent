
import requests

BOT_TOKEN = "your_bot_token"
CHAT_ID = "your_chat_id"

def send_telegram(finding):
    try:
        message = f"🚨 *{finding['severity'].upper()}* alert from *{finding['agent']}*\n*{finding['title']}*\n{finding['description']}"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
        print("[Telegram] Alert sent.")
    except Exception as e:
        print(f"[Telegram] Failed to send: {e}")
