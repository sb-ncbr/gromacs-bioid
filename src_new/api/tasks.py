"""Celery tasks for BAT3 pipeline."""

import logging
import os
import signal
import socket
import threading
import time
from pathlib import Path
from typing import Optional

from src_new.api.run_reaper import read_run_status
from src_new.celery_app import celery

# --- W3 A1 (BH-039): per-run execution lock -------------------------------
# Broker Redis `timeout 60` closes idle consumer connections while both
# pool slots are busy; Celery then restores the unacked message and a
# second pod executes the SAME run concurrently into the same run
# directory (g0a2091-1028: 32/125 tasks received 2-3x; M13 x3, F14 x2).
_LOCK_PREFIX = "bat3:runlock:"
_LOCK_TTL_S = 120
_LOCK_HEARTBEAT_S = 30.0  # heartbeat cadence; also refreshes the lock TTL

_RELEASE_LOCK_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('del', KEYS[1]) else return 0 end")
_REFRESH_LOCK_LUA = (
    "if redis.call('get', KEYS[1]) == ARGV[1] then "
    "return redis.call('expire', KEYS[1], ARGV[2]) else return 0 end")


def _execution_token() -> str:
    """W3.1 item 5 (A1): hostname:pid:thread-ident. The fleet runs
    Celery with --pool=threads --concurrency=2, where hostname:pid alone
    is IDENTICAL for two duplicate executions inside one worker process
    — the token check could not tell them apart (a refresh by either
    thread would validate the other's lock, and either could release
    the other's lock)."""
    return (f"{socket.gethostname()}:{os.getpid()}:"
            f"{threading.get_ident()}")


def _run_lock_client():
    """Redis client for the per-run execution lock (CELERY_BROKER_URL).

    Short timeouts: a wedged broker must not wedge the task; the caller
    falls back to the heartbeat heuristic when this raises.
    """
    import redis as redis_lib
    url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
    return redis_lib.from_url(url, socket_timeout=3, socket_connect_timeout=3)


def _child_log_setup(run_dir: str):
    """Forked-child log setup (bughunt W3 A4 / BH-007).

    - SIGTERM back to SIG_DFL: the Celery pool worker installs a warm-
      shutdown SIGTERM handler; an inherited handler would swallow
      terminate() and force the parent onto the +30s SIGKILL escalation.
    - Strip ALL inherited ROOT handlers (removeHandler only - never close:
      the descriptors belong to the parent's handler objects).
    - Attach THIS run's handlers; returned for teardown before child exit.
    """
    from src_new.utils.logging_utils import (
        detach_inherited_root_handlers, setup_run_log_handlers)
    try:
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
    except (ValueError, OSError):
        pass  # not in main thread / restricted context: best effort
    detach_inherited_root_handlers()
    return setup_run_log_handlers(str(run_dir))


