from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from app.config import RAW_DIR

def save_raw(prefix: str, payload: dict[str, Any]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = RAW_DIR / f"{prefix}_{timestamp}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
