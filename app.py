# app.py
from flask import Flask, request
import requests
import os
import re
from urllib.parse import quote_plus, urlparse
from bs4 import BeautifulSoup
import google.generativeai as genai

app = Flask(__name__)

# ----------------------------------------------------
# Environment
# ----------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

# مرجع سایت
SITE_BASE_URL = os.environ.get("SITE_BASE_URL", "https://irancoral.ir")

# Gemini init
genai.configure(api_key=GEMINI_API_KEY)

# ----------------------------------------------------
# Utilities
# ----------------------------------------------------
UA_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    )
}

def send_telegram(chat_id, text):
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=8,
        )
    except Exception as e:
        print("Telegram send error:", e)

def is_persian_text(text: str) -> bool:
    # اگر حداقل یک کاراکتر فارسی/عربی وجود داشته باشد، فارسی در نظر بگیر
    return any('\u0600' <= ch <= '\u06FF' for ch in text)

def is_english_only(text: str) -> bool:
    # اگر هیچ کاراکتر فارسی نباشد و عمدتاً ASCII باشد، انگلیسیِ کامل
    if is_persian_text(text):
        return False
    try:
        text.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False

def http_get(url: str, timeout=12):
    return requests.get(url, headers=UA_HEADERS, timeout=timeout)

def normalize_url(u: str) -> str:
    # فقط لینک‌های داخل irancoral.ir را قبول کن
    try:
        p = urlparse(u)
        if not p.scheme:
            u = SITE_BASE_URL.rstrip('/') + '/' + u.lstrip('/')
        if "irancoral.ir" in urlparse(u).netloc:
            return u
    except Exception:
        pass
    return ""

# ----------------------------------------------------
# IranCoral Crawling (سبک و سریع)
# ----------------------------------------------------
def extract_product_info(url: str) -> str:
    """
    تلاش برای بیرون‌کشیدن داده‌های محصول ووکامرس از irancoral.ir
    """
    try:
        url = normalize_url(url)
        if not url:
            return ""
        r = http_get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        title = (
            (soup.select_one("h1.product_title") or soup.select_one("h1.entry-title"))
            or soup.find("h1")
        )
        title = title.get_text(strip=True) if title else ""

        # قیمت
        price_el = soup.select_one(".woocommerce-Price-amount")
        if not price_el:
            price_el = soup.select_one(".price")
        price = price_el.get_text(strip=True) if price_el else ""

        # وضعیت موجودی
        stock_el = soup.select_one(".stock")
        stock = stock_el.get_text(strip=True) if stock_el else ""

        # توضیح کوتاه محصول
        short_desc_el = soup.select_one(".woocommerce-product-details__short-description")
        if not short_desc_el:
            # fallback: بخش توضیحات تب اصلی
            short_desc_el = soup.select_one("#tab-description") or soup.select_one(".entry-content")
        short_desc = short_desc_el.get_text(" ", strip=True)[:800] if short_desc_el else ""

        # تجمیع
        chunks = []
        if title: chunks.append(f"نام محصول: {title}")
        if price: chunks.append(f"قیمت: {price}")
        if stock: chunks.append(f"موجودی: {stock}")
        if short_desc: chunks.append(f"توضیح: {short_desc}")
        chunks.append(f"لینک: {url}")

        return "\n".join(chunks).strip()
    except Exception as e:
        print("extract_product_info error:", e)
        return ""

def extract_article_info(url: str) -> str:
    """
    در صورت مقاله/برگه: متن اصلی را خلاصه استخراج کن
    """
    try:
        url = normalize_url(url)
        if not url:
            return ""
        r = http_get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        content = soup.select_one(".entry-content") or soup.find("article") or soup.body
        text = content.get_text(" ", strip=True) if content else ""
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return ""
        return f"مقاله/صفحه: {url}\nمتن: {text[:2000]}"
    except Exception as e:
        print("extract_article_info error:", e)
        return ""

