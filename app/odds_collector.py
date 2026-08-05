from __future__ import annotations

import argparse
import traceback
from datetime import date, datetime, timezone
from typing import Any

from app.api_client import ApiFootballClient
from app.db import connection, init_database, IS_POSTGRES
from app.storage import save_raw


ODDS_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS odds (
    odds_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL,
    bookmaker_id INTEGER NOT NULL,
    bookmaker_name TEXT NOT NULL,
    bet_id INTEGER NOT NULL,
    bet_name TEXT NOT NULL,
    value_name TEXT NOT NULL,
    odd REAL NOT NULL,
    api_update TEXT NOT NULL DEFAULT '',
    collected_at TEXT NOT NULL,
    UNIQUE (
        fixture_id,
        bookmaker_id,
        bet_id,
        value_name,
        api_update
    )
);

CREATE INDEX IF NOT EXISTS idx_odds_fixture
ON odds(fixture_id);

CREATE INDEX IF NOT EXISTS idx_odds_market
ON odds(bet_name, value_name);
"""

ODDS_SCHEMA_POSTGRES = ODDS_SCHEMA_SQLITE.replace(
    "odds_id INTEGER PRIMARY KEY AUTOINCREMENT", "odds_id BIGSERIAL PRIMARY KEY"
)

def init_odds_database() -> None:
    init_database()

    with connection() as conn:
        conn.executescript(ODDS_SCHEMA_POSTGRES if IS_POSTGRES else ODDS_SCHEMA_SQLITE)


def load_fixture_ids() -> set[int]:
    with connection() as conn:
        rows = conn.execute(
            "SELECT fixture_id FROM fixtures"
        ).fetchall()

    return {int(row["fixture_id"]) for row in rows}


def extract_rows(
    items: list[dict[str, Any]],
    valid_fixture_ids: set[int],
) -> list[tuple]:
    collected_at = datetime.now(timezone.utc).isoformat()
    rows: list[tuple] = []

    for item in items:
        fixture = item.get("fixture") or {}
        fixture_id = fixture.get("id")

        if not isinstance(fixture_id, int):
            continue

        if fixture_id not in valid_fixture_ids:
            continue

        api_update = str(item.get("update") or "")
        bookmakers = item.get("bookmakers") or []

        for bookmaker in bookmakers:
            bookmaker_id = bookmaker.get("id")
            bookmaker_name = bookmaker.get("name")

            if not isinstance(bookmaker_id, int):
                continue

            if not isinstance(bookmaker_name, str):
                continue

            for bet in bookmaker.get("bets") or []:
                bet_id = bet.get("id")
                bet_name = bet.get("name")

                if not isinstance(bet_id, int):
                    continue

                if not isinstance(bet_name, str):
                    continue

                for value in bet.get("values") or []:
                    value_name = value.get("value")
                    odd_value = value.get("odd")

                    if not isinstance(value_name, str):
                        continue

                    try:
                        odd = float(odd_value)
                    except (TypeError, ValueError):
                        continue

                    if odd <= 1:
                        continue

                    rows.append(
                        (
                            fixture_id,
                            bookmaker_id,
                            bookmaker_name,
                            bet_id,
                            bet_name,
                            value_name,
                            odd,
                            api_update,
                            collected_at,
                        )
                    )

    return rows


def save_rows(rows: list[tuple]) -> int:
    if not rows:
        return 0

    with connection() as conn:
        insert_prefix = "INSERT INTO"
        conflict = """
            ON CONFLICT (fixture_id, bookmaker_id, bet_id, value_name, api_update)
            DO UPDATE SET odd=excluded.odd, bookmaker_name=excluded.bookmaker_name, collected_at=excluded.collected_at
        """ if IS_POSTGRES else ""
        sql = f"""
            {insert_prefix} odds (
                fixture_id,
                bookmaker_id,
                bookmaker_name,
                bet_id,
                bet_name,
                value_name,
                odd,
                api_update,
                collected_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            {conflict}
        """
        if IS_POSTGRES:
            conn.executemany(sql, rows)
        else:
            conn.executemany(sql.replace("INSERT INTO", "INSERT OR REPLACE INTO", 1), rows)

    return len(rows)


def collect_odds(target_date: str) -> tuple[int, int, int]:
    client = ApiFootballClient()
    valid_fixture_ids = load_fixture_ids()

    print(
        f"Avvio raccolta quote per {target_date}. "
        f"Partite disponibili nel database: {len(valid_fixture_ids)}.",
        flush=True,
    )

    current_page = 1
    total_pages = 1

    pages_requested = 0
    fixtures_received = 0
    odds_saved = 0

    while current_page <= total_pages:
        print(
            f"Richiesta pagina quote {current_page}/{total_pages}...",
            flush=True,
        )

        payload = client.get(
            "odds",
            {
                "date": target_date,
                "page": current_page,
            },
        )

        pages_requested += 1

        save_raw(
            f"odds_{target_date}_page_{current_page}",
            payload,
        )

        response = payload.get("response") or []
        fixtures_received += len(response)

        rows = extract_rows(
            response,
            valid_fixture_ids,
        )

        saved_now = save_rows(rows)
        odds_saved += saved_now

        paging = payload.get("paging") or {}
        total_pages = min(int(paging.get("total") or 1), 3)

        print(
            f"Pagina {current_page}/{total_pages} completata: "
            f"{len(response)} partite ricevute, "
            f"{saved_now} quote salvate.",
            flush=True,
        )

        current_page += 1

    return pages_requested, fixtures_received, odds_saved

def collect_odds_for_fixtures(fixture_ids: list[int]) -> tuple[int, int]:
    client = ApiFootballClient()
    fixtures_received = 0
    odds_saved = 0

    for fixture_id in fixture_ids:
        print(f"Raccolta quote partita {fixture_id}...", flush=True)

        payload = client.get(
            "odds",
            {"fixture": fixture_id},
        )

        response = payload.get("response") or []
        fixtures_received += len(response)

        rows = extract_rows(response, {fixture_id})
        saved_now = save_rows(rows)
        odds_saved += saved_now

        print(
            f"Partita {fixture_id}: {saved_now} quote salvate.",
            flush=True,
        )

    return fixtures_received, odds_saved
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Raccoglie le quote pre-partita da API-Football."
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
    )
    args = parser.parse_args()

    try:
        init_odds_database()

        pages, fixtures, saved = collect_odds(args.date)

        print(
            "Raccolta quote completata: "
            f"{pages} pagine richieste, "
            f"{fixtures} partite ricevute, "
            f"{saved} quote salvate.",
            flush=True,
        )

    except Exception as exc:
        print(
            f"Raccolta quote fallita: {type(exc).__name__}: {exc}",
            flush=True,
        )
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()