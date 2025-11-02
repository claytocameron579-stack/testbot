# app.py
from flask import Flask, request
import requests
import os
import openai
import time

app = Flask(__name__)

# env vars
BOT_TOKEN = os.environ.get("BOT_TOKEN")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
# optional: choose model; start with gpt-3.5-turbo
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-3.5-turbo")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

openai.api_key = OPENAI_API_KEY

# تنظیمات عملیاتی
KEYWORDS = ["آکواریوم", "ماهی", "فیلتر", "غذا", "گلدفیش", "بتا", "بخاری", "هیتر", "ضدکلر"]
MAX_USER_TEXT = 2000  # حداکثر کاراکتر که به مدل ارسال می‌کنیم
OPENAI_TIMEOUT = 15   # ثانیه برای درخواست به OpenAI

def send_telegram(chat_id, text, parse_mode=None):
    payload = {"chat_id": chat_id, "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=5)
    except Exception:
        pass

def build_system_prompt():
    return (
        "تو یک کارشناس حرفه‌ای آکواریوم و ماهی‌های زینتی هستی. "
        "جواب‌ها را به فارسیِ ساده، کاربردی و کوتاه بده. "
        "اگر اطلاعات کافی از سوال در متن نیست، یک سوال تکمیلی کوتاه بپرس. "
        "در پاسخ‌ها ادعاهای قطعی نکن مگر از منبع مطمئن مطلع باشی. "
        "اگر سوال مرتبط با خرید یا مشخصات محصول باشه، صرفاً مشاوره بده (قیمت/موجودی رو از ووکامرس جدا می‌گیریم)."
    )

@app.route("/")
def home():
    return "Bot is running with AI!"

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json() or {}
    msg = data.get("message", {}) or {}
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id:
        return "ok"

    if not text:
        send_telegram(chat_id, "پیام‌ت متن‌دار باشه لطفاً.")
        return "ok"

    # گیت موضوعی — اگر مرتبط نبود سریع رد کن
    if not any(k in text for k in KEYWORDS):
        send_telegram(chat_id, "من فقط دربارهٔ آکواریوم و ماهی پاسخ می‌دم 🙂")
        return "ok"

    # کوتاه کردن متن طولانی کاربر
    if len(text) > MAX_USER_TEXT:
        text = text[:MAX_USER_TEXT] + " ..."

    # پیام سیستم + کاربر
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": text}
    ]

    # فراخوانی OpenAI با مدیریت خطا و زمان‌بندی ساده
    try:
        start = time.time()
        resp = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=messages,
            max_tokens=400,
            temperature=0.6,
            request_timeout=OPENAI_TIMEOUT
        )
        latency = time.time() - start
        reply = resp.choices[0].message.get("content", "").strip()
        if not reply:
            raise ValueError("empty reply")
    except openai.error.AuthenticationError:
        reply = "خطا: کلید OpenAI معتبر نیست. لطفاً تنظیمات را بررسی کن."
    except Exception as e:
        # لاگ ساده (تو محیط تولید بهتره لاگ‌جمع‌کن استفاده کنی)
        print("OpenAI error:", str(e))
        reply = "متأسفم، خطایی در پردازش هوش مصنوعی پیش آمد. کمی بعد امتحان کن."

    # ارسال پاسخ
    send_telegram(chat_id, reply)
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
