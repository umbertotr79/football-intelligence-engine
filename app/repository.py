from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from app.db import connection

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def upsert_fixture(item: dict[str, Any], raw_file: str) -> None:
    fixture = item["fixture"]
    league = item["league"]
    teams = item["teams"]
    goals = item.get("goals") or {}
    status = fixture.get("status") or {}
    venue = fixture.get("venue") or {}
    now = now_iso()

    with connection() as conn:
        conn.execute(
            """
            INSERT INTO leagues (league_id, name, country, logo_url, season, last_seen_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(league_id) DO UPDATE SET
                name=excluded.name,
                country=excluded.country,
                logo_url=excluded.logo_url,
                season=excluded.season,
                last_seen_at=excluded.last_seen_at
            """,
            (league["id"], league["name"], league.get("country"),
             league.get("logo"), league.get("season"), now),
        )

        for side in ("home", "away"):
            team = teams[side]
            conn.execute(
                """
                INSERT INTO teams (team_id, name, code, logo_url, last_seen_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(team_id) DO UPDATE SET
                    name=excluded.name,
                    code=excluded.code,
                    logo_url=excluded.logo_url,
                    last_seen_at=excluded.last_seen_at
                """,
                (team["id"], team["name"], team.get("code"),
                 team.get("logo"), now),
            )

        conn.execute(
            """
            INSERT INTO fixtures (
                fixture_id, league_id, season, round, kickoff_utc, timezone,
                venue_name, venue_city, referee, status_short, status_long,
                elapsed, home_team_id, away_team_id, home_goals, away_goals,
                updated_at, raw_file
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fixture_id) DO UPDATE SET
                status_short=excluded.status_short,
                status_long=excluded.status_long,
                elapsed=excluded.elapsed,
                home_goals=excluded.home_goals,
                away_goals=excluded.away_goals,
                referee=excluded.referee,
                updated_at=excluded.updated_at,
                raw_file=excluded.raw_file
            """,
            (
                fixture["id"], league["id"], league.get("season"),
                league.get("round"), fixture["date"], fixture.get("timezone"),
                venue.get("name"), venue.get("city"), fixture.get("referee"),
                status.get("short"), status.get("long"), status.get("elapsed"),
                teams["home"]["id"], teams["away"]["id"],
                goals.get("home"), goals.get("away"), now, raw_file
            ),
        )
