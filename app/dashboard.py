from __future__ import annotations
import os
from flask import Flask, render_template_string
from app.db import init_database
from app.over15_engine import Settings, backtest, upcoming

app=Flask(__name__)
HTML="""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Football Intelligence Engine</title><style>
body{font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:24px}.wrap{max-width:1100px;margin:auto}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.card,table{background:#1e293b;border-radius:12px;padding:16px}h1,h2{margin-top:0}
table{width:100%;border-collapse:collapse;padding:0}th,td{padding:10px;border-bottom:1px solid #334155;text-align:left}.good{color:#4ade80}.muted{color:#94a3b8}
</style></head><body><div class='wrap'><h1>Football Intelligence Engine — Over 1.5 v1</h1>
<div class='cards'><div class='card'><b>Partite analizzate</b><h2>{{r.matches_analyzed}}</h2></div><div class='card'><b>Selezioni simulate</b><h2>{{r.bets}}</h2></div><div class='card'><b>Vinte / Perse</b><h2>{{r.wins}} / {{r.losses}}</h2></div><div class='card'><b>Hit rate</b><h2 class='good'>{{'%.2f'|format(r.hit_rate)}}%</h2></div><div class='card'><b>ROI</b><h2>{{'n/d' if r.roi is none else ('%.2f%%'|format(r.roi))}}</h2><span class='muted'>Serve storico quote per un ROI reale</span></div></div>
<h2 style='margin-top:28px'>Selezioni future</h2><table><tr><th>Partita</th><th>Competizione</th><th>Score</th><th>Trend casa/trasferta</th><th>Quota</th></tr>
{% for p in picks %}<tr><td>{{p.home_team}} - {{p.away_team}}</td><td>{{p.league_name}}</td><td>{{p.score}}/100</td><td>{{p.home_rate}}% / {{p.away_rate}}%</td><td>{{p.odd or 'n/d'}}</td></tr>{% else %}<tr><td colspan=5>Nessuna selezione disponibile.</td></tr>{% endfor %}</table>
</div></body></html>"""
@app.get('/')
def home():
    cfg=Settings(); return render_template_string(HTML,r=backtest(cfg),picks=upcoming(cfg)[:50])
if __name__=='__main__':
    init_database(); app.run(host='0.0.0.0',port=int(os.getenv('PORT','8080')))
