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
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SECRET_KEY = os.getenv("SECRET_KEY")

# File to track posted games
POSTED_GAMES_FILE = "posted_games.txt"

# Load copy bank
with open("copy_bank.json", "r") as f:
    COPY_LINES = json.load(f)["lines"]

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
print("🎬 Condensed Game Bot: 6AM UK delivery")

# 🔍 Find most recent completed Giants gamePk
def get_latest_giants_gamepk():
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    start_date = (now_uk - timedelta(days=3)).strftime("%Y-%m-%d")
    end_date = now_uk.strftime("%Y-%m-%d")

    url = (
        f"https://statsapi.mlb.com/api/v1/schedule"
        f"?sportId=1&teamId=137&startDate={start_date}&endDate={end_date}"
    )
    res = requests.get(url)
    if res.status_code != 200:
        logging.error("❌ Failed to fetch schedule.")
        return None

    dates = res.json().get("dates", [])
    all_games = []
    for date in dates:
        for game in date.get("games", []):
            if game.get("status", {}).get("detailedState") == "Final":
                all_games.append((game["gameDate"], game["gamePk"]))

    if not all_games:
        logging.info("🛑 No recent completed Giants games found.")
        return None

    most_recent_game = sorted(all_games, key=lambda x: x[0])[-1]
    logging.info(f"🧩 Latest completed gamePk: {most_recent_game[1]}")
    return most_recent_game[1]

# 🎥 Find condensed game video
def find_condensed_game_video(game_pk):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/content"
    response = requests.get(url)
    if response.status_code != 200:
        logging.error(f"Failed to fetch content for gamePk {game_pk}")
        return None, None

    data = response.json()
    videos = data.get("highlights", {}).get("highlights", {}).get("items", [])

    for video in videos:
        title = video.get("title", "").lower()
        description = video.get("description", "").lower()

        if "condensed" in title or "condensed" in description:
            playback_url = None

            for playback in video.get("playbacks", []):
                if "mp4" in playback.get("name", "").lower():
                    playback_url = playback.get("url")
                    break

            if not playback_url:
                playback_url = f"https://www.mlb.com{video.get('url', '')}"

            logging.info(f"🎬 Found Condensed Game Video:\nTitle: {video['title']}\nURL: {playback_url}")
            return video["title"], playback_url

    logging.info("No condensed game video found.")
    return None, None

# 🧠 Post tracker
def get_posted_games():
    try:
        with open(POSTED_GAMES_FILE, "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_posted_game(game_pk):
    with open(POSTED_GAMES_FILE, "a") as f:
        f.write(f"{game_pk}\n")
    logging.info(f"💾 Saved gamePk: {game_pk}")

# 🚀 Send to Telegram
def send_telegram_message(title, url):
    if title.lower().startswith("condensed game: "):
        game_info = title[17:].strip()
    else:
        game_info = title.strip()

    message = (
        f"<b>📼 {game_info}</b>\n"
        f"<code>────────────────────────────</code>\n"
        f"🎥 <a href=\"{url}\">▶ Watch Condensed Game</a>\n\n"
        f"<i>{random.choice(COPY_LINES)}</i>"
    )

    res = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
    )

    if res.status_code == 200:
        logging.info("✅ Sent to Telegram.")
    else:
        logging.error(f"❌ Telegram error: {res.text}")

# 🍽 Main function
def run_bot(skip_posted_check=False):
    game_pk = get_latest_giants_gamepk()
    if not game_pk:
        logging.info("🛑 No Giants game found.")
        return

    if not skip_posted_check:
        posted = get_posted_games()
        if str(game_pk) in posted:
            logging.info("🛑 Already posted for this gamePk.")
            return

    title, url = find_condensed_game_video(game_pk)
    if not url:
        logging.info("🛑 No condensed video to post.")
        return

    send_telegram_message(title, url)

    if not skip_posted_check:
        save_posted_game(str(game_pk))

# 🧭 Flask app
app = Flask(__name__)

@app.route('/')
def home():
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    if 6 <= now_uk.hour < 9:
        run_bot()
        return "✅ Bot ran during 6–9AM window.\n"
    return "✅ Bot awake but outside scan window.\n"

@app.route('/ping')
def ping():
    return "✅ Condensed Game Bot is alive.\n"

@app.route('/secret')
def secret():
    key = request.args.get("key")
    if key == SECRET_KEY:
        run_bot()
        return "✅ Secret triggered bot run.\n"
    return "❌ Unauthorized.\n"

@app.route('/debug')
def debug():
    key = request.args.get("key")
    if key == SECRET_KEY:
        logging.info("🚨 DEBUG MODE: Forcing post regardless of history.")
        run_bot(skip_posted_check=True)
        return "✅ Debug run completed (forced post).\n"
    return "❌ Unauthorized.\n"

@app.route('/log')
def show_log():
    try:
        with open("posted_games.txt", "r") as f:
            content = f.read()
            return f"<pre>{content}</pre>" if content else "📂 Log is empty."
    except FileNotFoundError:
        return "📂 No posted_games.txt yet."

@app.route('/reset')
def reset_log():
    key = request.args.get("key")
    if key == SECRET_KEY:
        try:
            open("posted_games.txt", "w").close()
            logging.info("🧹 Log manually cleared via /reset.")
            return "🧹 Log reset successfully.\n"
        except Exception as e:
            return f"❌ Failed to reset log: {e}\n"
    return "❌ Unauthorized.\n"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
