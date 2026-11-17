"""Run retention: finished runs are removed after their retention period.

Policy per run, in results.json pipeline.retention:
    {"policy": "default"}                 BAT3_RETENTION_DAYS (30) after it finished
    {"policy": "days", "days": N}         N days after it finished (1-365)
    {"policy": "preserve"}                kept indefinitely
Runs without the field (submitted before 2026-11-10) get the default period
counted from POLICY_START, so nothing older expires before 2026-12-10.

Safety, because a wrong deletion cannot be undone:
- Report-only unless BAT3_RETENTION_ENFORCE=1: the sweep computes what would
  expire (shown on the admin page) and touches nothing.
- Never deleted: the example runs (BAT3_EXAMPLE_RUNS and whatever the
  examples endpoint serves), preserved runs, runs not in a final state,
  results.json written in the last hour, anything that is not a plain run
  directory (names starting "_", symlinks, missing or unreadable results.json).
- Expired runs are MOVED to <runs>/_expired/<run_id> (same filesystem, a
  rename) and purged only BAT3_RETENTION_GRACE_DAYS (7) later; until then the
  admin page can restore them.
- At most MAX_PER_SWEEP (50) runs are expired per hourly sweep, oldest due
  first; the rest wait for the next sweeps (up to 1,200 a day).
- Circuit breaker: if runs on the default policy alone are due for more than
  half of all runs (a wrong BAT3_RETENTION_DAYS, a clock jump), the sweep
  expires nothing and logs an error. Runs submitted with their own short
  retention (e.g. a campaign's 1 day) are not counted against it.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from .security import valid_run_id

log = logging.getLogger(__name__)

POLICY_START = datetime(2026, 11, 10, tzinfo=timezone.utc)
EXPIRED_DIR = "_expired"
TERMINAL = {"success", "failed", "cancelled", "timeout", "error"}
MAX_CUSTOM_DAYS = 365
#: What the owner of a finished run may choose on the results page, in days
#: from that moment. "preserve" stays admin-only (2026-11-17).
OWNER_CHOICES = (30, 90, 180, 365)
MAX_PER_SWEEP = int(os.environ.get("BAT3_RETENTION_MAX_PER_SWEEP", "50"))
FRESH_WRITE_S = 3600


def default_days() -> int:
    return int(os.environ.get("BAT3_RETENTION_DAYS", "30"))


def grace_days() -> int:
    return int(os.environ.get("BAT3_RETENTION_GRACE_DAYS", "7"))


def enforcing() -> bool:
    return os.environ.get("BAT3_RETENTION_ENFORCE", "0") == "1"


class RetentionError(ValueError):
    pass


def parse_retention(value: Optional[str]) -> dict[str, Any]:
    """The `retention` form field: '' / 'default', a number of days, or 'preserve'."""
    raw = (value or "").strip().lower()
    if raw in ("", "default"):
        return {"policy": "default"}
    if raw == "preserve":
        return {"policy": "preserve"}
    try:
        days = int(raw)
    except ValueError:
        raise RetentionError("retention must be 'default', 'preserve' or a number of days")
    if not 1 <= days <= MAX_CUSTOM_DAYS:
        raise RetentionError(f"retention must be between 1 and {MAX_CUSTOM_DAYS} days")
    return {"policy": "days", "days": days}


def _parse_time(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def expires_at(data: dict[str, Any]) -> Optional[datetime]:
    """When a run expires; None = never (preserved, or not finished)."""
    pipeline = data.get("pipeline") if isinstance(data.get("pipeline"), dict) else {}
    if pipeline.get("status") not in TERMINAL:
        return None
    retention = pipeline.get("retention")
    finished = (_parse_time(pipeline.get("finished_at")) or _parse_time(data.get("updated_at"))
                or _parse_time(data.get("created_at")))
    if finished is None:
        return None
    if not isinstance(retention, dict):
        # submitted before retention existed: the default period from POLICY_START
        return max(finished, POLICY_START) + timedelta(days=default_days())
    policy = retention.get("policy")
    if policy == "preserve":
        return None
    if policy == "days" and isinstance(retention.get("days"), int) and retention["days"] > 0:
        # "from": the owner chose to keep the run N days from that moment
        return (_parse_time(retention.get("from")) or finished) + timedelta(days=retention["days"])
    return finished + timedelta(days=default_days())


def describe(data: dict[str, Any]) -> dict[str, Any]:
    """Retention as shown to people: policy, days and expiry (ISO) or None."""
    pipeline = data.get("pipeline") if isinstance(data.get("pipeline"), dict) else {}
    retention = pipeline.get("retention") if isinstance(pipeline.get("retention"), dict) else None
    exp = expires_at(data)
    policy = retention.get("policy") if retention else "default"
    days = retention.get("days") if retention and policy == "days" else (
        None if policy == "preserve" else default_days())
    return {"policy": policy, "days": days, "expires_at": exp.isoformat() if exp else None}


def keep_for(run_dir: Path, days: int, now: Optional[datetime] = None) -> dict[str, Any]:
    """The owner keeps a finished run `days` (OWNER_CHOICES) from now; returns describe().

    Only extends: RetentionError if the run is not finished, is kept
    permanently, or would expire no later than it does already.
    """
    if days not in OWNER_CHOICES:
        raise RetentionError(f"days must be one of {', '.join(map(str, OWNER_CHOICES))}")
    now = now or datetime.now(timezone.utc)
    data = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    pipeline = data.get("pipeline") if isinstance(data.get("pipeline"), dict) else {}
    if pipeline.get("status") not in TERMINAL:
        raise RetentionError("A run can be kept longer once it has finished.")
    current = expires_at(data)
    if current is None:
        raise RetentionError("This run is already kept permanently.")
    new = now + timedelta(days=days)
    if new <= current:
        raise RetentionError(f"This run is already kept until {current.date().isoformat()}.")
    set_policy(run_dir, {"policy": "days", "days": days, "from": now.isoformat()})
    pipeline["retention"] = {"policy": "days", "days": days, "from": now.isoformat()}
    return describe(data)


_examples_cache: tuple[float, Optional[set]] = (0.0, None)


def is_example(runs_dir: Path, run_id: str) -> bool:
    """Is the run an example (never deleted)? Example list cached for a minute."""
    global _examples_cache
    at, ids = _examples_cache
    if ids is None or time.time() - at > 60:
        try:
            ids = protected_run_ids(runs_dir)
        except Exception:
            ids = ids or set()
        _examples_cache = (time.time(), ids)
    return run_id in ids


def protected_run_ids(runs_dir: Path) -> set[str]:
    """Runs that are never expired: the examples (configured and served)."""
    ids: set[str] = set()
    raw = os.environ.get("BAT3_EXAMPLE_RUNS", "").strip()
    if raw:
        try:
            ids.update(str(x) for x in json.loads(raw))
        except ValueError:
            ids.update(x.strip() for x in raw.split(",") if x.strip())
    try:
        from .routes.runs import served_example_ids
        ids.update(served_example_ids(runs_dir))
    except Exception as exc:  # never let this widen what can be deleted
        log.error("retention: could not list served examples (%s); sweep skipped", exc)
        raise
    return ids


def candidates(runs_dir: Path, now: Optional[datetime] = None,
               protected: Optional[Iterable[str]] = None) -> list[dict[str, Any]]:
    """Runs whose retention has passed and that pass every safety rule."""
    now = now or datetime.now(timezone.utc)
    protected = set(protected if protected is not None else protected_run_ids(runs_dir))
    out = []
    for entry in sorted(runs_dir.iterdir()):
        name = entry.name
        if name.startswith((".", "_")) or not valid_run_id(name) or name in protected:
            continue
        if entry.is_symlink() or not entry.is_dir():
            continue
        results = entry / "results.json"
        if results.is_symlink() or not results.is_file():
            continue
        try:
            if time.time() - results.stat().st_mtime < FRESH_WRITE_S:
                continue
            data = json.loads(results.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        exp = expires_at(data)
        if exp is not None and exp <= now:
            ret = data.get("pipeline", {}).get("retention")
            out.append({"run_id": name, "expires_at": exp.isoformat(),
                        "status": data.get("pipeline", {}).get("status"),
                        "policy": ret.get("policy") if isinstance(ret, dict) else "legacy"})
    out.sort(key=lambda c: c["expires_at"])
    return out


def _count_runs(runs_dir: Path) -> int:
    return sum(1 for e in runs_dir.iterdir()
               if e.is_dir() and not e.name.startswith((".", "_")) and valid_run_id(e.name))


def sweep(runs_dir: Path, now: Optional[datetime] = None,
          enforce: Optional[bool] = None) -> dict[str, Any]:
    """One retention pass: move expired runs to _expired, purge old trash."""
    now = now or datetime.now(timezone.utc)
    enforce = enforcing() if enforce is None else enforce
    due = candidates(runs_dir, now)
    total = _count_runs(runs_dir)
    summary: dict[str, Any] = {"enforce": enforce, "due": len(due), "total_runs": total,
                               "moved": [], "purged": [], "aborted": None, "waiting": 0}
    on_default = sum(1 for c in due if c["policy"] in ("default", "legacy"))
    if on_default > total / 2:
        summary["aborted"] = (f"{on_default} of {total} runs on the default retention are due at once: "
                              "nothing expired, check BAT3_RETENTION_DAYS and the clock")
        log.error("retention: %s", summary["aborted"])
        return summary
    batch, summary["waiting"] = due[:MAX_PER_SWEEP], max(0, len(due) - MAX_PER_SWEEP)
    trash = runs_dir / EXPIRED_DIR
    if enforce:
        for item in batch:
            src = runs_dir / item["run_id"]
            dst = trash / item["run_id"]
            if dst.exists():
                continue
            trash.mkdir(exist_ok=True)
            (src / ".expired_at").write_text(now.isoformat())
            os.rename(src, dst)
            summary["moved"].append(item["run_id"])
            log.warning("retention: expired %s (due %s), kept in %s for %s days",
                        item["run_id"], item["expires_at"], EXPIRED_DIR, grace_days())
        if trash.is_dir():
            for entry in trash.iterdir():
                stamp = entry / ".expired_at"
                when = _parse_time(stamp.read_text().strip()) if stamp.is_file() else None
                if when and when + timedelta(days=grace_days()) <= now and not entry.is_symlink():
                    shutil.rmtree(entry)
                    summary["purged"].append(entry.name)
    return summary


def restore(runs_dir: Path, run_id: str) -> None:
    """Move an expired run back from _expired (and preserve it)."""
    if not valid_run_id(run_id):
        raise RetentionError("invalid run id")
    src, dst = runs_dir / EXPIRED_DIR / run_id, runs_dir / run_id
    if not src.is_dir():
        raise RetentionError("not in the expired runs")
    if dst.exists():
        raise RetentionError("a run with this id exists")
    os.rename(src, dst)
    (dst / ".expired_at").unlink(missing_ok=True)
    set_policy(dst, {"policy": "preserve"})


def set_policy(run_dir: Path, retention: dict[str, Any]) -> None:
    """Write pipeline.retention atomically (finished runs only)."""
    path = run_dir / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("pipeline", {})["retention"] = retention
    tmp = path.with_name(f".results.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def expired_listing(runs_dir: Path) -> list[dict[str, Any]]:
    trash = runs_dir / EXPIRED_DIR
    out = []
    if trash.is_dir():
        for entry in sorted(trash.iterdir()):
            stamp = entry / ".expired_at"
            when = _parse_time(stamp.read_text().strip()) if stamp.is_file() else None
            out.append({"run_id": entry.name,
                        "expired_at": when.isoformat() if when else None,
                        "purge_at": (when + timedelta(days=grace_days())).isoformat() if when else None})
    return out
