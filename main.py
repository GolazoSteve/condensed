import os
import requests
import logging
from bs4 import BeautifulSoup
from flask import Flask, request
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_game_pk(date_str):
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={date_str}"
    resp = requests.get(url)
    data = resp.json()
    games = data["dates"][0]["games"]
    for game in games:
        if game["teams"]["home"]["team"]["name"] == "San Francisco Giants" or \
           game["teams"]["away"]["team"]["name"] == "San Francisco Giants":
            return game["gamePk"]
    return None

def get_condensed_game_link(game_pk):
    url = f"https://www.mlb.com/gameday/{game_pk}/video"
    headers = {"User-Agent": "Mozilla/5.0"}
    resp = requests.get(url, headers=headers)
    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.find_all("a", href=True):
        text = (a.text or "").lower()
        if "condensed game" in text:
            return f'https://www.mlb.com{a["href"]}'
    return None

def send_to_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    return requests.post(url, data=payload)

@app.route("/", methods=["GET"])
def check_highlights():
    if request.args.get("key") != os.getenv("AUTH_KEY"):
        return "Forbidden", 403

    date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    logging.info(f"📅 Checking for Giants condensed game on {date}")

    game_pk = get_game_pk(date)
    if not game_pk:
        logging.warning("❌ No gamePk found for the Giants.")
        return "No game found", 200

    link = get_condensed_game_link(game_pk)
    if link:
        message = f"🎞️ Giants Condensed Game ({date}): {link}"
        send_to_telegram(message)
        logging.info("✅ Condensed game link sent to Telegram.")
        return "Sent to Telegram", 200
    else:
        logging.warning("❌ No condensed game link found on video page.")
        return "No condensed game found", 200

if __name__ == "__main__":
    app.run()
