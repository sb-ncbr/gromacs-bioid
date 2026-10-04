"""Validation queue processor - processes queue items by triggering BAT3 validations.

Fixed version (2026-09-09 incident remediation):
- Atomic queue row claiming (SELECT ... FOR UPDATE SKIP LOCKED) - no double dispatch
- Per-item transactions (one bad item no longer rolls back the whole batch)
- Exact run linkage via ValidationQueue.run_id (added column)
- Error messages persisted on queue items AND bat3 runs
- Celery dispatch failure -> requeue with retry, not stuck 'processing'
- Activity logging reachable again
- Stale sweeper: zombie runs/queue/entries/batches reconciled with reason 'stale_timeout'
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from mddbr_client import TERMINAL_FAILURE_CLASSES, download_simulation_files

import models

logger = logging.getLogger(__name__)

STALE_HOURS = int(os.environ.get("VALIDATION_STALE_HOURS", "24"))
MAX_RETRIES = 3


def _utcnow() -> datetime:
    return datetime.utcnow()


def _log_activity_safe(db: Session, job_id: str, activity_type: str, message: str,
                       severity: str = "info", details: Optional[dict] = None) -> None:
    """Best-effort activity logging that never breaks processing."""
    try:
        from indexing_enhancements import log_activity
        log_activity(db=db, job_id=job_id, activity_type=activity_type,
                     message=message, severity=severity, details=details or {})
    except Exception as log_error:
        logger.debug(f"Could not log activity: {log_error}")


def _claim_queue_item(db: Session, batch_id: Optional[str],
                      exclude_ids: Optional[list] = None) -> Optional[models.ValidationQueue]:
    """Atomically claim one queued item (row lock, skipped if already locked).

    exclude_ids is MANDATORY within a batch claim loop: this app uses
    sessionmaker(autoflush=False), so a pending status change is invisible
    to the next SELECT in the same transaction, and SKIP LOCKED does not
    skip rows locked by our own transaction - without exclusion the same
    row is returned again and again (P2-18 duplicate intake).
    """
    query = db.query(models.ValidationQueue).filter(
        models.ValidationQueue.status == "queued"
    )
    if exclude_ids:
        query = query.filter(~models.ValidationQueue.id.in_(exclude_ids))
    if batch_id:
        query = query.filter(models.ValidationQueue.batch_id == batch_id)
    return query.order_by(
        models.ValidationQueue.priority,
        models.ValidationQueue.created_at,
    ).with_for_update(skip_locked=True).first()


def _fail_queue_item(queue_item: models.ValidationQueue, reason: str, entry=None) -> None:
    queue_item.status = "failed"
    queue_item.last_error = reason[:500] if reason else "unknown error"
    queue_item.completed_at = _utcnow()
    if entry is not None:
        entry.status = "failed"

def _release_reserved_item(item_id: int, error: str) -> None:
    """Phase-2 crash path: the claim reserve already committed this item as
    'processing'; return it to the queue (retry budget) or fail it.

    Never touches items that reached run-dispatch (run_id linked) - those are
    owned by the celery task / stale sweeper from that point on.
    Uses a fresh session: the worker's own session may be unhealthy.
    """
    session = models.SessionLocal()
    try:
        item = session.query(models.ValidationQueue).get(item_id)
        if item is None or item.status != "processing" or item.run_id:
            return
        item.retry_count = (item.retry_count or 0) + 1
        item.last_error = f"intake failed: {error[:400]}"
        if item.retry_count < MAX_RETRIES:
            item.status = "queued"
            item.started_at = None
        else:
            item.status = "failed"
            item.completed_at = _utcnow()
        session.commit()
    except Exception as rel_err:
        logger.error(f"Failed to release reserved queue item {item_id}: {rel_err}")
        try:
            session.rollback()
        except Exception:
            pass
    finally:
        try:
            session.close()
        except Exception:
            pass


def _process_single_item(db: Session, queue_item: models.ValidationQueue,
                         batch_id: Optional[str]) -> bool:
    """One transactional unit: download -> create run -> dispatch -> link.

    Returns True if a validation was started. Caller owns commit/rollback.
    Runs inside the lock held by _claim_queue_item.
    """
    entry = db.query(models.MddbEntry).filter(
        models.MddbEntry.id == queue_item.entry_id
    ).first()
    if not entry:
        _fail_queue_item(queue_item, "entry not found")
        return False

    entry_dir = f"/data/validation/{entry.id}"
    input_dir = f"{entry_dir}/input"
    results_path = f"{entry_dir}/results.json"
    config_path = f"{entry_dir}/config.ini"
    # Fall back to shared tuned config when the entry has no local config
    # (avoids from_default_ini() which enables the very slow nr/core_nt BLAST)
    if not os.path.exists(config_path):
        shared_cfg = os.environ.get("VALIDATION_SHARED_CONFIG", "/data/validation/config_shared.ini")
        if os.path.exists(shared_cfg):
            config_path = shared_cfg

    os.makedirs(input_dir, mode=0o777, exist_ok=True)
    try:
        os.chmod(entry_dir, 0o777)
    except OSError as chmod_err:
        logger.warning(f"Could not chmod {entry_dir}: {chmod_err}")

    # Download simulation files from MDDBR (skip when already present)
    if not entry.local_accession:
        _fail_queue_item(queue_item, "entry has no local_accession", entry)
        return False

    local_acc = entry.local_accession

    already_downloaded = os.path.isdir(input_dir) and any(
        f for f in os.listdir(input_dir) if not f.startswith(".")
    )
    if not already_downloaded:
        logger.info(f"Downloading files for entry {entry.local_accession}")
        ok, failure_class = download_simulation_files(db, entry.id, local_acc, input_dir)
        if not ok:
            queue_item.retry_count = (queue_item.retry_count or 0) + 1
            if failure_class in TERMINAL_FAILURE_CLASSES:
                # 404 / unusable data: retrying is pointless, fail permanently
                _fail_queue_item(queue_item, f"{failure_class} (terminal)", entry)
            else:
                queue_item.last_error = f"{failure_class} (attempt {queue_item.retry_count})"
                if queue_item.retry_count < MAX_RETRIES:
                    queue_item.status = "queued"  # released; claimed again later
                else:
                    _fail_queue_item(queue_item, queue_item.last_error, entry)
            return False

    # Create Bat3Run record
    run_id = f"validation-{entry.id}-{_utcnow().strftime('%Y%m%d%H%M%S')}"
    run = models.Bat3Run(
        entry_id=entry.id,
        run_id=run_id,
        status="running",
        input_dir=input_dir,
        results_path=results_path,
        config_path=config_path,
        started_at=_utcnow(),
        created_at=_utcnow(),
    )
    db.add(run)
    db.flush()  # populate run.id

    # Dispatch Celery task - UI-flagged claims jump to the dedicated ui queue
    try:
        from config import CELERY_BROKER_URL
        from celery import Celery
        from src_new.celery_app import redis_broker_transport_opts
        celery_app = Celery(
            "validation",
            broker=CELERY_BROKER_URL,
            broker_transport_options=redis_broker_transport_opts(),
        )
        ui_queue = os.environ.get("VALIDATION_UI_QUEUE", "")
        ui_prefix = os.environ.get("VALIDATION_UI_BATCH_PREFIX", "ui")
        task_kwargs = {
            "run_id": run_id,
            "input_dir": input_dir,
            "results_path": results_path,
            "config_path": config_path,
        }
        send_opts = {}
        if ui_queue and queue_item.batch_id and str(queue_item.batch_id).startswith(ui_prefix):
            send_opts["queue"] = ui_queue
            route_note = f" -> ui queue {ui_queue}"
        else:
            route_note = ""
        task_result = celery_app.send_task(
            "src_new.api.tasks.run_pipeline_task",
            kwargs=task_kwargs,
            **send_opts,
        )
        if route_note:
            logger.info(f"Routed {run_id}{route_note}")
        run.celery_task_id = task_result.id
    except Exception as celery_error:
        # Do NOT strand the item in 'processing': requeue with retry instead
        queue_item.retry_count = (queue_item.retry_count or 0) + 1
        queue_item.last_error = f"celery dispatch failed: {str(celery_error)[:400]}"
        if queue_item.retry_count < MAX_RETRIES:
            queue_item.status = "queued"
        else:
            _fail_queue_item(queue_item, queue_item.last_error, entry)
        run.status = "failed"
        run.error_message = f"celery dispatch failed: {str(celery_error)[:800]}"
        run.completed_at = _utcnow()
        return False

    # Success: exact linkage persisted on the queue row (new run_id column)
    queue_item.run_id = run.id
    queue_item.status = "processing"
    queue_item.started_at = _utcnow()
    entry.status = "processing"

    _log_activity_safe(
        db,
        job_id=batch_id or f"validation-{entry.id}",
        activity_type="validation_started",
        message=f"Validation started for entry {entry.local_accession}",
        severity="info",
        details={"entry_id": entry.id, "bat3_run_id": run.id, "celery_task_id": run.celery_task_id},
    )
    return True


def process_validation_queue(
    db: Session,
    concurrency: int = 5,
    batch_id: Optional[str] = None,
) -> int:
    """Claim and start up to `concurrency` queued validations.

    Each item is its own transaction (claim lock held until commit),
    so one failing item never discards progress of others.
    """
    # Phase 1: atomically claim up to `concurrency` items (fast).
    claimed_ids = []
    try:
        for _ in range(max(1, concurrency)):
            queue_item = _claim_queue_item(db, batch_id, exclude_ids=claimed_ids)
            if not queue_item:
                break
            # Reserve immediately: without this the row stays 'queued' for
            # the whole download (minutes) and every dispatcher tick
            # re-claims it, spawning duplicate intake threads that race the
            # same input dir (P2-18). Phase 2 either finalizes the dispatch
            # (status stays processing + run linked) or releases/fails it.
            queue_item.status = "processing"
            queue_item.started_at = _utcnow()
            claimed_ids.append(queue_item.id)
        db.commit()
    except Exception as e:
        logger.error(f"Error claiming queue items: {e}")
        db.rollback()
        return 0

    if not claimed_ids:
        return 0

    # Phase 2: process claimed items in parallel (downloads dominate
    # intake latency ~GB-scale trajectories). Each worker gets its own
    # DB session and commits independently.
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _process(item_id: int) -> bool:
        session = models.SessionLocal()
        try:
            item = session.query(models.ValidationQueue).get(item_id)
            if item is None:
                return False
            ok = _process_single_item(session, item, batch_id)
            session.commit()
            return ok
        except Exception as item_error:
            logger.error(f"Failed to process queue item {item_id}: {item_error}")
            try:
                session.rollback()
            except Exception:
                pass
            _release_reserved_item(item_id, str(item_error))
            return False
        finally:
            try:
                session.close()
            except Exception:
                pass

    started_count = 0
    max_workers = min(len(claimed_ids), int(os.environ.get("VALIDATION_INTAKE_WORKERS", "16")))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_process, cid): cid for cid in claimed_ids}
        for fut in as_completed(futures):
            try:
                if fut.result():
                    started_count += 1
            except Exception as fut_error:
                logger.error(f"Intake worker failed: {fut_error}")

    if started_count:
        logger.info(f"Queue processor: started {started_count} validations")
    return started_count


def cancel_queued_validations(
    db: Session,
    batch_id: Optional[str] = None,
) -> int:
    """Cancel queued/processing validation items."""
    try:
        query = db.query(models.ValidationQueue).filter(
            models.ValidationQueue.status.in_(["queued", "processing", "paused"])
        )
        if batch_id:
            query = query.filter(models.ValidationQueue.batch_id == batch_id)
        queued_items = query.all()
        if not queued_items:
            return 0
        cancelled_count = 0
        for queue_item in queued_items:
            try:
                queue_item.status = "cancelled"
                queue_item.completed_at = _utcnow()
                if queue_item.entry:
                    queue_item.entry.status = "pending"
                cancelled_count += 1
            except Exception as item_error:
                logger.error(f"Failed to cancel queue item {queue_item.id}: {item_error}")
                continue
        db.commit()
        logger.info(f"Cancelled {cancelled_count} queued validations")
        return cancelled_count
    except Exception as e:
        logger.error(f"Error cancelling queued validations: {e}")
        db.rollback()
        return 0


def cancel_active_batches(
    db: Session,
    batch_id: Optional[str] = None,
) -> int:
    """Cancel active batch runs by updating their status."""
    try:
        query = db.query(models.BatchRun).filter(models.BatchRun.status == "running")
        if batch_id:
            query = query.filter(models.BatchRun.batch_id == batch_id)
        batches = query.all()
        if not batches:
            return 0
        for batch in batches:
            batch.status = "cancelled"
        db.commit()
        logger.info(f"Cancelled {len(batches)} active batches")
        return len(batches)
    except Exception as e:
        logger.error(f"Error cancelling batches: {e}")
        db.rollback()
        return 0


def _resolve_run_for_queue_item(db: Session, queue_item: models.ValidationQueue):
    """Resolve the Bat3Run for a queue item (exact linkage preferred)."""
    if queue_item.run_id:
        run = db.query(models.Bat3Run).filter(models.Bat3Run.id == queue_item.run_id).first()
        if run:
            return run
    # Legacy fallback: latest run for the entry
    return db.query(models.Bat3Run).filter(
        models.Bat3Run.entry_id == queue_item.entry_id,
        models.Bat3Run.status.in_(["running", "pending"]),
    ).order_by(models.Bat3Run.created_at.desc()).first()


def _celery_meta_many(celery_task_ids: list) -> dict:
    """Read many celery result metas in ONE Redis round trip (MGET chunks).

    Returns {task_id: meta_dict}; missing keys are omitted. Critical at
    thousands-of-processing scale (the old per-item connection loop stalled
    the 30s completion job into permanent self-throttle).
    """
    import redis
    from config import CELERY_BROKER_URL
    redis_url = CELERY_BROKER_URL.replace("redis://", "")
    host, rest = redis_url.split(":", 1)
    port = int(rest.split("/")[0])
    out = {}
    if not celery_task_ids:
        return out
    r = redis.Redis(host=host, port=port, decode_responses=True, socket_timeout=10)
    try:
        keys = [f"celery-task-meta-{t}" for t in celery_task_ids]
        for i in range(0, len(keys), 500):
            chunk_keys = keys[i:i + 500]
            vals = r.mget(chunk_keys)
            for key, raw in zip(chunk_keys, vals):
                if raw:
                    try:
                        out[key.replace("celery-task-meta-", "", 1)] = json.loads(raw)
                    except Exception:
                        continue
        return out
    finally:
        r.close()


def _celery_meta(celery_task_id: str) -> Optional[dict]:
    """Read celery result metadata from Redis. Returns None if missing/expired."""
    import redis
    from config import CELERY_BROKER_URL
    redis_url = CELERY_BROKER_URL.replace("redis://", "")
    host, rest = redis_url.split(":", 1)
    port = int(rest.split("/")[0])
    r = redis.Redis(host=host, port=port, decode_responses=True, socket_timeout=5)
    try:
        raw = r.get(f"celery-task-meta-{celery_task_id}")
        return json.loads(raw) if raw else None
    finally:
        r.close()


def _settle_queue_item(db: Session, queue_item: models.ValidationQueue,
                       run: models.Bat3Run, success: bool, error_text: str = "") -> None:
    """Apply terminal outcome to queue item + run + entry."""
    finished = _utcnow()
    if success:
        queue_item.status = "completed"
        queue_item.last_error = None
    else:
        queue_item.status = "failed"
        queue_item.last_error = (error_text or "unknown failure")[:500]
    queue_item.completed_at = finished

    run.status = queue_item.status
    run.error_message = None if success else (error_text or "unknown failure")[:2000]
    run.completed_at = finished

    if queue_item.entry:
        queue_item.entry.status = queue_item.status


def _update_batch_counters(db: Session, queue_item: models.ValidationQueue) -> None:
    if not queue_item.batch_id:
        return
    batch = db.query(models.BatchRun).filter(
        models.BatchRun.batch_id == queue_item.batch_id
    ).first()
    if not batch:
        return
    if queue_item.status == "completed":
        batch.completed_entries = (batch.completed_entries or 0) + 1
    elif queue_item.status == "failed":
        batch.failed_entries = (batch.failed_entries or 0) + 1
    total_done = (batch.completed_entries or 0) + (batch.failed_entries or 0)
    if batch.total_entries and total_done >= batch.total_entries:
        batch.status = "completed"
        batch.completed_at = _utcnow()


def check_task_completions(
    db: Session,
    batch_id: Optional[str] = None,
) -> int:
    """Settle 'processing' queue items by reading Celery results from Redis.

    Per-item commits; errors persisted; exact run linkage; activity logging.
    """
    try:
        query = db.query(models.ValidationQueue).filter(
            models.ValidationQueue.status == "processing"
        )
        if batch_id:
            query = query.filter(models.ValidationQueue.batch_id == batch_id)
        processing_items = query.all()
        if not processing_items:
            return 0

        # Preload runs in one pass and batch-read metas in one MGET chunk set
        runs_by_id = {}
        task_ids = []
        items_with_run = []
        for queue_item in processing_items:
            run = _resolve_run_for_queue_item(db, queue_item)
            if not run or not run.celery_task_id:
                continue
            runs_by_id[queue_item.id] = run
            task_ids.append(run.celery_task_id)
            items_with_run.append(queue_item)
        metas = _celery_meta_many(task_ids)

        updated_count = 0
        for queue_item in items_with_run:
            try:
                run = runs_by_id[queue_item.id]
                meta = metas.get(run.celery_task_id)
                if meta is None:
                    # Result expired from Redis (>24h); sweeper handles these
                    continue

                outcome = meta.get("status")
                settled = None
                error_text = ""
                if outcome == "FAILURE":
                    settled = False
                    result_exc = meta.get("result")
                    error_text = str(result_exc)[:800] if result_exc else "celery task FAILURE"
                elif outcome == "SUCCESS":
                    task_result = meta.get("result", {})
                    if isinstance(task_result, dict) and task_result.get("status") == "failed":
                        settled = False
                        error_text = str(task_result.get("error") or task_result)[:800]
                    elif isinstance(task_result, dict) and task_result.get("status") == "degraded":
                        settled = True
                        error_text = str(task_result.get("error"))[:800] if task_result.get("error") else ""
                    else:
                        settled = True

                if settled is None:
                    continue

                _settle_queue_item(db, queue_item, run, settled, error_text)
                _update_batch_counters(db, queue_item)
                _log_activity_safe(
                    db,
                    job_id=queue_item.batch_id or f"validation-{queue_item.entry_id}",
                    activity_type="validation_completed" if settled else "validation_failed",
                    message=f"Validation {'completed' if settled else 'failed'} for entry {queue_item.entry_id}",
                    severity="info" if settled else "error",
                    details={"entry_id": queue_item.entry_id, "bat3_run_id": run.id,
                             "celery_task_id": run.celery_task_id, "error": error_text[:300] if error_text else None},
                )
                db.commit()
                updated_count += 1
            except Exception as item_error:
                logger.error(f"Error checking completion for queue item {queue_item.id}: {item_error}")
                db.rollback()  # this item only
                continue

        if updated_count:
            logger.info(f"Updated {updated_count} completed validations")
        return updated_count
    except Exception as e:
        logger.error(f"Error checking task completions: {e}")
        db.rollback()
        return 0


# ---------------------------------------------------------------------------
# S3: NFS-truth settlement (queue vs runs split-brain repair)
#
# check_task_completions settles strictly from Celery task metas in Redis, but
# metas expire (~24h) while long pipeline tasks routinely outlive them and the
# sweeper then marks the run failed and requeues: results.json exists on disk
# with all stages terminal, yet the queue row churns forever (proven 2026-09-18:
# completed counter flat >29h while results.json files were being finalized).
#
# This janitor settles 'processing' queue rows from the RESULTS FILE itself:
# every stage success/skipped -> completed. Conservative: it never marks
# failures (failed-stage rows are left to the sweeper/manual review) and it
# skips files whose mtime is too fresh (exporter may still be writing).
#
# results.json is large (tens of MB), so the stage map is extracted WITHOUT a
# full json.load: top-level "tasks" sits near the START of the file (observed
# key order: schema_version, created_at, updated_at, pipeline, tasks, ...,
# data last) -> read a small HEAD slice; fall back to a TAIL slice in case a
# future serializer reorders. The object is then brace-matched out of the
# slice and parsed on its own.
# ---------------------------------------------------------------------------

RESULTS_TRUTH_ENABLED = os.environ.get("VALIDATION_RESULTS_TRUTH_SETTLE", "1") == "1"
RESULTS_ROOT = os.environ.get("VALIDATION_RESULTS_ROOT", "/data/validation")
RESULTS_MIN_AGE_S = int(os.environ.get("VALIDATION_RESULTS_TRUTH_MIN_AGE_S", "900"))
RESULTS_PER_TICK = int(os.environ.get("VALIDATION_RESULTS_TRUTH_PER_TICK", "400"))
_HEAD_BYTES = 64 * 1024
_TAIL_BYTES = 256 * 1024


def _extract_tasks_object(blob: str) -> Optional[dict]:
    """Locate a top-level "tasks" object in a JSON fragment and parse it.

    Brace-matching is string/escape aware. Returns None on any mismatch.
    """
    anchor = blob.find('"tasks"')
    if anchor < 0:
        return None
    colon = blob.find(":", anchor)
    brace_start = blob.find("{", colon)
    if brace_start < 0:
        return None
    depth = 0
    end = -1
    in_str = False
    esc = False
    for i in range(brace_start, len(blob)):
        ch = blob[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    if end < 0:
        return None
    try:
        tasks = json.loads(blob[brace_start:end + 1])
    except Exception:
        return None
    return tasks if isinstance(tasks, dict) and tasks else None


def _read_results_stage_status(results_path: str) -> Optional[dict]:
    """Extract {stage_name: status} from a results.json without a full parse.

    Tries the HEAD slice first (tasks block precedes the huge data payload in
    the observed serialization order), then the TAIL slice as a fallback.
    Returns None on any failure (missing file, torn write, parse mismatch).
    Never raises.
    """
    try:
        size = os.path.getsize(results_path)
        with open(results_path, "rb") as fh:
            head = fh.read(_HEAD_BYTES).decode("utf-8", errors="ignore")
            fh.seek(max(0, size - _TAIL_BYTES))
            tail = fh.read().decode("utf-8", errors="ignore")
        tasks = _extract_tasks_object(head)
        if tasks is None:
            tasks = _extract_tasks_object(tail)
        if not tasks:
            return None
        out = {}
        for name, blk in tasks.items():
            if isinstance(blk, dict) and "status" in blk:
                out[str(name)] = blk["status"]
        return out or None
    except Exception:
        return None


def settle_by_results_truth(db: Session) -> int:
    """Settle oldest 'processing' queue rows from their results.json state.

    All stages success/skipped -> settle completed via _settle_queue_item.
    Everything else -> leave untouched. Per-item commits; never raises.
    """
    if not RESULTS_TRUTH_ENABLED:
        return 0
    now = _utcnow()
    min_started_before = now - timedelta(seconds=RESULTS_MIN_AGE_S)
    try:
        items = (
            db.query(models.ValidationQueue)
            .filter(models.ValidationQueue.status == "processing")
            .filter(
                (models.ValidationQueue.started_at < min_started_before)
                | (models.ValidationQueue.started_at.is_(None))
            )
            .order_by(
                models.ValidationQueue.started_at.asc().nullsfirst(),
                models.ValidationQueue.id.asc(),
            )
            .limit(RESULTS_PER_TICK)
            .all()
        )
        if not items:
            return 0
        settled = 0
        for queue_item in items:
            try:
                run = _resolve_run_for_queue_item(db, queue_item)
                if not run:
                    continue
                # Stale-artifact guard: an all-success results.json written by
                # an OLD run cycle (e.g. after a requeue-all wave) must not
                # complete the CURRENT attempt. Require the file to have been
                # written after this attempt started (600s slack for clock
                # jitter between DB and NFS). Rows never dispatched (started_at
                # NULL) always carry old artifacts -> skip.
                if queue_item.started_at is None:
                    continue
                results_path = os.path.join(
                    RESULTS_ROOT, str(queue_item.entry_id), "results.json"
                )
                try:
                    mtime = os.path.getmtime(results_path)
                except OSError:
                    continue
                if now.timestamp() - mtime < RESULTS_MIN_AGE_S:
                    # exporter may still be writing this file
                    continue
                if mtime < (queue_item.started_at.timestamp() - 600):
                    # artifact predates this run attempt -> stale truth
                    continue
                stages = _read_results_stage_status(results_path)
                if not stages:
                    continue
                if all(s in ("success", "skipped", "warning") for s in stages.values()):
                    _settle_queue_item(db, queue_item, run, True, "settled via results.json (nfs-truth)")
                    _update_batch_counters(db, queue_item)
                    _log_activity_safe(
                        db,
                        job_id=queue_item.batch_id or f"validation-{queue_item.entry_id}",
                        activity_type="validation_completed",
                        message=f"Validation completed for entry {queue_item.entry_id} (nfs-truth settle)",
                        severity="info",
                        details={
                            "entry_id": queue_item.entry_id,
                            "bat3_run_id": run.id,
                            "celery_task_id": run.celery_task_id,
                            "settle_source": "results_truth",
                        },
                    )
                    db.commit()
                    settled += 1
            except Exception as item_error:
                logger.error(f"nfs-truth settle error for queue item {queue_item.id}: {item_error}")
                db.rollback()
                continue
        if settled:
            logger.info(f"nfs-truth: settled {settled} completed validations")
        return settled
    except Exception as e:
        logger.error(f"Error in nfs-truth settle: {e}")
        db.rollback()
        return 0


def sweep_stale_validations(db: Session, stale_hours: int = STALE_HOURS) -> dict:
    """Reconcile zombie state left by expired Celery results / dead workers.

    - bat3_runs 'running'/'pending' older than stale_hours -> failed ('stale_timeout')
    - queue items 'processing' older than stale_hours -> requeued with retry
      budget consumed; terminally failed (quarantine, entry failed too) once
      MAX_RETRIES stale cycles are reached (F-05)
    - entries stuck 'processing' with no live queue/run -> back to 'pending'
    - batch counters recomputed from queue rows; all-done -> 'completed'
    """
    cutoff = _utcnow() - timedelta(hours=stale_hours)
    stats = {"runs_failed": 0, "queue_requeued": 0, "queue_quarantined": 0,
             "entries_reset": 0, "batches_completed": 0}
    try:
        # 1) stale bat3 runs
        stale_runs = db.query(models.Bat3Run).filter(
            models.Bat3Run.status.in_(["running", "pending"]),
            models.Bat3Run.created_at < cutoff,
        ).all()
        for run in stale_runs:
            run.status = "failed"
            run.error_message = f"stale_timeout: no completion observed for >{stale_hours}h"
            run.completed_at = _utcnow()
            stats["runs_failed"] += 1

        # 2) stale processing queue rows -> requeue (or fail if retries exhausted)
        stale_items = db.query(models.ValidationQueue).filter(
            models.ValidationQueue.status == "processing",
            (models.ValidationQueue.started_at < cutoff)
            | ((models.ValidationQueue.started_at.is_(None)) & (models.ValidationQueue.created_at < cutoff)),
        ).all()
        # F-05: consume the shared retry budget per stale cycle; terminally
        # fail (quarantine) after MAX_RETRIES cycles instead of requeueing
        # forever - unbounded requeue was the pathological-straggler factory.
        for item in stale_items:
            item.retry_count = (item.retry_count or 0) + 1
            item.last_error = (
                f"stale_timeout: no completion for >{stale_hours}h "
                f"(stale cycle {item.retry_count}/{MAX_RETRIES})"
            )
            if item.retry_count < MAX_RETRIES:
                item.status = "queued"
                item.started_at = None
                stats["queue_requeued"] += 1
            else:
                _fail_queue_item(item, item.last_error, item.entry)
                stats["queue_quarantined"] += 1

        # 3) entries stuck 'processing' without an active queue row or run
        processing_entries = db.query(models.MddbEntry).filter(
            models.MddbEntry.status == "processing"
        ).all()
        for entry in processing_entries:
            active_queue = db.query(models.ValidationQueue).filter(
                models.ValidationQueue.entry_id == entry.id,
                models.ValidationQueue.status.in_(["queued", "processing"]),
            ).first()
            active_run = db.query(models.Bat3Run).filter(
                models.Bat3Run.entry_id == entry.id,
                models.Bat3Run.status.in_(["pending", "running"]),
            ).first()
            if not active_queue and not active_run:
                entry.status = "pending"
                stats["entries_reset"] += 1

        # 4) batch counters recompute
        running_batches = db.query(models.BatchRun).filter(
            models.BatchRun.status == "running"
        ).all()
        for batch in running_batches:
            rows = db.query(models.ValidationQueue).filter(
                models.ValidationQueue.batch_id == batch.batch_id
            ).all()
            if not rows:
                continue
            done = sum(1 for r in rows if r.status == "completed")
            failed = sum(1 for r in rows if r.status in ("failed", "cancelled"))
            batch.completed_entries = done
            batch.failed_entries = failed
            if batch.total_entries and (done + failed) >= batch.total_entries:
                batch.status = "completed"
                batch.completed_at = _utcnow()
                stats["batches_completed"] += 1

        if any(stats.values()):
            db.commit()
            logger.info(f"Stale sweep: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Error in stale sweep: {e}")
        db.rollback()
        return stats
