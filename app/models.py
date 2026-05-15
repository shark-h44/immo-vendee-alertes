"""Modèles de données simples pour les annonces et emails."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class EmailMessageData:
    message_id: str
    subject: str
    sender: str
    received_at: str
    body_text: str
    body_html: str


@dataclass
class ParsedAnnonce:
    source: str
    url: str
    url_normalized: str
    titre: str
    ville: str | None = None
    prix: float | None = None
    surface: float | None = None
    type_bien: str | None = None
    dpe: str | None = None
    charges_annuelles: float | None = None
    taxe_fonciere: float | None = None
    description: str | None = None
    raw_email_excerpt: str | None = None
    received_at: str | None = None
    last_email_message_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunStats:
    emails_found: int = 0
    emails_already_processed: int = 0
    emails_processed_ok: int = 0
    emails_processed_error: int = 0
    annonces_extracted: int = 0
    annonces_inserted: int = 0
    annonces_updated: int = 0
    started_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    finished_at: str | None = None
