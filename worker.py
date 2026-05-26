# worker.py

import os
import json
import time

import feedparser
import requests

from db import (
    post_exists,
    save_post,
    cleanup_old_posts
)

# =====================================================
# CONFIG
# =====================================================

RSS_URL = "https://www.reddit.com/r/AskReddit/new/.rss"

MODEL_NAME = "gemini-2.0-flash-lite"

API_KEYS = [
    os.getenv("GEMINI_KEY_1"),
    os.getenv("GEMINI_KEY_2"),
    os.getenv("GEMINI_KEY_3"),
]

API_KEYS = [
    key for key in API_KEYS
    if key
]

current_key_index = 0

# =====================================================
# KEY ROTATION
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

Most AskReddit questions are mediocre.
A score above 85 should be extremely rare.

Score meaning:
0-30 = low engagement
30-50 = average engagement
50-70 = good engagement
70-85 = high engagement
85-100 = exceptional viral potential

The "topic" field must describe the TOPIC.

Possible topics:
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

Do NOT use:
- weak
- average
- good
- strong
- exceptional

as topics.

Keep reasons under 20 words.

Return ONLY valid JSON array.

[
  {{
    "title": "",
    "score": 0,
    "topic": "",
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

                print(response.status_code)
                print(response.text)

                time.sleep(5)

                continue

            result = response.json()

            text = (
                result["candidates"][0]
                ["content"]["parts"][0]["text"]
            )

            parsed = json.loads(text)

            return parsed

        except Exception as e:

            print(e)

            time.sleep(5)

            continue

    return []

# =====================================================
# FETCH POSTS
# =====================================================

def fetch_posts():

    feed = feedparser.parse(RSS_URL)

    new_entries = []

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

            print(e)

    BATCH_SIZE = 3

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

        for item, analysis in zip(
            batch,
            analyses
        ):

            try:

                save_post(
                    item["post_id"],
                    item["title"],
                    item["url"],
                    item["posted_time"],
                    int(analysis["score"]),
                    analysis["reason"],
                    analysis["topic"]
                )

            except Exception as e:

                print(e)

# =====================================================
# RUN
# =====================================================

if __name__ == "__main__":

    cleanup_old_posts()

    fetch_posts()

    print("Worker completed.")