import os
import requests
from flask import Flask, request
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TRIGGER_KEY = os.getenv("TRIGGER_KEY")

GIANTS_VIDEO_URL = "https://www.mlb.com/giants/video"

def find_condensed_game_url():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(GIANTS_VIDEO_URL, headers=headers)
    if response.status_code != 200:
        print(f"⚠️ Failed to fetch Giants video page: {response.status_code}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.find_all("a", class_="media-card-block")

    found_any = False
    for card in cards:
        title = card.get("aria-label", "") or card.get("title", "")
        href = card.get("href", "")
        if title:
            print(f"🔍 Found video: {title}")
        if "condensed game" in title.lower():
            url = f"https://www.mlb.com{href}" if href.startswith("/") else href
            print(f"🎯 Found condensed game: {title} — {url}")
            return url
        found_any = True

    if not found_any:
        print("❌ No videos found on the page.")
    else:
        print("😅 No condensed game found today.")
    return None

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    response = requests.post(url, data=data)
    return response.status_code == 200

@app.route("/", methods=["GET"])
def index():
    key = request.args.get("key")
    if key != TRIGGER_KEY:
        return "Forbidden", 403

    print("🧼 Scraping Giants video page for condensed game...")
    condensed_url = find_condensed_game_url()
    if not condensed_url:
        return "No condensed game found", 200

    sent = send_telegram_message(f"🎥 Giants Condensed Game:\n{condensed_url}")
    return "Posted to Telegram" if sent else "Failed to post to Telegram", 200

if __name__ == "__main__":
    app.run(debug=True)
