import os
import requests
from flask import Flask, request
from datetime import datetime, timedelta
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

def find_video_links(game_pk):
    api_url = f"https://bdfed.stitch.mlbinfra.com/bdfed/milestone/v1/{game_pk}/en"
    response = requests.get(api_url)
    if response.status_code != 200:
        print(f"⚠️ Failed to load video API: {api_url}")
        return []

    data = response.json()
    found = []

    for item in data.get("milestones", []):
        title = item.get("headline", "No title")
        keywords = ", ".join(item.get("keywordsOnMilestone", []))
        playbacks = item.get("playbacks", [])
        mp4s = [p["url"] for p in playbacks if p["url"].endswith(".mp4")]

        if mp4s:
            url = mp4s[0]  # Just grab the first one
            found.append((title, url, keywords))
            print(f"📹 {title} — {keywords}\n🔗 {url}\n")

    return found

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

    videos = find_video_links(game_pk)
    if not videos:
        return "No videos found for this game", 200

    for title, url, keywords in videos:
        if "condensed" in title.lower() or "condensed game" in keywords.lower():
            sent = send_telegram_message(f"🎥 Giants Condensed Game:\n{url}")
            return "Posted to Telegram" if sent else "Failed to post to Telegram", 200

    print("😅 Videos found, but no condensed game.")
    return "No condensed game video found", 200

if __name__ == "__main__":
    app.run(debug=True)
