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

Reaper semantics (bughunt BH-005, 2026-10-27):
- `queued` runs are NEVER failed. Broker-queued messages are invisible to
  celery inspect (active/reserved/scheduled only shows what workers hold),
  and inspect itself is unreliable on this deployment — on 27 Oct 127
  never-started runs were failed as worker_lost while patiently queued.
- `running` runs are judged primarily by a HEARTBEAT file
  (run_dir/heartbeat, touched every 30 s by run_pipeline_task): stale
  beyond 15 min -> failed in ONE sweep. The age is measured against a
  probe file's mtime (both server-assigned), so worker/API clock skew
  cannot poison it.
- `running` runs WITHOUT a heartbeat (legacy, deploy transition) keep the
  previous inspect-based two-miss rule.
- Two-miss hysteresis absorbs transient inspection gaps (broker restart,
  inspect timeouts) without flapping runs to failed.
- Sticky terminal: run_pipeline_task exits with "skipped_terminal" when
  the run already reached a terminal state, so an acks_late redelivery
  cannot flip a reaped/failed run back to running.
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
import re
import time
from pathlib import Path

import redis as redis_lib

logger = logging.getLogger(__name__)

STATUS_ZOMBIE_CANDIDATES = frozenset({"running"})  # BH-005: queued NEVER
STATUS_TERMINAL = frozenset(
    {"success", "completed", "failed", "error", "cancelled", "canceled"}
)
MISSES_TO_FAIL = 2
DEFAULT_INTERVAL_S = 300
LEADER_LOCK_KEY = "bat3:run_reaper:leader"
HEARTBEAT_NAME = "heartbeat"
HEARTBEAT_STALE_S = 900.0  # 15 min without a touch -> zombie


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


def mark_worker_lost(results_path: Path, *, sweep_count: int,
                     cause: str | None = None) -> bool:
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
        detail=cause or (
            "pipeline task absent from the celery fleet for "
            f"{sweep_count} consecutive reaper sweeps; marked failed by "
            "zombie-run reconciler (OQ-16). Inputs preserved — rerun the "
            "run to retry."
        ),
    )
    rm.record_error(
        "worker_lost",
        cause or (
            "run's celery task vanished (worker hard-kill class; SIGBUS/exit 135 "
            "incident 2026-10-13). See events."
        ),
        step_id="pipeline_dispatch",
        critical=True,
    )
    return True


def heartbeat_age(results_path: Path) -> float | None:
    """Age of run_dir/heartbeat in seconds, NFS-skew-safe, or None.

    Both the heartbeat's mtime and the "now" reference come from the file
    server (the probe file we write this instant), so worker/API host clock
    skew cannot poison the comparison. None when no heartbeat exists or
    the filesystem refuses the probe.
    """
    hb = results_path.parent / HEARTBEAT_NAME
    probe = results_path.parent / ".reaper_probe"
    try:
        hb_mtime = hb.stat().st_mtime
        probe.write_bytes(b"")
        try:
            now = probe.stat().st_mtime
        finally:
            probe.unlink(missing_ok=True)
        return max(0.0, float(now) - float(hb_mtime))
    except Exception:
        return None


# W3.1 item 4 (A9): the adhoc staging dir lives under the runs dir in the
# deployment (/app/runs/_adhoc) — never treat it as a run directory.
ADHOC_DIR_NAME = "_adhoc"
_ADHOC_CIF_RE = re.compile(r"^[0-9a-f]{64}\.cif$")


def adhoc_retention_s() -> float:
    """Adhoc retention window in seconds (env BAT3_ADHOC_RETENTION_DAYS,
    default 7). Staged mmCIFs are content-addressed (deduplicated across
# runs), so they only need to outlive the longest run + RCSB caching."""
    raw = os.environ.get("BAT3_ADHOC_RETENTION_DAYS", "7")
    try:
        days = float(raw)
    except (TypeError, ValueError):
        days = 7.0
    return max(days, 0.0) * 86400.0


def sweep_adhoc(adhoc_dir: Path, retention_s: float | None = None) -> dict:
    """Delete stale adhoc staging files (W3.1 item 4 retention).

    Touches ONLY <64-hex>.cif files and abandoned ``.*.tmp`` staging
    files whose mtime is older than the retention window; everything
    else in the directory is left alone."""
    summary = {"adhoc_scanned": 0, "adhoc_deleted": 0, "adhoc_errors": 0}
    if retention_s is None:
        retention_s = adhoc_retention_s()
    if not adhoc_dir.is_dir():
        return summary
    try:
        entries = list(adhoc_dir.iterdir())
    except OSError as exc:
        logger.warning("run_reaper: adhoc dir %s unreadable: %s",
                       adhoc_dir, exc)
        summary["adhoc_errors"] += 1
        return summary
    now = time.time()
    for f in entries:
        name = f.name
        is_staging_tmp = name.startswith(".") and name.endswith(".tmp")
        if not (is_staging_tmp or _ADHOC_CIF_RE.match(name)):
            continue  # foreign file: not ours to touch
        summary["adhoc_scanned"] += 1
        try:
            if now - f.stat().st_mtime > retention_s:
                f.unlink()
                summary["adhoc_deleted"] += 1
        except OSError:
            summary["adhoc_errors"] += 1
    if summary["adhoc_deleted"] or summary["adhoc_errors"]:
        logger.info("run_reaper adhoc sweep: %s", summary)
    return summary


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
        if run_dir.name == ADHOC_DIR_NAME:
            continue  # W3.1 item 4 (A9): staging dir, not a run
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
            continue  # unknown/queued statuses: never reaped (BH-005)
        seen_candidates.add(run_id)
        # BH-005: heartbeat is the PRIMARY liveness signal for running
        # runs — broker-queued messages are invisible to inspect and
        # inspect is unreliable on this fleet.
        hb_age = heartbeat_age(results_path)
        if hb_age is not None:
            if hb_age <= HEARTBEAT_STALE_S:
                misses.pop(run_id, None)
                continue
            if mark_worker_lost(
                results_path,
                sweep_count=misses.pop(run_id, 0) + 1,
                cause=(
                    f"pipeline heartbeat stale for {hb_age:.0f} s "
                    f"(> {HEARTBEAT_STALE_S:.0f} s); marked failed by "
                    "zombie-run reconciler. Inputs preserved — rerun the "
                    "run to retry."
                ),
            ):
                summary["zombies_failed"].append(run_id)
                logger.error(
                    "run_reaper: run %s marked failed (stale heartbeat, "
                    "%.0f s)", run_id, hb_age,
                )
            continue
        # no heartbeat (legacy/transition): previous inspect-based rule
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
                # W3.1 item 4 (A9): adhoc retention (no-op when the dir
                # does not exist; env BAT3_ADHOC_DIR wins over the default
                # <runs>/_adhoc location)
                adhoc = os.environ.get("BAT3_ADHOC_DIR", "").strip()
                adhoc_dir = Path(adhoc) if adhoc else runs_dir / ADHOC_DIR_NAME
                await asyncio.to_thread(sweep_adhoc, adhoc_dir)
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
