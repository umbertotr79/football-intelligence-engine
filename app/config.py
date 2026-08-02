from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_FOOTBALL_KEY", "").strip()
BASE_URL = os.getenv(
    "API_FOOTBALL_BASE_URL",
    "https://v3.football.api-sports.io",
).rstrip("/")
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", "data/football_engine.db"))
TIMEZONE = os.getenv("TIMEZONE", "Europe/Rome")
RAW_DIR = DATABASE_PATH.parent / "raw"

DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)
