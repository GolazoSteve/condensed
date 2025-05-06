import os
import requests
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TRIGGER_KEY = os.getenv("TRIGGER_KEY")

GRAPHQL_URL = "https://www.mlb.com/api/graphql"

# Raw GraphQL query string
GRAPHQL_QUERY = """
query VideoSearch($query: String!, $page: Int!, $pageSize: Int!, $sortOrder: String!, $filters: VideoSearchFilters) {
  videos(query: $query, page: $page, pageSize: $pageSize, sortOrder: $sortOrder, filters: $filters) {
    results {
      title
      slug
      keywords
    }
  }
}
"""

def find_condensed_game_video():
    payload = {
        "operationName": "VideoSearch",
        "query": GRAPHQL_QUERY,
        "variables": {
            "query": "giants condensed",
            "page": 1,
            "pageSize": 25,
            "sortOrder": "desc",
            "filters": {
                "team_id": "137"  # San Francisco Giants team ID
            }
        }
    }

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }

    response = requests.post(GRAPHQL_URL, json=payload, headers=headers)

    if response.status_code != 200:
        print(f"❌ GraphQL request failed: {response.status_code}")
        return None

    data = response.json()
    videos = data.get("data", {}).get("videos", {}).get("results", [])

    if not videos:
        print("😐 No videos returned by GraphQL.")
        return None

    for vid in videos:
        title = vid.get("title", "")
        slug = vid.get("slug", "")
        keywords = ", ".join(vid.get("keywords", []))
        print(f"📹 {title} — {keywords}")
        if "condensed" in title.lower() or "condensed" in keywords.lower():
            url = f"https://www.mlb.com/video/{slug}"
            print(f"🎯 Found condensed game: {title} — {url}")
            return url

    print("😅 No condensed game found in video search.")
    return None

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    response = requests.post(url, data=data)
    return response.status_code == 200

@app.route("/", methods=["GET"])
def index():
    key = request.args.get("key")
    if key != TRIGGER_KEY:
        return "Forbidden", 403

    print("🧼 Searching Giants videos via raw GraphQL POST...")
    video_url = find_condensed_game_video()
    if not video_url:
        return "No condensed game found", 200

    sent = send_telegram_message(f"🎥 Giants Condensed Game:\n{video_url}")
    return "Posted to Telegram" if sent else "Failed to post to Telegram", 200

if __name__ == "__main__":
    app.run(debug=True)
