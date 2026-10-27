"""Celery tasks for BAT3 pipeline."""

import logging
import os
from pathlib import Path
from typing import Optional

from src_new.celery_app import celery


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
    from src_new.utils.logging_utils import setup_run_log_handlers, teardown_run_log_handlers

    logger = logging.getLogger(f"pipeline_{run_id}")
    logger.setLevel(logging.INFO)
    run_dir = Path(input_dir).parent
    log_handlers = setup_run_log_handlers(str(run_dir))

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
    
    Args:
        run_id: The unique run identifier.
        input_dir: Path to the input directory containing uploaded files.
        results_path: Path to the results.json file.
        config_path: Optional path to the config.ini file.
    
    Returns:
        dict with status and results/error information.
    """
    # Import inside task to avoid event loop issues
    from src_new.results.results_manager import ResultsManager
    from src_new.utils.logging_utils import setup_run_log_handlers, teardown_run_log_handlers
    
    # Set up logging for the task
    logger = logging.getLogger(f"pipeline_{run_id}")
    logger.setLevel(logging.INFO)
    
    thread_input_dir = Path(input_dir)
    thread_results_path = Path(results_path)
    thread_config_path = Path(config_path) if config_path else None
    
    # Determine run_dir and attach log handlers
    run_dir = thread_input_dir.parent
    log_handlers = setup_run_log_handlers(str(run_dir))

    # BH-005 (sticky terminal): an acks_late redelivery of this message
    # (e.g. after the reaper marked the run failed, or after a worker
    # hard-kill where the run actually completed) must NOT flip a
    # terminal run back to running — exit without touching results.
    from src_new.api.run_reaper import STATUS_TERMINAL, read_run_status
    _prior_status = read_run_status(thread_results_path)
    if _prior_status in STATUS_TERMINAL:
        logging.getLogger(f"pipeline_{run_id}").info(
            "run %s already terminal (%s) — redelivered message skipped",
            run_id, _prior_status,
        )
        return {"status": "skipped_terminal", "run_id": run_id,
                "prior_status": _prior_status}

    # BH-005 (heartbeat): touch run_dir/heartbeat every 30 s while this
    # task lives. The reaper judges running runs by this file's mtime
    # (against a server-assigned probe), NOT by celery inspect — inspect
    # is unreliable on this fleet and queued messages are invisible to it.
    from src_new.api.run_reaper import HEARTBEAT_NAME
    import threading
    heartbeat_path = run_dir / HEARTBEAT_NAME
    try:
        heartbeat_path.touch()
    except Exception:
        heartbeat_path = None
    _hb_stop = threading.Event()

    def _hb_loop() -> None:
        while not _hb_stop.wait(30.0):
            try:
                if heartbeat_path is not None:
                    heartbeat_path.touch()
            except Exception:
                pass

    _hb_thread = threading.Thread(target=_hb_loop, daemon=True,
                                  name=f"hb_{run_id}")
    _hb_thread.start()

    # SPIN_DEBUG diagnostics (env-gated, no behavior change when unset):
    # every 120s dump ALL thread stacks to stderr so live-spin capture works
    # without ptrace (postmortem instrument for the unbounded-compute class).
    # (The pipeline itself now runs in a child process — the child arms its
    # own timer; this one watches the parent-side task thread.)
    if os.environ.get("SPIN_DEBUG") == "1":
        try:
            import faulthandler as _fh
            _fh.dump_traceback_later(120, repeat=True)
            print("[SPIN_DEBUG] faulthandler stack dump timer armed (120s)", flush=True)
        except Exception as _spin_exc:
            print(f"[SPIN_DEBUG] failed to arm: {_spin_exc}", flush=True)

    # bughunt BH-004 (process isolation): the pipeline runs in a CHILD
    # process with a wall-clock limit. The threads pool cannot kill a
    # C-level spin per task (the bond-order ladder hung R01/P24/M13/F13
    # forever — the in-thread guard misses capped/coordinate-polymer
    # fragments); the child is terminated at the limit, the run is marked
    # failed with code "timeout", and the message is ACKED (no
    # redelivery loop). Default 3h matches the campaign watchdog horizon.
    import multiprocessing
    from src_new.results.results_manager import ResultsManager
    limit_s = float(os.environ.get("BAT3_PIPELINE_TIMEOUT_S", 3 * 3600))
    ctx = multiprocessing.get_context("fork")
    parent_conn, child_conn = ctx.Pipe(duplex=False)
    child = ctx.Process(
        target=_run_pipeline_child,
        args=(run_id, input_dir, str(thread_results_path),
              config_path, child_conn),
        name=f"pipeline_{run_id}",
        daemon=True,
    )

    try:
        child.start()
        child_conn.close()
        child.join(limit_s)
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
                rm = ResultsManager(str(thread_results_path))
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
            rm = ResultsManager(str(thread_results_path))
            rm.record_error(
                code="pipeline_child_crashed",
                message=f"pipeline child process died unexpectedly ({detail})",
                critical=True,
            )
            rm.finish_run("failed")
        except Exception:
            pass
        return {"status": "failed", "run_id": run_id, "error": detail}
    finally:
        # Clean up log handlers
        try:
            _hb_stop.set()
            _hb_thread.join(timeout=2.0)
        except Exception:
            pass
        try:
            teardown_run_log_handlers(log_handlers)
        except Exception:
            pass  # Don't break error logging on failure