def _run_pipeline_child(run_id: str, input_dir: str, results_path: str,
                        config_path: Optional[str], conn) -> None:
    """Run the full pipeline in a CHILD process (bughunt BH-004).

    The threads-pool worker cannot be killed per-task: a C-level compute
    spin (bond-order ladder on capped glycan/coordinate-polymer fragments)
    hung worker slots forever — the in-thread ladder guard misses those
    classes. The parent task joins this child with a wall-clock limit
    (BAT3_PIPELINE_TIMEOUT_S) and terminates it on expiry, marking the run
    failed with code "timeout" and ACKING the message (no redelivery loop).
    """
    import multiprocessing  # noqa: F401  (documenting the context)
    from src_new.pipeline_steps import build_load_and_export_tasks
    from src_new.executor.executor import PipelineExecutor
    from src_new.results.results_manager import ResultsManager
    from src_new.config.loader import RunConfig
    from src_new.utils.logging_utils import teardown_run_log_handlers

    logger = logging.getLogger(f"pipeline_{run_id}")
    logger.setLevel(logging.INFO)
    run_dir = Path(input_dir).parent
    # Attach THIS run's handlers ONLY (W3 A4): strips anything inherited
    # from the fork parent first (removeHandler, never close).
    log_handlers = _child_log_setup(str(run_dir))

    if os.environ.get("SPIN_DEBUG") == "1":
        try:
            import faulthandler as _fh
            _fh.dump_traceback_later(120, repeat=True)
        except Exception:
            pass

    try:
        tasks = build_load_and_export_tasks()
        if config_path and Path(config_path).exists():
            config = RunConfig.from_ini_path(config_path)
        else:
            config = RunConfig.from_default_ini()
        config.pdb.curr_uuid = run_id

        results_manager = ResultsManager(results_path)
        executor = PipelineExecutor(
            steps=tasks,
            results_manager=results_manager,
            pipeline_name="BAT3",
        )
        executor.run(
            output_directory=Path(input_dir).parent,
            working_directory=Path(input_dir),
            run_config=config,
        )
        conn.send(("ok", None))
    except Exception as e:
        logger.error(f"Pipeline failed with exception: {e}")
        try:
            rm = ResultsManager(results_path)
            rm.record_error(
                code="pipeline_execution_failed",
                message=str(e),
                critical=True,
                exception_type=type(e).__name__,
            )
            rm.finish_run("failed")
        except Exception:
            pass
        conn.send(("failed", str(e)))
    finally:
        try:
            teardown_run_log_handlers(log_handlers)
        except Exception:
            pass
        try:
            conn.close()
        except Exception:
            pass


