import os
import logging
import requests
from flask import Flask, request
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MLB_TEAM_ID_SFG = 137  # San Francisco Giants

def get_game_id_for_yesterday(team_id):
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={yesterday}&teamId={team_id}"
    resp = requests.get(url)
    data = resp.json()

    try:
        game_id = data["dates"][0]["games"][0]["gamePk"]
        logging.info(f"✅ Found game ID: {game_id}")
        return game_id
    except (IndexError, KeyError):
        logging.warning("⚠️ No game found for yesterday.")
        return None

def find_condensed_game_url(content_json):
    """Search various sections of the content JSON for a 'condensed game' video URL."""
    sections = [
        content_json.get("media", {}).get("epg", []),
        content_json.get("media", {}).get("milestones", {}).get("items", []),
        content_json.get("media", {}).get("highlights", {}).get("highlights", {}).get("items", [])
    ]

    for section in sections:
        if isinstance(section, list):
            for item in section:
                videos = item.get("items", []) if isinstance(item, dict) else section
                for video in videos:
                    title = video.get("title", "").lower()
                    playback = video.get("playbacks", [])
                    if "condensed game" in title:
                        for pb in playback:
                            if pb.get("name") == "mp4Avc":
                                logging.info(f"🎥 Found condensed game: {video['title']}")
                                return pb["url"]
    return None

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    response = requests.post(url, json=payload)
    logging.info(f"📨 Telegram status: {response.status_code}")

def check_and_post():
    game_id = get_game_id_for_yesterday(MLB_TEAM_ID_SFG)
    if not game_id:
        return "No game ID"

    content_url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/content"
    content = requests.get(content_url).json()

    video_url = find_condensed_game_url(content)
    if video_url:
        send_telegram_message(f"🎬 Giants Condensed Game:\n{video_url}")
        return "Posted condensed game"
    else:
        logging.warning("❌ No condensed game video found in content.")
        return "No video found"

@app.route("/")
def home():
    return "Condensed Game Bot is up."

@app.route("/", methods=["GET"])
def trigger():
    key = request.args.get("key")
    if key == "go_sfg":
        logging.info("🔐 Secret override triggered.")
        return check_and_post()
    return "Condensed Game Bot ready."
