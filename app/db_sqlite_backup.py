from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from typing import Iterator
from app.config import DATABASE_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS leagues (
    league_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT,
    logo_url TEXT,
    season INTEGER,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS teams (
    team_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT,
    logo_url TEXT,
    last_seen_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fixtures (
    fixture_id INTEGER PRIMARY KEY,
    league_id INTEGER NOT NULL,
    season INTEGER,
    round TEXT,
    kickoff_utc TEXT NOT NULL,
    timezone TEXT,
    venue_name TEXT,
    venue_city TEXT,
    referee TEXT,
    status_short TEXT,
    status_long TEXT,
    elapsed INTEGER,
    home_team_id INTEGER NOT NULL,
    away_team_id INTEGER NOT NULL,
    home_goals INTEGER,
    away_goals INTEGER,
    updated_at TEXT NOT NULL,
    raw_file TEXT,
    FOREIGN KEY (league_id) REFERENCES leagues(league_id),
    FOREIGN KEY (home_team_id) REFERENCES teams(team_id),
    FOREIGN KEY (away_team_id) REFERENCES teams(team_id)
);

CREATE INDEX IF NOT EXISTS idx_fixtures_kickoff ON fixtures(kickoff_utc);
CREATE INDEX IF NOT EXISTS idx_fixtures_league ON fixtures(league_id);

CREATE TABLE IF NOT EXISTS collection_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    target_date TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    api_results INTEGER DEFAULT 0,
    fixtures_saved INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT,
    raw_file TEXT
);
"""

@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_database() -> None:
    with connection() as conn:
        conn.executescript(SCHEMA)
