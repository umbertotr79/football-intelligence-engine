from __future__ import annotations

import argparse
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from app.db import connection, init_database
from app.odds_collector import collect_odds_for_fixtures
FINISHED = {"FT", "AET", "PEN"}

@dataclass
class Settings:
    recent_matches: int = 10
    min_matches: int = 5
    min_score: int = 70
    min_home_rate: float = 0.60
    min_away_rate: float = 0.60
    stake: float = 1.0

@dataclass
class TeamWindow:
    games: deque

    @classmethod
    def create(cls, size: int):
        return cls(deque(maxlen=size))

    def add(self, gf: int, ga: int) -> None:
        self.games.append((gf, ga))

    @property
    def matches(self) -> int: return len(self.games)
    @property
    def over_rate(self) -> float:
        return sum(1 for gf, ga in self.games if gf + ga >= 2) / len(self.games) if self.games else 0.0
    @property
    def avg_goals(self) -> float:
        return sum(gf + ga for gf, ga in self.games) / len(self.games) if self.games else 0.0

def score(home: TeamWindow, away: TeamWindow) -> int:
    rate = (home.over_rate + away.over_rate) / 2
    goals = (home.avg_goals + away.avg_goals) / 2
    return round(rate * 70 + min(goals / 3.0, 1.0) * 30)

def qualifies(home: TeamWindow, away: TeamWindow, cfg: Settings) -> bool:
    return (home.matches >= cfg.min_matches and away.matches >= cfg.min_matches
            and home.over_rate >= cfg.min_home_rate and away.over_rate >= cfg.min_away_rate
            and score(home, away) >= cfg.min_score)

def load_finished() -> list[dict[str, Any]]:
    with connection() as conn:
        rows = conn.execute("""
            SELECT f.fixture_id, f.kickoff_utc, f.league_id, l.name AS league_name,
                   f.home_team_id, h.name AS home_team, f.away_team_id, a.name AS away_team,
                   f.home_goals, f.away_goals
            FROM fixtures f
            JOIN leagues l ON l.league_id=f.league_id
            JOIN teams h ON h.team_id=f.home_team_id
            JOIN teams a ON a.team_id=f.away_team_id
            WHERE f.status_short IN ('FT','AET','PEN')
              AND f.home_goals IS NOT NULL AND f.away_goals IS NOT NULL
            ORDER BY f.kickoff_utc ASC
        """).fetchall()
    return [dict(r) for r in rows]

def best_over15_odd(fixture_id: int) -> float | None:
    with connection() as conn:
        try:
            row = conn.execute("""
                SELECT MAX(odd) AS odd FROM odds
                WHERE fixture_id=?
                  AND LOWER(bet_name)= 'goals over/under'
                  AND (value_name='Over 1.5' OR value_name='Over 1.5 Goals')
            """, (fixture_id,)).fetchone()
        except Exception:
            return None
    return float(row["odd"]) if row and row["odd"] is not None else None

def backtest(cfg: Settings) -> dict[str, Any]:
    matches = load_finished()
    windows: dict[int, TeamWindow] = defaultdict(lambda: TeamWindow.create(cfg.recent_matches))
    bets = wins = losses = 0
    profit = 0.0
    scored: list[dict[str, Any]] = []
    for m in matches:
        home, away = windows[m["home_team_id"]], windows[m["away_team_id"]]
        if qualifies(home, away, cfg):
            s = score(home, away)
            won = int(m["home_goals"]) + int(m["away_goals"]) >= 2
            odd = best_over15_odd(int(m["fixture_id"]))
            # Se non abbiamo quote storiche, usiamo solo hit-rate; niente ROI inventato.
            pnl = ((odd - 1) * cfg.stake if won else -cfg.stake) if odd else None
            bets += 1
            wins += int(won); losses += int(not won)
            if pnl is not None: profit += pnl
            scored.append({**m, "score": s, "won": won, "odd": odd, "pnl": pnl})
        home.add(int(m["home_goals"]), int(m["away_goals"]))
        away.add(int(m["away_goals"]), int(m["home_goals"]))
    with_odds = [x for x in scored if x["odd"] is not None]
    return {
        "matches_analyzed": len(matches), "bets": bets, "wins": wins, "losses": losses,
        "hit_rate": (wins / bets * 100) if bets else 0.0,
        "bets_with_odds": len(with_odds),
        "profit_units": profit,
        "roi": (profit / (len(with_odds) * cfg.stake) * 100) if with_odds else None,
        "items": scored,
    }

def upcoming(cfg: Settings) -> list[dict[str, Any]]:
    finished = load_finished()
    windows: dict[int, TeamWindow] = defaultdict(lambda: TeamWindow.create(cfg.recent_matches))
    for m in finished:
        windows[m["home_team_id"]].add(int(m["home_goals"]), int(m["away_goals"]))
        windows[m["away_team_id"]].add(int(m["away_goals"]), int(m["home_goals"]))
    now = datetime.now(timezone.utc).isoformat()
    with connection() as conn:
        rows = conn.execute("""
            SELECT f.fixture_id, f.kickoff_utc, l.name AS league_name,
                   f.home_team_id, h.name AS home_team, f.away_team_id, a.name AS away_team
            FROM fixtures f JOIN leagues l ON l.league_id=f.league_id
            JOIN teams h ON h.team_id=f.home_team_id JOIN teams a ON a.team_id=f.away_team_id
            WHERE f.kickoff_utc>=? AND f.status_short IN ('NS','TBD') ORDER BY f.kickoff_utc
        """, (now,)).fetchall()
    picks=[]
    for r in rows:
        r=dict(r); h=windows[r["home_team_id"]]; a=windows[r["away_team_id"]]
        if qualifies(h,a,cfg):
            r.update(score=score(h,a), home_rate=round(h.over_rate*100,1), away_rate=round(a.over_rate*100,1),
                     home_avg=round(h.avg_goals,2), away_avg=round(a.avg_goals,2), odd=best_over15_odd(int(r["fixture_id"])))
            picks.append(r)
    return sorted(picks, key=lambda x:x["score"], reverse=True)

def main() -> None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--backtest", action="store_true")
    parser.add_argument("--min-score", type=int, default=70)
    args=parser.parse_args()
    init_database(); cfg=Settings(min_score=args.min_score)
    if args.backtest:
        r=backtest(cfg)
        print(f"Partite analizzate: {r['matches_analyzed']}")
        print(f"Selezioni: {r['bets']} | Vinte: {r['wins']} | Perse: {r['losses']}")
        print(f"Hit rate: {r['hit_rate']:.2f}%")
        if r['roi'] is None: print("ROI: non calcolabile senza quote storiche abbinate")
        else: print(f"ROI: {r['roi']:.2f}% | Profitto: {r['profit_units']:.2f} unità")
    else:
         picks = upcoming(cfg)

    fixture_ids = [p["fixture_id"] for p in picks]
    if fixture_ids:
        collect_odds_for_fixtures(fixture_ids)
        picks = upcoming(cfg)

    print(f"Selezioni Over 1.5: {len(picks)}")
    for p in picks[:30]:
        print(
            f"{p['home_team']} - {p['away_team']} | "
            f"{p['score']}/100 | "
            f"{p['home_rate']}%-{p['away_rate']}% | "
            f"quota {p['odd'] or 'n/d'}"
        )
if __name__ == "__main__": main()
