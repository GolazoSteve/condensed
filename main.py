import os
import requests
import logging
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SECRET_KEY = os.getenv("SECRET_KEY")

MLB_STATS_API = "https://statsapi.mlb.com/api/v1/schedule"
MLB_VIDEO_PAGE = "https://www.mlb.com/gameday/{gamePk}/video"

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)


def get_giants_gamepk(date_str):
    params = {
        "sportId": 1,
        "date": date_str,
        "teamId": 137,  # Giants team ID
    }
    res = requests.get(MLB_STATS_API, params=params)
    res.raise_for_status()
    data = res.json()
    dates = data.get("dates", [])
    if not dates:
        return None
    games = dates[0].get("games", [])
    if not games:
        return None
    return games[0].get("gamePk")


def find_condensed_game_url(gamePk):
    url = MLB_VIDEO_PAGE.format(gamePk=gamePk)
    res = requests.get(url)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")
    for a in soup.find_all("a", href=True):
        text = a.get_text().lower()
        alt = a.get("aria-label", "").lower()
        if "condensed game" in text or "condensed game" in alt:
            return "https://www.mlb.com" + a["href"]
    return None


def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    res = requests.post(url, json=payload)
    res.raise_for_status()


@app.route("/")
def home():
    key = request.args.get("key")
    if key != SECRET_KEY:
        return "Access denied", 403

    today = datetime.utcnow().date() - timedelta(days=1)
    date_str = today.strftime("%Y-%m-%d")
    logging.info(f"📅 Checking for Giants condensed game on {date_str}")

    try:
        gamePk = get_giants_gamepk(date_str)
        if not gamePk:
            logging.warning("❌ No gamePk found for Giants on that date.")
            return "No game found", 200

        video_url = find_condensed_game_url(gamePk)
        if video_url:
            logging.info(f"✅ Found condensed game: {video_url}")
            send_telegram_message(f"🎬 Giants condensed game ({date_str}): {video_url}")
            return "Posted to Telegram", 200
        else:
            logging.warning("❌ No condensed game link found on video page.")
            return "No condensed game video found", 200

    except Exception as e:
        logging.exception("🔥 Error during condensed game lookup")
        return "Error occurred", 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
