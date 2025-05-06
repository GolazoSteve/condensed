import os
import requests
from bs4 import BeautifulSoup
from flask import Flask, request, abort
from datetime import datetime, timedelta
import logging
import re
import telegram

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Environment variables
AUTH_KEY = os.getenv("AUTH_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_gamepk_for_giants(target_date):
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={target_date}"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    for date_info in data.get("dates", []):
        for game in date_info.get("games", []):
            teams = game.get("teams", {})
            if teams.get("away", {}).get("team", {}).get("name") == "San Francisco Giants" or \
               teams.get("home", {}).get("team", {}).get("name") == "San Francisco Giants":
                return game.get("gamePk")
    return None

def extract_condensed_game_url(html):
    soup = BeautifulSoup(html, 'html.parser')
    scripts = soup.find_all('script')
    for script in scripts:
        if script.string and 'mp4' in script.string:
            matches = re.findall(r'(https:[^\s"']+\.mp4)', script.string)
            for url in matches:
                if 'condensed' in url or 'asset_1280x720_59_4000K.mp4' in url:
                    return url
    return None

def send_to_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        logging.warning("Telegram credentials missing.")
        return
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)

@app.route("/")
def check_highlight():
    key = request.args.get("key")
    if AUTH_KEY and key != AUTH_KEY:
        abort(403)

    target_date = (datetime.utcnow() - timedelta(hours=8)).strftime("%Y-%m-%d")
    logging.info(f"📅 Checking for Giants condensed game on {target_date}")

    game_pk = get_gamepk_for_giants(target_date)
    if not game_pk:
        logging.warning("⚠️ No Giants game found for date.")
        return "No game found."

    video_url = f"https://www.mlb.com/gameday/{game_pk}/video"
    html = requests.get(video_url).text
    video_link = extract_condensed_game_url(html)

    if video_link:
        logging.info(f"✅ Found condensed game: {video_link}")
        send_to_telegram(f"Giants Condensed Game Highlights ({target_date}):\n{video_link}")
        return f"Sent: {video_link}"
    else:
        logging.warning("❌ No condensed game link found on video page.")
        return "No condensed game found."

if __name__ == "__main__":
    app.run(debug=True, port=5000)
