import os
import logging
import requests
from bs4 import BeautifulSoup
from flask import Flask, request
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SECRET_KEY = os.getenv("SECRET_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

app = Flask(__name__)

def get_giants_game_pk(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={date_str}"
    response = requests.get(url)
    data = response.json()
    for date in data.get("dates", []):
        for game in date.get("games", []):
            teams = game.get("teams", {})
            if teams.get("away", {}).get("team", {}).get("name") == "San Francisco Giants" or \
               teams.get("home", {}).get("team", {}).get("name") == "San Francisco Giants":
                return game.get("gamePk")
    return None

def scrape_gameday_video_page(game_pk):
    url = f"https://www.mlb.com/gameday/{game_pk}/video"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.85 Safari/537.36"
    }
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        logger.warning(f"⚠️ Failed to load video page: {url}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    for link in soup.find_all("a", href=True):
        text = link.get_text(" ", strip=True).lower()
        aria = (link.get("aria-label") or "").lower()
        alt = (link.get("alt") or "").lower()
        title = (link.get("title") or "").lower()
        if "condensed game" in text or "condensed game" in aria or "condensed game" in alt or "condensed game" in title:
            href = link["href"]
            full_url = f"https://www.mlb.com{href}" if href.startswith("/") else href
            return full_url

    logger.warning("❌ No condensed game link found on video page.")
    return None

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False,
    }
    response = requests.post(url, json=payload)
    return response.ok

@app.route("/")
def home():
    key = request.args.get("key")
    if key != SECRET_KEY:
        return "Forbidden", 403

    yesterday = datetime.utcnow() - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")
    logger.info(f"📅 Checking for Giants condensed game on {date_str}")

    game_pk = get_giants_game_pk(date_str)
    if not game_pk:
        return "No game found", 200

    condensed_url = scrape_gameday_video_page(game_pk)
    if condensed_url:
        send_telegram_message(f"🎞️ Giants Condensed Game: {condensed_url}")
        return "Posted", 200
    else:
        return "Not found", 200

if __name__ == "__main__":
    app.run(debug=True, port=10000)
