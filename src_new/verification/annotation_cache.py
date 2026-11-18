"""Annotation scores shared between runs and worker pods (2026-11-18).

Each annotation scorer kept successful scores only in memory, and every run
is a new process: the ChEBI entry of water was fetched again in every run.
During an EBI slowdown (2026-11-18: ChEBI answering in 27-48 s or 504) each
run then waited 10 s per entry and scored those matches without the
annotation term. Successful scores are now kept in the cache Redis
(BAT3_SHARED_CACHE_URL) with no expiry: the cache grows (owner's decision,
2026-11-18; expiry once traffic grows). The cache Redis evicts only keys
with an expiry (volatile-lru) and snapshots to disk, so these survive both
memory pressure and restarts (deploy/bioid-cache-redis.yaml).

- Key: identifier type, identifier and whether live fetches were allowed
  (offline and live scores of the same entry can differ).
- Only real scores are stored: a scorer's None (fetch failed, not
  applicable, budget used up) is never cached.
- Any Redis error switches the layer off for a minute in that process.
"""
from __future__ import annotations

import dataclasses
import json
import logging
import os
import time
from typing import Any, Optional

from .models import AnnotationQuality

log = logging.getLogger(__name__)

PREFIX = "bioid:ann:v1"

_client = None
_off_until = 0.0


def _redis():
    global _client
    url = os.environ.get("BAT3_SHARED_CACHE_URL", "").strip()
    if not url or time.time() < _off_until:
        return None
    if _client is None:
        import redis
        _client = redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5)
    return _client


def _trip(exc: Exception) -> None:
    global _off_until
    _off_until = time.time() + 60
    log.warning("annotation cache unavailable (%s); off for 60 s", exc)


def _key(ident_type: str, identifier: str, live_fetch: bool) -> str:
    return f"{PREFIX}:{'live' if live_fetch else 'offline'}:{ident_type}:{identifier}"


def get(ident_type: str, identifier: str, live_fetch: bool) -> Optional[AnnotationQuality]:
    client = _redis()
    if client is None:
        return None
    try:
        raw = client.get(_key(ident_type, identifier, live_fetch))
    except Exception as exc:
        _trip(exc)
        return None
    if not raw:
        return None
    try:
        fields = {f.name for f in dataclasses.fields(AnnotationQuality)}
        return AnnotationQuality(**{k: v for k, v in json.loads(raw).items() if k in fields})
    except (ValueError, TypeError):
        return None


def put(ident_type: str, identifier: str, live_fetch: bool, quality: Any) -> None:
    if not isinstance(quality, AnnotationQuality):
        return
    client = _redis()
    if client is None:
        return
    try:
        client.set(_key(ident_type, identifier, live_fetch),
                   json.dumps(dataclasses.asdict(quality), default=str))
    except Exception as exc:
        _trip(exc)
