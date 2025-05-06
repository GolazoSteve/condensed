from flask import Flask, request
import requests
import datetime
import os
import logging
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import re
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage

load_dotenv()

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_BCC = os.getenv("EMAIL_BCC", "").split(",")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

POSTED_LOG = "posted_games.txt"
FORCE_DEBUG_KEY = "go_sfg"

MLB_SCHEDULE_URL = "https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=137&date={date}"
MLB_CONTENT_URL = "https://www.mlb.com/gameday/{game_pk}/video"
MLB_VIDEO_API = "https://statsapi.mlb.com/api/v1/game/{game_pk}/content"


# Ensures posted_games.txt exists
def ensure_log():
    if not os.path.exists(POSTED_LOG):
        with open(POSTED_LOG, "w") as f:
            f.write("")


def get_posted_game_pks():
    ensure_log()
    with open(POSTED_LOG, "r") as f:
        return set(line.strip() for line in f.readlines())


def mark_game_posted(game_pk):
    with open(POSTED_LOG, "a") as f:
        f.write(f"{game_pk}\n")


def get_latest_game_pk():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    url = MLB_SCHEDULE_URL.format(date=today)
    response = requests.get(url)
    if response.status_code != 200:
        logging.warning("Failed to fetch schedule")
        return None

    data = response.json()
    games = data.get("dates", [{}])[0].get("games", [])
    for game in reversed(games):
        if game.get("status", {}).get("detailedState") == "Final":
            return game.get("gamePk")
    return None


def find_condensed_game_video(game_pk):
    url = MLB_VIDEO_API.format(game_pk=game_pk)
    response = requests.get(url)
    if response.status_code != 200:
        logging.warning(f"Failed to fetch content for gamePk {game_pk}")
        return None, None, None

    data = response.json()
    videos = data.get("highlights", {}).get("highlights", {}).get("items", [])

    for video in videos:
        title = video.get("title", "").lower()
        description = video.get("description", "").lower()

        if "condensed" in title or "condensed" in description:
            playback_url = None
            thumbnail_url = video.get("image", {}).get("cuts", {}).get("1280x720", {}).get("src")

            for playback in video.get("playbacks", []):
                if "mp4" in playback.get("name", "").lower():
                    playback_url = playback.get("url")
                    break

            if not playback_url:
                playback_url = f"https://www.mlb.com{video.get('url', '')}"

            title_clean = video['title'].replace("Condensed Game: ", "📼 ")
            return title_clean, playback_url, thumbnail_url

    return None, None, None


def send_telegram_message(title, url, thumb=None):
    caption = f"{title}\n────────────────────────────\n🎥 ▶ <a href=\"{url}\">Watch Condensed Game</a>\n\n<em>Every outfield assist feels fresher before 9 a.m.</em>"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "photo": thumb if thumb else "https://upload.wikimedia.org/wikipedia/en/5/59/San_Francisco_Giants_Logo.svg",
        "caption": caption,
        "parse_mode": "HTML"
    }
    response = requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto", data=payload)
    if response.status_code == 200:
        logging.info("✅ Sent to Telegram.")
    else:
        logging.error(f"❌ Telegram error: {response.text}")


def send_email(subject, body, image_url=None):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_SENDER
    msg['Bcc'] = ",".join(EMAIL_BCC)
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    if image_url:
        img_data = requests.get(image_url).content
        image = MIMEImage(img_data)
        image.add_header('Content-ID', '<thumbnail>')
        msg.attach(image)

    with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        logging.info("📧 Email sent.")


def run_bot(skip_posted_check=False):
    now = datetime.datetime.now()
    if not (6 <= now.hour < 9):
        logging.info("⏱️ Outside 6-9am window.")
        return

    game_pk = get_latest_game_pk()
    if not game_pk:
        logging.warning("No completed game found.")
        return

    logging.info(f"🧩 Latest completed gamePk: {game_pk}")

    if not skip_posted_check and str(game_pk) in get_posted_game_pks():
        logging.info("📭 Already posted.")
        return

    title, url, thumb = find_condensed_game_video(game_pk)
    if url:
        logging.info(f"🎬 Found Condensed Game Video:\nTitle: {title}\nURL: {url}")
        send_telegram_message(title, url, thumb)
        send_email(title, f"Watch here: {url}", thumb)
        mark_game_posted(game_pk)
    else:
        logging.info("No condensed game video found.")


@app.route("/")
def home():
    return "Condensed Bot Active"


@app.route("/ping")
def ping():
    return "pong"


@app.route("/debug")
def debug():
    if request.args.get("key") != FORCE_DEBUG_KEY:
        return "Unauthorized", 403
    logging.info("🚨 DEBUG MODE: Forcing post regardless of history.")
    run_bot(skip_posted_check=True)
    return "Triggered"


@app.route("/check")
def check():
    now = datetime.datetime.now()
    if now.hour == 7:
        posted = get_posted_game_pks()
        latest = get_latest_game_pk()
        if latest and str(latest) not in posted:
            link = f"https://condensed.onrender.com/debug?key={FORCE_DEBUG_KEY}"
            fallback_msg = ("⏰ It's 7AM and there's no condensed game yet.\n"
                            f"You can try manually here: {link}")
            send_telegram_message("Manual Check", link)
            send_email("No condensed game yet", fallback_msg)
    return "Checked"


if __name__ == "__main__":
    app.run(debug=True)
