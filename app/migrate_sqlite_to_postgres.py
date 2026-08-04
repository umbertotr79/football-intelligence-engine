from __future__ import annotations
import os, sqlite3
import psycopg
from psycopg.rows import dict_row
from app.config import DATABASE_PATH
from app.db import POSTGRES_SCHEMA

TABLES=["leagues","teams","fixtures","collection_runs"]

def main():
    url=os.getenv("DATABASE_URL","")
    if not url: raise SystemExit("DATABASE_URL mancante")
    if not DATABASE_PATH.exists(): raise SystemExit(f"SQLite non trovato: {DATABASE_PATH}")
    src=sqlite3.connect(DATABASE_PATH); src.row_factory=sqlite3.Row
    with psycopg.connect(url, row_factory=dict_row) as dst:
        for stmt in POSTGRES_SCHEMA.split(';'):
            if stmt.strip(): dst.execute(stmt)
        for table in TABLES:
            rows=src.execute(f"SELECT * FROM {table}").fetchall()
            if not rows: print(f"{table}: 0"); continue
            cols=rows[0].keys(); ph=','.join(['%s']*len(cols)); names=','.join(cols)
            conflict={"leagues":"league_id","teams":"team_id","fixtures":"fixture_id","collection_runs":"run_id"}[table]
            sql=f"INSERT INTO {table} ({names}) VALUES ({ph}) ON CONFLICT ({conflict}) DO NOTHING"
            dst.executemany(sql,[tuple(r[c] for c in cols) for r in rows]); print(f"{table}: {len(rows)}")
        dst.commit()
    src.close(); print("Migrazione completata")
if __name__=='__main__': main()
