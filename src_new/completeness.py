"""Is a run incomplete for reasons another attempt could fix? (2026-11-18)

A finished run can lack answers because a remote database was down, busy or
slow, or because a stage ran out of time. Those gaps are already recorded as
warnings; this reads them. Used by the API (the "incomplete" field, the
re-run button) and by the workers (automatic retries, retries.py).

Not counted: not-applicable outcomes, local BLAST/Foldseek timeouts (they
would time out again) and rejected queries (outcomes.failure_class).
"""
from __future__ import annotations

from typing import Any

from .identification.outcomes import RETRYABLE, failure_class

#: warning code -> service name when the warning does not name one
CODES = {
    "identifier_resolver_failed": None,
    "stage_time_budget": "time limit",
    "structure_search_unavailable": "RCSB structure search",
    "verification_failed": "verification",
    "annotation_fetch_failed": None,  # details.service, e.g. chebi_annotation
}


def _segment(code: str, warning: dict[str, Any]) -> str | None:
    details = warning.get("details") or {}
    seg = details.get("segment") or details.get("fragment")
    if seg:
        return str(seg)
    if code == "verification_failed":  # message "<segment>: <error>"
        head = str(warning.get("message") or "").split(":", 1)[0].strip()
        return head or None
    return None


def gaps(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Retryable gaps of a run, one entry per (code, service, reason):
    {code, service, reason, segments, count, example}."""
    out: dict[tuple[str, str, str], dict[str, Any]] = {}
    for w in data.get("warnings") or []:
        if not isinstance(w, dict):
            continue
        code = w.get("code")
        if code not in CODES:
            continue
        message = str(w.get("message") or "")
        reason = "budget" if code == "stage_time_budget" else failure_class(message)
        if reason not in RETRYABLE:
            continue
        details = w.get("details") or {}
        service = details.get("service") or CODES[code] or message.split(" (", 1)[0][:60]
        if code == "stage_time_budget" and w.get("step_id"):
            service = f"time limit ({w['step_id']})"
        item = out.setdefault((code, service, reason), {
            "code": code, "service": service, "reason": reason,
            "segments": [], "count": 0, "example": message[:200]})
        item["count"] += int(details.get("count") or 1) if code == "annotation_fetch_failed" else 1
        seg = _segment(code, w)
        if seg and seg not in item["segments"]:
            item["segments"].append(seg)
    return sorted(out.values(), key=lambda g: (-g["count"], g["service"]))


def is_incomplete(data: dict[str, Any]) -> bool:
    return bool(gaps(data))
