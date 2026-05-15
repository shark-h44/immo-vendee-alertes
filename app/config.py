"""Chargement configuration YAML et .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


@dataclass
class MailSecrets:
    host: str
    port: int
    user: str
    password: str
    folder: str
    mark_as_seen: bool


def str_to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def load_config(config_path: str | Path = "config.yml") -> dict[str, Any]:
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Fichier de configuration introuvable: {config_file}")
    with config_file.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_mail_secrets(env_path: str | Path | None = None) -> MailSecrets:
    env_path = Path(env_path or os.getenv("ENV_PATH", ".env"))
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    return MailSecrets(
        host=os.getenv("IMAP_HOST", ""),
        port=int(os.getenv("IMAP_PORT", "993")),
        user=os.getenv("IMAP_USER", ""),
        password=os.getenv("IMAP_PASSWORD", ""),
        folder=os.getenv("IMAP_FOLDER", "INBOX"),
        mark_as_seen=str_to_bool(os.getenv("MARK_EMAILS_AS_SEEN"), False),
    )


def ensure_directories(db_path: str | Path | None = None, output_path: str | Path | None = None) -> None:
    db_file = Path(db_path or os.getenv("DB_PATH", "data/annonces.sqlite"))
    out_file = Path(output_path or os.getenv("OUTPUT_PATH", "output/rapport.html"))
    db_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.parent.mkdir(parents=True, exist_ok=True)
