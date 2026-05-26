# app.py

import time
import json
import sqlite3
from datetime import datetime, timedelta

import feedparser
import pandas as pd
import pytz
import requests
import streamlit as st

# =====================================================
# CONFIG
# =====================================================

RSS_URL = "https://www.reddit.com/r/AskReddit/new/.rss"

DB_NAME = "reddit_posts.db"

REFRESH_SECONDS = 150  # 2.5 minutes

POLAND_TZ = pytz.timezone("Europe/Warsaw")

# =====================================================
# GEMINI CONFIG
# =====================================================

# Add your Gemini API keys here
API_KEYS = [
    "AIzaSyBit0TeESoPhJqVWh0-mWLuvZ9-2wNqfr0",
    "AIzaSyB0wAh8HOvo1_KLDZHjTbLue2FQpjCKfcw",
    "AIzaSyAk-tD-ZqK_CVOxZzXomq4XODzp6XzcQRY",
]

MODEL_NAME = "gemini-2.5-flash-lite"
current_key_index = 0

# =====================================================
# STREAMLIT CONFIG
# =====================================================

st.set_page_config(
    page_title="AskReddit Engagement Monitor",
    layout="wide"
)

# =====================================================
# DATABASE
# =====================================================

conn = sqlite3.connect(
    DB_NAME,
    check_same_thread=False
)

cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS posts (
    post_id TEXT PRIMARY KEY,
    title TEXT,
    url TEXT,
    posted_time TEXT,
    engagement_score INTEGER,
    reasons TEXT,
    category TEXT,
    fetched_at TEXT
)
""")

conn.commit()

# =====================================================
# TIMEZONE
# =====================================================

def convert_to_poland_time(time_str):

    try:

        # Parse ISO format
        utc_dt = datetime.fromisoformat(
            time_str.replace("Z", "+00:00")
        )

        # Convert to Poland timezone
        poland_dt = utc_dt.astimezone(
            POLAND_TZ
        )

        # Format: dd/mm/yyyy hrs:min:sec
        return poland_dt.strftime(
            "%d/%m/%Y %H:%M:%S"
        )

    except Exception:
        return time_str
# =====================================================
# DATABASE HELPERS
# =====================================================

def post_exists(post_id):

    cursor.execute(
        "SELECT 1 FROM posts WHERE post_id=?",
        (post_id,)
    )

    return cursor.fetchone() is not None


def save_post(
    post_id,
    title,
    url,
    posted_time,
    score,
    reasons,
    category
):

    cursor.execute("""
    INSERT INTO posts (
        post_id,
        title,
        url,
        posted_time,
        engagement_score,
        reasons,
        category,
        fetched_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        post_id,
        title,
        url,
        posted_time,
        score,
        reasons,
        category,
        datetime.utcnow().isoformat()
    ))

    conn.commit()


def cleanup_old_posts():

    cutoff_date = (
        datetime.utcnow() - timedelta(days=7)
    ).isoformat()

    cursor.execute("""
    DELETE FROM posts
    WHERE fetched_at < ?
    """, (cutoff_date,))

    deleted = cursor.rowcount

    conn.commit()

    print(f"Deleted {deleted} old posts.")

# =====================================================
# GEMINI KEY ROTATION
# =====================================================

def get_next_api_key():

    global current_key_index

    key = API_KEYS[current_key_index]

    current_key_index = (
        current_key_index + 1
    ) % len(API_KEYS)

    return key

# =====================================================
# GEMINI ANALYSIS
# =====================================================

def analyze_titles_batch(titles):

    prompt = f"""
You are evaluating AskReddit questions.

Analyze each Reddit title for likely engagement and comment volume.

Consider:
- emotional trigger
- curiosity gap
- controversy
- relatability
- storytelling potential
- uniqueness
- broad appeal
- discussion potential

Be critical and selective.
The "category" field must describe the TOPIC of the question.

Possible categories include:
- Relationships
- Confessions
- Psychology
- Social Issues
- Ethics
- Money
- Career
- Nostalgia
- Controversial
- Funny
- Hypothetical
- Fear
- Family
- Dating
- Technology
- Society
- Life Advice
- Human Behavior
- General Discussion

Most AskReddit questions are mediocre.
High scores should be rare.

Scoring: Should be on a scale of 1-100, 1 being least engaging and 100 being the most.

Be concise.
Keep reasons under 20 words.
Return ONLY valid JSON array.

JSON format:

[
  {{
    "title": "",
    "score": 0,
    "category": "",
    "reason": ""
  }}
]

Titles:

{chr(10).join([f"- {t}" for t in titles])}
"""

    for attempt in range(len(API_KEYS)):

        api_key = get_next_api_key()

        url = (
            f"https://generativelanguage.googleapis.com/"
            f"v1beta/models/{MODEL_NAME}:generateContent"
            f"?key={api_key}"
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
                "maxOutputTokens": 700,
                "response_mime_type": "application/json"
            }
        }

        try:

            response = requests.post(
                url,
                json=payload,
                timeout=120
            )

            if response.status_code != 200:

                print(
                    f"API Key Failed: "
                    f"{response.status_code}"
                )

                continue

            result = response.json()

            text = (
                result["candidates"][0]
                ["content"]["parts"][0]["text"]
            )

            parsed = json.loads(text)

            return parsed

        except Exception as e:

            print(
                f"Gemini Error: {e}"
            )

            continue

    return []

