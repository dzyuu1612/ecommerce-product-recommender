"""SQLite schema and connection helpers.

SQLite stands in for the operational Postgres database in the full-scale
architecture: it is the single source of truth for the catalog, users, and
the raw behavior-event stream that everything downstream is built from.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

DEFAULT_DB_PATH = Path(__file__).resolve().parents[2] / "data" / "recsys_lite.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS products (
    item_id      INTEGER PRIMARY KEY,
    title        TEXT NOT NULL,
    category_id  INTEGER NOT NULL,
    brand_id     INTEGER NOT NULL,
    price        REAL NOT NULL,
    price_bucket INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS events (
    event_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    item_id    INTEGER NOT NULL,
    event_type INTEGER NOT NULL,
    ts         INTEGER NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (user_id),
    FOREIGN KEY (item_id) REFERENCES products (item_id)
);

CREATE INDEX IF NOT EXISTS idx_events_user_ts ON events (user_id, ts);
CREATE INDEX IF NOT EXISTS idx_events_item ON events (item_id);
"""


def connect(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def reset_db(db_path: Path | str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Drop and recreate every table. Used by the generator CLI for a clean run."""
    conn = connect(db_path)
    conn.executescript(
        "DROP TABLE IF EXISTS events; "
        "DROP TABLE IF EXISTS products; "
        "DROP TABLE IF EXISTS users;"
    )
    init_db(conn)
    return conn


@contextmanager
def session(db_path: Path | str = DEFAULT_DB_PATH):
    conn = connect(db_path)
    try:
        init_db(conn)
        yield conn
    finally:
        conn.close()
