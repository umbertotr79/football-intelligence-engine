from __future__ import annotations
from typing import Any
import requests
from app.config import API_KEY, BASE_URL

class ApiFootballError(RuntimeError):
    pass

class ApiFootballClient:
    def __init__(self) -> None:
        if not API_KEY or API_KEY == "INCOLLA_QUI_LA_TUA_NUOVA_CHIAVE":
            raise ApiFootballError("Chiave API mancante.")
        self.session = requests.Session()
        self.session.headers.update({"x-apisports-key": API_KEY})

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{BASE_URL}/{endpoint.lstrip('/')}"
        try:
            response = self.session.get(url, params=params or {}, timeout=45)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise ApiFootballError(f"Richiesta fallita: {exc}") from exc
        except ValueError as exc:
            raise ApiFootballError("Risposta API non valida.") from exc

        if payload.get("errors"):
            raise ApiFootballError(f"Errori API: {payload['errors']}")
        return payload

    def status(self) -> dict[str, Any]:
        return self.get("status")

    def fixtures_by_date(self, date_iso: str, timezone: str) -> dict[str, Any]:
        return self.get("fixtures", {"date": date_iso, "timezone": timezone})
