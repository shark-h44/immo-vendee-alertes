"""Entrée principale du projet."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from analyzers import analyze_annonce
from config import ensure_directories, load_config, load_mail_secrets
from db import fetch_all_annonces, get_conn, init_db, is_email_processed, mark_email_processed, upsert_annonce
from email_parser import parse_email_to_annonces
from mail_reader import fetch_recent_emails, load_eml_file
from models import RunStats
from report import generate_report
from utils import setup_logging

LOGGER = logging.getLogger(__name__)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyse d'alertes immo en Vendée")
    parser.add_argument("--no-mail", action="store_true", help="Ne lit pas la boîte mail")
    parser.add_argument("--days-back", type=int, default=None, help="Nombre de jours de recherche")
    parser.add_argument("--limit", type=int, default=100, help="Limite d'emails lus")
    parser.add_argument("--debug", action="store_true", help="Logs détaillés")
    parser.add_argument("--eml-file", type=str, default=None, help="Parse un fichier .eml local pour test")
    return parser


def process_emails(config: dict, args, conn, stats: RunStats) -> None:
    secrets = load_mail_secrets()
    if "mail" in config:
        if config["mail"].get("mark_as_seen") is not None:
            secrets.mark_as_seen = bool(config["mail"]["mark_as_seen"])

    days_back = args.days_back if args.days_back is not None else int(config.get("mail", {}).get("days_back", 30))

    emails = []
    if args.eml_file:
        emails = [load_eml_file(args.eml_file)]
        LOGGER.info("Mode test .eml activé: 1 email chargé")
    elif not args.no_mail:
        emails = fetch_recent_emails(secrets, days_back=days_back, limit=args.limit)

    stats.emails_found = len(emails)

    for em in emails:
        if is_email_processed(conn, em.message_id):
            stats.emails_already_processed += 1
            continue

        try:
            annonces = parse_email_to_annonces(em, config)
            stats.annonces_extracted += len(annonces)
            for annonce in annonces:
                analysis = analyze_annonce(annonce, config)
                _, status = upsert_annonce(conn, annonce, analysis)
                if status == "inserted":
                    stats.annonces_inserted += 1
                else:
                    stats.annonces_updated += 1

            mark_email_processed(
                conn,
                message_id=em.message_id,
                subject=em.subject,
                sender=em.sender,
                received_at=em.received_at,
                status="ok",
            )
            stats.emails_processed_ok += 1

        except Exception as exc:
            stats.emails_processed_error += 1
            mark_email_processed(
                conn,
                message_id=em.message_id,
                subject=em.subject,
                sender=em.sender,
                received_at=em.received_at,
                status="error",
                error=str(exc)[:500],
            )
            LOGGER.exception("Erreur traitement email %s", em.message_id)


def main() -> None:
    args = build_arg_parser().parse_args()
    setup_logging(args.debug)
    config_path = os.getenv("CONFIG_PATH", "config.yml")
    db_path = os.getenv("DB_PATH", "data/annonces.sqlite")
    output_path = os.getenv("OUTPUT_PATH", "output/rapport.html")

    ensure_directories(db_path=db_path, output_path=output_path)

    try:
        config = load_config(config_path)
    except FileNotFoundError as exc:
        LOGGER.error(str(exc))
        sys.exit(1)

    env_path = Path(os.getenv("ENV_PATH", ".env"))
    if not env_path.exists() and not args.no_mail and not args.eml_file:
        LOGGER.warning("Fichier .env absent (%s). Les variables d'environnement système seront utilisées.", env_path)

    stats = RunStats()

    conn = get_conn(Path(db_path))
    init_db(conn)

    try:
        process_emails(config, args, conn, stats)
    except (ValueError, RuntimeError) as exc:
        if args.no_mail or args.eml_file:
            LOGGER.warning("Lecture mail ignorée: %s", exc)
        else:
            LOGGER.error("Erreur IMAP: %s", exc)
            sys.exit(1)

    annonces = fetch_all_annonces(conn)
    report_path = generate_report(output_path, config, stats, annonces)

    LOGGER.info("Emails trouvés: %s", stats.emails_found)
    LOGGER.info("Emails déjà traités: %s", stats.emails_already_processed)
    LOGGER.info("Annonces extraites: %s", stats.annonces_extracted)
    LOGGER.info("Nouvelles annonces: %s", stats.annonces_inserted)
    LOGGER.info("Annonces mises à jour: %s", stats.annonces_updated)
    LOGGER.info("Rapport généré: %s", Path(report_path).resolve())


if __name__ == "__main__":
    main()
