"""Calls to databases and web services, counted per service (2026-11-18).

Measure only: nothing here changes a request, a result or an error. Two
sources feed it:

- every database lookup of the identify stage (IdentifierResolver.resolve:
  local BLAST and Foldseek as well as remote searches), as "db:<resolver>";
- every HTTP request a worker makes (requests.Session.send, patched once at
  worker start), as "http:<host>", which covers the verification stage's
  fetches too. (ChEMBL's REST fallback uses requests since 2026-11-21.)

Counts are kept in memory and written every 10 s by a background thread to
the cache-only Redis (BAT3_SHARED_CACHE_URL) in 5-minute buckets kept for
48 h, so a call never waits for Redis. Searches in progress are published
per process under a key that expires 60 s after its last refresh: a killed
pod's searches disappear on their own. Any Redis error drops that batch and
switches writing off for a minute. Without the URL nothing is written.

Each run also keeps its own totals (run_summary), persisted with the run
under data/run_health/service_calls.
"""
from __future__ import annotations

import itertools
import json
import logging
import os
import threading
import time
from collections import Counter
from contextlib import contextmanager
from typing import Any, Iterator, Optional

log = logging.getLogger(__name__)

PREFIX = "bioid:ss:v1"
BUCKET_S = 300
KEEP_S = 48 * 3600
FLUSH_S = 10.0
PROC_TTL_S = 60
# Latency bins (s, upper bounds); a time above the last one counts as "inf".
LAT_BINS = (0.1, 0.3, 1, 3, 10, 30, 100, 300, 1000, 3600, 43200)
#: outcomes that are not calls to the service (answered from a cache)
CACHE_OUTCOMES = frozenset({"cache_shared", "cache_local"})

_lock = threading.Lock()
_pending: Counter = Counter()      # (bucket, field) -> n
_run: Counter = Counter()          # "service|stage|outcome" -> n, this process
_inflight: dict[int, dict[str, Any]] = {}
_tokens = itertools.count(1)
_stage = "other"
_flusher_pid: Optional[int] = None
_client = None
_off_until = 0.0


def _after_fork() -> None:
    """A forked pipeline child starts with empty counts and no flusher."""
    global _lock, _flusher_pid, _client
    _lock = threading.Lock()
    _pending.clear()
    _run.clear()
    _inflight.clear()
    _flusher_pid = None
    _client = None


if hasattr(os, "register_at_fork"):
    os.register_at_fork(after_in_child=_after_fork)


def set_stage(stage: str) -> None:
    """The pipeline stage now running in this process (one run per process)."""
    global _stage
    _stage = stage or "other"


def _bin(seconds: float) -> str:
    for upper in LAT_BINS:
        if seconds <= upper:
            return str(upper)
    return "inf"


