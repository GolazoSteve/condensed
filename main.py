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

def extract_preloaded_state(html):
    soup = BeautifulSoup(html, "html.parser")
    script_tags = soup.find_all("script")

    for tag in script_tags:
        if tag.string and "window.__PRELOADED_STATE__" in tag.string:
            try:
                match = re.search(r"window\.__PRELOADED_STATE__\s*=\s*(\{.*\});", tag.string, re.DOTALL)
                if match:
                    json_text = match.group(1)
                    return json.loads(json_text)
            except Exception as e:
                print(f"❌ Failed to parse PRELOADED_STATE: {e}")
    return None

def find_condensed_game_url(game_pk):
    video_page_url = f"https://www.mlb.com/gameday/{game_pk}/video"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(video_page_url, headers=headers)
    if response.status_code != 200:
        print(f"⚠️ Failed to load video page: {video_page_url}")
        return None

    state = extract_preloaded_state(response.text)
    if not state:
        print("❌ No PRELOADED_STATE found.")
        return None

    media_items = state.get("mediaPlayback", {}).get("items", [])
    for item in media_items:
        title = item.get("title", "").lower()
        playback_url = item.get("playbacks", [{}])[0].get("url", "")
        if "condensed" in title and playback_url:
            print(f"🎯 Found condensed game: {title}")
            return playback_url

    print("😅 No condensed game video found in PRELOADED_STATE.")
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
