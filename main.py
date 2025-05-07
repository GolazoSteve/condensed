import os
import requests
import unicodedata
import json
import random
import logging
from datetime import datetime
from flask import Flask, request
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
SECRET_KEY = os.getenv("SECRET_KEY")

POSTED_VIDEOS_FILE = "posted_videos.txt"
LAST_POSTED_DATE_FILE = "last_posted_date.txt"

# Load copy bank
with open("copy_bank.json", "r") as f:
    copy_data = json.load(f)
    COPY_LINES = copy_data["lines"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
print("🎯 Breakfast Bot: Giants Highlights @ 6AM UK daily")

app = Flask(__name__)

def send_telegram_message(title, url):
    random_line = random.choice(COPY_LINES)
    message = (
        f"📺 <b>{title}</b>\n\n"
        f"Watch now on YouTube:\n"
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

def get_posted_videos():
    try:
        with open(POSTED_VIDEOS_FILE, "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_posted_video(video_id):
    with open(POSTED_VIDEOS_FILE, "a") as f:
        f.write(f"{video_id}\n")
    logging.info(f"💾 Saved video ID: {video_id}")

def get_last_posted_date():
    try:
        with open(LAST_POSTED_DATE_FILE, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None

def save_last_posted_date(date_str):
    with open(LAST_POSTED_DATE_FILE, "w") as f:
        f.write(date_str)
    logging.info(f"💾 Saved posted date: {date_str}")

def fetch_giants_highlights(force=False):
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    today_str = now_uk.strftime("%Y-%m-%d")
    if not force and get_last_posted_date() == today_str:
        logging.info("🛑 Already posted today — skipping YouTube search.")
        return

    posted_videos = get_posted_videos()

    url = "https://www.googleapis.com/youtube/v3/search"
    params = {
        "key": YOUTUBE_API_KEY,
        "channelId": "UCoLrcjPV5PbUrUyXq5mjc_A",
        "part": "snippet",
        "order": "date",
        "maxResults": 25,
        "type": "video"
    }

    res = requests.get(url, params=params)
    logging.info(f"🌐 YouTube API called: {res.url}")
    if res.status_code != 200:
        logging.error("❌ YouTube API failed.")
        return

    data = res.json()
    logging.info("🔍 Checking returned video titles for 'Giants' + 'Highlights':")
    for item in data.get("items", []):
        if item["id"]["kind"] != "youtube#video":
            continue

        title = item["snippet"]["title"]
        clean_title = unicodedata.normalize("NFKD", title).strip().lower()
        logging.info(f"- {title} → {clean_title}")

        if "giants" in clean_title and "highlights" in clean_title:
            video_id = item["id"]["videoId"]
            if not force and video_id in posted_videos:
                logging.info(f"⚪ Already posted video ID: {video_id}")
                continue

            video_url = f"https://www.youtube.com/watch?v={video_id}"
            logging.info("🎯 NEW GIANTS HIGHLIGHT FOUND!")
            send_telegram_message(title, video_url)
            save_posted_video(video_id)
            save_last_posted_date(today_str)
            return
    logging.info("❌ No new Giants highlights found.")

@app.route('/')
def home():
    secret_key = request.args.get('key')
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    current_hour = now_uk.hour

    if secret_key:
        if secret_key == SECRET_KEY:
            fetch_giants_highlights()
            return "✅ Secret key accepted. Bot ran and checked highlights.\n"
        else:
            return "❌ Unauthorized.\n"

    if 6 <= current_hour < 9:
        fetch_giants_highlights()
        return "✅ Breakfast Bot ran successfully (inside window).\n"
    else:
        return "✅ Breakfast Bot awake, but outside scan window.\n"

@app.route('/force')
def force():
    key = request.args.get('key')
    if key != SECRET_KEY:
        return "❌ Unauthorized.\n", 401
    logging.info("🚨 FORCE MODE: Ignoring posted date check.")
    fetch_giants_highlights(force=True)
    return "✅ Force check completed.\n"

@app.route('/ping')
def ping():
    return "✅ Breakfast Bot is awake.\n"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