def record(service: str, outcome: str, seconds: Optional[float] = None, retries: int = 0) -> None:
    """Count one call. Never raises."""
    try:
        stage = _stage
        bucket = int(time.time() // BUCKET_S)
        base = f"{service}|{stage}"
        with _lock:
            _pending[(bucket, f"{base}|{outcome}")] += 1
            if seconds is not None:
                _pending[(bucket, f"{base}|ms")] += int(seconds * 1000)
                _pending[(bucket, f"{base}|lat:{_bin(seconds)}")] += 1
            if retries:
                _pending[(bucket, f"{base}|retries")] += int(retries)
                _run[f"{base}|retries"] += int(retries)
            _run[f"{base}|{outcome}"] += 1
        _ensure_flusher()
    except Exception:
        pass


@contextmanager
def in_flight(service: str) -> Iterator[None]:
    """Mark a search as running while the block runs. Never raises itself."""
    token = None
    try:
        token = next(_tokens)
        with _lock:
            _inflight[token] = {"service": service, "stage": _stage, "started": time.time()}
        _ensure_flusher()
    except Exception:
        token = None
    try:
        yield
    finally:
        if token is not None:
            try:
                with _lock:
                    _inflight.pop(token, None)
            except Exception:
                pass


def run_summary() -> dict[str, int]:
    """This process's counts ("service|stage|outcome" -> n)."""
    with _lock:
        return dict(_run)


def reset_run() -> None:
    with _lock:
        _run.clear()


# -- writing ---------------------------------------------------------------------

def _redis():
    global _client
    url = os.environ.get("BAT3_SHARED_CACHE_URL", "").strip()
    if not url or time.time() < _off_until:
        return None
    if _client is None:
        import redis
        _client = redis.Redis.from_url(url, socket_timeout=1.0, socket_connect_timeout=1.0)
    return _client


def _trip(exc: Exception) -> None:
    global _off_until
    _off_until = time.time() + 60
    log.warning("service stats: Redis unavailable (%s); off for 60 s", exc)


def _proc_key() -> str:
    return f"{PREFIX}:proc:{os.environ.get('HOSTNAME', 'local')}:{os.getpid()}"


def flush() -> None:
    """Write pending counts and the searches in progress. Never raises."""
    try:
        with _lock:
            pending = dict(_pending)
            _pending.clear()
            running = list(_inflight.values())
        client = _redis()
        if client is None:
            return
        pipe = client.pipeline(transaction=False)
        for bucket in {b for b, _ in pending}:
            key = f"{PREFIX}:b:{bucket}"
            for (b, field), n in pending.items():
                if b == bucket:
                    pipe.hincrby(key, field, n)
            pipe.expire(key, KEEP_S)
        if running:
            pipe.set(_proc_key(), json.dumps({"pod": os.environ.get("HOSTNAME", ""),
                                              "running": running}), ex=PROC_TTL_S)
        else:
            pipe.delete(_proc_key())
        pipe.execute()
    except Exception as exc:
        _trip(exc)


def _loop() -> None:
    while True:
        time.sleep(FLUSH_S)
        flush()


def _ensure_flusher() -> None:
    global _flusher_pid
    if _flusher_pid == os.getpid() or not os.environ.get("BAT3_SHARED_CACHE_URL"):
        return
    _flusher_pid = os.getpid()
    threading.Thread(target=_loop, name="service-stats-flush", daemon=True).start()


# -- HTTP ------------------------------------------------------------------------

# Hosts that answer "not found" with a 5xx status: CACTUS returns 500 with a
# "Page not found (404)" page for an InChIKey it does not know (2026-11-20).
NOT_FOUND_5XX = {"cactus.nci.nih.gov": "Page not found"}


def not_found_5xx(url: str, status: Optional[int], text: Optional[str]) -> bool:
    """A 5xx that is really 'not found' (NOT_FOUND_5XX)."""
    if status is None or status < 500:
        return False
    from urllib.parse import urlsplit
    marker = NOT_FOUND_5XX.get(urlsplit(url).hostname or "")
    return bool(marker) and isinstance(text, str) and marker in text


def _http_outcome(status: Optional[int], exc: Optional[BaseException]) -> str:
    if exc is not None:
        return f"error:{type(exc).__name__}"
    if status == 429:
        return "http_429"
    if status is not None and status >= 500:
        return "http_5xx"
    if status is not None and status >= 400:
        return "http_4xx"
    return "ok"


def record_http(url: str, status: Optional[int], seconds: float,
                exc: Optional[BaseException] = None, retries: int = 0) -> None:
    try:
        from urllib.parse import urlsplit
        host = urlsplit(url).hostname or "?"
        record(f"http:{host}", _http_outcome(status, exc), seconds, retries)
    except Exception:
        pass


def install_http_hook() -> bool:
    """Count every requests.Session.send (idempotent). True when installed."""
    try:
        import requests
    except ImportError:
        return False
    send = requests.Session.send
    if getattr(send, "_service_stats", False):
        return True

    def counted_send(self, request, **kwargs):
        t0 = time.monotonic()
        try:
            response = send(self, request, **kwargs)
        except BaseException as exc:
            record_http(getattr(request, "url", ""), None, time.monotonic() - t0, exc)
            raise
        try:
            retries = getattr(getattr(response.raw, "retries", None), "history", None) or ()
            status = response.status_code
            if status >= 500 and not kwargs.get("stream") and not_found_5xx(
                    request.url, status, getattr(response, "text", "")):
                status = 404
            record_http(request.url, status, time.monotonic() - t0, retries=len(retries))
        except Exception:
            pass
        return response

    counted_send._service_stats = True  # type: ignore[attr-defined]
    requests.Session.send = counted_send
    return True


# -- reading (API) ---------------------------------------------------------------

def _p(bins: Counter, q: float) -> Optional[float]:
    total = sum(bins.values())
    if not total:
        return None
    seen = 0
    for upper in [*map(str, LAT_BINS), "inf"]:
        seen += bins.get(upper, 0)
        if seen >= q * total:
            return float(upper) if upper != "inf" else float("inf")
    return None


def summarize(fields: dict[str, int]) -> list[dict[str, Any]]:
    """Per service and stage: calls by outcome, errors, retries, mean and
    approximate p50/p95 (upper edge of the latency bin)."""
    rows: dict[tuple[str, str], dict[str, Any]] = {}
    for field, n in fields.items():
        try:
            service, stage, what = field.split("|", 2)
        except ValueError:
            continue
        row = rows.setdefault((service, stage), {"service": service, "stage": stage,
                                                 "outcomes": Counter(), "ms": 0,
                                                 "bins": Counter(), "retries": 0})
        if what == "ms":
            row["ms"] += n
        elif what == "retries":
            row["retries"] += n
        elif what.startswith("lat:"):
            row["bins"][what[4:]] += n
        else:
            row["outcomes"][what] += n
    out = []
    for row in rows.values():
        outcomes: Counter = row["outcomes"]
        live = sum(n for o, n in outcomes.items() if o not in CACHE_OUTCOMES)
        errors = sum(n for o, n in outcomes.items()
                     if o.startswith("error") or o in ("http_5xx", "http_429"))
        timed = sum(row["bins"].values())
        out.append({
            "service": row["service"], "stage": row["stage"],
            "calls": live, "cached": sum(outcomes[o] for o in CACHE_OUTCOMES),
            "errors": errors, "error_share": round(errors / live, 3) if live else None,
            "retries": row["retries"], "outcomes": dict(outcomes),
            "mean_s": round(row["ms"] / 1000 / timed, 3) if timed else None,
            "p50_s": _p(row["bins"], 0.5), "p95_s": _p(row["bins"], 0.95),
        })
    out.sort(key=lambda r: (-(r["errors"] or 0), -(r["calls"] or 0), r["service"]))
    return out


def window(client, seconds: int, now: Optional[float] = None) -> dict[str, int]:
    """Summed bucket fields over the last `seconds`."""
    now = now or time.time()
    last = int(now // BUCKET_S)
    first = int((now - seconds) // BUCKET_S) + 1
    pipe = client.pipeline(transaction=False)
    for b in range(first, last + 1):
        pipe.hgetall(f"{PREFIX}:b:{b}")
    total: Counter = Counter()
    for h in pipe.execute():
        for k, v in (h or {}).items():
            total[k.decode() if isinstance(k, bytes) else k] += int(v)
    return dict(total)


def series(client, service: str, hours: int = 24, now: Optional[float] = None) -> list[dict[str, Any]]:
    """Calls and errors per hour for one service (all stages)."""
    now = now or time.time()
    out = []
    for h in range(hours, 0, -1):
        end = now - (h - 1) * 3600
        rows = [r for r in summarize(window(client, 3600, end)) if r["service"] == service]
        out.append({"hour_end": int(end), "calls": sum(r["calls"] for r in rows),
                    "errors": sum(r["errors"] for r in rows)})
    return out


def running_now(client) -> list[dict[str, Any]]:
    """Searches in progress on every live worker process."""
    out = []
    for key in client.scan_iter(match=f"{PREFIX}:proc:*", count=500):
        raw = client.get(key)
        if not raw:
            continue
        try:
            value = json.loads(raw)
        except ValueError:
            continue
        for item in value.get("running") or []:
            out.append({**item, "pod": value.get("pod", "")})
    out.sort(key=lambda r: r.get("started", 0))
    return out


def reader():
    """Redis client for the API's readers, or None when not configured."""
    return _redis()


# -- checks (admin page, watchdog alarms) ------------------------------------------

#: NCBI databases read from the shared NFS volume (Deep search).
NCBI_SERVICES = frozenset(f"db:{n}{s}" for n in ("blast_nr_protein", "blast_nt", "blast_core_nt")
                          for s in ("", "@sim"))
#: Alarm when a service failed at least this share of at least this many calls in 30 min.
DOWN_SHARE, DOWN_MIN_CALLS = 0.5, 10


def ncbi_alarm_at() -> int:
    """NCBI searches running at once that raise an alarm: they share ~50 MB/s,
    so at 3 each nr search needs ~6.6 h and at 6 none fits the 12 h limit."""
    try:
        return max(1, int(os.environ.get("BAT3_NCBI_RUNNING_ALARM", "3")))
    except ValueError:
        return 3


def failing(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Services failing in `rows` (a summarize() of the last 30 min), all stages together."""
    by: dict[str, dict[str, Any]] = {}
    for r in rows:
        agg = by.setdefault(r["service"], {"service": r["service"], "calls": 0, "errors": 0,
                                           "outcomes": Counter()})
        agg["calls"] += r["calls"]
        agg["errors"] += r["errors"]
        agg["outcomes"].update(r["outcomes"])
    return [{**a, "outcomes": dict(a["outcomes"])} for a in by.values()
            if a["calls"] >= DOWN_MIN_CALLS and a["errors"] / a["calls"] >= DOWN_SHARE]
