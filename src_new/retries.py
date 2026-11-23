"""Queues and automatic retries of incomplete runs (2026-11-18).

Queues ("lanes"): web submissions and the repository lane (campaigns such as
mdval: separate Celery queue and worker pool, submission needs a token). A
run records its lane at submission (pipeline.queue; older runs: web).

Automatic retries are set per lane on the admin page (off by default):
maximum attempts, delay between them, and which failures count (a run
incomplete for retryable reasons, completeness.py, except time limits; a
worker lost mid-run).
A retried run keeps its run id, so clients need no extra logic:

1. The worker finishing an incomplete attempt (or the reaper finding a lost
   one) sets status "retry_scheduled" with pipeline.retry {attempt, at, ...}
   instead of a final status. The API reports it as "queued".
2. The reaper sweep (API leader, every 5 min) re-queues due runs: the
   attempt's results.json and logs move to attempts/<n>/, a fresh
   results.json keeps the submission fields and the attempts history, and
   the same run id goes back on its lane's queue.
3. The last attempt ends normally. Lookups that succeeded before come from
   the shared resolver cache, so only the failed ones are repeated.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

LANES = ("web", "repository")
STATUS = "retry_scheduled"
POLICY_FILE = "_settings/retry_policy.json"
DEFAULT_POLICY = {"enabled": False, "max_attempts": 3, "delay_minutes": 60,
                  "incomplete": True, "worker_lost": True}
LIMITS = {"max_attempts": (1, 10), "delay_minutes": (1, 24 * 60)}
#: pipeline fields a retry keeps (the rest is the attempt's own)
KEEP = ("name", "run_id", "run_name", "preset", "creator_ip_hash", "owner_token_sha256",
        "retention", "queue", "rerun_of", "superseded_by", "attempts")


def celery_queue(lane: str) -> Optional[str]:
    """Celery queue of a lane (None = Celery's default queue)."""
    if lane == "repository":
        return os.environ.get("BAT3_REPO_QUEUE", "validation.repo.celery")
    return os.environ.get("VALIDATION_UI_QUEUE") or None


def lane_of(pipeline: dict[str, Any]) -> str:
    lane = (pipeline or {}).get("queue")
    return lane if lane in LANES else "web"


# -- policy ------------------------------------------------------------------------

def _runs_dir(runs_dir: Optional[Path] = None) -> Path:
    return Path(runs_dir or os.environ.get("BAT3_RUNS_DIR", "runs"))


def policies(runs_dir: Optional[Path] = None) -> dict[str, dict[str, Any]]:
    try:
        stored = json.loads((_runs_dir(runs_dir) / POLICY_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        stored = {}
    return {lane: {**DEFAULT_POLICY, **(stored.get(lane) or {})} for lane in LANES}


def policy(lane: str, runs_dir: Optional[Path] = None) -> dict[str, Any]:
    return policies(runs_dir)[lane if lane in LANES else "web"]


def set_policy(lane: str, change: dict[str, Any], runs_dir: Optional[Path] = None) -> dict[str, Any]:
    """Validate and store a lane's policy; ValueError on a bad value."""
    if lane not in LANES:
        raise ValueError(f"unknown queue {lane!r}")
    current = policies(runs_dir)
    new = dict(current[lane])
    for key, value in change.items():
        if key not in DEFAULT_POLICY:
            raise ValueError(f"unknown setting {key!r}")
        if isinstance(DEFAULT_POLICY[key], bool):
            if not isinstance(value, bool):
                raise ValueError(f"{key} must be true or false")
        else:
            lo, hi = LIMITS[key]
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                raise ValueError(f"{key} must be a whole number from {lo} to {hi}")
        new[key] = value
    current[lane] = new
    path = _runs_dir(runs_dir) / POLICY_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    tmp.write_text(json.dumps(current, indent=2), encoding="utf-8")
    os.replace(tmp, path)
    return new


# -- deciding ----------------------------------------------------------------------

def plan(payload: dict[str, Any], why: str, runs_dir: Optional[Path] = None,
         now: Optional[float] = None) -> Optional[dict[str, Any]]:
    """pipeline.retry for this attempt, or None (no retry). `why` is
    "incomplete" or "worker_lost". Never raises."""
    try:
        pipeline = payload.get("pipeline") or {}
        # 2026-11-23: a cancelled run is never retried (cancellation.py)
        if pipeline.get("status") == "cancelled" or (pipeline.get("retry") or {}).get("cancelled"):
            return None
        from . import cancellation
        if cancellation.is_cancelled(pipeline.get("run_id")):
            return None
        lane = lane_of(pipeline)
        pol = policy(lane, runs_dir)
        if not pol["enabled"] or not pol.get(why):
            return None
        attempt = len(pipeline.get("attempts") or []) + 1
        if attempt >= pol["max_attempts"]:
            return None
        gaps: list = []
        if why == "incomplete":
            # 2026-11-21 (mdval audit item 7): time limits are not retried
            # automatically: the next attempt runs under the same budget and
            # would most likely run out of time again. Remote failures are.
            from .completeness import remote_gaps
            gaps = [{k: g[k] for k in ("service", "reason", "count")} for g in remote_gaps(payload)]
            if not gaps:
                return None
        now = time.time() if now is None else now
        return {"attempt": attempt, "max_attempts": pol["max_attempts"], "reason": why,
                "gaps": gaps[:20], "at": now + pol["delay_minutes"] * 60,
                "scheduled_at": now}
    except Exception as exc:
        log.warning("retries: could not plan a retry (%s); finishing normally", exc)
        return None


def schedule(payload: dict[str, Any], retry: dict[str, Any]) -> None:
    """Mark the attempt as waiting for a retry (in place; the caller saves)."""
    pipeline = payload.setdefault("pipeline", {})
    pipeline["status"] = STATUS
    pipeline["retry"] = retry
    pipeline["attempt_finished_at"] = datetime.now(timezone.utc).isoformat()


# -- re-queueing (reaper) ----------------------------------------------------------

def due(pipeline: dict[str, Any], now: Optional[float] = None) -> bool:
    retry = pipeline.get("retry") or {}
    now = time.time() if now is None else now
    return pipeline.get("status") == STATUS and float(retry.get("at") or 0) <= now


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{os.urandom(4).hex()}.tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def requeue(run_dir: Path, enqueue=None) -> bool:
    """Start the next attempt of a due run. True when re-queued.

    `enqueue(run_id, input_dir, results_path, config_path, queue)` sends the
    Celery task (default: run_pipeline_task.apply_async)."""
    results_path = run_dir / "results.json"
    data = json.loads(results_path.read_text(encoding="utf-8"))
    pipeline = data.get("pipeline") or {}
    if pipeline.get("status") != STATUS:
        return False
    # 2026-11-23: cancelled after this attempt was scheduled: end it there
    from . import cancellation
    if cancellation.is_cancelled(run_dir.name, run_dir):
        pipeline["status"] = "cancelled"
        pipeline["retry"] = {**(pipeline.get("retry") or {}), "cancelled": True}
        pipeline["finished_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_write(results_path, data)
        return False
    retry = pipeline.get("retry") or {}
    n = int(retry.get("attempt") or len(pipeline.get("attempts") or []) + 1)
    archive = run_dir / "attempts" / str(n)
    archive.mkdir(parents=True, exist_ok=True)
    shutil.copy2(results_path, archive / "results.json")
    for name in ("results.log", "results.debug.log"):
        if (run_dir / name).exists():
            shutil.move(str(run_dir / name), str(archive / name))

    attempts = list(pipeline.get("attempts") or [])
    attempts.append({"attempt": n, "reason": retry.get("reason"), "gaps": retry.get("gaps") or [],
                     "started_at": pipeline.get("started_at"),
                     "finished_at": pipeline.get("attempt_finished_at"),
                     "results": f"attempts/{n}/results.json"})
    fresh_pipeline = {k: pipeline[k] for k in KEEP if k in pipeline}
    fresh_pipeline.update({"status": "queued", "attempts": attempts,
                           "requeued_at": datetime.now(timezone.utc).isoformat()})
    fresh = {"created_at": data.get("created_at"), "pipeline": fresh_pipeline}
    _atomic_write(results_path, fresh)

    config_path = run_dir / "config.ini"
    send = enqueue or _enqueue
    try:
        send(run_dir.name, str(run_dir / "input"), str(results_path),
             str(config_path) if config_path.exists() else None,
             celery_queue(lane_of(fresh_pipeline)))
    except Exception:
        # put it back: the next sweep tries again
        data["pipeline"]["retry"] = {**retry, "at": time.time() + 60}
        _atomic_write(results_path, data)
        raise
    return True


def _enqueue(run_id: str, input_dir: str, results_path: str, config_path: Optional[str],
             queue: Optional[str]) -> None:
    from .api.tasks import run_pipeline_task
    run_pipeline_task.apply_async(
        task_id=run_id,
        kwargs={"run_id": run_id, "input_dir": input_dir, "results_path": results_path,
                "config_path": config_path},
        **({"queue": queue} if queue else {}),
    )


def client_status(pipeline: dict[str, Any]) -> str:
    """The status clients see: a run waiting for a retry is "queued"."""
    status = (pipeline or {}).get("status") or "created"
    return "queued" if status == STATUS else status
