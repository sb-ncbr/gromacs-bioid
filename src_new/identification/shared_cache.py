"""Resolver results shared between worker pods (2026-11-17).

Every pod keeps its own SQLite resolver cache (cache_manager.py); a shared
SQLite file on NFS was corrupted repeatedly, so the shared layer is a
cache-only Redis (BAT3_SHARED_CACHE_URL; unset = off), separate from the
Celery broker so a full cache can never touch the job queue: it runs with a
memory cap and least-recently-used eviction.

- Key: resolver, mode, sha256(signature) and a fingerprint of the settings
  that shape resolver answers (thresholds, database paths, search modes),
  so runs with different settings never share answers. Timeouts, threads
  and which resolvers a preset enables are left out.
- Value: the result and its hits metadata. The local SQLite cache drops
  the metadata, and without it the deferred nr/nt skip (supplementary.py)
  cannot see that an exact match exists; the shared layer is read first.
- Only non-empty results without an error are stored (as the local cache):
  a transient failure must never be cached as "no hits".
- Any Redis error switches the layer off for a minute in that process.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from typing import Any, Optional

log = logging.getLogger(__name__)

PREFIX = "bioid:rc:v1"
TTL_S = 30 * 86400
_ANSWER_SECTIONS = ("blast", "chembl", "idsm", "pubchem", "alphafind", "pdb", "foldseek", "names")
_IGNORED_FIELDS = ("curr_uuid", "adhoc_files_dir", "deployment_file_url", "use_deployment_file_access",
                   "ssh_", "timeout", "retry", "poll", "num_threads", "_exec")

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
    log.warning("shared resolver cache unavailable (%s); off for 60 s", exc)


def fingerprint(config: Any) -> str:
    """Hash of the settings that shape resolver answers (cached on the config)."""
    cached = getattr(config, "_shared_cache_fp", None)
    if cached:
        return cached
    full = config.to_dict()
    picked = {s: {k: v for k, v in (full.get(s) or {}).items()
                  if not any(f in k for f in _IGNORED_FIELDS)}
              for s in _ANSWER_SECTIONS}
    fp = hashlib.sha256(json.dumps(picked, sort_keys=True, default=str).encode()).hexdigest()[:16]
    try:
        object.__setattr__(config, "_shared_cache_fp", fp)
    except Exception:
        pass
    return fp


def _key(resolver: Any, signature: str, similarity: bool) -> str:
    sig = hashlib.sha256(signature.encode("utf-8", "surrogatepass")).hexdigest()
    return f"{PREFIX}:{fingerprint(resolver.config)}:{resolver.name}:{'sim' if similarity else 'id'}:{sig}"


def get(resolver: Any, signature: str, similarity: bool) -> Optional[tuple[list, Optional[dict]]]:
    """(result, hits metadata) or None on a miss / when off."""
    client = _redis()
    if client is None:
        return None
    try:
        raw = client.get(_key(resolver, signature, similarity))
    except Exception as exc:
        _trip(exc)
        return None
    if not raw:
        return None
    try:
        value = json.loads(raw)
        result = value["r"]
        if similarity:
            result = [(str(i), float(s)) for i, s in result]
        return result, value.get("m")
    except (ValueError, KeyError, TypeError):
        return None


def put(resolver: Any, signature: str, similarity: bool, result: Any, metadata: Optional[dict]) -> None:
    if not result or not isinstance(result, list):
        return
    client = _redis()
    if client is None:
        return
    try:
        value = json.dumps({"r": result, "m": metadata}, default=str)
        client.set(_key(resolver, signature, similarity), value, ex=TTL_S)
    except Exception as exc:
        _trip(exc)
