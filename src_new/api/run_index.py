"""Cached per-run summaries for the run list and the admin page.

results.json files are 1-5 MB on NFS; listing runs used to parse every one
of them on every request. Summaries are cached per process and a file is
read again only when its size or mtime changes (finished runs never do).

Each request still stats every run's results.json. Under shared-storage
load a stat took ~0.15 s, so 310 runs in a row took 50 s and the main page
hung (2026-11-17); they are issued in parallel now (0.5 s in the same
conditions), and so are the reads of changed files.
"""
from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from src_new.completeness import gaps
from src_new.identification.outcomes import user_warnings
from src_new.retries import lane_of

from . import retention
from .security import valid_run_id

_lock = threading.Lock()
_cache: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}
#: Stats in flight at once (cheap, latency-bound).
_IO_THREADS = 32
#: Changed results.json files read and parsed at once. Each is 1-5 MB and
#: several times that once parsed; 32 at once in each of the API's worker
#: processes, with mdval's runs changing all the time, pushed the API pod
#: to its memory limit and it was OOM-killed (2026-11-17).
_READ_THREADS = 4


def _summary(run_id: str, data: dict[str, Any]) -> dict[str, Any]:
    pipeline = data.get("pipeline") if isinstance(data.get("pipeline"), dict) else {}
    errors = data.get("critical_errors") or []
    first_error = None
    if errors and isinstance(errors[0], dict):
        first_error = str(errors[0].get("message") or errors[0].get("code") or "")[:300]
    return {
        "run_id": run_id,
        "status": pipeline.get("status", "unknown"),
        "run_name": pipeline.get("run_name"),
        "input_kind": pipeline.get("input_kind"),
        "preset": pipeline.get("preset"),
        "created_at": data.get("created_at") or "",
        "started_at": pipeline.get("started_at"),
        "finished_at": pipeline.get("finished_at"),
        "updated_at": data.get("updated_at"),
        "warning_count": len(user_warnings(data.get("warnings"))),
        "error": first_error,
        "retention": retention.describe(data),
        "has_owner_token": bool(pipeline.get("owner_token_sha256")),
        "queue": lane_of(pipeline),
        "attempt": len(pipeline.get("attempts") or []) + 1,
        "retry_at": (pipeline.get("retry") or {}).get("at") if pipeline.get("status") == "retry_scheduled" else None,
        "incomplete": sum(g["count"] for g in gaps(data)),
        "superseded_by": pipeline.get("superseded_by"),
        # internal (never returned by public routes)
        "_pipeline": {k: pipeline.get(k) for k in ("creator_ip", "creator_ip_hash")},
    }


def _stat(path: Path):
    try:
        return path.stat()
    except OSError:
        return None


def _read(name: str, path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return _summary(name, data) if isinstance(data, dict) else None


def summaries(runs_dir: Path) -> list[dict[str, Any]]:
    """One summary per run directory (unreadable or malformed runs skipped)."""
    try:
        entries = list(os.scandir(runs_dir))
    except FileNotFoundError:
        return []
    names = [e.name for e in entries
             if not e.name.startswith((".", "_")) and valid_run_id(e.name) and e.is_dir()]
    paths = {name: runs_dir / name / "results.json" for name in names}
    with ThreadPoolExecutor(_IO_THREADS) as pool:
        stats = dict(zip(names, pool.map(_stat, paths.values())))
        found: dict[str, dict[str, Any]] = {}
        stale: dict[str, tuple[int, int]] = {}
        for name in names:
            st = stats[name]
            if st is None:
                continue
            key = (st.st_size, st.st_mtime_ns)
            with _lock:
                hit = _cache.get(name)
            if hit and hit[0] == key:
                found[name] = hit[1]
            else:
                stale[name] = key
    with ThreadPoolExecutor(_READ_THREADS) as readers:
        for name, summary in zip(stale, readers.map(_read, stale, [paths[n] for n in stale])):
            if summary is None:
                continue
            with _lock:
                _cache[name] = (stale[name], summary)
            found[name] = summary
    with _lock:
        for gone in set(_cache) - set(found):
            _cache.pop(gone, None)
    return [found[name] for name in names if name in found]
