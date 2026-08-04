from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone

from app.api_client import ApiFootballClient, ApiFootballError
from app.config import TIMEZONE
from app.db import connection, init_database
from app.repository import upsert_fixture
from app.storage import save_raw


def create_run(start_date: str, days: int) -> int:
    with connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO collection_runs (
                started_at,
                target_date,
                endpoint,
                status
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                f"{start_date} - {days} giorni",
                "historical_fixtures",
                "RUNNING",
            ),
        )
        return int(cursor.lastrowid)


def finish_run(
    run_id: int,
    status: str,
    api_results: int = 0,
    saved: int = 0,
    error: str | None = None,
) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE collection_runs
            SET
                finished_at = ?,
                status = ?,
                api_results = ?,
                fixtures_saved = ?,
                error_message = ?
            WHERE run_id = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                status,
                api_results,
                saved,
                error,
                run_id,
            ),
        )


def collect_history(days: int) -> tuple[int, int]:
    client = ApiFootballClient()

    total_received = 0
    total_saved = 0

    first_day = date.today() - timedelta(days=days)

    for offset in range(days):
        target_day = first_day + timedelta(days=offset)
        target_date = target_day.isoformat()

        print(
            f"Raccolta storico {offset + 1}/{days}: {target_date}...",
            flush=True,
        )

        payload = client.fixtures_by_date(
            target_date,
            TIMEZONE,
        )

        raw_path = save_raw(
            f"historical_fixtures_{target_date}",
            payload,
        )

        response = payload.get("response") or []
        total_received += len(response)

        saved_today = 0

        for item in response:
            upsert_fixture(
                item,
                str(raw_path),
            )
            saved_today += 1

        total_saved += saved_today

        print(
            f"{target_date}: "
            f"{len(response)} partite ricevute, "
            f"{saved_today} salvate.",
            flush=True,
        )

    return total_received, total_saved


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Raccoglie lo storico delle partite."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Numero di giorni passati da recuperare.",
    )
    args = parser.parse_args()

    if args.days < 1 or args.days > 60:
        raise SystemExit(
            "Il numero di giorni deve essere compreso tra 1 e 60."
        )

    init_database()

    start_date = (
        date.today() - timedelta(days=args.days)
    ).isoformat()

    run_id = create_run(
        start_date=start_date,
        days=args.days,
    )

    try:
        received, saved = collect_history(args.days)

        finish_run(
            run_id=run_id,
            status="SUCCESS",
            api_results=received,
            saved=saved,
        )

        print(
            "Raccolta storico completata: "
            f"{args.days} giorni elaborati, "
            f"{received} partite ricevute, "
            f"{saved} partite salvate.",
            flush=True,
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
            error=str(exc),
        )

        raise SystemExit(
            f"Raccolta storico fallita: {exc}"
        ) from exc


if __name__ == "__main__":
    main()