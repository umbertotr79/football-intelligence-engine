# Football Intelligence Engine v0.2

Primo Data Collector operativo.

## Funzioni
- connessione ad API-Football;
- controllo account;
- download partite per data;
- salvataggio in SQLite;
- salvataggio JSON grezzo;
- prevenzione duplicati;
- report sulle raccolte.

## Avvio
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.init_db
python -m app.collect_daily --date 2026-08-02
python -m app.report
```
