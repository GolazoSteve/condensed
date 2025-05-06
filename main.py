import os
import logging
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import Flask, request

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SECRET_KEY = os.getenv("SECRET_KEY", "go_sfg")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
}

def get_giants_game_pk(date):
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={date}"
    response = requests.get(url)
    data = response.json()
    for date_info in data.get("dates", []):
        for game in date_info.get("games", []):
            teams = game.get("teams", {})
            if teams.get("away", {}).get("team", {}).get("name") == "San Francisco Giants" or \
               teams.get("home", {}).get("team", {}).get("name") == "San Francisco Giants":
                return game.get("gamePk")
    return None

def get_condensed_game_url(game_pk):
    url = f"https://www.mlb.com/gameday/{game_pk}/video"
    logging.info(f"🌐 Scraping: {url}")
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, "html.parser")
    scripts = soup.find_all("script")

    for script in scripts:
        if script.string:
            matches = re.findall(r'(https:[^\s"']+\.mp4)', script.string)
            for match in matches:
                logging.info(f"🎞 Found MP4: {match}")
                if "condensed" in match.lower():
                    return match
    return None

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("🚫 Telegram credentials not set")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "disable_web_page_preview": False}
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        logging.info("📣 Telegram message sent")
    except requests.exceptions.RequestException as e:
        logging.error(f"🔥 Telegram send error: {e}")

@app.route("/")
def home():
    key = request.args.get("key")
    if key != SECRET_KEY:
        return "Forbidden", 403

    target_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    logging.info(f"📅 Checking for Giants condensed game on {target_date}")
    game_pk = get_giants_game_pk(target_date)

    if not game_pk:
        logging.warning("❌ No Giants game found on that date")
        return "No game", 200

    video_url = get_condensed_game_url(game_pk)

    if video_url:
        send_telegram_message(f"🎬 Giants condensed game ({target_date}): {video_url}")
    else:
        logging.warning("❌ No condensed game link found on video page.")

    return "Done", 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)
