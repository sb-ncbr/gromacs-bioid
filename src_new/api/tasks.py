"""Celery tasks for BAT3 pipeline."""

import logging
import os
import signal
import socket
import threading
import time
from pathlib import Path
from typing import Optional

from celery.exceptions import Reject
from celery.signals import worker_shutting_down

from src_new import cancellation, retries
from src_new.api.run_reaper import read_pipeline, read_run_status
from src_new.celery_app import celery

# --- W3 A1 (BH-039): per-run execution lock -------------------------------
# Broker Redis `timeout 60` closes idle consumer connections while both
# pool slots are busy; Celery then restores the unacked message and a
# second pod executes the SAME run concurrently into the same run
# directory (g0a2091-1028: 32/125 tasks received 2-3x; M13 x3, F14 x2).
_LOCK_PREFIX = "bat3:runlock:"
_LOCK_TTL_S = 120
_LOCK_HEARTBEAT_S = 30.0  # heartbeat cadence; also refreshes the lock TTL
# 2026-11-23: after a cancel the pipeline gets this long to stop by itself
# (cancellation.py) before its process group is terminated.
_CANCEL_GRACE_S = 20.0
# 2026-11-23: graceful worker shutdown (SIGTERM: redeploy, scale-down,
# eviction). Celery's warm-shutdown handler sends worker_shutting_down in the
# main process before it waits for running tasks; every running task then
# stops its pipeline (SIGTERM, SIGKILL after _SHUTDOWN_STOP_S), puts the run
# back in the queue under the same run id (retries.restart: not an attempt)
# and returns, so its message is acked. Well within the pod's grace period
# (terminationGracePeriodSeconds: 60).
_WORKER_STOPPING = threading.Event()
_SHUTDOWN_STOP_S = 3.0