@celery.task(bind=True)
def run_pipeline_task(
    self,
    *,
    run_id: str,
    input_dir: str,
    results_path: str,
    config_path: Optional[str] = None,
) -> dict:
    """Run the BAT3 pipeline as a Celery task.

    W3 A1 (BH-039): an atomic per-run Redis lock makes broker
    redeliveries (the `timeout 60` consumer-drop class; 32/125 tasks in
    g0a2091-1028 executed 2-3x) a no-op instead of a second concurrent
    execution into the same run directory. The lock is taken BEFORE the
    first heartbeat touch, so a skipped redelivery never modifies the run
    directory. W3 A4 (BH-007): the parent attaches NO log handlers; all
    run-file handlers exist only inside the forked child.
    """
    from src_new.api.run_reaper import HEARTBEAT_NAME, STATUS_TERMINAL

    logger = logging.getLogger(f"pipeline_{run_id}")
    logger.setLevel(logging.INFO)
    thread_results_path = Path(results_path)
    run_dir = Path(input_dir).parent
    heartbeat_path = run_dir / HEARTBEAT_NAME

    # BH-005 (sticky terminal): an acks_late redelivery of this message
    # (e.g. after the reaper marked the run failed, or after a worker
    # hard-kill where the run actually completed) must NOT flip a
    # terminal run back to running — exit without touching results.
    status_now = read_run_status(thread_results_path)
    if status_now in STATUS_TERMINAL:
        logger.info(
            "run %s already terminal (%s) — redelivered message skipped",
            run_id, status_now)
        return {"status": "skipped_terminal", "run_id": run_id,
                "prior_status": status_now}

    # W3 A1: per-run atomic execution lock (SET NX EX + token-checked
    # refresh/release). Lock held => a duplicate execution is running
    # elsewhere: ACK (return) with skipped_running.
    lock_client = None
    lock_token = _execution_token()
    try:
        lock_client = _run_lock_client()
        got = lock_client.set(_LOCK_PREFIX + run_id, lock_token,
                              nx=True, ex=_LOCK_TTL_S)
        if not got:
            logger.info("[%s] skipped_running: execution lock held by "
                        "another worker", run_id)
            return {"status": "skipped_running", "run_id": run_id}
    except Exception as exc:
        # Broker unreachable -> heartbeat fallback: a RUNNING run with a
        # fresh heartbeat (<90 s) is being executed elsewhere; a stale
        # heartbeat means the other worker died -> proceed.
        lock_client = None
        logger.warning("[%s] run lock backend unavailable (%s); using "
                       "heartbeat fallback", run_id, exc)
        try:
            fresh = heartbeat_path.exists() and \
                (time.time() - heartbeat_path.stat().st_mtime) < 90
        except OSError:
            fresh = False
        if status_now == "running" and fresh:
            logger.info("[%s] skipped_running: run active elsewhere "
                        "(fresh heartbeat)", run_id)
            return {"status": "skipped_running", "run_id": run_id}

    # BH-005 (heartbeat): touch every 30 s while this task lives; the
    # reaper judges running runs by this file's mtime. A1: only AFTER
    # the lock decision. The loop also refreshes the lock TTL.
    _hb_stop = threading.Event()
    # W3.1 item 5 (A1): set when the lock was lost mid-run to a re-took
    # duplicate execution — aborts the child, acks aborted_lock_lost.
    _lock_lost = threading.Event()

    def _hb_loop() -> None:
        while not _hb_stop.wait(_LOCK_HEARTBEAT_S):
            try:
                heartbeat_path.touch()
            except Exception:
                pass
            if lock_client is not None:
                try:
                    ok = lock_client.eval(_REFRESH_LOCK_LUA, 1,
                                          _LOCK_PREFIX + run_id,
                                          lock_token, _LOCK_TTL_S)
                    if not ok:
                        # W3.1 item 5 (A1): the key vanished mid-run
                        # (Redis restart without persistence / eviction /
                        # failover — any outage > _LOCK_TTL_S). RE-TAKE
                        # it; if a redelivered duplicate already did, WE
                        # must stop: the duplicate owns the run now.
                        got = lock_client.set(
                            _LOCK_PREFIX + run_id, lock_token,
                            nx=True, ex=_LOCK_TTL_S)
                        if not got:
                            holder = None
                            try:
                                holder = lock_client.get(
                                    _LOCK_PREFIX + run_id)
                            except Exception:
                                pass
                            logger.error(
                                "[%s] execution lock lost mid-run (now "
                                "held by %r); aborting this execution — "
                                "the duplicate owns the run",
                                run_id, holder)
                            _lock_lost.set()
                            return
                except Exception:
                    pass  # backend down: retry on the next beat

    _hb_thread = threading.Thread(target=_hb_loop, daemon=True,
                                  name=f"hb_{run_id}")
    _hb_thread.start()

    # SPIN_DEBUG diagnostics (env-gated, no behavior change when unset):
    # every 120s dump ALL thread stacks to stderr so live-spin capture works
    # without ptrace (postmortem instrument for the unbounded-compute class).
    if os.environ.get("SPIN_DEBUG") == "1":
        try:
            import faulthandler as _fh
            _fh.dump_traceback_later(120, repeat=True)
            print("[SPIN_DEBUG] faulthandler stack dump timer armed (120s)", flush=True)
        except Exception as _spin_exc:
            print(f"[SPIN_DEBUG] failed to arm: {_spin_exc}", flush=True)

    try:
        outcome = _spawn_pipeline_child(run_id, input_dir,
                                        thread_results_path, config_path,
                                        abort_event=_lock_lost)
        if _lock_lost.is_set() and isinstance(outcome, dict):
            # keep the ack truthful even if the child raced to finish
            outcome.setdefault("status", "aborted_lock_lost")
        return outcome
    finally:
        _hb_stop.set()
        try:
            _hb_thread.join(timeout=2.0)
        except Exception:
            pass
        if lock_client is not None:
            try:
                lock_client.eval(_RELEASE_LOCK_LUA, 1,
                                 _LOCK_PREFIX + run_id, lock_token)
            except Exception:
                pass


