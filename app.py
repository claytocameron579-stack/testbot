from flask import Flask, request
import requests
import os
import google.generativeai as genai

app = Flask(__name__)

# ------------------------------------
# Environment Variables
# ------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")  # از Environment گرفته میشه
genai.configure(api_key=GEMINI_API_KEY)

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
# Gemini Response
# ------------------------------------
def get_ai_reply_gemini(user_message: str) -> str:
    """ارسال متن کاربر به مدل Gemini و دریافت پاسخ"""
    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(user_message)
        if hasattr(response, "text"):
            return response.text.strip()
        else:
            return "❓ پاسخی از مدل دریافت نشد."
    except Exception as e:
        print("Gemini error:", e)
        return "⚠️ خطا در اتصال به مدل هوش مصنوعی گوگل."

# ------------------------------------
# Flask Routes
# ------------------------------------
@app.route('/')
def home():
    return "🤖 Telegram Bot connected to Google Gemini API is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json() or {}
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return "ok"

    reply = get_ai_reply_gemini(text)
    send_telegram(chat_id, reply)
    return "ok"

# ------------------------------------
# Run locally (optional)
# ------------------------------------
if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
