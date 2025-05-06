import os
import requests
import json
import random
import logging
from datetime import datetime, timedelta
from flask import Flask, request
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SECRET_KEY = os.getenv("SECRET_KEY")

POSTED_GAMES_FILE = "posted_games.txt"

with open("copy_bank.json", "r") as f:
    COPY_LINES = json.load(f)["lines"]

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

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
    line = random.choice(COPY_LINES)
    message = (
        f"🎬 <b>{title}</b>\n\n"
        f"Watch the condensed game:\n"
        f"👉 <a href=\"{url}\">{url}</a>\n\n"
        f"<i>{line}</i>"
    )
    res = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
    )
    if res.status_code == 200:
        logging.info("✅ Sent to Telegram.")
    else:
        logging.error(f"❌ Telegram error: {res.text}")

def search_all_video_sections(content, game_id):
    sections = [
        ("media.epg", content.get("media", {}).get("epg", [])),
        ("media.milestones.items", content.get("media", {}).get("milestones", {}).get("items", [])),
        ("media.editorial.recap.mlb.items", content.get("editorial", {}).get("recap", {}).get("mlb", {}).get("items", [])),
        ("highlights.featured.items", content.get("highlights", {}).get("featured", {}).get("items", [])),
    ]

    for section_name, items in sections:
        for item in items:
            title = item.get("title", "").lower()
            keywords = " ".join([kw.get("value", "").lower() for kw in item.get("keywords", [])])
            combined = f"{title} {keywords}"

            logging.info(f"🔍 [{section_name}] Checking video: {title}")

            if "condensed game" in combined:
                playback = item.get("playbacks", [])[0]
                url = playback.get("url")
                if url:
                    logging.info(f"🎯 Found condensed game video in {section_name}")
                    send_telegram_message(item.get("title", "Condensed Game"), url)
                    save_posted_game(game_id)
                    return True
    return False

def fetch_condensed_game():
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    date_str = (now_uk - timedelta(days=1)).strftime("%Y-%m-%d")
    logging.info(f"📅 Checking for Giants condensed game on {date_str}")

    schedule_url = "https://statsapi.mlb.com/api/v1/schedule"
    params = {"teamId": 137, "date": date_str, "sportId": 1}
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

    content_url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/content"
    res = requests.get(content_url)
    if res.status_code != 200:
        logging.error("❌ Failed to fetch game content.")
        return

    content = res.json()
    found = search_all_video_sections(content, game_id)

    if not found:
        logging.info("❌ No condensed game video found in any section.")

@app.route('/')
def home():
    secret_key = request.args.get("key")
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    if secret_key:
        if secret_key == SECRET_KEY:
            logging.info("🔐 Secret override triggered.")
            fetch_condensed_game()
            return "✅ Manual override: Bot ran.\n"
        return "❌ Unauthorized.\n"
    if 6 <= now_uk.hour < 9:
        fetch_condensed_game()
        return "✅ Bot ran during morning window.\n"
    return "⏸️ Outside scan window.\n"

@app.route('/ping')
def ping():
    return "✅ Condensed Game Bot is awake.\n"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
