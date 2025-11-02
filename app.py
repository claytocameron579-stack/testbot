from flask import Flask, request
import requests
import os

app = Flask(__name__)

# ----------------------------
# Environment Variables
# ----------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Hugging Face Config
HUGGINGFACE_API_KEY = os.environ.get("HUGGINGFACE_API_KEY")
HF_MODEL = os.environ.get("HF_MODEL", "google/flan-t5-base")
HF_API = f"https://api-inference.huggingface.co/models/{HF_MODEL}"
HEADERS = {"Authorization": f"Bearer {HUGGINGFACE_API_KEY}"}

# ----------------------------
# Keyword Filter (Only Aquarium)
# ----------------------------
KEYWORDS = ["آکواریوم", "ماهی", "غذا", "فیلتر", "بخاری", "گلدفیش", "ضدکلر", "سیفون", "مرجان", "نمک"]

# ----------------------------
# Helper: Send message to Telegram
# ----------------------------
def send_telegram(chat_id, text):
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})
    except Exception as e:
        print("Telegram error:", e)

# ----------------------------
# Hugging Face AI Response
# ----------------------------
def get_ai_reply_hf(user_message: str) -> str:
    """
    دریافت پاسخ از مدل Hugging Face (رایگان)
    """
    payload = {
        "inputs": user_message,
        "parameters": {"max_new_tokens": 200, "temperature": 0.7},
        "options": {"wait_for_model": True}
    }

    try:
        r = requests.post(HF_API, headers=HEADERS, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()

        # استخراج پاسخ از ساختار API
        if isinstance(data, list) and len(data) > 0:
            first = data[0]
            if isinstance(first, dict):
                txt = first.get("generated_text") or first.get("summary_text") or ""
                return txt.strip()
        elif isinstance(data, dict) and "error" in data:
            return "⚠️ مدل آماده نیست یا خطایی رخ داده: " + data["error"]

        return "❓ پاسخی از مدل دریافت نشد."
    except Exception as e:
        print("HF error:", e)
        return "خطا در ارتباط با هوش مصنوعی رایگان."

# ----------------------------
# Flask Routes
# ----------------------------
@app.route('/')
def home():
    return "🤖 Telegram Bot with Hugging Face AI is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json() or {}
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return "ok"

    # فقط اگر درباره آکواریوم و ماهی بود پاسخ بده
    if not any(k in text for k in KEYWORDS):
        send_telegram(chat_id, "من فقط درباره آکواریوم و ماهی پاسخ می‌دم 🙂")
        return "ok"

    # دریافت پاسخ از Hugging Face
    reply = get_ai_reply_hf(text)
    send_telegram(chat_id, reply)
    return "ok"

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

