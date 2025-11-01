from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

@app.route('/')
def home():
    return "Telegram bot is running!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    if not data or 'message' not in data:
        return 'ok'

    chat_id = data['message']['chat']['id']
    text = data['message'].get('text', '')

    # فقط درباره آکواریوم جواب بده
    if any(word in text for word in ["آکواریوم", "ماهی", "فیلتر", "غذا"]):
        reply = "🐠 بله! بگو ببینم دنبال چی هستی در مورد آکواریوم؟"
    else:
        reply = "من فقط درباره آکواریوم و ماهی پاسخ می‌دم 🙂"

    requests.post(f"{TELEGRAM_API}/sendMessage", json={"chat_id": chat_id, "text": reply})
    return 'ok'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
