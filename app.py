# app.py

from datetime import datetime

import pandas as pd
import pytz
import streamlit as st

from db import load_posts

# =====================================================
# CONFIG
# =====================================================

POLAND_TZ = pytz.timezone(
    "Europe/Warsaw"
)

st.set_page_config(
    page_title="AskReddit Engagement Monitor",
    layout="wide"
)

# =====================================================
# TIME FORMAT
# =====================================================

def convert_to_poland_time(time_str):

    try:

        utc_dt = datetime.strptime(
            time_str,
            "%a, %d %b %Y %H:%M:%S %Z"
        )

        utc_dt = pytz.utc.localize(
            utc_dt
        )

        poland_dt = utc_dt.astimezone(
            POLAND_TZ
        )

        return poland_dt.strftime(
            "%d/%m/%Y %H:%M:%S"
        )

    except Exception:

        try:

            utc_dt = datetime.fromisoformat(
                time_str.replace(
                    "Z",
                    "+00:00"
                )
            )

            poland_dt = utc_dt.astimezone(
                POLAND_TZ
            )

            return poland_dt.strftime(
                "%d/%m/%Y %H:%M:%S"
            )

        except Exception:
            return time_str

# =====================================================
# LOAD DATA
# =====================================================

rows = load_posts()

df = pd.DataFrame(
    rows,
    columns=[
        "Title",
        "Reddit Link",
        "Posted",
        "Score",
        "Reason",
        "Topic",
        "Fetched At"
    ]
)

if len(df) > 0:

    df["Posted"] = df["Posted"].apply(
        convert_to_poland_time
    )

# =====================================================
# UI
# =====================================================

st.title(
    "🔥 AskReddit Engagement Monitor"
)

st.markdown("""
Monitors AskReddit RSS feed and scores
questions using Gemini Flash Lite.
""")

# =====================================================
# STATS
# =====================================================

col1, col2, col3 = st.columns(3)

with col1:

    st.metric(
        "Total Posts",
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
# TABLE
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
    "🚀 Highest Potential"
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