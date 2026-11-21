"""Retries for HTTP lookups in remote databases (2026-11-21).

2026-11-21 (mdval audit item 6): PubChem's searches (pubchempy over urllib,
no timeout, no retry), ChEMBL's REST fallback and GlyCosmos made one
attempt each, and a PubChem timeout came back as [] — the same answer as
"not found". One helper for all of them:

- retried: HTTP 429, 5xx, timeouts and connection errors, up to ATTEMPTS
  attempts with jittered backoff (Retry-After honoured, capped);
- not retried: any other 4xx (the query was rejected and would be again),
  a 5xx that is really "not found" (service_stats.not_found_5xx) and a 5xx
  that is a rejection of the query (REJECTED_5XX);
- the caller's stage budget can stop the retries (give_up).

request() returns the last response whatever its status (the caller knows
which statuses are answers); a timeout or connection error that persists is
raised. Requests go through requests.Session.send, so service_stats counts
every attempt.
"""
from __future__ import annotations

import logging
import random
import time
from typing import Callable, Optional
from urllib.parse import urlsplit

import requests

logger = logging.getLogger("identifier")

ATTEMPTS = 3
# delays before the 2nd and 3rd attempt, jittered x0.75-1.25
BACKOFF_S = (2.0, 6.0)
MAX_RETRY_AFTER_S = 30.0

# Hosts that answer a query they cannot process with a 5xx: ChEMBL returns
# 500 "Problem standardizing the query molecule" for a SMILES with an
# impossible valence (C(C)(C)(C)(C)C, 2026-11-21) — an answer, not an outage.
REJECTED_5XX = {"www.ebi.ac.uk": "Problem standardizing the query molecule"}


def _sleep(seconds: float) -> None:  # patched in tests
    time.sleep(seconds)


def rejected_5xx(url: str, status: Optional[int], text: Optional[str]) -> bool:
    """A 5xx that rejects the query (REJECTED_5XX)."""
    if status is None or status < 500:
        return False
    marker = REJECTED_5XX.get(urlsplit(url).hostname or "")
    return bool(marker) and isinstance(text, str) and marker in text


def retryable_status(url: str, status: int, text: Optional[str] = None) -> bool:
    if status == 429:
        return True
    if status < 500:
        return False
    from . import service_stats
    return not (service_stats.not_found_5xx(url, status, text) or rejected_5xx(url, status, text))


def retryable_exception(exc: BaseException) -> bool:
    return isinstance(exc, (requests.exceptions.Timeout, requests.exceptions.ConnectionError,
                            requests.exceptions.ChunkedEncodingError))


def _delay(attempt: int, response: Optional[requests.Response]) -> float:
    base = BACKOFF_S[min(attempt, len(BACKOFF_S) - 1)] * random.uniform(0.75, 1.25)
    after = response.headers.get("Retry-After") if response is not None else None
    try:
        return max(base, min(float(after), MAX_RETRY_AFTER_S)) if after else base
    except (TypeError, ValueError):
        return base


def request(method: str, url: str, *, session: Optional[requests.Session] = None,
            attempts: int = ATTEMPTS, give_up: Optional[Callable[[], bool]] = None,
            **kwargs) -> requests.Response:
    """One HTTP request with retries (module docstring). kwargs go to
    requests (timeout defaults to 30 s)."""
    kwargs.setdefault("timeout", 30)
    send = session.request if session is not None else requests.request
    attempts = max(1, attempts)
    for attempt in range(attempts):
        last = attempt == attempts - 1 or (give_up is not None and give_up())
        try:
            response = send(method, url, **kwargs)
        except requests.exceptions.RequestException as exc:
            if last or not retryable_exception(exc):
                raise
            delay = _delay(attempt, None)
            logger.info("%s %s failed (%s); retry %d/%d after %.1fs",
                        method, urlsplit(url).hostname, type(exc).__name__,
                        attempt + 1, attempts - 1, delay)
            _sleep(delay)
            continue
        status = response.status_code
        if last or not retryable_status(url, status, _text(response)):
            return response
        delay = _delay(attempt, response)
        logger.info("%s %s answered HTTP %s; retry %d/%d after %.1fs",
                    method, urlsplit(url).hostname, status, attempt + 1, attempts - 1, delay)
        _sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover


def _text(response: requests.Response) -> str:
    try:
        return response.text or ""
    except Exception:
        return ""


def body_excerpt(response: requests.Response, n: int = 300) -> str:
    """The first n characters of a response body, on one line (for errors and logs)."""
    return " ".join(_text(response)[:n].split())
