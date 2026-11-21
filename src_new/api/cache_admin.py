"""The shared cache on the admin page (2026-11-21).

The cache-only Redis (BAT3_SHARED_CACHE_URL, deploy/bioid-cache-redis.yaml)
holds three kinds of keys:

- resolver results (identification/shared_cache.py, bioid:rc:v1, 30-day TTL),
- annotation scores (verification/annotation_cache.py, bioid:ann:v1, no TTL),
- the service measurements (service_stats.py, bioid:ss:v1, 48 h).

With maxmemory-policy volatile-lru only keys with a TTL are evicted when the
memory is full: resolver results and measurements, never annotation scores.

This module reads Redis's memory and counters, counts keys per kind (and
resolver results per database), works out how often the identify stage's
lookups were answered from a cache, and purges resolver results (all, or
one database) or annotation scores in a background thread.
"""
from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections import Counter
from typing import Any, Optional

log = logging.getLogger(__name__)

KINDS = {
    "results": {"prefix": "bioid:rc:v1:", "label": "Resolver results", "expires": "30 days"},
    "annotations": {"prefix": "bioid:ann:v1:", "label": "Annotation scores", "expires": "never"},
    "measurements": {"prefix": "bioid:ss:v1:", "label": "Service measurements", "expires": "48 h"},
}
PURGEABLE = ("results", "annotations")
SCAN_COUNT = 10_000
SAMPLE = 200          # keys per kind whose memory is measured
BATCH = 1_000         # keys per UNLINK
HOURS = 48            # the measurements' retention

_client = None
_purge_lock = threading.Lock()
_purge: dict[str, Any] = {}


def client():
    """Redis for the admin readers (longer timeouts than the hot paths), or None."""
    global _client
    url = os.environ.get("BAT3_SHARED_CACHE_URL", "").strip()
    if not url:
        return None
    if _client is None:
        import redis
        _client = redis.Redis.from_url(url, socket_timeout=15.0, socket_connect_timeout=2.0)
    return _client


def _s(v) -> str:
    return v.decode() if isinstance(v, bytes) else str(v)


def redis_info(r) -> dict[str, Any]:
    info: dict[str, Any] = {}
    for section in ("memory", "stats", "server"):
        info.update(r.info(section))
    hits, misses = int(info.get("keyspace_hits", 0)), int(info.get("keyspace_misses", 0))
    return {
        "used_bytes": int(info.get("used_memory", 0)),
        "max_bytes": int(info.get("maxmemory", 0)),
        "policy": _s(info.get("maxmemory_policy", "")),
        "keys": int(r.dbsize()),
        "evicted": int(info.get("evicted_keys", 0)),
        "expired": int(info.get("expired_keys", 0)),
        "hits": hits, "misses": misses,
        "hit_share": round(hits / (hits + misses), 3) if hits + misses else None,
        "uptime_s": int(info.get("uptime_in_seconds", 0)),
    }


def _result_key(key: str) -> Optional[tuple[str, str]]:
    """bioid:rc:v1:<fp>:<cache_name>:<id|sim>:<sha> -> (cache_name, id|sim)."""
    parts = key.split(":")
    return (parts[4], parts[5]) if len(parts) == 7 else None


def keys_summary(r) -> dict[str, Any]:
    """Keys and estimated memory per kind; resolver results per database."""
    counts: Counter = Counter()
    samples: dict[str, list[str]] = {k: [] for k in KINDS}
    by_db: dict[str, Counter] = {}
    other = 0
    for raw in r.scan_iter(count=SCAN_COUNT):
        key = _s(raw)
        kind = next((k for k, v in KINDS.items() if key.startswith(v["prefix"])), None)
        if kind is None:
            other += 1
            continue
        counts[kind] += 1
        if len(samples[kind]) < SAMPLE:
            samples[kind].append(key)
        if kind == "results":
            parsed = _result_key(key)
            if parsed:
                by_db.setdefault(parsed[0], Counter())[parsed[1]] += 1
    kinds = []
    for kind, meta in KINDS.items():
        sizes = []
        if samples[kind]:
            pipe = r.pipeline(transaction=False)
            for key in samples[kind]:
                pipe.memory_usage(key)
            sizes = [int(s) for s in pipe.execute() if s is not None]
        avg = sum(sizes) / len(sizes) if sizes else 0
        kinds.append({"kind": kind, "label": meta["label"], "expires": meta["expires"],
                      "keys": counts[kind], "est_bytes": int(avg * counts[kind]),
                      "purgeable": kind in PURGEABLE})
    databases = []
    for cache_name, c in by_db.items():
        resolver, _, release = cache_name.partition("@")
        databases.append({"cache_name": cache_name, "resolver": resolver, "release": release or None,
                          "identity": c.get("id", 0), "similarity": c.get("sim", 0),
                          "keys": c.get("id", 0) + c.get("sim", 0)})
    databases.sort(key=lambda d: -d["keys"])
    return {"kinds": kinds, "databases": databases, "other_keys": other, "counted_at": time.time()}


