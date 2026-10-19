"""Zombie-run reconciler (OQ-16 fix, 2026-10-19).

Why this exists (2026-10-13 incident, V-31): a hard worker kill (SIGBUS on
NFS-mmap blast IO, exit 135) evaporated in-flight pipeline tasks — celery's
default early-ack had already acknowledged them, so they were lost forever —
while results.json kept status "running"/"queued" forever. Users then saw a
queue that "looks stuck": idle fleet + phantom-running runs + queued runs
queued behind the phantom capacity claim. No live task existed anywhere in
the broker (queue lists literally absent in Redis).

Two independent fixes land together (this module is the FAST guarantee):

1. celery_app now sets task_acks_late + task_reject_on_worker_lost for the
   pipeline app, so a hard-killed run's message is broker-redelivered (on a
   visibility_timeout horizon, currently up to 6h).
2. THIS REAPER marks zombie runs failed within ~2 sweeps (default 10 min),
   independent of crash class or broker state. It deliberately does NOT
   auto-redispatch: a poison input could otherwise thrash the fleet with a
   crash/redispatch loop. Operator reruns via the UI (inputs are preserved).

Reaper semantics:
- Runs with pipeline.status in {"running", "queued"} whose run_id == task_id
  is absent from the fleet's live task set (active + reserved + scheduled)
  for TWO CONSECUTIVE sweeps are marked failed with a "worker_lost"
  critical error and a trailing event. Terminal statuses are untouched.
- Two-miss hysteresis absorbs transient inspection gaps (broker restart,
  inspect timeouts) without flapping runs to failed.
- The api runs 4 uvicorn processes (each starts this loop); a Redis
  SET NX PX leader lock ensures only one sweeps. Input: BAT3_RUNS_DIR +
  CELERY_BROKER_URL (shared redis also holds the leader lock).

Everything except the asyncio loop driver is a pure function for testing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path

import redis as redis_lib

logger = logging.getLogger(__name__)

STATUS_ZOMBIE_CANDIDATES = frozenset({"running", "queued"})
STATUS_TERMINAL = frozenset(
    {"success", "completed", "failed", "error", "cancelled", "canceled"}
)
MISSES_TO_FAIL = 2
DEFAULT_INTERVAL_S = 300
LEADER_LOCK_KEY = "bat3:run_reaper:leader"


def read_run_status(results_path: Path) -> str | None:
    """Read pipeline.status from a run's results.json (None if unreadable)."""
    try:
        with open(results_path, encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None
    pipeline = payload.get("pipeline") if isinstance(payload, dict) else None
    status = (pipeline or {}).get("status")
    return status if isinstance(status, str) else None


def mark_worker_lost(results_path: Path, *, sweep_count: int) -> bool:
    """Mark a zombie run failed in-place. Returns True when written.

    Uses ResultsManager so the write keeps schema/validation invariants.
    """
    from ..results.results_manager import ResultsManager

    try:
        rm = ResultsManager(str(results_path))
    except Exception as exc:  # unreadable/corrupt — leave it, log only
        logger.warning("run_reaper: cannot load %s (%s)", results_path, exc)
        return False
    rm.finish_run("failed")
    rm.add_event(
        "worker_lost",
        detail=(
            "pipeline task absent from the celery fleet for "
            f"{sweep_count} consecutive reaper sweeps; marked failed by "
            "zombie-run reconciler (OQ-16). Inputs preserved — rerun the "
            "run to retry."
        ),
    )
    rm.record_error(
        "worker_lost",
        "run's celery task vanished (worker hard-kill class; SIGBUS/exit 135 "
        "incident 2026-10-13). See events.",
        step_id="pipeline_dispatch",
        critical=True,
    )
    return True


def sweep(runs_dir: Path, live_task_ids: set[str], misses: dict[str, int]) -> dict:
    """Reconcile one sweep. Pure w.r.t. its inputs; returns a small summary.

    misses is caller-owned state persisting across sweeps (per-process).
    """
    summary = {"scanned": 0, "zombies_failed": [], "errors": 0}
    if not runs_dir.is_dir():
        logger.warning("run_reaper: runs dir %s missing", runs_dir)
        return summary

    seen_candidates: set[str] = set()
    for run_dir in runs_dir.iterdir():
        results_path = run_dir / "results.json"
        if not results_path.is_file():
            continue
        summary["scanned"] += 1
        run_id = run_dir.name
        status = read_run_status(results_path)
        if status is None:
            summary["errors"] += 1
            continue
        if status in STATUS_TERMINAL:
            misses.pop(run_id, None)
            continue
        if status not in STATUS_ZOMBIE_CANDIDATES:
            continue
        seen_candidates.add(run_id)
        if run_id in live_task_ids:
            misses.pop(run_id, None)
            continue
        count = misses.get(run_id, 0) + 1
        misses[run_id] = count
        if count >= MISSES_TO_FAIL:
            if mark_worker_lost(results_path, sweep_count=count):
                summary["zombies_failed"].append(run_id)
                logger.error(
                    "run_reaper: run %s marked failed (worker_lost, %d sweeps)",
                    run_id, count,
                )
            misses.pop(run_id, None)

    # Forget candidates that vanished from disk entirely
    for run_id in list(misses):
        if run_id not in seen_candidates:
            misses.pop(run_id, None)
    return summary


def collect_live_task_ids(celery_app, timeout: float = 10.0) -> set[str]:
    """Task ids currently known to the fleet (active + reserved + scheduled)."""
    inspector = celery_app.control.inspect(timeout=timeout)
    ids: set[str] = set()
    for bucket in (inspector.active, inspector.reserved, inspector.scheduled):
        try:
            per_node = bucket() or {}
        except Exception as exc:
            logger.warning("run_reaper: inspect bucket failed (%s)", exc)
            continue
        for tasks in per_node.values():
            for t in tasks or []:
                tid = t.get("id")
                if tid:
                    ids.add(tid)
    return ids


async def reaper_loop(celery_app, runs_dir: Path, redis_url: str,
                      interval_s: int = DEFAULT_INTERVAL_S) -> None:
    """Forever-loop driver. Redis leader lock: exactly one sweeper cluster-wide."""
    redis_client = redis_lib.from_url(redis_url, socket_timeout=10)
    misses: dict[str, int] = {}
    identity = f"{os.uname().nodename}:{os.getpid()}"
    logger.info("run_reaper: started (interval=%ss, runs=%s)", interval_s, runs_dir)
    while True:
        try:
            got_lock = redis_client.set(
                LEADER_LOCK_KEY, identity, nx=True, px=int(interval_s * 1.5 * 1000)
            )
            if got_lock:
                live = await asyncio.to_thread(collect_live_task_ids, celery_app)
                summary = await asyncio.to_thread(sweep, runs_dir, live, misses)
                if summary["zombies_failed"]:
                    logger.error("run_reaper sweep: %s", summary)
        except Exception as exc:
            logger.warning("run_reaper sweep failed: %s", exc)
        await asyncio.sleep(interval_s)


def start_reaper(celery_app, runs_dir: Path) -> asyncio.Task | None:
    """Entry point for the FastAPI lifespan. Env: BAT3_RUN_REAPER=0 disables."""
    if os.environ.get("BAT3_RUN_REAPER", "1") == "0":
        logger.info("run_reaper: disabled via BAT3_RUN_REAPER=0")
        return None
    redis_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    interval = int(os.environ.get("BAT3_RUN_REAPER_INTERVAL_S", DEFAULT_INTERVAL_S))
    return asyncio.create_task(reaper_loop(celery_app, runs_dir, redis_url, interval))
