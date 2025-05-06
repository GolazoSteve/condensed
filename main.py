import os
import requests
import json
import random
import logging
from datetime import datetime, timedelta
from flask import Flask, request
from dotenv import load_dotenv
from zoneinfo import ZoneInfo  # Clean timezone handling

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SECRET_KEY = os.getenv("SECRET_KEY")

POSTED_GAMES_FILE = "posted_games.txt"

# Load witty copy lines
with open("copy_bank.json", "r") as f:
    copy_data = json.load(f)
    COPY_LINES = copy_data["lines"]

# Flask app
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
print("🎬 Condensed Game Bot: Running...")

def get_posted_games():
    try:
        with open(POSTED_GAMES_FILE, "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_posted_game(game_id):
    with open(POSTED_GAMES_FILE, "a") as f:
        f.write(f"{game_id}\n")
    logging.info(f"💾 Saved game ID: {game_id}")

def send_telegram_message(title, url):
    random_line = random.choice(COPY_LINES)
    message = (
        f"🎬 <b>{title}</b>\n\n"
        f"Watch the condensed game:\n"
        f"👉 <a href=\"{url}\">{url}</a>\n\n"
        f"<i>{random_line}</i>"
    )
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    res = requests.post(api_url, data=payload)
    if res.status_code == 200:
        logging.info("✅ Sent to Telegram.")
    else:
        logging.error(f"❌ Telegram error: {res.text}")

def fetch_condensed_game():
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    yesterday = now_uk - timedelta(days=1)
    date_str = yesterday.strftime("%Y-%m-%d")

    logging.info(f"📅 Checking for Giants condensed game on {date_str}")

    # Step 1: Get Giants schedule for yesterday
    schedule_url = f"https://statsapi.mlb.com/api/v1/schedule"
    params = {
        "teamId": 137,  # Giants
        "date": date_str,
        "sportId": 1
    }
    res = requests.get(schedule_url, params=params)
    if res.status_code != 200:
        logging.error("❌ Failed to fetch schedule.")
        return

    games = res.json().get("dates", [])
    if not games:
        logging.info("🛑 No games found for yesterday.")
        return

    game = games[0]["games"][0]
    game_id = str(game["gamePk"])

    if game_id in get_posted_games():
        logging.info(f"⚪ Already posted for game ID: {game_id}")
        return

    # Step 2: Fetch media content for the game
    content_url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/content"
    res = requests.get(content_url)
    if res.status_code != 200:
        logging.error("❌ Failed to fetch game content.")
        return

    items = res.json().get("media", {}).get("epg", [])
    for section in items:
        if section.get("title", "").lower() == "condensed game":
            videos = section.get("items", [])
            if videos:
                video = videos[0]
                title = video.get("title", "Condensed Game")
                url = video.get("playbacks", [])[0].get("url")
                if url:
                    send_telegram_message(title, url)
                    save_posted_game(game_id)
                    return

    logging.info("❌ No condensed game video found in media/epg data for this game.")
logging.debug(json.dumps(items, indent=2))  # <-- Optional: logs the raw EPG structure


@app.route('/')
def home():
    secret_key = request.args.get("key")
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    current_hour = now_uk.hour

    if secret_key:
        if secret_key == SECRET_KEY:
            logging.info("🔐 Secret override triggered.")
            fetch_condensed_game()
            return "✅ Manual override: Bot ran.\n"
        else:
            return "❌ Unauthorized.\n"

    # Cron-based daily run
    if 6 <= current_hour < 9:
        fetch_condensed_game()
        return "✅ Bot ran during morning window.\n"
    else:
        return "⏸️ Outside scan window.\n"

@app.route('/ping')
def ping():
    return "✅ Condensed Game Bot is awake.\n"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
