"""Parsing heuristique des emails d'alertes immobilières."""

from __future__ import annotations

import logging
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from models import EmailMessageData, ParsedAnnonce
from utils import clean_text, normalize_url

LOGGER = logging.getLogger(__name__)

SOURCE_MAP = {
    "leboncoin.fr": "leboncoin",
    "seloger.com": "seloger",
    "ouestfrance-immo.com": "ouestfrance",
    "pap.fr": "pap",
    "bienici.com": "bienici",
}

ANNONCE_HINTS = ["annonce", "immobilier", "vente", "maison", "appartement", "logement", "biens"]


def detect_source(sender: str, subject: str, url: str) -> str:
    joined = f"{sender} {subject} {url}".lower()
    for domain, source in SOURCE_MAP.items():
        if domain in joined:
            return source
    return "inconnue"


def extract_links_from_email(email_data: EmailMessageData) -> list[tuple[str, str]]:
    links: list[tuple[str, str]] = []

    if email_data.body_html:
        soup = BeautifulSoup(email_data.body_html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            text = clean_text(a.get_text(" ", strip=True), 200)
            if href.startswith("http"):
                links.append((href, text))

    if email_data.body_text:
        raw_links = re.findall(r"https?://[^\s<>'\"]+", email_data.body_text)
        for link in raw_links:
            links.append((link.strip(), ""))

    seen = set()
    unique = []
    for url, text in links:
        if url not in seen:
            seen.add(url)
            unique.append((url, text))
    return unique


def _is_candidate_link(url: str) -> bool:
    low = url.lower()
    if not low.startswith("http"):
        return False
    domain = urlparse(low).netloc
    if any(k in domain for k in SOURCE_MAP):
        return True
    return any(h in low for h in ANNONCE_HINTS)


def _extract_price(text: str) -> float | None:
    patterns = [r"(\d{2,3}[\s\.]?\d{3})\s*€", r"(\d{4,6})\s*€"]
    for p in patterns:
        m = re.search(p, text, flags=re.IGNORECASE)
        if m:
            return float(m.group(1).replace(" ", "").replace(".", ""))
    return None


def _extract_surface(text: str) -> float | None:
    m = re.search(r"(\d{1,3}(?:[\.,]\d+)?)\s*(?:m²|m2|m\s?2)", text, flags=re.IGNORECASE)
    if not m:
        return None
    return float(m.group(1).replace(",", "."))


def _extract_dpe(text: str) -> str | None:
    m = re.search(r"DPE\s*[:\-]?\s*([A-G])", text, flags=re.IGNORECASE)
    return m.group(1).upper() if m else None


def _extract_type_bien(text: str) -> str | None:
    low = text.lower()
    if "maison" in low:
        return "maison"
    if any(x in low for x in ["appartement", "studio", "t1", "t2", "t3"]):
        return "appartement"
    return None


def _extract_ville(text: str, villes: list[str]) -> str | None:
    low = text.lower()
    for ville in villes:
        if ville.lower() in low:
            return ville
    return None


def parse_email_to_annonces(email_data: EmailMessageData, config: dict) -> list[ParsedAnnonce]:
    text = clean_text(email_data.body_text or "", 5000)
    html_text = ""
    if email_data.body_html:
        soup = BeautifulSoup(email_data.body_html, "html.parser")
        html_text = clean_text(soup.get_text(" ", strip=True), 5000)

    full_text = clean_text(f"{email_data.subject} {text} {html_text}", 8000)
    links = extract_links_from_email(email_data)

    villes = config.get("criteres", {}).get("villes", [])
    annonces: list[ParsedAnnonce] = []

    for url, link_text in links:
        if not _is_candidate_link(url):
            continue

        src = detect_source(email_data.sender, email_data.subject, url)
        titre = clean_text(link_text or email_data.subject, 220)
        prix = _extract_price(full_text)
        surface = _extract_surface(full_text)
        dpe = _extract_dpe(full_text)
        type_bien = _extract_type_bien(full_text)
        ville = _extract_ville(full_text, villes)

        parsed = ParsedAnnonce(
            source=src,
            url=url,
            url_normalized=normalize_url(url),
            titre=titre,
            ville=ville,
            prix=prix,
            surface=surface,
            type_bien=type_bien,
            dpe=dpe,
            description=clean_text(full_text, 1000),
            raw_email_excerpt=clean_text(full_text, 350),
            received_at=email_data.received_at,
            last_email_message_id=email_data.message_id,
        )
        annonces.append(parsed)

    LOGGER.debug("Email %s -> %s annonces candidates", email_data.message_id, len(annonces))
    return annonces
