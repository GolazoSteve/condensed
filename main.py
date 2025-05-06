import os
import re
import json
import requests
from flask import Flask, request
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TRIGGER_KEY = os.getenv("TRIGGER_KEY")

def get_yesterday_date():
    uk_now = datetime.utcnow() + timedelta(hours=1)
    yesterday = uk_now - timedelta(days=1)
    return yesterday.strftime("%Y-%m-%d")

def get_giants_game_pk(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
    response = requests.get(url)
    if response.status_code != 200:
        return None
    data = response.json()
    for date in data.get("dates", []):
        for game in date.get("games", []):
            teams = game.get("teams", {})
            if teams.get("away", {}).get("team", {}).get("name") == "San Francisco Giants" or \
               teams.get("home", {}).get("team", {}).get("name") == "San Francisco Giants":
                return game.get("gamePk")
    return None

def find_condensed_game_url(game_pk):
    video_page_url = f"https://www.mlb.com/gameday/{game_pk}/video"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(video_page_url, headers=headers)
    if response.status_code != 200:
        print(f"⚠️ Failed to load video page: {video_page_url}")
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")
    for script in scripts:
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "VideoObject":
                title = data.get("name", "").lower()
                if "condensed" in title:
                    print(f"🎯 Found condensed video: {title}")
                    return data.get("contentUrl")
        except (json.JSONDecodeError, TypeError):
            continue

    print("❌ No condensed game video found in JSON.")
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

    date = get_yesterday_date()
    print("📅 Checking for Giants condensed game on", date)
    game_pk = get_giants_game_pk(date)
    if not game_pk:
        print("❌ No Giants game found.")
        return "No Giants game found", 200

    video_url = find_condensed_game_url(game_pk)
    if not video_url:
        return "No condensed game link found", 200

    sent = send_telegram_message(f"🎥 Giants Condensed Game:\n{video_url}")
    return "Posted to Telegram" if sent else "Failed to post to Telegram", 200

if __name__ == "__main__":
    app.run(debug=True)
