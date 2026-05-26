# view_db.py

import sqlite3
import pandas as pd

DB_NAME = "reddit_posts.db"

# Connect to database
conn = sqlite3.connect(DB_NAME)

# Query all posts
query = """
SELECT
    post_id,
    title,
    url,
    posted_time,
    engagement_score,
    reasons,
    category,
    fetched_at
FROM posts
ORDER BY fetched_at DESC
"""

# Load into dataframe
df = pd.read_sql_query(query, conn)

# Print all rows
print(df.to_string(index=False))

# Close connection
conn.close()
print(df.to_markdown(index=False))