def site_search_snippets(query: str, limit_pages: int = 5):
    """
    جستجوی ساده در سایت با پارامتر ?s= (وردپرس) و استخراج چند نتیجه اول
    سپس هر لینک را باز کرده و خلاصه‌ای کوتاه می‌سازد.
    """
    try:
        search_url = f"{SITE_BASE_URL.rstrip('/')}/?s={quote_plus(query)}"
        r = http_get(search_url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        links = []
        # نتایج محصول ووکامرس
        for a in soup.select("a.woocommerce-LoopProduct-link"):
            href = a.get("href")
            if href: links.append(href)
        # نتایج مقاله/پست
        for h2 in soup.select("h2.entry-title a"):
            href = h2.get("href")
            if href: links.append(href)

        # یکتا و محدود
        seen = set()
        uniq = []
        for u in links:
            u = normalize_url(u)
            if u and u not in seen:
                uniq.append(u)
                seen.add(u)
            if len(uniq) >= limit_pages:
                break

        snippets = []
        for u in uniq:
            if "/product/" in u:
                info = extract_product_info(u)
            else:
                info = extract_article_info(u)
            if info:
                snippets.append(info)
        return snippets
    except Exception as e:
        print("site_search_snippets error:", e)
        return []

def extract_irancoral_context(user_text: str, max_total_chars: int = 3500) -> str:
    """
    - اگر کاربر لینک irancoral داد: همان‌ها را استخراج کن
    - در غیر این صورت: با ?s= جستجو کن و چند نتیجه خلاصه برگردان
    """
    # لینک‌های ایران‌کورال داخل پیام
    urls = re.findall(r"https?://[^\s]+", user_text)
    urls = [u for u in urls if "irancoral.ir" in u]

    ctx_parts = []
    total = 0

    if urls:
        for u in urls:
            block = extract_product_info(u) if "/product/" in u else extract_article_info(u)
            if block:
                ctx_parts.append(block)
                total += len(block)
                if total >= max_total_chars:
                    break
    else:
        # جستجوی آزاد در سایت
        snips = site_search_snippets(user_text, limit_pages=4)
        for s in snips:
            ctx_parts.append(s)
            total += len(s)
            if total >= max_total_chars:
                break

    return "\n\n---\n\n".join(ctx_parts)

# ----------------------------------------------------
# Gemini wrapper (فقط بر اساس کانتکست ایران‌کورال)
# ----------------------------------------------------
def get_ai_reply_from_irancoral(user_message: str) -> str:
    # سیاست زبان:
    # - اگر کاربر کاملاً غیر فارسی نوشت => اجازه انگلیسی
    # - در غیر این صورت => فارسی اجباری
    allow_english = is_english_only(user_message)
    lang_instruction = (
        "Always answer in English." if allow_english
        else "فقط و فقط به زبان فارسی پاسخ بده."
    )

    # کانتکست از ایران‌کورال
    context = extract_irancoral_context(user_message)

    # اگر هیچ کانتکستی نتونستیم بگیریم، مدل را مجبور کنیم به صراحت بگوید به منبع ایران‌کورال دسترسی ندارد
    if not context:
        context = (
            "منابع ایران‌کورال یافت نشد. اگر پاسخ نیاز به منبع دارد، "
            "صراحتاً بگو که نتیجه‌ای از irancoral.ir پیدا نشد و سؤال تکمیلی بپرس."
        )

    system_instruction = (
        f"{lang_instruction}\n"
        "تو یک کارشناس آکواریوم و ماهی‌های زینتی و فروشگاه ایران‌کورال هستی. "
        "قانون طلایی: فقط و فقط بر اساس اطلاعاتی که از سایت irancoral.ir در «بخش منابع» ارسال می‌شود پاسخ بده. "
        "اگر منابع برای پاسخ کافی نیست، خیلی کوتاه بگو که منابع کافی از ایران‌کورال پیدا نشد و بپرس چه جزئیاتی می‌خواهد. "
        "اگر محصول مناسب در منابع بود، همان را با لینک ایران‌کورال پیشنهاد بده. "
        "از خودت چیزی اضافه نکن، و از منابع غیر ایران‌کورال استفاده نکن."
    )

    prompt = (
        f"{system_instruction}\n\n"
        f"بخش منابع (از irancoral.ir):\n{context}\n\n"
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
        # پاکسازی خیلی سبک (اگر احیاناً فرمت عجیب آمد)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL|re.IGNORECASE).strip()
        if not text:
            return "⚠️ پاسخی تولید نشد. لطفاً سؤال را دقیق‌تر بفرمایید."
        return text
    except Exception as e:
        print("Gemini error:", e)
        return "❌ خطا در اتصال به مدل هوش مصنوعی؛ کمی بعد دوباره تلاش کنید."

# ----------------------------------------------------
# Flask routes
# ----------------------------------------------------
@app.route("/")
def home():
    return "🤖 IranCoral AI assistant is running."

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json() or {}
    msg = data.get("message", {})
    chat_id = msg.get("chat", {}).get("id")
    text = (msg.get("text") or "").strip()

    if not chat_id or not text:
        return "ok"

    reply = get_ai_reply_from_irancoral(text)
    send_telegram(chat_id, reply)
    return "ok"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
