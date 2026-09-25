"""Celery tasks for validation API."""

import sys
from pathlib import Path

from celery import Celery

from src_new.config.loader import CELERY_BROKER_URL, DATABASE_URL
from src_new.celery_app import redis_broker_transport_opts

# Initialize Celery app
celery = Celery("validation", broker=CELERY_BROKER_URL)

# Configure Celery
celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_always_eager=False,  # Queue tasks to Redis, don't run locally
    task_ignore_result=False,  # Store task results
    # 2026-09-25 wedge-class hardening: bounds broker READS only, never task
    # execution; see redis_broker_transport_opts docstring. This app (the
    # validation worker fleet) previously had NO transport hardening at all.
    broker_connection_retry=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options=redis_broker_transport_opts(),
)


@celery.task
def schedule_validation(
    entry_id: int,
    input_dir: str,
    results_path: str,
    config_path: str,
) -> str:
    """
    Schedule a validation run for an entry by calling BAT3 worker task.

    Args:
        entry_id: The MDDB entry ID.
        input_dir: Path to input directory with data files.
        results_path: Path to results.json output file.
        config_path: Path to config.ini file.

    Returns:
        Celery task ID.
    """
    import logging
    from mddbr_client import download_simulation_files
    from src_new.api.tasks import run_pipeline_task
    from sqlalchemy import create_engine, text
    from src_new.config.loader import DATABASE_URL
    
    logger = logging.getLogger(__name__)
    
    # First, fetch entry info from database to get local_accession
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT local_accession FROM mddb_entries WHERE id = :entry_id"),
                {"entry_id": entry_id}
            )
            row = result.fetchone()
            
            if not row:
                logger.error(f"Entry {entry_id} not found in database")
                return f"failed-entry-{entry_id}-not-found"
            
            local_accession = row.local_accession
            logger.info(f"Entry {entry_id} has local_accession: {local_accession}")
            
            # Download simulation files
            logger.info(f"Downloading files for {local_accession}...")
            success, _failure_class = download_simulation_files(
                db_session=None,
                entry_id=entry_id,
                local_accession=local_accession,
                input_dir=input_dir
            )

            if not success:
                logger.error(
                    f"Failed to download files for entry {entry_id}: {_failure_class}"
                )
                return f"failed-download-{entry_id}"
            
            logger.info(f"Files downloaded successfully for {entry_id}")
            
            # Now run the pipeline
            run_id = f"validation-{entry_id}"
            task = run_pipeline_task.delay(
                run_id=run_id,
                input_dir=input_dir,
                results_path=results_path,
                config_path=config_path,
            )
            return task.id
            
    except Exception as e:
        logger.error(f"Error scheduling validation for entry {entry_id}: {e}")
        import traceback
        traceback.print_exc()
        return f"failed-{entry_id}-{str(e)}"


@celery.task
def fetch_entry_metadata(entry_id: int, local_accession: str) -> dict:
    """
    Fetch metadata for an entry from MDDBR.

    Args:
        entry_id: The MDDB entry ID.
        local_accession: The local accession identifier.

    Returns:
        Dict with metadata status.
    """
    from .mddbr_client import MddbrClient

    client = MddbrClient()
    try:
        project = client.get_project(local_accession)
        references = client.get_references(local_accession)
        filenotes = client.get_filenotes(local_accession)
        
        return {
            "entry_id": entry_id,
            "status": "success",
            "project": project,
            "references_count": len(references) if references else 0,
            "filenotes_count": len(filenotes) if filenotes else 0,
        }
    except Exception as e:
        return {
            "entry_id": entry_id,
            "status": "failed",
            "error": str(e),
        }

# Import run_pipeline_task to register it on this celery app
# This is needed because schedule_validation calls run_pipeline_task
from src_new.api.tasks import run_pipeline_task as _run_pipeline_task_ref
