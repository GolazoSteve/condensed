import os
import json
import logging
import requests
from datetime import datetime
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
POST_KEY = os.getenv("POST_KEY")  # e.g. go_sfg

HEADERS = {
    "Content-Type": "application/json",
    "Origin": "https://www.mlb.com",
    "Referer": "https://www.mlb.com/",
    "User-Agent": "Mozilla/5.0"
}

SEARCH_URL = "https://search-api.svc.mlb.com/svc/search/v2/mlb_global"


def find_giants_condensed_game():
    logging.info("🎯 Searching MLB API for latest Giants condensed game...")
    payload = {
        "query": {
            "term": {
                "keywords": "giants condensed game"
            }
        },
        "from": 0,
        "size": 10,
        "sort": {
            "startDate": "desc"
        },
        "filters": {
            "language": ["en"]
        }
    }

    try:
        response = requests.post(SEARCH_URL, headers=HEADERS, json=payload)
        response.raise_for_status()
        results = response.json().get("docs", [])

        for doc in results:
            title = doc.get("title", "").lower()
            url = doc.get("url", "")
            if "giants" in title and "condensed game" in title:
                logging.info(f"✅ Found: {title} - {url}")
                return url

        logging.warning("❌ No suitable condensed game found in API results.")
        return None

    except Exception as e:
        logging.error(f"❌ API query failed: {e}")
        return None


def post_to_telegram(video_url):
    message = f"🎬 Giants Condensed Game is live:\n{video_url}"
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "disable_web_page_preview": False
    }

    try:
        res = requests.post(telegram_url, json=payload)
        res.raise_for_status()
        logging.info("📣 Posted to Telegram.")
    except Exception as e:
        logging.error(f"❌ Telegram post failed: {e}")


@app.route("/")
def home():
    secret = request.args.get("key", None)
    if secret and secret == POST_KEY:
        logging.info("🔐 Secret override triggered.")
        run_bot()
        return "✅ Manual check triggered."
    return "👋 Condensed Game Bot is online."


def run_bot():
    logging.info(f"📅 Checking for Giants condensed game on {datetime.utcnow().date()}")
    video_url = find_giants_condensed_game()

    if video_url:
        post_to_telegram(video_url)
    else:
        logging.warning("❌ No video found to post.")


if __name__ == "__main__":
    app.run(debug=False)
