from __future__ import annotations

import os
import sqlite3

import psycopg
from psycopg.rows import dict_row

from app.config import DATABASE_PATH
from app.db import POSTGRES_SCHEMA


TABLES = [
    "leagues",
    "teams",
    "fixtures",
    "collection_runs",
]


def main() -> None:
    database_url = os.getenv("DATABASE_URL", "").strip()

    if not database_url:
        raise SystemExit("DATABASE_URL mancante")

    if not DATABASE_PATH.exists():
        raise SystemExit(f"SQLite non trovato: {DATABASE_PATH}")

    sqlite_conn = sqlite3.connect(DATABASE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    try:
        with psycopg.connect(database_url, row_factory=dict_row) as postgres_conn:
            for statement in POSTGRES_SCHEMA.split(";"):
                statement = statement.strip()
                if statement:
                    postgres_conn.execute(statement)

            for table in TABLES:
                rows = sqlite_conn.execute(
                    f"SELECT * FROM {table}"
                ).fetchall()

                if not rows:
                    print(f"{table}: 0")
                    continue

                columns = list(rows[0].keys())
                column_names = ",".join(columns)
                placeholders = ",".join(["%s"] * len(columns))

                conflict_column = {
                    "leagues": "league_id",
                    "teams": "team_id",
                    "fixtures": "fixture_id",
                    "collection_runs": "run_id",
                }[table]

                sql = (
                    f"INSERT INTO {table} ({column_names}) "
                    f"VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict_column}) DO NOTHING"
                )

                values = [
                    tuple(row[column] for column in columns)
                    for row in rows
                ]

                with postgres_conn.cursor() as cursor:
                    cursor.executemany(sql, values)

                print(f"{table}: {len(rows)}")

            postgres_conn.commit()

    finally:
        sqlite_conn.close()

    print("Migrazione completata")


if __name__ == "__main__":
    main()