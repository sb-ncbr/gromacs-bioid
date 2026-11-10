"""Cached per-run summaries for the run list and the admin page.

results.json files are 1-5 MB on NFS; listing runs used to parse every one
of them on every request. Summaries are cached per process and a file is
read again only when its size or mtime changes (finished runs never do).
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any

from . import retention
from .security import valid_run_id

_lock = threading.Lock()
_cache: dict[str, tuple[tuple[int, int], dict[str, Any]]] = {}


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
        "warning_count": len(data.get("warnings") or []),
        "error": first_error,
        "retention": retention.describe(data),
        "has_owner_token": bool(pipeline.get("owner_token_sha256")),
        # internal (never returned by public routes)
        "_pipeline": {k: pipeline.get(k) for k in ("creator_ip", "creator_ip_hash")},
    }


def summaries(runs_dir: Path) -> list[dict[str, Any]]:
    """One summary per run directory (unreadable or malformed runs skipped)."""
    out = []
    seen = set()
    try:
        entries = list(os.scandir(runs_dir))
    except FileNotFoundError:
        return out
    for entry in entries:
        name = entry.name
        if name.startswith((".", "_")) or not valid_run_id(name) or not entry.is_dir():
            continue
        path = Path(entry.path) / "results.json"
        try:
            st = path.stat()
        except OSError:
            continue
        key = (st.st_size, st.st_mtime_ns)
        seen.add(name)
        with _lock:
            hit = _cache.get(name)
        if hit and hit[0] == key:
            out.append(hit[1])
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        summary = _summary(name, data)
        with _lock:
            _cache[name] = (key, summary)
        out.append(summary)
    with _lock:
        for gone in set(_cache) - seen:
            _cache.pop(gone, None)
    return out
