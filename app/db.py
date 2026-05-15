"""Accès SQLite."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from models import ParsedAnnonce
from utils import now_iso

DB_PATH = Path(os.getenv("DB_PATH", "data/annonces.sqlite"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS emails_processed (
    id INTEGER PRIMARY KEY,
    message_id TEXT UNIQUE,
    subject TEXT,
    sender TEXT,
    received_at TEXT,
    processed_at TEXT,
    status TEXT,
    error TEXT
);

CREATE TABLE IF NOT EXISTS annonces (
    id INTEGER PRIMARY KEY,
    source TEXT,
    url TEXT UNIQUE,
    url_normalized TEXT,
    titre TEXT,
    ville TEXT,
    prix REAL,
    surface REAL,
    type_bien TEXT,
    dpe TEXT,
    charges_annuelles REAL,
    taxe_fonciere REAL,
    description TEXT,
    first_seen_at TEXT,
    last_seen_at TEXT,
    last_email_message_id TEXT,
    prix_m2 REAL,
    niveau_travaux TEXT,
    budget_travaux REAL,
    prix_total_estime REAL,
    prix_m2_apres_travaux REAL,
    score INTEGER,
    decision TEXT,
    arguments_json TEXT,
    raw_email_excerpt TEXT
);

CREATE TABLE IF NOT EXISTS price_history (
    id INTEGER PRIMARY KEY,
    annonce_id INTEGER,
    prix REAL,
    seen_at TEXT,
    source TEXT,
    FOREIGN KEY(annonce_id) REFERENCES annonces(id)
);

CREATE INDEX IF NOT EXISTS idx_annonces_url_normalized ON annonces(url_normalized);
CREATE INDEX IF NOT EXISTS idx_emails_message_id ON emails_processed(message_id);
"""


def get_conn(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def is_email_processed(conn: sqlite3.Connection, message_id: str) -> bool:
    cur = conn.execute("SELECT 1 FROM emails_processed WHERE message_id = ?", (message_id,))
    return cur.fetchone() is not None


def mark_email_processed(
    conn: sqlite3.Connection,
    message_id: str,
    subject: str,
    sender: str,
    received_at: str,
    status: str,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO emails_processed (
            message_id, subject, sender, received_at, processed_at, status, error
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (message_id, subject, sender, received_at, now_iso(), status, error),
    )
    conn.commit()


def upsert_annonce(conn: sqlite3.Connection, annonce: ParsedAnnonce, analysis: dict[str, Any]) -> tuple[int, str]:
    now = now_iso()
    existing = conn.execute(
        "SELECT id, prix, first_seen_at FROM annonces WHERE url_normalized = ? OR url = ?",
        (annonce.url_normalized, annonce.url),
    ).fetchone()

    if existing:
        annonce_id = int(existing["id"])
        conn.execute(
            """
            UPDATE annonces SET
                source=?, url=?, url_normalized=?, titre=?, ville=?, prix=?, surface=?, type_bien=?, dpe=?,
                charges_annuelles=?, taxe_fonciere=?, description=?, last_seen_at=?, last_email_message_id=?,
                prix_m2=?, niveau_travaux=?, budget_travaux=?, prix_total_estime=?, prix_m2_apres_travaux=?,
                score=?, decision=?, arguments_json=?, raw_email_excerpt=?
            WHERE id=?
            """,
            (
                annonce.source,
                annonce.url,
                annonce.url_normalized,
                annonce.titre,
                annonce.ville,
                annonce.prix,
                annonce.surface,
                annonce.type_bien,
                annonce.dpe,
                annonce.charges_annuelles,
                annonce.taxe_fonciere,
                annonce.description,
                now,
                annonce.last_email_message_id,
                analysis.get("prix_m2"),
                analysis.get("niveau_travaux"),
                analysis.get("budget_travaux"),
                analysis.get("prix_total_estime"),
                analysis.get("prix_m2_apres_travaux"),
                analysis.get("score"),
                analysis.get("decision"),
                json.dumps(analysis.get("arguments", []), ensure_ascii=False),
                annonce.raw_email_excerpt,
                annonce_id,
            ),
        )
        if annonce.prix is not None and existing["prix"] != annonce.prix:
            conn.execute(
                "INSERT INTO price_history (annonce_id, prix, seen_at, source) VALUES (?, ?, ?, ?)",
                (annonce_id, annonce.prix, now, annonce.source),
            )
        conn.commit()
        return annonce_id, "updated"

    cur = conn.execute(
        """
        INSERT INTO annonces (
            source, url, url_normalized, titre, ville, prix, surface, type_bien, dpe,
            charges_annuelles, taxe_fonciere, description, first_seen_at, last_seen_at,
            last_email_message_id, prix_m2, niveau_travaux, budget_travaux, prix_total_estime,
            prix_m2_apres_travaux, score, decision, arguments_json, raw_email_excerpt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            annonce.source,
            annonce.url,
            annonce.url_normalized,
            annonce.titre,
            annonce.ville,
            annonce.prix,
            annonce.surface,
            annonce.type_bien,
            annonce.dpe,
            annonce.charges_annuelles,
            annonce.taxe_fonciere,
            annonce.description,
            now,
            now,
            annonce.last_email_message_id,
            analysis.get("prix_m2"),
            analysis.get("niveau_travaux"),
            analysis.get("budget_travaux"),
            analysis.get("prix_total_estime"),
            analysis.get("prix_m2_apres_travaux"),
            analysis.get("score"),
            analysis.get("decision"),
            json.dumps(analysis.get("arguments", []), ensure_ascii=False),
            annonce.raw_email_excerpt,
        ),
    )
    annonce_id = int(cur.lastrowid)
    if annonce.prix is not None:
        conn.execute(
            "INSERT INTO price_history (annonce_id, prix, seen_at, source) VALUES (?, ?, ?, ?)",
            (annonce_id, annonce.prix, now, annonce.source),
        )
    conn.commit()
    return annonce_id, "inserted"


def fetch_all_annonces(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    cur = conn.execute("SELECT * FROM annonces ORDER BY score DESC, last_seen_at DESC")
    return cur.fetchall()


def get_price_history(conn: sqlite3.Connection, annonce_id: int) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT prix, seen_at, source FROM price_history WHERE annonce_id = ? ORDER BY seen_at ASC",
        (annonce_id,),
    )
    return cur.fetchall()
