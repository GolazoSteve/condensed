import os
import requests
import json
import random
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import Mimemultipart
from datetime import datetime, timedelta
from flask import Flask, request
from dotenv import load_dotenv
from zoneinfo import ZoneInfo

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SECRET_KEY = os.getenv("SECRET_KEY")
EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

POSTED_GAMES_FILE = "posted_games.txt"

with open("copy_bank.json", "r") as f:
    COPY_LINES = json.load(f)["lines"]

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
print("🎬 Condensed Game Bot: 6AM UK delivery")

def get_latest_giants_gamepk():
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    start_date = (now_uk - timedelta(days=3)).strftime("%Y-%m-%d")
    end_date = now_uk.strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=137&startDate={start_date}&endDate={end_date}"
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

def find_condensed_game_video(game_pk):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_pk}/content"
    response = requests.get(url)
    if response.status_code != 200:
        logging.error(f"Failed to fetch content for gamePk {game_pk}")
        return None, None, None

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

            thumbnail = video.get("image", {}).get("cuts", {}).get("640x360", {}).get("src")

            logging.info(f"🎬 Found Condensed Game Video:\nTitle: {video['title']}\nURL: {playback_url}")
            return video["title"], playback_url, thumbnail

    logging.info("No condensed game video found.")
    return None, None, None

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

def send_email(subject, body_html, recipient):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_SENDER

    part = MIMEText(body_html, "html")
    msg.attach(part)

    bcc_list = [email.strip() for email in recipient.split(",")]

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, bcc_list, msg.as_string())

    logging.info(f"✉️ Sent email to {len(bcc_list)} BCC recipient(s).")

def send_telegram_message(title, url, image):
    game_info = title.replace("Condensed Game: ", "").strip()
    caption_text = (
        f"<b>📼 {game_info}</b>\n"
        f"<code>────────────────────────────</code>\n"
        f"🎥 <a href=\"{url}\">▶ Watch Condensed Game</a>\n\n"
        f"<i>{random.choice(COPY_LINES)}</i>"
    )

    if image:
        res = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": CHAT_ID,
                "photo": image,
                "caption": caption_text,
                "parse_mode": "HTML"
            }
        )
    else:
        res = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": caption_text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
        )

    if res.status_code == 200:
        logging.info("✅ Sent to Telegram.")
    else:
        logging.error(f"❌ Telegram error: {res.text}")

    email_html = (f'<img src="{image}" width="100%" style="border-radius:8px; margin-bottom:12px;"><br>' if image else "") + caption_text.replace("\n", "<br>")
    send_email(f"📼 {game_info} — Condensed Game", email_html, EMAIL_RECIPIENT)

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
    title, url, thumbnail = find_condensed_game_video(game_pk)
    if not url:
        logging.info("🛑 No condensed video to post.")
        return
    send_telegram_message(title, url, thumbnail)
    if not skip_posted_check:
        save_posted_game(str(game_pk))
