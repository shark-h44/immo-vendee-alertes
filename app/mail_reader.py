"""Lecture IMAP et chargement .eml local."""

from __future__ import annotations

import email
import imaplib
import logging
from datetime import datetime, timedelta
from email.message import Message
from email.utils import parsedate_to_datetime
from pathlib import Path

from config import MailSecrets
from models import EmailMessageData
from utils import clean_text


LOGGER = logging.getLogger(__name__)


def _decode_payload(part: Message) -> str:
    charset = part.get_content_charset() or "utf-8"
    payload = part.get_payload(decode=True)
    if payload is None:
        raw = part.get_payload()
        return raw if isinstance(raw, str) else ""
    try:
        return payload.decode(charset, errors="replace")
    except LookupError:
        return payload.decode("utf-8", errors="replace")


def message_to_data(msg: Message) -> EmailMessageData:
    subject = str(email.header.make_header(email.header.decode_header(msg.get("Subject", ""))))
    sender = msg.get("From", "")
    message_id = msg.get("Message-ID", "").strip() or f"fallback-{hash(subject + sender)}"
    date_raw = msg.get("Date", "")
    try:
        received_dt = parsedate_to_datetime(date_raw).isoformat() if date_raw else datetime.utcnow().isoformat()
    except Exception:
        received_dt = datetime.utcnow().isoformat()

    body_text = ""
    body_html = ""

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain" and not body_text:
                body_text = _decode_payload(part)
            elif ctype == "text/html" and not body_html:
                body_html = _decode_payload(part)
    else:
        ctype = msg.get_content_type()
        if ctype == "text/html":
            body_html = _decode_payload(msg)
        else:
            body_text = _decode_payload(msg)

    return EmailMessageData(
        message_id=message_id,
        subject=clean_text(subject, 300),
        sender=clean_text(sender, 300),
        received_at=received_dt,
        body_text=body_text,
        body_html=body_html,
    )


def fetch_recent_emails(secrets: MailSecrets, days_back: int = 30, limit: int = 100) -> list[EmailMessageData]:
    if not secrets.host or not secrets.user or not secrets.password:
        raise ValueError("Variables IMAP incomplètes (IMAP_HOST/IMAP_USER/IMAP_PASSWORD).")

    conn = None
    emails: list[EmailMessageData] = []
    try:
        conn = imaplib.IMAP4_SSL(secrets.host, secrets.port)
        conn.login(secrets.user, secrets.password)
        LOGGER.info("Connexion IMAP OK")
        conn.select(secrets.folder)

        since = (datetime.utcnow() - timedelta(days=days_back)).strftime("%d-%b-%Y")
        status, data = conn.search(None, f'(SINCE "{since}")')
        if status != "OK":
            LOGGER.error("Recherche IMAP KO")
            return []

        ids = data[0].split()[-limit:]
        LOGGER.info("%s emails trouvés (fenêtre %s jours)", len(ids), days_back)

        for uid in ids:
            status, msg_data = conn.fetch(uid, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)
            emails.append(message_to_data(msg))

            if secrets.mark_as_seen:
                conn.store(uid, "+FLAGS", "\\Seen")

    except Exception as exc:
        LOGGER.exception("Connexion IMAP KO: %s", exc)
        raise RuntimeError("Connexion IMAP impossible.") from exc
    finally:
        if conn:
            try:
                conn.logout()
            except Exception:
                pass

    return emails


def load_eml_file(path: str | Path) -> EmailMessageData:
    with Path(path).open("rb") as f:
        msg = email.message_from_binary_file(f)
    return message_to_data(msg)
