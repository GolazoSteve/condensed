import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_game_pk(date_str):
    """Get gamePk for the Giants game on the given date."""
    schedule_url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={date_str}"
    response = requests.get(schedule_url)
    data = response.json()

    for date in data.get("dates", []):
        for game in date.get("games", []):
            if game["teams"]["home"]["team"]["name"] == "San Francisco Giants" or game["teams"]["away"]["team"]["name"] == "San Francisco Giants":
                return game["gamePk"]
    return None

def find_condensed_game_url(game_pk):
    """Scrape the gameday video page and return .mp4 URL if available."""
    url = f"https://www.mlb.com/gameday/{game_pk}/video"
    res = requests.get(url)
    soup = BeautifulSoup(res.text, "html.parser")

    for script in soup.find_all("script"):
        if script.string and ".mp4" in script.string:
            matches = re.findall(r"(https:[^\s\"']+\.mp4)", script.string)
            for match in matches:
                if "condensed" in match.lower():
                    return match
    return None

def send_to_telegram(video_url):
    """Send the video URL to Telegram chat."""
    message = f"📽️ Giants Condensed Game:\n{video_url}"
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    response = requests.post(telegram_url, data=payload)
    return response.ok

@app.route("/", methods=["GET"])
def check_for_highlights():
    key = request.args.get("key")
    if key != os.getenv("KEY"):
        return "Forbidden", 403

    target_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    print(f"📅 Checking for Giants condensed game on {target_date}")

    game_pk = get_game_pk(target_date)
    if not game_pk:
        print("⚠️ No Giants game found for that date.")
        return "No Giants game found", 200

    video_url = find_condensed_game_url(game_pk)
    if not video_url:
        print("❌ No condensed game link found.")
        return "No condensed game found", 200

    sent = send_to_telegram(video_url)
    if sent:
        print("✅ Sent to Telegram!")
        return "Sent to Telegram", 200
    else:
        print("❌ Failed to send to Telegram.")
        return "Failed to send", 500

if __name__ == "__main__":
    app.run()
