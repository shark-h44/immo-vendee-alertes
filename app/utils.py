"""Utilitaires projet."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "fbclid",
    "gclid",
    "msclkid",
}


def setup_logging(debug: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    filtered_query = [
        (k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS
    ]
    normalized = parsed._replace(query=urlencode(filtered_query, doseq=True), fragment="")
    return urlunparse(normalized)


def clean_text(value: str, max_len: int = 1200) -> str:
    txt = re.sub(r"\s+", " ", (value or "")).strip()
    return txt[:max_len]


def extract_first_number(raw: str) -> float | None:
    if not raw:
        return None
    normalized = raw.replace(" ", "").replace(".", "").replace(",", ".")
    match = re.search(r"\d+(?:\.\d+)?", normalized)
    return float(match.group(0)) if match else None


def score_color(score: int) -> str:
    if score >= 75:
        return "#1f7a3d"
    if score >= 60:
        return "#d97706"
    return "#b42318"
