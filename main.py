import os
import requests
import logging
from flask import Flask, request, abort
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

MLB_API_BASE = "https://statsapi.mlb.com/api/v1"
TEAM_ID = 137  # Giants

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
DEBUG_KEY = os.getenv("DEBUG_KEY", "go_sfg")

def get_schedule(date_str):
    url = f"{MLB_API_BASE}/schedule?sportId=1&date={date_str}"
    resp = requests.get(url)
    if not resp.ok:
        return []
    return resp.json().get("dates", [])[0].get("games", [])

def get_game_video_page(game_pk):
    return f"https://www.mlb.com/gameday/{game_pk}/video"

def find_condensed_game_url(game_pk):
    video_page = get_game_video_page(game_pk)
    resp = requests.get(video_page)
    if not resp.ok:
        return None, None
    soup = BeautifulSoup(resp.text, "html.parser")
    for script in soup.find_all("script"):
        if "Condensed Game" in script.text and ".mp4" in script.text:
            text = script.text
            title_start = text.find("Condensed Game")
            title = text[title_start:text.find('"', title_start)]
            start = text.find("https://", text.find(".mp4") - 300)
            end = text.find(".mp4", start) + 4
            url = text[start:end]
            return title, url
    return None, None

def send_email(subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECEIVER
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        logging.info("📧 Email sent.")
    except Exception as e:
        logging.error(f"Email error: {e}")

def send_telegram(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    response = requests.post(url, json=payload)
    if not response.ok:
        logging.error(f"Telegram error: {response.text}")

def find_latest_game_with_video(force_any_team=False):
    today = datetime.now()
    for delta in range(0, 5):
        date_str = (today - timedelta(days=delta)).strftime("%Y-%m-%d")
        games = get_schedule(date_str)
        if not games:
            continue
        for game in reversed(games):  # Check latest first
            if not force_any_team and game.get("teams", {}).get("away", {}).get("team", {}).get("id") != TEAM_ID \
               and game.get("teams", {}).get("home", {}).get("team", {}).get("id") != TEAM_ID:
                continue
            game_pk = game.get("gamePk")
            title, video_url = find_condensed_game_url(game_pk)
            if title and video_url:
                logging.info(f"🎬 Found Condensed Game Video:\nTitle: {title}\nURL: {video_url}")
                return title, video_url
    logging.info("❌ No condensed game found for any game.")
    return None, None

def run_bot(force_all=False):
    logging.info("🚨 FORCE MODE: Ignoring posted date check." if force_all else "🧪 DEBUG MODE: Forcing post regardless of history.")
    title, video_url = find_latest_game_with_video(force_any_team=force_all)
    if title and video_url:
        send_telegram(f"{title}\n{video_url}")
        send_email(title, video_url)
    else:
        logging.info("No suitable condensed video found.")

@app.route("/")
def root():
    if request.args.get("reset") == DEBUG_KEY:
        return "🔁 Reset received", 200
    return "🎯 Breakfast Bot: Giants Highlights @ 6AM UK daily", 200

@app.route("/ping")
def ping():
    return "", 200

@app.route("/debug")
def debug():
    if request.args.get("key") != DEBUG_KEY:
        abort(403)
    run_bot(force_all=False)
    return "✅ Debug complete", 200

@app.route("/force")
def force():
    if request.args.get("key") != DEBUG_KEY:
        abort(403)
    run_bot(force_all=True)
    return "✅ Forced post complete", 200

if __name__ == "__main__":
    app.run(debug=True, port=5000)
