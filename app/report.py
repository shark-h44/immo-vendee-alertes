"""Génération du rapport HTML."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, BaseLoader

from utils import score_color

TEMPLATE = r"""
<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rapport immobilier Vendée</title>
<style>
:root{--bg:#f6f7fb;--card:#fff;--ink:#172030;--muted:#5f6b7a;--line:#e7ebf2}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(160deg,#eef2f8,#f8fbff);font-family:Segoe UI,Arial,sans-serif;color:var(--ink)}
.wrap{max-width:1200px;margin:0 auto;padding:24px}
.head{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:20px 0}
.kpi,.card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px;box-shadow:0 8px 20px rgba(15,32,64,.06)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:14px}
.small{color:var(--muted);font-size:13px}.title{font-weight:700;font-size:17px;margin:0 0 4px}
.badge{display:inline-block;padding:5px 9px;border-radius:999px;color:#fff;font-weight:700;font-size:12px}
a{color:#0b5ed7;text-decoration:none}a:hover{text-decoration:underline}
ul{margin:8px 0 0 18px;padding:0}
</style>
</head>
<body>
<div class="wrap">
  <div class="head">
    <div>
      <h1>{{ project_name }}</h1>
      <div class="small">Généré le {{ generated_at }}</div>
    </div>
  </div>

  <div class="kpis">
    <div class="kpi"><div class="small">Emails traités</div><div>{{ stats.emails_processed_ok }}</div></div>
    <div class="kpi"><div class="small">Annonces en base</div><div>{{ annonces|length }}</div></div>
    <div class="kpi"><div class="small">Nouvelles annonces</div><div>{{ stats.annonces_inserted }}</div></div>
    <div class="kpi"><div class="small">Mises à jour</div><div>{{ stats.annonces_updated }}</div></div>
  </div>

  <h2>Top opportunités</h2>
  <div class="grid">
  {% for a in top %}
    <article class="card">
      <div class="badge" style="background:{{ a.score_color }}">Score {{ a.score or 0 }}</div>
      <h3 class="title">{{ a.titre or "Sans titre" }}</h3>
      <div class="small">{{ a.decision or "-" }}</div>
      <p><strong>{{ a.prix or "?" }} €</strong> - {{ a.surface or "?" }} m² - {{ a.prix_m2 or "?" }} €/m²</p>
      <p>{{ a.ville or "Ville inconnue" }} | {{ a.source }}</p>
      <p>DPE: {{ a.dpe or "inconnu" }} | Travaux: {{ a.niveau_travaux or "?" }}</p>
      <p>Budget travaux: {{ a.budget_travaux or 0 }} € | Total estimé: {{ a.prix_total_estime or "?" }} €</p>
      <p><a href="{{ a.url }}" target="_blank" rel="noopener">Ouvrir l'annonce</a></p>
      {% if a.arguments %}
      <ul>{% for arg in a.arguments %}<li>{{ arg }}</li>{% endfor %}</ul>
      {% endif %}
      <p class="small">{{ a.description or "" }}</p>
    </article>
  {% endfor %}
  </div>
</div>
</body>
</html>
"""


def generate_report(output_path: str | Path, config: dict, stats, annonces_rows: list) -> str:
    env = Environment(loader=BaseLoader())
    template = env.from_string(TEMPLATE)

    annonces = []
    for row in annonces_rows:
        args = []
        try:
            args = json.loads(row["arguments_json"] or "[]")
        except Exception:
            args = []
        data = dict(row)
        data["arguments"] = args
        data["score_color"] = score_color(int(row["score"] or 0))
        annonces.append(data)

    top = annonces[:12]
    html = template.render(
        project_name=config.get("projet", {}).get("nom", "Rapport immobilier"),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        stats=stats,
        annonces=annonces,
        top=top,
    )

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return str(out)