# =====================================================
# FETCH POSTS
# =====================================================

def fetch_posts():

    feed = feedparser.parse(RSS_URL)

    new_entries = []

    # =================================================
    # DEDUPLICATION
    # =================================================

    for entry in feed.entries:

        try:

            url = entry.link

            post_id = (
                url.split("/comments/")[1]
                .split("/")[0]
            )

            if post_exists(post_id):
                continue

            new_entries.append({
                "post_id": post_id,
                "title": entry.title,
                "url": url,
                "posted_time": entry.published
            })

        except Exception as e:

            print(
                f"Deduplication Error: {e}"
            )

    # =================================================
    # BATCH ANALYSIS
    # =================================================

    BATCH_SIZE = 5

    all_new_posts = []

    for i in range(
        0,
        len(new_entries),
        BATCH_SIZE
    ):

        batch = new_entries[
            i:i+BATCH_SIZE
        ]

        titles = [
            item["title"]
            for item in batch
        ]

        analyses = analyze_titles_batch(
            titles
        )

        # =================================================
        # SAVE RESULTS
        # =================================================

        for item, analysis in zip(
            batch,
            analyses
        ):

            try:

                score = int(
                    analysis.get(
                        "score",
                        0
                    )
                )

                category = analysis.get(
                    "category",
                    "General"
                )

                reason = analysis.get(
                    "reason",
                    "No reason provided."
                )

                # Safety cap
                score = max(
                    0,
                    min(score, 100)
                )

                save_post(
                    item["post_id"],
                    item["title"],
                    item["url"],
                    item["posted_time"],
                    score,
                    reason,
                    category
                )

                all_new_posts.append({
                    "Title": item["title"],
                    "Score": score,
                    "Category": category,
                    "Posted": convert_to_poland_time(
                        item["posted_time"]
                    ),
                    "Reason": reason,
                    "Reddit Link": item["url"]
                })

            except Exception as e:

                print(
                    f"Save Error: {e}"
                )

    return all_new_posts

# =====================================================
# LOAD POSTS
# =====================================================

def load_posts(limit=100):

    query = f"""
    SELECT
        title,
        url,
        posted_time,
        engagement_score,
        reasons,
        category,
        fetched_at
    FROM posts
    ORDER BY datetime(fetched_at) DESC
    LIMIT {limit}
    """

    df = pd.read_sql_query(
        query,
        conn
    )

    df.columns = [
        "Title",
        "Reddit Link",
        "Posted",
        "Score",
        "Reason",
        "Category",
        "Fetched At"
    ]

    df["Posted"] = df["Posted"].apply(
        convert_to_poland_time
    )

    return df

# =====================================================
# INITIAL FETCH
# =====================================================

cleanup_old_posts()

cursor.execute(
    "SELECT COUNT(*) FROM posts"
)

count = cursor.fetchone()[0]

if count == 0:
    fetch_posts()

# =====================================================
# UI
# =====================================================

st.title(
    "🔥 AskReddit Engagement Monitor"
)

st.markdown("""
Tracks new AskReddit posts and uses
Gemini Flash to estimate engagement
potential.
""")

# =====================================================
# FETCH BUTTON
# =====================================================

col1, col2 = st.columns(2)

with col1:

    if st.button(
        "🔄 Fetch Latest Posts"
    ):

        with st.spinner(
            "Fetching and analyzing..."
        ):

            new_posts = fetch_posts()

        st.success(
            f"Fetched {len(new_posts)} new posts."
        )

with col2:

    st.info(
        f"Auto-refresh every "
        f"{REFRESH_SECONDS // 60} minutes"
    )

# =====================================================
# LOAD DATA
# =====================================================

try:

    df = load_posts()

except Exception as e:

    st.error(
        f"Error loading posts: {e}"
    )

    df = pd.DataFrame(columns=[
        "Title",
        "Reddit Link",
        "Posted",
        "Score",
        "Reason",
        "Category",
        "Fetched At"
    ])

# =====================================================
# MAIN TABLE
# =====================================================

st.subheader(
    "📋 Latest Posts"
)

st.dataframe(
    df,
    use_container_width=True
)

# =====================================================
# TOP POSTS
# =====================================================

st.subheader(
    "🚀 Highest Engagement Potential"
)

if len(df) > 0:

    top_df = df.sort_values(
        by="Score",
        ascending=False
    ).head(10)

    st.dataframe(
        top_df,
        use_container_width=True
    )

# =====================================================
# STATS
# =====================================================

st.subheader("📊 Stats")

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Total Posts Stored",
        len(df)
    )

with col2:

    avg_score = (
        round(df["Score"].mean(), 1)
        if len(df) > 0
        else 0
    )

    st.metric(
        "Average Score",
        avg_score
    )

with col3:

    max_score = (
        df["Score"].max()
        if len(df) > 0
        else 0
    )

    st.metric(
        "Highest Score",
        max_score
    )

# =====================================================
# FOOTER
# =====================================================

st.caption(
    "RSS Source: "
    "https://www.reddit.com/r/AskReddit/new/.rss"
)

# =====================================================
# AUTO REFRESH
# =====================================================

time.sleep(REFRESH_SECONDS)

fetch_posts()

st.rerun()