def _lookups(fields: dict[str, int]) -> dict[str, Counter]:
    """Identify-stage lookups per database: answered by the shared cache, by
    a worker's local cache, or searched live (service_stats outcomes)."""
    from src_new.service_stats import CACHE_OUTCOMES
    out: dict[str, Counter] = {}
    for field, n in fields.items():
        try:
            service, _stage, what = field.split("|", 2)
        except ValueError:
            continue
        if not service.startswith("db:") or what in ("ms", "retries") or what.startswith("lat:"):
            continue
        c = out.setdefault(service[3:], Counter())
        c["shared" if what == "cache_shared" else "local" if what in CACHE_OUTCOMES else "live"] += n
    return out


def _share(c: Counter) -> Optional[float]:
    total = c["shared"] + c["local"] + c["live"]
    return round((c["shared"] + c["local"]) / total, 3) if total else None


def usage(r, now: Optional[float] = None) -> dict[str, Any]:
    """Cache answers per database (last 24 h) and per hour (last 48 h)."""
    from src_new import service_stats as ss
    now = now or time.time()
    rows = []
    for name, c in _lookups(ss.window(r, 86400, now)).items():
        rows.append({"service": name, "shared": c["shared"], "local": c["local"], "live": c["live"],
                     "answered_share": _share(c)})
    rows.sort(key=lambda x: -(x["shared"] + x["local"] + x["live"]))
    hour = 3600
    end = (int(now) // hour + 1) * hour
    hourly = []
    for h in range(HOURS, 0, -1):
        t_end = end - (h - 1) * hour
        total: Counter = Counter()
        for c in _lookups(ss.window(r, hour, t_end - 1)).values():
            total.update(c)
        hourly.append({"t": t_end - hour, "shared": total["shared"], "local": total["local"],
                       "live": total["live"], "answered_share": _share(total)})
    total = Counter()
    for x in rows:
        total.update({"shared": x["shared"], "local": x["local"], "live": x["live"]})
    return {"last_24h": rows, "total_24h": {**total, "answered_share": _share(total)}, "hourly": hourly}


# -- purge ---------------------------------------------------------------------

def purge_state() -> dict[str, Any]:
    with _purge_lock:
        return dict(_purge)


def _pattern(kind: str, cache_name: Optional[str]) -> str:
    prefix = KINDS[kind]["prefix"]
    if cache_name:
        return f"{prefix}*:{cache_name}:*"
    return f"{prefix}*"


def start_purge(r, kind: str, cache_name: Optional[str] = None) -> dict[str, Any]:
    """Delete resolver results (all, or one database: its cache name, e.g.
    'blast_nr_protein@2026-10-22') or every annotation score, in a thread."""
    if kind not in PURGEABLE:
        raise ValueError(f"Only {', '.join(PURGEABLE)} can be purged.")
    if cache_name and (kind != "results" or not re.fullmatch(r"[A-Za-z0-9_.-]+(@[A-Za-z0-9_.-]+)?", cache_name)
                       or cache_name in ("id", "sim")):
        raise ValueError("A database can only be named for resolver results, by its cache name.")
    with _purge_lock:
        if _purge.get("running"):
            raise RuntimeError("A purge is already running.")
        _purge.clear()
        _purge.update(running=True, kind=kind, cache_name=cache_name, deleted=0,
                      started_at=time.time(), finished_at=None, error=None)
    threading.Thread(target=_run_purge, args=(r, _pattern(kind, cache_name)),
                     name="cache-purge", daemon=True).start()
    return purge_state()


def _run_purge(r, pattern: str) -> None:
    deleted = 0
    try:
        batch: list = []
        for key in r.scan_iter(match=pattern, count=SCAN_COUNT):
            batch.append(key)
            if len(batch) >= BATCH:
                deleted += r.unlink(*batch)
                batch = []
                with _purge_lock:
                    _purge["deleted"] = deleted
        if batch:
            deleted += r.unlink(*batch)
        error = None
    except Exception as exc:
        log.warning("cache purge %s failed: %s", pattern, exc)
        error = str(exc)
    with _purge_lock:
        _purge.update(running=False, deleted=deleted, finished_at=time.time(), error=error)
    log.info("cache purge %s: %d keys deleted", pattern, deleted)
