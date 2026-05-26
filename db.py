# db.py

import sqlite3
from datetime import datetime, timedelta

DB_NAME = "reddit_posts.db"

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
    topic TEXT,
    fetched_at TEXT
)
""")

conn.commit()


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
    topic
):

    cursor.execute("""
    INSERT INTO posts (
        post_id,
        title,
        url,
        posted_time,
        engagement_score,
        reasons,
        topic,
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
        topic,
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

    conn.commit()


def load_posts(limit=100):

    query = f"""
    SELECT
        title,
        url,
        posted_time,
        engagement_score,
        reasons,
        topic,
        fetched_at
    FROM posts
    ORDER BY datetime(fetched_at) DESC
    LIMIT {limit}
    """

    cursor.execute(query)

    rows = cursor.fetchall()

    return rows