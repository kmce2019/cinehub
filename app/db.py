"""Simple SQLite database for user ratings.

This module provides helper functions to initialize the ratings table,
insert/update ratings, and fetch existing ratings. Ratings are stored
per-source and key (e.g. "jellyfin"/"12345" or "tmdb"/"movie:6789").
"""

import os
import sqlite3
from pathlib import Path

DB_DIR = Path(os.environ.get("DB_DIR", "/app/data"))
DB_PATH = DB_DIR / "data.db"


def init_db() -> None:
    """Ensure the ratings table exists.

    This function creates the ratings table if it does not already exist.
    The table stores a source string, key string, integer stars (1-5),
    and a timestamp for when the rating was last updated.
    """
    DB_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ratings (
                source TEXT NOT NULL,
                key TEXT NOT NULL,
                stars INTEGER NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source, key)
            )
            """
        )
        con.commit()


def upsert_rating(source: str, key: str, stars: int) -> None:
    """Insert or update a rating.

    :param source: Identifier for the rating source (e.g. "jellyfin", "tmdb").
    :param key: Unique key identifying the rated item within the source.
    :param stars: Integer rating (1-5).
    """
    stars = max(1, min(5, int(stars)))
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            """
            INSERT INTO ratings (source, key, stars) VALUES (?, ?, ?)
            ON CONFLICT(source, key) DO UPDATE SET stars=excluded.stars, updated_at=CURRENT_TIMESTAMP
            """,
            (source, key, stars),
        )
        con.commit()


def get_rating(source: str, key: str) -> int | None:
    """Fetch an existing rating for a source/key.

    :param source: Rating source identifier.
    :param key: Unique key identifying the item.
    :return: Integer rating if present, else None.
    """
    with sqlite3.connect(DB_PATH) as con:
        cur = con.cursor()
        cur.execute(
            "SELECT stars FROM ratings WHERE source=? AND key=?", (source, key)
        )
        row = cur.fetchone()
        return int(row[0]) if row else None