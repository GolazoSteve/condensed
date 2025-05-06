import os
import logging
import requests
from flask import Flask, request
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re

load_dotenv()
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

app = Flask(__name__)

def get_game_pk(target_date):
    """Fetch Giants gamePk from the MLB stats API."""
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={target_date}"
    res = requests.get(url)
    data = res.json()
    for date in data.get("dates", []):
        for game in date.get("games", []):
            if game.get("teams", {}).get("home", {}).get("team", {}).get("name") == "San Francisco Giants" or \
               game.get("teams", {}).get("away", {}).get("team", {}).get("name") == "San Francisco Giants":
                return game["gamePk"]
    return None

def get_condensed_game_url(game_pk):
    """Scrape the Gameday video page for a condensed game link."""
    url = f"https://www.mlb.com/gameday/{game_pk}/video"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")
    scripts = soup.find_all("script")

    for script in scripts:
        if script.string and ".mp4" in script.string:
            matches = re.findall(r"(https:[^\s\"']+\.mp4)", script.string)
            for match in matches:
                if "condensed" in match:
                    return match
    return None

def send_telegram_message(text):
    """Send a message to Telegram."""
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    response = requests.post(telegram_url, data=payload)
    return response.status_code == 200

@app.route("/")
def home():
    return "Condensed game bot active!"

@app.route("/", methods=["GET"])
def run_bot():
    key = request.args.get("key")
    if key != os.getenv("SECRET_KEY"):
        return "Forbidden", 403

    target_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    logging.info(f"📅 Checking for Giants condensed game on {target_date}")

    game_pk = get_game_pk(target_date)
    if not game_pk:
        logging.warning("❌ No gamePk found for Giants.")
        return "No game found", 200

    url = get_condensed_game_url(game_pk)
    if not url:
        logging.warning("❌ No condensed game link found on video page.")
        return "No condensed game found", 200

    logging.info(f"✅ Condensed game found: {url}")
    sent = send_telegram_message(f"🎞️ Giants Condensed Game ({target_date}):\n{url}")
    return "Posted to Telegram!" if sent else "Failed to send message", 200

if __name__ == "__main__":
    app.run(debug=True)
