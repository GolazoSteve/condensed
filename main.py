import os
import logging
from flask import Flask, request
import requests
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SEARCH_API = "https://search-api.svc.mlb.com/svc/search/v2/mlb_global"
MLB_VIDEO_DOMAIN = "https://www.mlb.com/video/"

posted_ids_file = "posted_video_ids.txt"

def load_posted_ids():
    if not os.path.exists(posted_ids_file):
        return set()
    with open(posted_ids_file, "r") as f:
        return set(line.strip() for line in f.readlines())

def save_posted_id(video_id):
    with open(posted_ids_file, "a") as f:
        f.write(f"{video_id}\n")

def fetch_condensed_game():
    params = {
        "query": "condensed game",
        "size": 25,
        "page": 0,
        "sort": "desc",
        "searchContexts": "mlb-global"
    }

    logging.info("🔍 Searching for recent videos with 'condensed game' in title...")
    try:
        response = requests.get(SEARCH_API, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        docs = data.get("docs", [])

        posted_ids = load_posted_ids()
        logging.info(f"📦 Found {len(docs)} video entries")
        for doc in docs:
            title = doc.get("title", "").lower()
            href = doc.get("url")
            doc_id = doc.get("id")
            logging.info(f"🔎 Title: {title}")

            if "condensed game" in title and doc_id not in posted_ids:
                full_url = f"{MLB_VIDEO_DOMAIN}{href}"
                send_telegram_message(f"🎬 {title.title()}\n{full_url}")
                save_posted_id(doc_id)
                logging.info(f"✅ Sent: {title}")
                return True

        logging.info("❌ No new condensed game video found.")
        return False

    except Exception as e:
        logging.error(f"🔥 Error fetching videos: {e}")
        return False

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False,
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        logging.error(f"Failed to send Telegram message: {e}")

@app.route("/", methods=["GET"])
def home():
    key = request.args.get("key")
    if key == "go_sfg":
        logging.info("🔐 Secret override triggered.")
        fetch_condensed_game()
    return "🎥 Bot is ready.", 200

if __name__ == "__main__":
    app.run(debug=True)
