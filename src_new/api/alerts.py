"""Alarm emails (2026-11-17): the nightly known-answers check and crash loops.

Sent through the university relay, no credentials: relay.muni.cz:25 with
STARTTLS accepts mail from the cluster (relay.fi.muni.cz refuses its NAT
address). BAT3_ALERT_EMAIL unset = alarms off (logged only). Each alarm has
a key; the same key is mailed at most once per `every_s` (Redis), so a
lasting problem does not flood the inbox. Sent alarms are listed on the
admin page.
"""
from __future__ import annotations

import json
import logging
import os
import smtplib
import time
from email.message import EmailMessage
from typing import Any, Optional

log = logging.getLogger(__name__)

RECENT_KEY = "bioid:alerts:recent"


def recipient() -> Optional[str]:
    return os.environ.get("BAT3_ALERT_EMAIL", "").strip() or None


def _send(subject: str, body: str, to: str) -> None:
    host = os.environ.get("BAT3_SMTP_HOST", "relay.muni.cz")
    port = int(os.environ.get("BAT3_SMTP_PORT", "25"))
    msg = EmailMessage()
    msg["From"] = os.environ.get("BAT3_ALERT_FROM", "BioID <noreply@bioid-ceitec.dyn.cloud.e-infra.cz>")
    msg["To"] = to
    msg["Subject"] = f"[BioID] {subject}"
    msg.set_content(body)
    with smtplib.SMTP(host, port, timeout=30) as s:
        s.ehlo()
        if s.has_extn("starttls"):
            s.starttls()
            s.ehlo()
        s.send_message(msg)


def alarm(key: str, subject: str, body: str, every_s: int = 6 * 3600) -> bool:
    """Mail an alarm unless `key` was mailed within `every_s`. True if sent."""
    from .security import _redis_client
    client = _redis_client()
    if client is not None:
        try:
            if not client.set(f"bioid:alerts:sent:{key}", "1", nx=True, ex=every_s):
                return False
        except Exception as exc:
            log.warning("alerts: Redis unavailable (%s); sending anyway", exc)
    entry = {"at": time.time(), "key": key, "subject": subject, "sent": False}
    to = recipient()
    if to:
        try:
            _send(subject, body, to)
            entry["sent"] = True
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {str(exc)[:200]}"
            log.error("alerts: could not send %r: %s", subject, exc)
    else:
        log.warning("alerts: BAT3_ALERT_EMAIL unset; not mailed: %s", subject)
    if client is not None:
        try:
            client.lpush(RECENT_KEY, json.dumps(entry))
            client.ltrim(RECENT_KEY, 0, 19)
        except Exception:
            pass
    return entry["sent"]


def recent() -> list[dict[str, Any]]:
    from .security import _redis_client
    client = _redis_client()
    if client is None:
        return []
    try:
        return [json.loads(x) for x in client.lrange(RECENT_KEY, 0, 19)]
    except Exception:
        return []
