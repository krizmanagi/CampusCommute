"""SQLite storage for hourly observations."""

import sqlite3
from contextlib import closing

from .synthetic import generate_observations

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    route_id  TEXT    NOT NULL,
    week      INTEGER NOT NULL,
    weekday   INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    hour      INTEGER NOT NULL CHECK (hour BETWEEN 0 AND 23),
    boardings INTEGER NOT NULL CHECK (boardings >= 0),
    PRIMARY KEY (route_id, week, weekday, hour)
);
CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

SYNTHETIC_SOURCE = "Synthetic demo data"


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path):
    """Create tables and seed synthetic data if the database is empty."""
    with closing(connect(path)) as conn:
        conn.executescript(SCHEMA)
        count = conn.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
        if count == 0:
            replace_observations(conn, generate_observations(), SYNTHETIC_SOURCE)


def replace_observations(conn, rows, source):
    """Atomically replace every observation. Rolls back on any error."""
    with conn:  # one transaction: commit on success, rollback on exception
        conn.execute("DELETE FROM observations")
        conn.executemany(
            "INSERT INTO observations (route_id, week, weekday, hour, boardings) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES ('source', ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (source,),
        )


def fetch_observations(conn):
    return [
        tuple(row)
        for row in conn.execute(
            "SELECT route_id, week, weekday, hour, boardings FROM observations "
            "ORDER BY route_id, week, weekday, hour"
        )
    ]


def get_source(conn):
    row = conn.execute("SELECT value FROM metadata WHERE key = 'source'").fetchone()
    return row[0] if row else "Unknown"
