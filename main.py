import os
import requests
import json
import random
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
print("\U0001F3AC Condensed Game Bot: 6AM UK delivery")

def get_latest_giants_gamepk():
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    start_date = (now_uk - timedelta(days=3)).strftime("%Y-%m-%d")
    end_date = now_uk.strftime("%Y-%m-%d")
    url = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId=137&startDate={start_date}&endDate={end_date}"
    res = requests.get(url)
    if res.status_code != 200:
        logging.error("\u274C Failed to fetch schedule.")
        return None

    dates = res.json().get("dates", [])
    all_games = []
    for date in dates:
        for game in date.get("games", []):
            if game.get("status", {}).get("detailedState") == "Final":
                all_games.append((game["gameDate"], game["gamePk"]))

    if not all_games:
        logging.info("\U0001F6D1 No recent completed Giants games found.")
        return None

    most_recent_game = sorted(all_games, key=lambda x: x[0])[-1]
    logging.info(f"\U0001F9E9 Latest completed gamePk: {most_recent_game[1]}")
    return most_recent_game[1]

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

            logging.info(f"\U0001F3AC Found Condensed Game Video:\nTitle: {video['title']}\nURL: {playback_url}")
            return video["title"], playback_url

    logging.info("No condensed game video found.")
    return None, None

def get_posted_games():
    try:
        with open(POSTED_GAMES_FILE, "r") as f:
            return set(f.read().splitlines())
    except FileNotFoundError:
        return set()

def save_posted_game(game_pk):
    with open(POSTED_GAMES_FILE, "a") as f:
        f.write(f"{game_pk}\n")
    logging.info(f"\U0001F4BE Saved gamePk: {game_pk}")

def send_email(subject, body_html, recipient):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_SENDER  # Visible 'To' field

    part = MIMEText(body_html, "html")
    msg.attach(part)

    bcc_list = [email.strip() for email in recipient.split(",")]

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, bcc_list, msg.as_string())

    logging.info(f"\u2709\ufe0f Sent email to {len(bcc_list)} BCC recipient(s).")

def send_telegram_message(title, url):
    game_info = title.replace("Condensed Game: ", "").strip()
    message_html = (
        f"<b>\U0001F4FC {game_info}</b>\n"
        f"<code>────────────────────────────</code>\n"
        f"\U0001F4FD <a href=\"{url}\">\u25B6 Watch Condensed Game</a>\n\n"
        f"<i>{random.choice(COPY_LINES)}</i>"
    )

    res = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message_html,
            "parse_mode": "HTML",
            "disable_web_page_preview": True
        }
    )
    if res.status_code == 200:
        logging.info("\u2705 Sent to Telegram.")
    else:
        logging.error(f"\u274C Telegram error: {res.text}")

    send_email(
        subject=f"\U0001F4FC {game_info} — Condensed Game",
        body_html=message_html.replace("\n", "<br>"),
        recipient=EMAIL_RECIPIENT
    )

def run_bot(skip_posted_check=False):
    game_pk = get_latest_giants_gamepk()
    if not game_pk:
        logging.info("\U0001F6D1 No Giants game found.")
        return
    if not skip_posted_check:
        posted = get_posted_games()
        if str(game_pk) in posted:
            logging.info("\U0001F6D1 Already posted for this gamePk.")
            return
    title, url = find_condensed_game_video(game_pk)
    if not url:
        logging.info("\U0001F6D1 No condensed video to post.")
        return
    send_telegram_message(title, url)
    if not skip_posted_check:
        save_posted_game(str(game_pk))

app = Flask(__name__)

@app.route('/')
def home():
    now_uk = datetime.now(ZoneInfo("Europe/London"))
    if 6 <= now_uk.hour < 9:
        game_pk = get_latest_giants_gamepk()
        posted = get_posted_games()

        if now_uk.hour == 7 and now_uk.minute == 0 and (not game_pk or str(game_pk) not in posted):
            fallback_message = (
                "\U0001F557 No condensed game posted yet.<br>"
                "Might just be MLB being slow.<br>"
                f"<a href=\"https://your-app.onrender.com/debug?key={SECRET_KEY}\">\U0001F527 Run debug manually</a>"
            )
            send_email("\u2753 Missing Morning Condensed Game", fallback_message, EMAIL_RECIPIENT)
            logging.info("\u26A0\ufe0f Sent 7AM fallback email.")
        else:
            run_bot()
        return "\u2705 Bot checked during 6–9AM window.\n"
    return "\u2705 Bot awake but outside scan window.\n"

@app.route('/ping')
def ping():
    return "\u2705 Condensed Game Bot is alive.\n"

@app.route('/secret')
def secret():
    key = request.args.get("key")
    if key == SECRET_KEY:
        run_bot()
        return "\u2705 Secret triggered bot run.\n"
    return "\u274C Unauthorized.\n"

@app.route('/debug')
def debug():
    key = request.args.get("key")
    if key == SECRET_KEY:
        logging.info("\U0001F6A8 DEBUG MODE: Forcing post regardless of history.")
        run_bot(skip_posted_check=True)
        return "\u2705 Debug run completed (forced post).\n"
    return "\u274C Unauthorized.\n"

@app.route('/log')
def show_log():
    try:
        with open("posted_games.txt", "r") as f:
            content = f.read()
            return f"<pre>{content}</pre>" if content else "\U0001F4C2 Log is empty."
    except FileNotFoundError:
        return "\U0001F4C2 No posted_games.txt yet."

@app.route('/reset')
def reset_log():
    key = request.args.get("key")
    if key == SECRET_KEY:
        try:
            open("posted_games.txt", "w").close()
            logging.info("\U0001F9F9 Log manually cleared via /reset.")
            return "\U0001F9F9 Log reset successfully.\n"
        except Exception as e:
            return f"\u274C Failed to reset log: {e}\n"
    return "\u274C Unauthorized.\n"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)
