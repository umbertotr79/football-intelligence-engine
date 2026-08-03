from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone

from app.db import connection


FINISHED_STATUSES = {"FT", "AET", "PEN"}
MIN_MATCHES_PER_TEAM = 5
RECENT_MATCHES_LIMIT = 10
MIN_SCORE = 70


@dataclass
class TeamStats:
    matches: int = 0
    over15: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def over15_rate(self) -> float:
        if self.matches == 0:
            return 0.0
        return self.over15 / self.matches

    @property
    def average_total_goals(self) -> float:
        if self.matches == 0:
            return 0.0
        return (self.goals_for + self.goals_against) / self.matches


def load_finished_matches() -> list[dict]:
    placeholders = ",".join("?" for _ in FINISHED_STATUSES)

    query = f"""
        SELECT
            fixture_id,
            kickoff_utc,
            home_team_id,
            away_team_id,
            home_goals,
            away_goals
        FROM fixtures
        WHERE status_short IN ({placeholders})
          AND home_goals IS NOT NULL
          AND away_goals IS NOT NULL
        ORDER BY kickoff_utc DESC
    """

    with connection() as conn:
        rows = conn.execute(query, tuple(FINISHED_STATUSES)).fetchall()

    return [dict(row) for row in rows]


def build_team_statistics(matches: list[dict]) -> dict[int, TeamStats]:
    team_matches: dict[int, list[dict]] = defaultdict(list)

    for match in matches:
        team_matches[match["home_team_id"]].append(
            {
                "goals_for": match["home_goals"],
                "goals_against": match["away_goals"],
            }
        )
        team_matches[match["away_team_id"]].append(
            {
                "goals_for": match["away_goals"],
                "goals_against": match["home_goals"],
            }
        )

    statistics: dict[int, TeamStats] = {}

    for team_id, games in team_matches.items():
        recent_games = games[:RECENT_MATCHES_LIMIT]
        stats = TeamStats()

        for game in recent_games:
            total_goals = game["goals_for"] + game["goals_against"]

            stats.matches += 1
            stats.goals_for += game["goals_for"]
            stats.goals_against += game["goals_against"]

            if total_goals >= 2:
                stats.over15 += 1

        statistics[team_id] = stats

    return statistics


def load_upcoming_matches() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()

    query = """
        SELECT
            f.fixture_id,
            f.kickoff_utc,
            f.league_id,
            l.name AS league_name,
            f.home_team_id,
            home.name AS home_team,
            f.away_team_id,
            away.name AS away_team
        FROM fixtures AS f
        JOIN leagues AS l
            ON l.league_id = f.league_id
        JOIN teams AS home
            ON home.team_id = f.home_team_id
        JOIN teams AS away
            ON away.team_id = f.away_team_id
        WHERE f.kickoff_utc >= ?
          AND f.status_short IN ('NS', 'TBD')
        ORDER BY f.kickoff_utc ASC
    """

    with connection() as conn:
        rows = conn.execute(query, (now,)).fetchall()

    return [dict(row) for row in rows]


def calculate_score(home: TeamStats, away: TeamStats) -> int:
    combined_over_rate = (home.over15_rate + away.over15_rate) / 2
    combined_goal_average = (
        home.average_total_goals + away.average_total_goals
    ) / 2

    rate_score = combined_over_rate * 70
    goals_score = min(combined_goal_average / 3.0, 1.0) * 30

    return round(rate_score + goals_score)


def select_over15_matches() -> list[dict]:
    finished_matches = load_finished_matches()
    team_statistics = build_team_statistics(finished_matches)
    upcoming_matches = load_upcoming_matches()

    selections: list[dict] = []

    for fixture in upcoming_matches:
        home_stats = team_statistics.get(fixture["home_team_id"])
        away_stats = team_statistics.get(fixture["away_team_id"])

        if home_stats is None or away_stats is None:
            continue

        if (
            home_stats.matches < MIN_MATCHES_PER_TEAM
            or away_stats.matches < MIN_MATCHES_PER_TEAM
        ):
            continue

        score = calculate_score(home_stats, away_stats)

        if score < MIN_SCORE:
            continue

        selections.append(
            {
                **fixture,
                "market": "Over 1.5 gol",
                "score": score,
                "home_over15_rate": round(home_stats.over15_rate * 100),
                "away_over15_rate": round(away_stats.over15_rate * 100),
                "home_goal_average": round(
                    home_stats.average_total_goals, 2
                ),
                "away_goal_average": round(
                    away_stats.average_total_goals, 2
                ),
            }
        )

    return selections


def print_report() -> None:
    selections = select_over15_matches()

    if not selections:
        print(
            "Nessuna segnalazione disponibile: "
            "servono più partite storiche per ogni squadra."
        )
        return

    print("\nSEGNALAZIONI OVER 1.5 GOL\n")

    for selection in selections:
        print(
            f"{selection['home_team']} - {selection['away_team']}\n"
            f"Competizione: {selection['league_name']}\n"
            f"Mercato: {selection['market']}\n"
            f"Punteggio statistico: {selection['score']}/100\n"
            f"Over 1.5 casa: {selection['home_over15_rate']}%\n"
            f"Over 1.5 trasferta: {selection['away_over15_rate']}%\n"
        )


if __name__ == "__main__":print_report()