from app.db import connection, init_database

def main() -> None:
    init_database()
    with connection() as conn:
        totals = conn.execute(
            """
            SELECT COUNT(*) AS fixtures,
                   COUNT(DISTINCT league_id) AS leagues,
                   MIN(kickoff_utc) AS first_match,
                   MAX(kickoff_utc) AS last_match
            FROM fixtures
            """
        ).fetchone()

        runs = conn.execute(
            """
            SELECT target_date, status, api_results, fixtures_saved, error_message
            FROM collection_runs
            ORDER BY run_id DESC
            LIMIT 10
            """
        ).fetchall()

    print("=== DATABASE ===")
    print(f"Partite: {totals['fixtures']}")
    print(f"Competizioni: {totals['leagues']}")
    print(f"Prima partita: {totals['first_match']}")
    print(f"Ultima partita: {totals['last_match']}")
    print("\n=== ULTIME RACCOLTE ===")
    for row in runs:
        print(
            f"{row['target_date']} | {row['status']} | "
            f"API: {row['api_results']} | salvate: {row['fixtures_saved']}"
        )
        if row["error_message"]:
            print(f"  Errore: {row['error_message']}")

if __name__ == "__main__":
    main()
