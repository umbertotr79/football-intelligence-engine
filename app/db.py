from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from app.config import DATABASE_PATH

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

SQLITE_SCHEMA = """
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
    raw_file TEXT
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

POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS leagues (
    league_id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    country TEXT,
    logo_url TEXT,
    season INTEGER,
    last_seen_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS teams (
    team_id BIGINT PRIMARY KEY,
    name TEXT NOT NULL,
    code TEXT,
    logo_url TEXT,
    last_seen_at TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS fixtures (
    fixture_id BIGINT PRIMARY KEY,
    league_id BIGINT NOT NULL REFERENCES leagues(league_id),
    season INTEGER,
    round TEXT,
    kickoff_utc TIMESTAMPTZ NOT NULL,
    timezone TEXT,
    venue_name TEXT,
    venue_city TEXT,
    referee TEXT,
    status_short TEXT,
    status_long TEXT,
    elapsed INTEGER,
    home_team_id BIGINT NOT NULL REFERENCES teams(team_id),
    away_team_id BIGINT NOT NULL REFERENCES teams(team_id),
    home_goals INTEGER,
    away_goals INTEGER,
    updated_at TIMESTAMPTZ NOT NULL,
    raw_file TEXT
);
CREATE INDEX IF NOT EXISTS idx_fixtures_kickoff ON fixtures(kickoff_utc);
CREATE INDEX IF NOT EXISTS idx_fixtures_league ON fixtures(league_id);
CREATE TABLE IF NOT EXISTS collection_runs (
    run_id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    target_date DATE NOT NULL,
    endpoint TEXT NOT NULL,
    api_results INTEGER DEFAULT 0,
    fixtures_saved INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT,
    raw_file TEXT
);
"""

class CompatConnection:
    def __init__(self, conn: Any, postgres: bool):
        self._conn = conn
        self.postgres = postgres

    def _sql(self, sql: str) -> str:
        return sql.replace("?", "%s") if self.postgres else sql

    def execute(self, sql: str, params: tuple | list = ()):
        return self._conn.execute(self._sql(sql), params)

    def executemany(self, sql: str, params):
        return self._conn.executemany(self._sql(sql), params)

    def executescript(self, script: str) -> None:
        if self.postgres:
            for statement in script.split(";"):
                if statement.strip():
                    self._conn.execute(statement)
        else:
            self._conn.executescript(script)

    def commit(self) -> None:
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

@contextmanager
def connection() -> Iterator[CompatConnection]:
    if IS_POSTGRES:
        import psycopg
        from psycopg.rows import dict_row
        raw = psycopg.connect(DATABASE_URL, row_factory=dict_row)
        conn = CompatConnection(raw, True)
    else:
        raw = sqlite3.connect(DATABASE_PATH)
        raw.row_factory = sqlite3.Row
        raw.execute("PRAGMA foreign_keys = ON")
        conn = CompatConnection(raw, False)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_database() -> None:
    with connection() as conn:
        conn.executescript(POSTGRES_SCHEMA if IS_POSTGRES else SQLITE_SCHEMA)
