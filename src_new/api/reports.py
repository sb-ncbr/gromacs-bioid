"""'This identification looks wrong' reports (2026-11-17).

Anyone viewing a result can report a molecule; reports land on the admin
page. One JSON file per report under <runs>/_reports/ (atomic, never served:
/files refuses names starting with "_"). Each keeps a snapshot of what BioID
answered, so the report still makes sense after the run expires. Reported
cases are candidates for the nightly known-answers check.
"""
from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .best_hit import coarse_grained_of, molecule_result

DIR = "_reports"
STATUSES = ("open", "resolved", "dismissed")
MAX_NOTE = 2000
PER_HOUR = 20  # per address


class ReportError(ValueError):
    pass


def _dir(runs_dir: Path) -> Path:
    return runs_dir / DIR


def answer_snapshot(data: dict[str, Any], segment: str) -> dict[str, Any]:
    """What BioID said about the segment, as the results page shows it."""
    ver = ((data.get("data") or {}).get("verification") or {}).get(segment) or {}
    r = molecule_result(ver.get("verified_hits") or [], coarse_grained_of(data, segment))
    return {k: r[k] for k in ("state", "database", "identifier", "url", "confidence")} | {
        "name": (r["best"] or {}).get("name") or r.get("name")}


def create(runs_dir: Path, run_id: str, data: dict[str, Any], segment: str,
           note: str = "", suggestion: str = "", ip_hash: Optional[str] = None) -> dict[str, Any]:
    segments = set(((data.get("data") or {}).get("verification") or {})) | set(
        ((data.get("data") or {}).get("identifiers") or {}))
    if segment not in segments:
        raise ReportError(f"Run '{run_id}' has no molecule '{segment}'.")
    now = datetime.now(timezone.utc)
    report = {
        "id": f"{now.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(3)}",
        "run_id": run_id,
        "segment": segment,
        "note": (note or "").strip()[:MAX_NOTE],
        "suggestion": (suggestion or "").strip()[:200],
        "answer": answer_snapshot(data, segment),
        "run_name": (data.get("pipeline") or {}).get("run_name"),
        "created_at": now.isoformat(),
        "status": "open",
        "admin_note": "",
        "reporter_hash": ip_hash,
    }
    _write(runs_dir, report)
    return report


def _write(runs_dir: Path, report: dict[str, Any]) -> None:
    d = _dir(runs_dir)
    d.mkdir(parents=True, exist_ok=True)
    path = d / f"{report['id']}.json"
    tmp = d / f".{report['id']}.{os.urandom(4).hex()}.tmp"
    tmp.write_text(json.dumps(report, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def listing(runs_dir: Path) -> list[dict[str, Any]]:
    """All reports, newest first."""
    out = []
    try:
        files = sorted(_dir(runs_dir).glob("*.json"), reverse=True)
    except OSError:
        return out
    for f in files:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def update(runs_dir: Path, report_id: str, status: Optional[str] = None,
           admin_note: Optional[str] = None) -> dict[str, Any]:
    if not report_id.replace("-", "").replace("T", "").isalnum():
        raise ReportError("unknown report")
    path = _dir(runs_dir) / f"{report_id}.json"
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ReportError("unknown report")
    if status is not None:
        if status not in STATUSES:
            raise ReportError(f"status must be one of {', '.join(STATUSES)}")
        report["status"] = status
    if admin_note is not None:
        report["admin_note"] = admin_note.strip()[:MAX_NOTE]
    _write(runs_dir, report)
    return report


def check_rate(ip_hash: Optional[str]) -> None:
    """ReportError when this address sent PER_HOUR reports this hour (Redis down: allowed)."""
    from .security import _redis_client
    client = _redis_client()
    if client is None or not ip_hash:
        return
    try:
        key = f"bioid:reports:{ip_hash}:{int(time.time() // 3600)}"
        count = int(client.incr(key))
        if count == 1:
            client.expire(key, 3700)
    except Exception:
        return
    if count > PER_HOUR:
        raise ReportError("Too many reports from your network address this hour. Please try again later.")
