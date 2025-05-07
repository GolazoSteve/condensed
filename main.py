import os 
import requests
import logging
import datetime
import smtplib
from flask import Flask, request
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# --- Config ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_BCC = os.getenv("EMAIL_BCC", "").split(",")
BOT_KEY = os.getenv("BOT_KEY") or "go_sfg"
POSTED_FILE = "posted_games.txt"

# --- Flask App ---
app = Flask(__name__)

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- Helper Functions ---
def get_latest_game_pk():
    today = datetime.date.today().isoformat()
    url = f"https://statsapi.mlb.com/api/v1/schedule/games/?sportId=1&date={today}"
    response = requests.get(url)
    if response.status_code != 200:
        logging.error("Failed to fetch schedule data")
        return None
    games = response.json().get("dates", [])[0].get("games", [])
    if not games:
        logging.info("No games found for today")
        return None
    completed_games = [g for g in games if g.get("status", {}).get("detailedState") == "Final"]
    if not completed_games:
        logging.info("No completed games yet")
        return None
    return completed_games[-1].get("gamePk")

def find_condensed_game_video(game_pk):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/content"
    response = requests.get(url)
    if response.status_code != 200:
        logging.error("Failed to fetch content for gamePk %s", game_pk)
        return None, None
    data = response.json()
    videos = data.get("highlights", {}).get("highlights", {}).get("items", [])
    for video in videos:
        title = video.get("title", "").lower()
        description = video.get("description", "").lower()
        if "condensed" in title or "condensed" in description:
            for playback in video.get("playbacks", []):
                if "1280x720" in playback.get("url", ""):
                    return video.get("title"), playback.get("url")
    return None, None

def has_been_posted(game_pk):
    if not os.path.exists(POSTED_FILE):
        return False
    with open(POSTED_FILE, "r") as f:
        return str(game_pk) in f.read()

def mark_as_posted(game_pk):
    with open(POSTED_FILE, "a") as f:
        f.write(f"{game_pk}\n")

def send_telegram_message(title, video_url):
    caption = (
        f"📼 {title.replace('Condensed Game: ', '')}\n"
        + "─" * 28 + "\n"
        + "🎥 ▶ Watch Condensed Game\n"
        + f"{video_url}\n\n"
        + "Every outfield assist feels fresher before 8 a.m."
    )
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": caption,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(endpoint, data=payload)
    if not response.ok:
        logging.error("Telegram error: %s", response.text)
    else:
        logging.info("✅ Sent to Telegram.")

def send_email(subject, video_url):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_SENDER
    msg['Subject'] = subject
    if EMAIL_BCC:
        msg['Bcc'] = ", ".join(EMAIL_BCC)
    body = f"<h2>{subject}</h2><p><a href=\"{video_url}\">Watch the condensed game</a></p>"
    msg.attach(MIMEText(body, 'html'))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        logging.info("📧 Email sent.")

def run_bot(skip_posted_check=False, skip_time_check=False):
    now = datetime.datetime.now()
    if not (6 <= now.hour < 9):
        if not skip_time_check:
            logging.info("⏱️ Outside 6-9am window.")
            return
        else:
            logging.info("⏱️ Time window override active (debug mode).")

    game_pk = get_latest_game_pk()
    if not game_pk:
        return
    logging.info("🧩 Latest completed gamePk: %s", game_pk)
    if not skip_posted_check and has_been_posted(game_pk):
        logging.info("📂 Already posted for this game.")
        return

    title, video_url = find_condensed_game_video(game_pk)
    if not video_url:
        logging.info("❌ No condensed game video found.")
        return

    logging.info("🎬 Found Condensed Game Video:\nTitle: %s\nURL: %s", title, video_url)
    send_telegram_message(title, video_url)
    send_email(title, video_url)
    mark_as_posted(game_pk)

# --- Routes ---
@app.route("/")
def home():
    return "Condensed Game Bot running!"

@app.route("/debug")
def debug():
    key = request.args.get("key")
    if key != BOT_KEY:
        return "Forbidden", 403
    logging.info("🚨 DEBUG MODE: Forcing post regardless of history.")
    run_bot(skip_posted_check=True, skip_time_check=True)
    return "Debug run complete."

@app.route("/reset")
def reset():
    key = request.args.get("reset")
    if key != BOT_KEY:
        return "Forbidden", 403
    if os.path.exists(POSTED_FILE):
        os.remove(POSTED_FILE)
    return "posted_games.txt reset."

@app.route("/ping")
def ping():
    return "OK"
