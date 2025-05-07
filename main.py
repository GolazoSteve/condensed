from flask import Flask, request
import os
import requests
import re
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DEBUG_KEY = os.getenv("DEBUG_KEY", "go_sfg")


def get_recent_giants_game_pk():
    today = datetime.utcnow().date()
    for delta in range(3):
        check_date = today - timedelta(days=delta)
        url = f"https://statsapi.mlb.com/api/v1/schedule?teamId=137&date={check_date}"
        resp = requests.get(url)
        if resp.status_code != 200:
            continue
        data = resp.json()
        games = data.get("dates", [{}])[0].get("games", [])
        for game in games:
            if game.get("status", {}).get("abstractGameCode") == "F":
                return game.get("gamePk")
    return None


def get_condensed_game_url(game_pk):
    video_page_url = f"https://www.mlb.com/gameday/{game_pk}/video"
    resp = requests.get(video_page_url)
    if resp.status_code != 200:
        return None

    match = re.search(r'"playbacks":\s*\[(.*?)\]', resp.text, re.DOTALL)
    if not match:
        return None

    playbacks_raw = match.group(1)
    condensed_match = re.search(
        r'"name":"Condensed Game".*?"url":"(https:[^"]+\.mp4)"', playbacks_raw
    )
    if condensed_match:
        return condensed_match.group(1).replace("\\u002F", "/")
    return None


def post_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "disable_web_page_preview": False,
    }
    resp = requests.post(url, json=payload)
    return resp.ok


@app.route('/')
def index():
    return "MLB Condensed Game Bot is running."


@app.route('/debug')
def debug():
    key = request.args.get("key")
    force_condensed = request.args.get("force_condensed") == "true"

    if key != DEBUG_KEY:
        return "Unauthorized", 403

    if force_condensed:
        logging.info("⚙️ Force-condensed mode triggered via debug endpoint.")
        game_pk = get_recent_giants_game_pk()
        if not game_pk:
            return "No completed Giants games found in the last 3 days.", 200

        video_url = get_condensed_game_url(game_pk)
        if video_url:
            posted = post_to_telegram(f"📽️ Giants Condensed Game:\n{video_url}")
            return "Condensed game posted to Telegram." if posted else "Failed to post.", 200
        return "Condensed game not found for that gamePk.", 200

    return "Debug mode active, but no force_condensed flag provided.", 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