def _spawn_pipeline_child(run_id: str, input_dir: str,
                          results_path: Path,
                          config_path: Optional[str],
                          abort_event: Optional[threading.Event] = None) -> dict:
    """BH-004 process isolation: run the pipeline in a CHILD process with
    a wall-clock limit. The threads pool cannot kill a C-level spin per
    task (the bond-order ladder hung R01/P24/M13/F13 forever); the child
    is terminated at the limit, the run is marked failed with code
    "timeout", and the message is ACKED (no redelivery loop). Default 3h
    matches the campaign watchdog horizon.
    """
    import multiprocessing
    from src_new.results.results_manager import ResultsManager

    logger = logging.getLogger(f"pipeline_{run_id}")
    limit_s = float(os.environ.get("BAT3_PIPELINE_TIMEOUT_S", 3 * 3600))
    ctx = multiprocessing.get_context("fork")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    child = ctx.Process(
        target=_run_pipeline_child,
        args=(run_id, input_dir, str(results_path),
              config_path, child_conn),
        name=f"pipeline_{run_id}",
        daemon=True,
    )

    child.start()
    child_conn.close()
    # W3.1 item 5 (A1): poll instead of one blocking join so a mid-run
    # lock loss (duplicate re-took the key) can abort the child. Same
    # wall-clock semantics for the timeout path as the old join().
    deadline = time.monotonic() + limit_s
    while child.is_alive():
        if abort_event is not None and abort_event.is_set():
            child.terminate()
            child.join(30.0)
            if child.is_alive():
                child.kill()
                child.join(10.0)
            logger.error(
                "pipeline child for %s aborted: execution lock lost "
                "mid-run to a duplicate execution", run_id,
            )
            try:
                rm = ResultsManager(str(results_path))
                rm.add_event(
                    "execution_lock_lost",
                    detail=(
                        "the per-run execution lock vanished mid-run "
                        "(Redis outage longer than the lock TTL) and a "
                        "redelivered duplicate execution re-took it; "
                        "this execution was aborted. The duplicate "
                        "owns the run."
                    ),
                )
            except Exception:
                pass
            return {"status": "aborted_lock_lost", "run_id": run_id,
                    "error": "execution_lock_lost"}
        if time.monotonic() >= deadline:
            break
        child.join(0.2)
    if child.is_alive():
        child.terminate()
        child.join(30.0)
        if child.is_alive():
            child.kill()
            child.join(10.0)
        logger.error(
            "pipeline child for %s exceeded %.0fs wall-clock — killed",
            run_id, limit_s,
        )
        try:
            rm = ResultsManager(str(results_path))
            rm.add_event(
                "task_timeout",
                detail=(
                    f"pipeline child process exceeded the "
                    f"{limit_s:.0f}s wall-clock limit and was "
                    "terminated (bughunt BH-004 isolation). Inputs "
                    "preserved — rerun the run to retry."
                ),
            )
            rm.record_error(
                code="timeout",
                message=(f"pipeline exceeded the {limit_s:.0f}s "
                         "wall-clock limit (worker slot freed by "
                         "process isolation)"),
                critical=True,
            )
            rm.finish_run("failed")
        except Exception:
            pass
        return {"status": "failed", "run_id": run_id,
                "error": "timeout"}

    outcome, detail = "crashed", f"child exit code {child.exitcode}"
    if parent_conn.poll(5.0):
        try:
            outcome, detail = parent_conn.recv()
        except Exception:
            pass
    parent_conn.close()

    if outcome == "ok":
        return {"status": "completed", "run_id": run_id}
    if outcome == "failed":
        return {"status": "failed", "run_id": run_id, "error": detail}
    # child died without a message (hard crash class)
    try:
        rm = ResultsManager(str(results_path))
        rm.record_error(
            code="pipeline_child_crashed",
            message=f"pipeline child process died unexpectedly ({detail})",
            critical=True,
        )
        rm.finish_run("failed")
    except Exception:
        pass
    return {"status": "failed", "run_id": run_id, "error": detail}
