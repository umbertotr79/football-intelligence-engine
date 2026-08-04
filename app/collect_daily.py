from __future__ import annotations
import argparse
from datetime import date, datetime, timezone
from app.api_client import ApiFootballClient, ApiFootballError
from app.config import TIMEZONE
from app.db import connection, init_database, IS_POSTGRES
from app.repository import upsert_fixture
from app.storage import save_raw

def create_run(target_date: str) -> int:
    with connection() as conn:
        sql = """
            INSERT INTO collection_runs (started_at, target_date, endpoint, status)
            VALUES (?, ?, ?, ?)
        """
        if IS_POSTGRES:
            cursor = conn.execute(sql + " RETURNING run_id", (datetime.now(timezone.utc).isoformat(), target_date, "fixtures", "RUNNING"))
            return int(cursor.fetchone()["run_id"])
        cursor = conn.execute(sql, (datetime.now(timezone.utc).isoformat(), target_date, "fixtures", "RUNNING"))
        return int(cursor.lastrowid)

def finish_run(run_id: int, status: str, api_results: int = 0,
               saved: int = 0, error: str | None = None,
               raw_file: str | None = None) -> None:
    with connection() as conn:
        conn.execute(
            """
            UPDATE collection_runs
            SET finished_at=?, status=?, api_results=?, fixtures_saved=?,
                error_message=?, raw_file=?
            WHERE run_id=?
            """,
            (datetime.now(timezone.utc).isoformat(), status, api_results,
             saved, error, raw_file, run_id),
        )

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()
    init_database()
    run_id = create_run(args.date)
    try:
        client = ApiFootballClient()
        save_raw("status", client.status())
        payload = client.fixtures_by_date(args.date, TIMEZONE)
        raw_path = save_raw(f"fixtures_{args.date}", payload)
        saved = 0
        for item in payload.get("response", []):
            upsert_fixture(item, str(raw_path))
            saved += 1
        finish_run(run_id, "SUCCESS", int(payload.get("results", 0)), saved, raw_file=str(raw_path))
        print(f"Raccolta completata: {saved} partite salvate per {args.date}.")
    except (ApiFootballError, KeyError, TypeError, ValueError) as exc:
        finish_run(run_id, "FAILED", error=str(exc))
        raise SystemExit(f"Raccolta fallita: {exc}") from exc

if __name__ == "__main__":
    main()
