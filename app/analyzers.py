"""Analyse, scoring et décision."""

from __future__ import annotations

from typing import Any

from db import get_price_history
from models import ParsedAnnonce

LIGHT = ["rafraichir", "rafraîchir", "peinture", "sols a refaire", "sols à refaire", "deco a revoir", "déco à revoir", "papier peint"]
MEDIUM = ["cuisine ancienne", "salle de bain ancienne", "salle d'eau ancienne", "electricite a revoir", "électricité à revoir", "chauffage electrique ancien", "menuiseries anciennes", "simple vitrage"]
HEAVY = ["a renover", "à rénover", "travaux a prevoir", "travaux à prévoir", "gros travaux", "renovation complete", "rénovation complète", "humidite", "humidité", "toiture a refaire", "toiture à refaire", "fort potentiel", "vendu en l'etat", "vendu en l’état"]


def _detect_travaux_level(description: str) -> tuple[str, list[str]]:
    low = (description or "").lower()
    heavy_hits = [k for k in HEAVY if k in low]
    if heavy_hits:
        return "lourd", heavy_hits
    medium_hits = [k for k in MEDIUM if k in low]
    if medium_hits:
        return "moyen", medium_hits
    light_hits = [k for k in LIGHT if k in low]
    if light_hits:
        return "leger", light_hits
    return "aucun", []


def _dpe_group(dpe: str | None) -> str:
    if not dpe:
        return "inconnu"
    d = dpe.upper()
    if d in {"A", "B", "C", "D"}:
        return "correct"
    if d == "E":
        return "moyen"
    return "defavorable"


def _calc_score(annonce: ParsedAnnonce, cfg: dict[str, Any], niveau_travaux: str) -> tuple[int, list[str]]:
    poids = cfg.get("scoring", {}).get("poids", {})
    criteres = cfg.get("criteres", {})

    p_prix_total = int(poids.get("prix_total", 15))
    p_prix_m2 = int(poids.get("prix_m2", 25))
    p_surface = int(poids.get("surface", 10))
    p_travaux = int(poids.get("travaux", 20))
    p_dpe = int(poids.get("dpe", 10))
    p_nego = int(poids.get("potentiel_negociation", 20))

    prix_max = float(criteres.get("prix_max", 0))
    surf_min = float(criteres.get("surface_min", 0))
    cible_m2 = float(criteres.get("prix_m2_cible", 1))

    score = 0.0
    args: list[str] = []

    if annonce.prix is not None and annonce.prix <= prix_max:
        score += p_prix_total

    prix_m2 = (annonce.prix / annonce.surface) if annonce.prix and annonce.surface else None
    if prix_m2 is not None:
        if prix_m2 <= cible_m2:
            score += p_prix_m2
        elif prix_m2 <= cible_m2 * 1.10:
            score += p_prix_m2 * 0.6
            args.append("Prix/m² supérieur à la cible.")
        elif prix_m2 <= cible_m2 * 1.25:
            score += p_prix_m2 * 0.3
            args.append("Prix/m² supérieur à la cible.")
        else:
            args.append("Prix/m² supérieur à la cible.")

    if annonce.surface is not None and annonce.surface >= surf_min:
        score += p_surface

    travaux_factor = {"aucun": 1.0, "leger": 0.75, "moyen": 0.45, "lourd": 0.15}[niveau_travaux]
    score += p_travaux * travaux_factor
    if niveau_travaux in {"moyen", "lourd", "leger"}:
        args.append("Travaux détectés.")

    dpe_group = _dpe_group(annonce.dpe)
    if dpe_group == "correct":
        score += p_dpe
    elif dpe_group == "moyen":
        score += p_dpe * 0.5
        args.append("DPE défavorable.")
    elif dpe_group == "defavorable":
        args.append("DPE défavorable.")
    else:
        score += p_dpe * 0.3

    nego = 0
    if niveau_travaux in {"moyen", "lourd"}:
        nego += 1
    if dpe_group in {"moyen", "defavorable"}:
        nego += 1
    if prix_m2 and prix_m2 > cible_m2:
        nego += 1
    if annonce.charges_annuelles is None:
        nego += 1
        args.append("Charges de copropriété non renseignées.")
    if annonce.taxe_fonciere is None:
        nego += 1
        args.append("Taxe foncière non renseignée.")

    score += p_nego * min(nego / 4, 1)

    for x in ["Copropriété à vérifier.", "Absence ou incertitude sur stationnement."]:
        if x not in args:
            args.append(x)

    final = max(0, min(100, round(score)))
    return final, args


def _decision(score: int) -> str:
    if score >= 75:
        return "À visiter en priorité"
    if score >= 60:
        return "À surveiller / visiter si emplacement intéressant"
    if score >= 45:
        return "Possible mais prudence"
    return "À écarter sauf élément exceptionnel"


def analyze_annonce(annonce: ParsedAnnonce, config: dict[str, Any], conn=None, annonce_id: int | None = None) -> dict[str, Any]:
    prix_m2 = (annonce.prix / annonce.surface) if annonce.prix and annonce.surface else None
    niveau_travaux, indices = _detect_travaux_level(annonce.description or "")

    cout_m2 = config.get("travaux", {}).get("cout_m2", {})
    coef = {"aucun": 0, "leger": cout_m2.get("leger", 200), "moyen": cout_m2.get("moyen", 650), "lourd": cout_m2.get("lourd", 1200)}
    budget_travaux = (annonce.surface or 0) * float(coef[niveau_travaux])

    prix_total_estime = (annonce.prix or 0) + budget_travaux if annonce.prix is not None else None
    prix_m2_apres = (prix_total_estime / annonce.surface) if prix_total_estime and annonce.surface else None

    score, args = _calc_score(annonce, config, niveau_travaux)
    if prix_m2_apres and config.get("criteres", {}).get("prix_m2_cible") and prix_m2_apres > config["criteres"]["prix_m2_cible"] * 1.2:
        args.append("Prix après travaux potentiellement élevé.")

    if conn is not None and annonce_id is not None:
        hist = get_price_history(conn, annonce_id)
        if len(hist) >= 2 and hist[-1]["prix"] < hist[-2]["prix"]:
            args.append("Baisse de prix détectée.")

    return {
        "prix_m2": round(prix_m2, 2) if prix_m2 else None,
        "niveau_travaux": niveau_travaux,
        "indices_travaux": indices,
        "budget_travaux": round(budget_travaux, 2),
        "prix_total_estime": round(prix_total_estime, 2) if prix_total_estime else None,
        "prix_m2_apres_travaux": round(prix_m2_apres, 2) if prix_m2_apres else None,
        "score": score,
        "decision": _decision(score),
        "arguments": list(dict.fromkeys(args)),
    }
