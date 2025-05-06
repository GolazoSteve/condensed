import os
import re
import requests
import logging
from bs4 import BeautifulSoup
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SECRET_KEY = os.getenv("SECRET_KEY", "go_sfg")

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

MLB_VIDEO_URL = "https://www.mlb.com/video"


def fetch_condensed_game():
    logging.info("🔍 Scraping MLB.com/video for condensed game links...")
    response = requests.get(MLB_VIDEO_URL)
    if response.status_code != 200:
        logging.error(f"Failed to fetch MLB.com/video page: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    script_tag = soup.find("script", text=re.compile("__INITIAL_STATE__"))

    if not script_tag:
        logging.warning("⚠️ Could not find initial state script tag.")
        return

    match = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});", script_tag.string, re.DOTALL)
    if not match:
        logging.warning("⚠️ Could not extract JSON from script tag.")
        return

    import json
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        logging.warning("⚠️ Failed to parse JSON from script tag.")
        return

    # Traverse the JSON to find condensed games
    videos = data.get("video", {}).get("results", [])
    for video in videos:
        title = video.get("title", "").lower()
        keywords = video.get("keywords", [])
        if "condensed game" in title and any("giants" in k.lower() for k in keywords):
            playbacks = video.get("playbacks", [])
            for playback in playbacks:
                url = playback.get("url")
                if url and url.endswith("4000K.mp4"):
                    logging.info(f"✅ Found condensed game: {url}")
                    send_telegram_message(url)
                    return

    logging.warning("❌ No Giants condensed game found.")


def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.error("Missing Telegram credentials.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        logging.info("📨 Telegram message sent.")
    else:
        logging.error(f"Telegram error: {response.text}")


@app.route("/")
def home():
    key = request.args.get("key")
    if key != SECRET_KEY:
        return "Forbidden", 403
    fetch_condensed_game()
    return "OK", 200


if __name__ == "__main__":
    app.run(debug=True)