@worker_shutting_down.connect
def _on_worker_shutting_down(**_kwargs) -> None:
    _WORKER_STOPPING.set()


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
            run_id=run_id,
        )
        conn.send(("ok", None))
    except cancellation.RunCancelled:
        # 2026-11-23: the executor already marked the run cancelled (or the
        # run was deleted); nothing to record here
        logger.warning("Pipeline %s cancelled", run_id)
        conn.send(("cancelled", None))
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
    dispatch: Optional[str] = None,
) -> dict:
    """Run the BAT3 pipeline as a Celery task.

    W3 A1 (BH-039): an atomic per-run Redis lock makes broker
    redeliveries (the `timeout 60` consumer-drop class; 32/125 tasks in
    g0a2091-1028 executed 2-3x) a no-op instead of a second concurrent
    execution into the same run directory. The lock is taken BEFORE the
    first heartbeat touch, so a skipped redelivery never modifies the run
    directory. W3 A4 (BH-007): the parent attaches NO log handlers; all
    run-file handlers exist only inside the forked child.

    2026-11-23: `dispatch` is set when the run was re-queued (retries.py);
    a message older than the run's pipeline.dispatch ends skipped_superseded.
    A worker shutting down hands an unstarted message back to the broker and
    re-queues a started run (_WORKER_STOPPING).
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
    pipeline_now = read_pipeline(thread_results_path)
    status_now = (pipeline_now or {}).get("status")
    # A finished attempt waiting for its automatic retry (retries.py) is
    # re-queued by the reaper with a fresh results.json, never redelivered.
    if status_now in STATUS_TERMINAL or status_now == "retry_scheduled":
        logger.info(
            "run %s already terminal (%s) — redelivered message skipped",
            run_id, status_now)
        return {"status": "skipped_terminal", "run_id": run_id,
                "prior_status": status_now}
    # 2026-11-23: cancelled or deleted while queued (revoke only reaches
    # workers that are up when it is sent)
    if cancellation.is_cancelled(run_id, run_dir):
        logger.info("run %s was cancelled or deleted — not started", run_id)
        return {"status": "skipped_cancelled", "run_id": run_id}
    # 2026-11-23: the run was re-queued since this message was sent (worker
    # restart, worker lost): the newer message runs it, now or later
    current_dispatch = (pipeline_now or {}).get("dispatch")
    if current_dispatch and dispatch != current_dispatch:
        logger.info("run %s was re-queued since this message was sent — "
                    "skipped_superseded", run_id)
        return {"status": "skipped_superseded", "run_id": run_id,
                "prior_status": status_now}
    # 2026-11-23: the worker is shutting down: hand the message back
    if _WORKER_STOPPING.is_set():
        logger.info("run %s not started: the worker is shutting down", run_id)
        raise Reject("worker shutting down", requeue=True)

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
    # 2026-11-23: and once now: a re-queued run's heartbeat is as old as its
    # last execution, and the reaper must not take the new one for dead
    # before the first beat.
    try:
        heartbeat_path.touch()
    except Exception:
        pass
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

    requeued = None  # 2026-11-23: the new dispatch after a worker restart
    try:
        if _WORKER_STOPPING.is_set():
            # 2026-11-23: shutting down since the checks above: not started
            raise Reject("worker shutting down", requeue=True)
        outcome = _spawn_pipeline_child(run_id, input_dir,
                                        thread_results_path, config_path,
                                        abort_event=_lock_lost,
                                        stop_event=_WORKER_STOPPING)
        if _lock_lost.is_set() and isinstance(outcome, dict):
            # keep the ack truthful even if the child raced to finish
            outcome.setdefault("status", "aborted_lock_lost")
        if isinstance(outcome, dict) and outcome.get("status") == "interrupted":
            # 2026-11-23: written while this execution still holds the run
            # lock, so a stale message arriving meanwhile sees the new
            # dispatch; the task is sent only after the lock is released
            # (below), or the new message would end skipped_running.
            outcome, requeued = _requeue_after_shutdown(run_id, run_dir, thread_results_path)
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
    if requeued:
        try:
            # the queue this message came from (workers lack the web lane's
            # queue name, VALIDATION_UI_QUEUE)
            queue = (getattr(self.request, "delivery_info", None) or {}).get("routing_key")
            retries.send_task(run_dir, requeued, queue=queue)
        except Exception as exc:
            # 2026-11-23: no new message: this one stays the run's message
            # and goes back to the broker
            logger.error("run %s: cannot send the re-queued task (%s); handing "
                         "this message back", run_id, exc)
            try:
                retries.set_dispatch(run_dir, dispatch)
            except Exception as exc2:
                logger.error("run %s: cannot restore its dispatch (%s)", run_id, exc2)
            raise Reject("re-queue failed", requeue=True)
        logger.warning("run %s re-queued under the same run id: the worker is "
                       "shutting down", run_id)
    return outcome


def _requeue_after_shutdown(run_id: str, run_dir: Path, results_path: Path):
    """2026-11-23: the pipeline was stopped because the worker is shutting
    down. Returns (task result, new dispatch or None). A cancelled run ends
    cancelled, a finished one keeps its status; when results.json cannot be
    rewritten the message goes back to the broker as it is (Reject)."""
    logger = logging.getLogger(f"pipeline_{run_id}")
    if cancellation.is_cancelled(run_id, run_dir, fresh=True):
        return _finish_cancelled(run_id, run_dir, results_path), None
    try:
        new = retries.restart(run_dir, detail=(
            "the worker running this run shut down (redeploy, scale-down or "
            "eviction); the run was queued again under the same run id and "
            "starts over"))
    except Exception as exc:
        logger.error("run %s: cannot re-queue it after the shutdown (%s); "
                     "handing the message back", run_id, exc)
        raise Reject("re-queue failed", requeue=True)
    if new is None:
        if cancellation.is_cancelled(run_id, run_dir, fresh=True):
            return _finish_cancelled(run_id, run_dir, results_path), None
        return {"status": "skipped_terminal", "run_id": run_id,
                "prior_status": read_run_status(results_path)}, None
    return {"status": "requeued_worker_restart", "run_id": run_id,
            "dispatch": new}, new


def _ncbi_extension_for(config_path: Optional[str]) -> float:
    """Extra wall-clock seconds for a run searching NCBI nr/nt/core_nt (the
    identify budget grows by the same amount, pipeline_steps.ncbi_extension_s)."""
    try:
        from src_new.config.loader import RunConfig
        from src_new.pipeline_steps import ncbi_extension_s
        if config_path and Path(config_path).exists():
            config = RunConfig.from_ini_path(config_path)
        else:
            config = RunConfig.from_default_ini()
        return float(ncbi_extension_s(config))
    except Exception:
        return 0.0


def _spawn_pipeline_child(run_id: str, input_dir: str,
                          results_path: Path,
                          config_path: Optional[str],
                          abort_event: Optional[threading.Event] = None,
                          stop_event: Optional[threading.Event] = None) -> dict:
    """BH-004 process isolation: run the pipeline in a CHILD process with
    a wall-clock limit. The threads pool cannot kill a C-level spin per
    task (the bond-order ladder hung R01/P24/M13/F13 forever); the child
    is terminated at the limit, the run is marked failed with code
    "timeout", and the message is ACKED (no redelivery loop). Default 3h
    matches the campaign watchdog horizon.

    2026-11-23: `stop_event` set (the worker is shutting down): the child is
    stopped within seconds and {"status": "interrupted"} returned; the
    caller re-queues the run.
    """
    import multiprocessing
    from src_new.results.results_manager import ResultsManager

    logger = logging.getLogger(f"pipeline_{run_id}")
    limit_s = float(os.environ.get("BAT3_PIPELINE_TIMEOUT_S", 3 * 3600)) \
        + _ncbi_extension_for(config_path)
    ctx = multiprocessing.get_context("fork")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    child = ctx.Process(
        target=_child_entry,
        args=(_run_pipeline_child, run_id, input_dir, str(results_path),
              config_path, child_conn),
        name=f"pipeline_{run_id}",
        daemon=True,
    )
    run_dir = Path(input_dir).parent
    cancel_seen = None  # 2026-11-23: monotonic time the cancel was first seen

    child.start()
    child_conn.close()
    # W3.1 item 5 (A1): poll instead of one blocking join so a mid-run
    # lock loss (duplicate re-took the key) can abort the child. Same
    # wall-clock semantics for the timeout path as the old join().
    deadline = time.monotonic() + limit_s
    while child.is_alive():
        if abort_event is not None and abort_event.is_set():
            _stop_child(child)
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
        # 2026-11-23: cancel/delete (cancellation.py; cached, so cheap here).
        # The pipeline stops by itself within seconds; if it does not (a
        # C-level compute, a wait not covered), stop its process group.
        if cancellation.is_cancelled(run_id, run_dir):
            if cancel_seen is None:
                cancel_seen = time.monotonic()
                logger.warning("run %s cancelled; waiting %.0fs for the pipeline to stop",
                               run_id, _CANCEL_GRACE_S)
            elif time.monotonic() - cancel_seen >= _CANCEL_GRACE_S:
                logger.error("run %s cancelled; pipeline did not stop — terminating it", run_id)
                _stop_child(child)
                parent_conn.close()
                return _finish_cancelled(run_id, run_dir, results_path)
        # 2026-11-23: the worker is shutting down: stop now, the caller
        # re-queues the run (a cancel seen above wins, without its grace)
        if stop_event is not None and stop_event.is_set():
            logger.warning("run %s: the worker is shutting down; stopping the "
                           "pipeline", run_id)
            _stop_child(child, grace_s=_SHUTDOWN_STOP_S)
            parent_conn.close()
            if cancel_seen is not None:
                return _finish_cancelled(run_id, run_dir, results_path)
            return {"status": "interrupted", "run_id": run_id}
        if time.monotonic() >= deadline:
            break
        child.join(0.2)
    if child.is_alive():
        _stop_child(child)
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

    if outcome == "cancelled" or (outcome != "ok" and cancellation.is_cancelled(run_id, run_dir)):
        return _finish_cancelled(run_id, run_dir, results_path)
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


def _child_entry(target, *args) -> None:
    """2026-11-23: the pipeline child leads its own process group, so stopping
    it also stops the BLAST / Foldseek processes it started (_stop_child)."""
    try:
        os.setpgid(0, 0)
    except OSError:
        pass
    target(*args)


def _stop_child(child, grace_s: float = 30.0) -> None:
    """SIGTERM the pipeline child and its process group, SIGKILL after
    `grace_s` (2026-11-23: terminate() alone left its BLAST runs behind)."""
    try:
        group = os.getpgid(child.pid) == child.pid
    except OSError:
        group = False

    def send(sig) -> None:
        try:
            if group:
                os.killpg(child.pid, sig)
            else:
                os.kill(child.pid, sig)
        except OSError:
            pass

    send(signal.SIGTERM)
    child.join(grace_s)
    if child.is_alive():
        send(signal.SIGKILL)
        child.join(10.0)
    elif group:
        send(signal.SIGKILL)  # whatever of the group ignored SIGTERM


def _finish_cancelled(run_id: str, run_dir: Path, results_path: Path) -> dict:
    """2026-11-23: a cancelled run ends "cancelled" (a pipeline write may have
    overwritten the API's status); a deleted run's directory stays deleted."""
    logger = logging.getLogger(f"pipeline_{run_id}")
    results_path = Path(results_path)
    try:
        if results_path.exists():
            from src_new.results.results_manager import ResultsManager
            rm = ResultsManager(str(results_path))
            if rm._payload.get("pipeline", {}).get("status") != "cancelled":
                rm.add_event("run_cancelled", detail="stopped by the worker")
                rm.finish_run("cancelled")
        elif run_dir.exists():
            # deleted while the pipeline ran: whatever it wrote since then
            import shutil
            shutil.rmtree(run_dir, ignore_errors=True)
            logger.warning("run %s was deleted; removed what the pipeline wrote after", run_id)
    except Exception as exc:
        logger.warning("run %s: cannot record the cancel (%s)", run_id, exc)
    return {"status": "cancelled", "run_id": run_id}
