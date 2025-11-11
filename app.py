# app.py
from flask import Flask, request
import requests
import os
import re
from urllib.parse import quote_plus
import html
import google.generativeai as genai

app = Flask(__name__)

# ------------------------------
# Environment
# ------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL  = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://irancoral.ir").rstrip("/")

# WooCommerce (اختیاری: اگر ندهی، فقط مقالات را می‌آوریم)
WC_CONSUMER_KEY    = os.environ.get("WC_CONSUMER_KEY")
WC_CONSUMER_SECRET = os.environ.get("WC_CONSUMER_SECRET")

genai.configure(api_key=GEMINI_API_KEY)

# ------------------------------
# Helpers
# ------------------------------
UA_HEADERS = {
    "User-Agent":
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
}

def send_telegram(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=8
        )
    except Exception as e:
        print("Telegram send error:", e)

def is_persian_text(s: str) -> bool:
    return any('\u0600' <= ch <= '\u06FF' for ch in s)

def is_english_only(s: str) -> bool:
    if is_persian_text(s):
        return False
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False

def strip_html(text: str) -> str:
    # تبدیل HTML به متن ساده
    if not text:
        return ""
    t = re.sub(r'<[^>]+>', ' ', text)
    t = html.unescape(t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

# ------------------------------
# WordPress REST (مقالات/آموزش)
# ------------------------------
def wp_search_posts(query: str, per_page: int = 5):
    """
    گرفتن پست‌های آموزشی مرتبط از WordPress REST:
    /wp-json/wp/v2/posts?search=...
    """
    try:
        url = f"{SITE_BASE_URL}/wp-json/wp/v2/posts"
        params = {
            "search": query,
            "per_page": per_page,
            "_fields": "id,link,title,excerpt,content"
        }
        r = requests.get(url, params=params, headers=UA_HEADERS, timeout=12)
        r.raise_for_status()
        posts = r.json()
        results = []
        for p in posts:
            title = strip_html((p.get("title") or {}).get("rendered", ""))
            excerpt = strip_html((p.get("excerpt") or {}).get("rendered", ""))
            content = strip_html((p.get("content") or {}).get("rendered", ""))
            link = p.get("link", "")
            # خلاصه‌ی کوتاه از محتوا
            body = content if content else excerpt
            snippet = (body[:900] + "…") if len(body) > 900 else body
            block = f"عنوان: {title}\nلینک: {link}\nمتن: {snippet}"
            results.append(block)
        return results
    except Exception as e:
        print("wp_search_posts error:", e)
        return []

# ------------------------------
# WooCommerce REST (محصولات) – اختیاری
# ------------------------------
def wc_search_products(query: str, per_page: int = 5):
    """
    اگر WC_CONSUMER_KEY/SECRET ست شده باشد، محصولات را از WooCommerce REST می‌گیرد.
    /wp-json/wc/v3/products?search=...
    """
    if not WC_CONSUMER_KEY or not WC_CONSUMER_SECRET:
        return []  # بدون کلید، این بخش را رد کن

    try:
        url = f"{SITE_BASE_URL}/wp-json/wc/v3/products"
        params = {
            "search": query,
            "per_page": per_page,
            "consumer_key": WC_CONSUMER_KEY,
            "consumer_secret": WC_CONSUMER_SECRET,
        }
        r = requests.get(url, params=params, headers=UA_HEADERS, timeout=12)
        r.raise_for_status()
        items = r.json()
        results = []
        for p in items:
            name = p.get("name", "")
            price = p.get("price", "")
            link = p.get("permalink", "")
            stock = p.get("stock_status", "")
            sd = strip_html(p.get("short_description", "") or "")
            stock_fa = "موجود ✅" if stock == "instock" else "ناموجود ❌" if stock else ""
            line = f"محصول: {name}\nقیمت: {price} تومان\nوضعیت: {stock_fa}\nتوضیح: {sd[:400]}\nلینک: {link}"
            results.append(line)
        return results
    except Exception as e:
        print("wc_search_products error:", e)
        return []

# ------------------------------
# Context Builder (فقط از ایران‌کورال)
# ------------------------------
def build_irancoral_context(user_text: str, max_chars: int = 3500) -> str:
    """
    ابتدا تلاش می‌کنیم از WooCommerce (اگر کلید داری) محصولات مرتبط را بیاوریم.
    سپس از پست‌های وردپرس (مقالات) نتایج مرتبط را می‌آوریم.
    همه‌ی منابع، فقط از irancoral.ir هستند.
    """
    parts = []

    # محصولات (اگر کلید داری)
    prod = wc_search_products(user_text, per_page=5)
    if prod:
        parts.append("== محصولات مرتبط از ایران‌کورال ==\n" + "\n\n".join(prod))

    # مقالات/پست‌ها
    posts = wp_search_posts(user_text, per_page=5)
    if posts:
        parts.append("== مقالات/آموزش از ایران‌کورال ==\n" + "\n\n".join(posts))

    ctx = "\n\n---\n\n".join(parts).strip()
    if len(ctx) > max_chars:
        ctx = ctx[:max_chars] + "…"
    return ctx

# ------------------------------
# Gemini: فقط بر اساس کانتکست ایران‌کورال
# ------------------------------
def answer_with_gemini_irancoral(user_message: str) -> str:
    allow_english = is_english_only(user_message)
    lang_instruction = (
        "Always answer in English."
        if allow_english else
        "فقط و فقط به زبان فارسی پاسخ بده."
    )

    context = build_irancoral_context(user_message)
    if not context:
        # حتی اگر هیچ نتیجه‌ای نیاید، صادقانه اعلام کن
        context = (
            "هیچ منبعی از irancoral.ir برای این پرسش پیدا نشد. "
            "اگر پاسخ نیاز به منبع دارد، صراحتاً بگو منبع موجود نیست و از کاربر جزئیات بیشتر بپرس."
        )

    system_instruction = (
        f"{lang_instruction}\n"
        "تو کارشناس آکواریوم و محصولات فروشگاه ایران‌کورال هستی. "
        "قانون طلایی: پاسخ را فقط بر پایه «منابع ایران‌کورال» که پایین آمده‌اند بساز؛ "
        "اگر منابع کافی نیستند، کوتاه بگو «منابع کافی از ایران‌کورال پیدا نشد» و سؤال تکمیلی بپرس. "
        "اگر محصول مناسب در منابع هست، همان را با لینک ایران‌کورال پیشنهاد بده. "
        "از منبع دیگری استفاده نکن."
    )

    prompt = (
        f"{system_instruction}\n\n"
        f"منابع از irancoral.ir:\n{context}\n\n"
        f"پرسش کاربر:\n{user_message}"
    )

    try:
        model = genai.GenerativeModel(GEMINI_MODEL)
        resp = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=450,
            ),
        )
        text = (resp.text or "").strip() if hasattr(resp, "text") else ""
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL|re.IGNORECASE).strip()
        if not text:
            return "⚠️ پاسخی تولید نشد. لطفاً سؤال را دقیق‌تر بفرمایید."
        return text
    except Exception as e:
        print("Gemini error:", e)
        return "❌ خطا در اتصال به مدل هوش مصنوعی؛ کمی بعد دوباره تلاش کنید."

# ------------------------------
# Flask
# ------------------------------
@app.route("/")
def home():
    return "🤖 IranCoral AI (Gemini + WP/Woo REST) is running."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json() or {}
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return "ok"

    reply = answer_with_gemini_irancoral(text)
    send_telegram(chat_id, reply)
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
