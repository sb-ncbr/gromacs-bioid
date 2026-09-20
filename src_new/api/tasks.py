"""Celery tasks for BAT3 pipeline."""

import logging
import os
from pathlib import Path
from typing import Optional

from src_new.celery_app import celery


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
    from src_new.pipeline_steps import build_load_and_export_tasks
    from src_new.executor.executor import PipelineExecutor
    from src_new.results.results_manager import ResultsManager
    from src_new.config.loader import RunConfig
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
        # Build tasks
        tasks = build_load_and_export_tasks()
        
        # Load config or use default
        if thread_config_path and thread_config_path.exists():
            config = RunConfig.from_ini_path(thread_config_path)
        else:
            config = RunConfig.from_default_ini()
        
        # Set the run UUID for PDB deployment file access
        config.pdb.curr_uuid = run_id
        
        # Create results manager and executor
        results_manager = ResultsManager(str(thread_results_path))
        executor = PipelineExecutor(
            steps=tasks,
            results_manager=results_manager,
            pipeline_name="BAT3"
        )
        
        # Run the pipeline
        executor.run(
            output_directory=thread_input_dir.parent,
            working_directory=thread_input_dir,
            run_config=config
        )
        
        return {"status": "completed", "run_id": run_id}
    except Exception as e:
        # Record critical error in results manager
        logger.error(f"Pipeline failed with exception: {e}")
        try:
            rm = ResultsManager(str(thread_results_path))
            rm.record_error(
                code="pipeline_execution_failed",
                message=str(e),
                critical=True,
                exception_type=type(e).__name__
            )
            rm.finish_run("failed")
        except Exception:
            pass  # Results manager may not exist yet
        
        return {"status": "failed", "run_id": run_id, "error": str(e)}
    finally:
        # Clean up log handlers
        try:
            teardown_run_log_handlers(log_handlers)
        except Exception:
            pass  # Don't break error logging on failure
