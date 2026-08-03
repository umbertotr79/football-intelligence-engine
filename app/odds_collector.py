from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from typing import Any

from app.api_client import ApiFootballClient, ApiFootballError
from app.db import connection, init_database
from app.storage import save_raw


ODDS_SCHEMA = """
CREATE TABLE IF NOT EXISTS odds (
    odds_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fixture_id INTEGER NOT NULL,
    bookmaker_id INTEGER NOT NULL,
    bookmaker_name TEXT NOT NULL,
    bet_id INTEGER NOT NULL,
    bet_name TEXT NOT NULL,
    value_name TEXT NOT NULL,
    odd REAL NOT NULL,
    api_update TEXT,
    collected_at TEXT NOT NULL,
    UNIQUE (
        fixture_id,
        bookmaker_id,
        bet_id,
        value_name,
        api_update
    ),
    FOREIGN KEY (fixture_id) REFERENCES fixtures(fixture_id)
);

CREATE INDEX IF NOT EXISTS idx_odds_fixture
ON odds(fixture_id);

CREATE INDEX IF NOT EXISTS idx_odds_market
ON odds(bet_name, value_name);

CREATE INDEX IF NOT EXISTS idx_odds_bookmaker
ON odds(bookmaker_id);

CREATE TABLE IF NOT EXISTS odds_collection_runs (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    target_date TEXT NOT NULL,
    pages_requested INTEGER DEFAULT 0,
    fixtures_received INTEGER DEFAULT 0,
    odds_saved INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT
);
"""


def init_odds_database() -> None:
    init_database()

    with connection() as conn:
        conn.executescript(ODDS_SCHEMA)


def create_run(target_date: str) -> int:
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO odds_collection_runs (
                started_at,
                target_date,
                status
            )
            VALUES (?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                target_date,
                "RUNNING",
            ),
        )

        return int(cursor.lastrowid)


def finish_run(
    run_id: int,
    status: str,
    pages_requested: int = 0,
    fixtures_received: int = 0,
    odds_saved: int = 0,
    error_message: str | None = None,
) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE odds_collection_runs
            SET
                finished_at = ?,
                pages_requested = ?,
                fixtures_received = ?,
                odds_saved = ?,
                status = ?,
                error_message = ?
            WHERE run_id = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                pages_requested,
                fixtures_received,
                odds_saved,
                status,
                error_message,
                run_id,
            ),
        )


def fixture_exists(fixture_id: int) -> bool:
    with connection() as conn:
        row = conn.execute(
            """
            SELECT fixture_id
            FROM fixtures
            WHERE fixture_id = ?
            """,
            (fixture_id,),
        ).fetchone()

    return row is not None


def save_odd(
    fixture_id: int,
    bookmaker_id: int,
    bookmaker_name: str,
    bet_id: int,
    bet_name: str,
    value_name: str,
    odd: float,
    api_update: str | None,
) -> bool:
    collected_at = datetime.now(timezone.utc).isoformat()

    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT OR REPLACE INTO odds (
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
            """,
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
            ),
        )

    return cursor.rowcount > 0


def process_fixture_odds(item: dict[str, Any]) -> int:
    fixture = item.get("fixture") or {}
    fixture_id = fixture.get("id")

    if not isinstance(fixture_id, int):
        return 0

    if not fixture_exists(fixture_id):
        return 0

    api_update = item.get("update")
    saved = 0

    bookmakers = item.get("bookmakers") or []

    for bookmaker in bookmakers:
        bookmaker_id = bookmaker.get("id")
        bookmaker_name = bookmaker.get("name")

        if not isinstance(bookmaker_id, int):
            continue

        if not isinstance(bookmaker_name, str):
            continue

        bets = bookmaker.get("bets") or []

        for bet in bets:
            bet_id = bet.get("id")
            bet_name = bet.get("name")

            if not isinstance(bet_id, int):
                continue

            if not isinstance(bet_name, str):
                continue

            values = bet.get("values") or []

            for value in values:
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

                if save_odd(
                    fixture_id=fixture_id,
                    bookmaker_id=bookmaker_id,
                    bookmaker_name=bookmaker_name,
                    bet_id=bet_id,
                    bet_name=bet_name,
                    value_name=value_name,
                    odd=odd,
                    api_update=api_update,
                ):
                    saved += 1

    return saved


def collect_odds(target_date: str) -> tuple[int, int, int]:
    client = ApiFootballClient()

    current_page = 1
    total_pages = 1
    pages_requested = 0
    fixtures_received = 0
    odds_saved = 0

    while current_page <= total_pages:
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

        for item in response:
            odds_saved += process_fixture_odds(item)

        paging = payload.get("paging") or {}
        total_pages = int(paging.get("total") or 1)
        current_page += 1

    return pages_requested, fixtures_received, odds_saved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Raccoglie le quote pre-partita da API-Football."
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Data delle partite nel formato YYYY-MM-DD.",
    )
    args = parser.parse_args()

    init_odds_database()
    run_id = create_run(args.date)

    try:
        pages, fixtures, saved = collect_odds(args.date)

        finish_run(
            run_id=run_id,
            status="SUCCESS",
            pages_requested=pages,
            fixtures_received=fixtures,
            odds_saved=saved,
        )

        print(
            "Raccolta quote completata: "
            f"{pages} pagine richieste, "
            f"{fixtures} partite ricevute, "
            f"{saved} quote salvate."
        )

    except (
        ApiFootballError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        finish_run(
            run_id=run_id,
            status="FAILED",
            error_message=str(exc),
        )

        raise SystemExit(
            f"Raccolta quote fallita: {exc}"
        ) from exc


if __name__ == "__main__":
    main()