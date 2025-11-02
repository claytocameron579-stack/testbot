from flask import Flask, request
import requests
import os
from openai import OpenAI

app = Flask(__name__)

# --- Environment Variables ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# --- Initialize OpenAI client ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Filters and Settings ---
KEYWORDS = ["آکواریوم", "ماهی", "غذا", "فیلتر", "گلدفیش", "بخاری", "ضدکلر", "سیفون", "مرجان", "نمک"]
MAX_USER_TEXT = 1500


# --- Telegram helper function ---
def send_telegram(chat_id, text):
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": text})
    except Exception as e:
        print("Telegram send error:", e)


# --- OpenAI response function ---
def get_ai_reply(user_message: str) -> str:
    try:
        messages = [
            {
                "role": "system",
                "content": (
                    "تو یک کارشناس حرفه‌ای آکواریوم و ماهی‌های زینتی هستی. "
                    "به زبان فارسی و کوتاه جواب بده. "
                    "اگر سوال خارج از حوزه آکواریوم یا ماهی بود، فقط بگو که نمی‌تونی پاسخ بدی."
                )
            },
            {"role": "user", "content": user_message}
        ]

        completion = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=400,
            temperature=0.7
        )

        return completion.choices[0].message.content.strip()

    except Exception as e:
        print("AI error:", e)
        return "در ارتباط با هوش مصنوعی مشکلی پیش آمده. لطفاً دوباره تلاش کن."


# --- Routes ---
@app.route("/")
def home():
    return "🤖 Bot is running with AI!"


@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(force=True)
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return "ok"

    # فقط اگر درباره‌ی آکواریوم بود
    if not any(k in text for k in KEYWORDS):
        send_telegram(chat_id, "من فقط درباره آکواریوم و ماهی پاسخ می‌دم 🙂")
        return "ok"

    # محدود کردن طول متن
    if len(text) > MAX_USER_TEXT:
        text = text[:MAX_USER_TEXT] + " ..."

    reply = get_ai_reply(text)
    send_telegram(chat_id, reply)
    return "ok"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
