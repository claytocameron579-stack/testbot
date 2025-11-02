from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

# ------------------------------------
# Environment Variables
# ------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Hugging Face Router Configuration
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY")
HF_MODEL = os.environ.get("HF_MODEL", "HuggingFaceTB/SmolLM3-3B:hf-inference")
HF_ROUTER_URL = "https://router.huggingface.co/v1/chat/completions"

ROUTER_HEADERS = {
    "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
    "Content-Type": "application/json"
}

# ------------------------------------
# Telegram Helper
# ------------------------------------
def send_telegram(chat_id, text):
    """ارسال پیام به تلگرام"""
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})
    except Exception as e:
        print("Telegram send error:", e)

# ------------------------------------
# Hugging Face Router Response
# ------------------------------------
def get_ai_reply_hf(user_message: str) -> str:
    """
    ارسال پیام به Hugging Face Router (OpenAI-compatible endpoint)
    """
    payload = {
        "model": HF_MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "تو یک کارشناس فروشگاه آکواریوم و ماهی هستی. "
                    "به فارسی و با لحن طبیعی و مؤدبانه پاسخ بده. "
                    "اگر پرسش درباره محصولات، آکواریوم یا ماهی بود، "
                    "به صورت آموزشی و کاربردی جواب بده و در صورت نیاز پیشنهاد خرید بده."
                )
            },
            {"role": "user", "content": user_message}
        ],
        "max_tokens": 250,
        "temperature": 0.7,
        "stream": False
    }

    try:
        r = requests.post(HF_ROUTER_URL, headers=ROUTER_HEADERS, data=json.dumps(payload), timeout=45)
        r.raise_for_status()
        data = r.json()

        if "choices" in data and len(data["choices"]) > 0:
            reply = data["choices"][0]["message"]["content"].strip()
            return reply
        else:
            return "⚠️ مدل پاسخی برنگرداند. لطفاً دوباره امتحان کنید."
    except Exception as e:
        err = getattr(e, "response", None)
        if err is not None:
            print("HF Router error:", e, "| body:", err.text)
        else:
            print("HF Router error:", e)
        return "❌ خطا در اتصال به مدل هوش مصنوعی رخ داد."

# ------------------------------------
# Flask Routes
# ------------------------------------
@app.route('/')
def home():
    return "🤖 Telegram Bot connected to Hugging Face Router API is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json() or {}
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return "ok"

    reply = get_ai_reply_hf(text)
    send_telegram(chat_id, reply)
    return "ok"

# ------------------------------------
# Run locally (optional)
# ------------------------------------
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
