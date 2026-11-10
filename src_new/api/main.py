"""FastAPI application for BAT3 Pipeline API."""

import os
import re
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, func, text
from sqlalchemy.orm import sessionmaker, Session

from . import tasks
from .routes.runs import router as runs_router, get_runs_dir
from .models import CapabilitiesResponse

logger = logging.getLogger(__name__)

# Database setup
# F-06: no credentials / resolvable cluster service name in repo defaults.
# Cluster always provides DATABASE_URL via env; the default is for local dev.
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://validation@localhost:5432/bat3_validation")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    runs_dir = get_runs_dir()
    runs_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=str(runs_dir)), name="files")
    logger.info("Initializing database tables...")
    # Zombie-run reconciler (OQ-16): marks runs failed whose celery task
    # vanished (worker hard-kill). Redis leader-locked inside; one sweeper
    # cluster-wide despite --workers 4. BAT3_RUN_REAPER=0 disables.
    from src_new.celery_app import celery as celery_app
    from src_new.api.run_reaper import start_reaper
    reaper_task = start_reaper(celery_app, runs_dir)
    yield
    if reaper_task is not None:
        reaper_task.cancel()


API_DESCRIPTION = """
Identify the biomolecules in a molecular dynamics simulation: upload the
files, poll the run, read the identifications.

* **REST API guide**: [/documentation/rest-api/](/documentation/rest-api/)
* **results.json structure**: [/documentation/results-json/](/documentation/results-json/)
* **For AI assistants**: the MCP server at `/mcp` ([guide](/documentation/mcp/))

Typical flow: `POST /api/v1/runs` (multipart: `files`, optional `run_name`,
`preset`, `config_json`) → poll `GET /api/v1/runs/{run_id}/status` until
`pipeline.status` is `success` or `failed` → `GET .../molecules`,
`.../verification`, `.../download/results.csv` or `.../download/results.json`.
No account is needed. Each file may be up to 128 MiB.
"""

app = FastAPI(
    title="BioID API",
    version="1",
    description=API_DESCRIPTION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
# The ingress routes /api and /files straight here: without this every JSON
# payload and the system mmCIF (22 MB text for a 240k-atom run) went out
# uncompressed. Streams (text/event-stream) are excluded by Starlette.
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)


def _run_file_allowed(path: str) -> bool:
    """/files/<run id>/<file> of a real run only. The runs directory also
    holds the shared resolver cache (everyone's searches), its old copies,
    staging and trash: none of that is served."""
    from src_new.api.security import valid_run_id
    parts = path[len("/files/"):].split("/")
    if parts[0] == "adhoc" or parts[0].startswith("validation-"):
        return True  # dedicated guarded routes above
    if len(parts) < 2 or not valid_run_id(parts[0]) or any(
            not p or p.startswith(".") or p.startswith("_") for p in parts):
        return False
    return (get_runs_dir() / parts[0] / "results.json").is_file()


@app.middleware("http")
async def harden_run_files(request, call_next):
    """/files serves what users uploaded and what runs produced from the
    BioID origin: only inside real run directories, and never let a browser
    sniff it into HTML or run scripts in it (an uploaded page would otherwise
    be live on this domain)."""
    if request.url.path.startswith("/files/") and not _run_file_allowed(request.url.path):
        return JSONResponse({"detail": "Not Found"}, status_code=404, headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'"})
    response = await call_next(request)
    if request.url.path.startswith("/files/"):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "sandbox; default-src 'none'"
    return response

app.include_router(runs_router, prefix="/runs", tags=["runs"])
app.include_router(runs_router, prefix="/api/v1/runs", tags=["runs"])
# /admin page backend (src_new/api/admin.py); not in the published schema
from .admin import router as admin_router  # noqa: E402
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# --- Capabilities advertisement (v3.143, BACKEND_GAPS contract) -----------
# Marker bumps once per additive wave; wave B1 (G1/G2/G3/G6/G8) = 1.
# Keep API_ADDITIONS in sync with test_api_contract.py's registered table.
API_ADDITIONS = [
    "api_v1",
    "run_name_summary",          # G1 — run_name on the run summary
    "segment_meta_copies",       # G3 — copies/display_name/chain per segment
    "segment_progress",          # G2 — /status progress block
    "results_csv",               # G6 — run-level CSV download
    "warning_details_segment_service",  # G4 — segment/service in warning details
    "hit_name_organism",       # G5 — name/organism on verified hits
    "unique_segment_names",    # G7 — full unique-group segments
    "segment_selectors",       # G9 — per-segment selectors on /render
    "capabilities",              # this endpoint
]


def _api_capabilities() -> CapabilitiesResponse:
    """Capabilities payload; typical-duration range comes from
    deployment env (BAT3_TYPICAL_DURATION_MIN/_MAX — BACKEND_GAPS G8),
    null when either is unset or malformed (UI shows its own estimate)."""
    from ..results.results_manager import _code_version

    duration: Optional[Dict[str, int]] = None
    try:
        dmin = os.environ.get("BAT3_TYPICAL_DURATION_MIN")
        dmax = os.environ.get("BAT3_TYPICAL_DURATION_MAX")
        if dmin is not None and dmax is not None:
            duration = {"min": int(dmin), "max": int(dmax)}
    except (TypeError, ValueError):
        duration = None

    return CapabilitiesResponse(
        api_version_marker=2,
        additions=list(API_ADDITIONS),
        typical_duration_minutes=duration,
        code_version=_code_version(),
    )


@app.get("/capabilities", response_model=CapabilitiesResponse)
@app.get("/api/v1/capabilities", response_model=CapabilitiesResponse)
async def get_capabilities():
    return _api_capabilities()


# --- Adhoc (run-independent) file serving (W3 A9, BH-044) -----------------
# Workers stage segment mmCIFs as <adhoc_root>/<sha256>.cif; RCSB structure
# search is pointed at /files/adhoc/<sha256>.cif — no run registry lookup,
# so Celery-dispatched runs get working structure search. Strict
# sha256 filename guard keeps the route read-only-safe.
# W3.2 item 3 (A9): pdb_struct stages query .pdb files the same way —
# both suffixes are accepted, nothing else.
_ADHOC_NAME_RE = re.compile(r"^[0-9a-f]{64}\.(cif|pdb)$")


def _adhoc_files_root() -> Path | None:
    """W3.1 item 4 (A9): the RAW env string is checked BEFORE Path() —
    ``Path("")`` is ``"."`` (truthy), which left the unset-env 404 guard
    dead and served sha-named files from the container CWD. Read per
    request so late/test-time env changes take effect."""
    raw = os.environ.get("BAT3_ADHOC_DIR", "").strip()
    return Path(raw) if raw else None


@app.get("/files/adhoc/{filename}", include_in_schema=False)
async def serve_adhoc_file(filename: str):
    """Serve a worker-staged adhoc mmCIF/PDB by content sha256 (404 on miss)."""
    root = _adhoc_files_root()
    if root is None or not _ADHOC_NAME_RE.match(filename):
        raise HTTPException(status_code=404, detail="Not Found")
    target = root / filename
    if not target.is_file():
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(str(target))


# --- Validation-runs file serving (F-N1a) ---------------------------------
# Registered BEFORE the /files StaticFiles mount (mount is added in lifespan,
# i.e. after import-time routes), so this pattern wins for validation-uuids;
# everything else under /files falls through to the static mount unchanged.
VALIDATION_FILES_ROOT = Path(os.environ.get("VALIDATION_FILES_ROOT", "/data/validation"))


@app.get("/files/validation-{rest:path}", include_in_schema=False)
async def serve_validation_file(rest: str):
    """Serve files for validation runs by uuid (validation-<eid>-<ts>).

    Resolved via VALIDATION_FILES_ROOT (validation NFS mount, read-only).
    Absent root / unknown uuid / traversal attempts -> 404 (same as before).
    """
    from .validation_files import resolve_validation_file

    target = resolve_validation_file(rest, VALIDATION_FILES_ROOT)
    if target is None:
        raise HTTPException(status_code=404, detail="Not Found")
    return FileResponse(str(target))


@app.get("/api/v1/health")
async def api_v1_health():
    """Health check for the /api/v1 namespace."""
    return {"status": "healthy"}


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    runs_dir = get_runs_dir()
    if not runs_dir.exists() or not os.access(str(runs_dir), os.W_OK):
        raise HTTPException(status_code=503, detail="Runs directory not writable")
    return {"status": "ready"}


@app.get("/runs/{run_id}/task")
async def get_task_status(run_id: str):
    from src_new.celery_app import celery
    result = celery.AsyncResult(run_id)
    return {"run_id": run_id, "status": result.status, "result": result.result if result.ready() else None}


@app.get("/stats")
async def get_stats():
    """Get validation statistics from database."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    
    db = SessionLocal()
    try:
        entries_total = db.query(func.count(db_models.MddbEntry.id)).scalar() or 0
        entries_pending = db.query(func.count(db_models.MddbEntry.id)).filter(db_models.MddbEntry.status == "pending").scalar() or 0
        entries_processing = db.query(func.count(db_models.MddbEntry.id)).filter(db_models.MddbEntry.status == "processing").scalar() or 0
        entries_completed = db.query(func.count(db_models.MddbEntry.id)).filter(db_models.MddbEntry.status == "completed").scalar() or 0
        entries_failed = db.query(func.count(db_models.MddbEntry.id)).filter(db_models.MddbEntry.status == "failed").scalar() or 0
        
        runs_total = db.query(func.count(db_models.Bat3Run.id)).scalar() or 0
        runs_completed = db.query(func.count(db_models.Bat3Run.id)).filter(db_models.Bat3Run.status == "completed").scalar() or 0
        runs_pending = db.query(func.count(db_models.Bat3Run.id)).filter(db_models.Bat3Run.status.in_(['pending', 'processing'])).scalar() or 0
        runs_failed = db.query(func.count(db_models.Bat3Run.id)).filter(db_models.Bat3Run.status == "failed").scalar() or 0
        
        queue_pending = db.query(func.count(db_models.ValidationQueue.id)).filter(db_models.ValidationQueue.status == "queued").scalar() or 0
        
        return {
            "entries_total": entries_total,
            "entries_pending": entries_pending,
            "entries_processing": entries_processing,
            "entries_completed": entries_completed,
            "entries_failed": entries_failed,
            "runs_total": runs_total,
            "runs_completed": runs_completed,
            "runs_pending": runs_pending,
            "runs_failed": runs_failed,
            "queue_pending": queue_pending
        }
    finally:
        db.close()


@app.get("/stats/dashboard")
async def get_dashboard_stats():
    """Dashboard statistics - alias for /stats."""
    return await get_stats()


# ============== VALIDATION ENDPOINTS ==============

@app.get("/validation/queue/status")
async def get_queue_status():
    """Get validation queue status summary."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    
    db = SessionLocal()
    try:
        total = db.query(func.count(db_models.ValidationQueue.id)).scalar()
        queued = db.query(func.count(db_models.ValidationQueue.id)).filter(db_models.ValidationQueue.status == "queued").scalar()
        processing = db.query(func.count(db_models.ValidationQueue.id)).filter(db_models.ValidationQueue.status == "processing").scalar()
        completed = db.query(func.count(db_models.ValidationQueue.id)).filter(db_models.ValidationQueue.status == "completed").scalar()
        failed = db.query(func.count(db_models.ValidationQueue.id)).filter(db_models.ValidationQueue.status == "failed").scalar()
        paused = db.query(func.count(db_models.ValidationQueue.id)).filter(db_models.ValidationQueue.status == "paused").scalar()
        
        progress_percent = ((completed + failed) / total * 100) if total > 0 else 0
        
        # Get active batches from batch_runs table
        active_batches = []
        batch_runs = db.query(db_models.BatchRun).filter(
            db_models.BatchRun.status.in_(["running", "processing", "pending"])
        ).order_by(db_models.BatchRun.created_at.desc()).limit(10).all()
        
        for run in batch_runs:
            active_batches.append({
                "batch_id": run.batch_id,
                "status": run.status,
                "total_entries": run.total_entries or 0,
                "completed_entries": run.completed_entries or 0,
                "failed_entries": run.failed_entries or 0,
                "started_at": str(run.created_at) if run.created_at else None
            })
        
        return {
            "queue": {
                "queued": queued,
                "processing": processing,
                "paused": paused,
                "completed": completed,
                "failed": failed,
                "progress_percent": progress_percent
            },
            "active_batches": active_batches
        }
    finally:
        db.close()


@app.get("/validation/queue/list")
async def get_queue_list(
    status: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List validation queue items with entry details."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    
    db = SessionLocal()
    try:
        query = db.query(db_models.ValidationQueue)
        if status:
            query = query.filter(db_models.ValidationQueue.status == status)
        items = query.order_by(db_models.ValidationQueue.created_at.desc()).offset(offset).limit(limit).all()
        
        result = []
        for item in items:
            entry = db.query(db_models.MddbEntry).filter(
                db_models.MddbEntry.id == item.entry_id
            ).first()
            result.append({
                "id": item.id,
                "entry_id": item.entry_id,
                "entry_local_accession": entry.local_accession if entry else f"Entry #{item.entry_id}",
                "batch_id": item.batch_id,
                "status": item.status,
                "priority": 0,
                "created_at": str(item.created_at) if item.created_at else None,
                "started_at": str(item.started_at) if hasattr(item, 'started_at') and item.started_at else None,
                "completed_at": str(item.completed_at) if hasattr(item, 'completed_at') and item.completed_at else None,
                "last_error": item.error_message if hasattr(item, 'error_message') and item.error_message else None
            })
        
        return {
            "items": result,
            "total": query.count()
        }
    finally:
        db.close()


@app.get("/validation/queue/workers")
async def get_queue_workers():
    """Get list of active Celery workers."""
    try:
        from src_new.celery_app import celery
        inspect = celery.control.inspect()
        active_workers = inspect.active() or {}
        registered = inspect.registered() or {}
        stats = inspect.stats() or {}
        
        workers = []
        for worker_name, tasks in active_workers.items():
            worker_info = {
                "worker_name": worker_name,
                "active_tasks": len(tasks) if tasks else 0,
                "registered_tasks": len(registered.get(worker_name, [])),
                "status": "online"
            }
            if worker_name in stats:
                worker_info["pool_size"] = stats[worker_name].get("pool", {}).get("max-concurrency", 0)
            workers.append(worker_info)
        
        return {"workers": workers}
    except Exception as e:
        logger.error(f"Error getting workers: {e}")
        return {"workers": [], "error": str(e)}


@app.get("/validation/workers/status")
async def get_worker_status():
    """Get worker status from K8s (authoritative) and Celery."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    
    db = SessionLocal()
    try:
        # Get K8s deployment info (AUTHORITATIVE)
        from kubernetes import client, config
        config.load_incluster_config()
        apps_v1 = client.AppsV1Api()
        
        deployment = apps_v1.read_namespaced_deployment(
            name="validation-worker",
            namespace="ceitec-biodata-ns"
        )
        
        k8s_replicas = deployment.status.replicas or 0
        ready_replicas = deployment.status.ready_replicas or 0
        available_replicas = deployment.status.available_replicas or 0
        
        # Get Celery worker info (for capacity)
        from src_new.celery_app import celery
        inspect = celery.control.inspect()
        try:
            active = inspect.active() or {}
            stats = inspect.stats() or {}
        except:
            active = {}
            stats = {}
        
        celery_workers = len(active)
        pool_capacity = sum(s.get("pool", {}).get("max-concurrency", 0) for s in stats.values())
        active_tasks = sum(len(t) for t in active.values())
        
        # Get queue info
        queued = db.query(func.count(db_models.ValidationQueue.id)).filter(db_models.ValidationQueue.status == "queued").scalar()
        processing = db.query(func.count(db_models.ValidationQueue.id)).filter(db_models.ValidationQueue.status == "processing").scalar()
        
        # Utilization based on K8s capacity
        max_capacity = k8s_replicas * 4
        utilization = (active_tasks / max_capacity * 100) if max_capacity > 0 else 0
        estimated_wait = (queued / (active_tasks + 1)) * 2 if active_tasks > 0 else queued * 2
        
        # Recommendation
        if utilization > 80 and queued > 100:
            rec = {"action": "scale_up", "suggested_replicas": k8s_replicas + 2, "reason": "High load"}
        elif utilization < 30 and queued < 10:
            rec = {"action": "scale_down", "suggested_replicas": max(1, k8s_replicas - 1), "reason": "Low load"}
        else:
            rec = {"action": "stable", "suggested_replicas": k8s_replicas, "reason": "Balanced"}
        
        return {
            "kubernetes": {
                "deployment": "validation-worker",
                "desired_replicas": k8s_replicas,
                "ready_replicas": ready_replicas,
                "available_replicas": available_replicas,
                "pods_healthy": ready_replicas == k8s_replicas
            },
            "celery": {
                "active_workers": celery_workers,
                "pool_capacity": pool_capacity,
                "active_tasks": active_tasks,
                "utilization_percent": round(utilization, 1)
            },
            "queue": {
                "queued": queued,
                "processing": processing,
                "estimated_wait_minutes": round(estimated_wait, 1)
            },
            "recommendation": rec
        }
    except Exception as e:
        logger.error(f"Worker status error: {e}")
        return {"error": str(e), "kubernetes": {"desired_replicas": 0}, "celery": {"active_workers": 0}}
    finally:
        db.close()


@app.post("/validation/workers/scale")
async def scale_workers(request: dict):
    """Scale worker deployment using K8s API."""
    try:
        from kubernetes import client, config
        replicas = request.get("replicas", 10)
        reason = request.get("reason", "Manual scaling")
        
        # Clamp replicas
        replicas = max(0, min(50, replicas))
        
        # Load K8s config (works in-cluster)
        config.load_incluster_config()
        
        apps_v1 = client.AppsV1Api()
        
        # Scale deployment
        apps_v1.patch_namespaced_deployment_scale(
            name="validation-worker",
            namespace="ceitec-biodata-ns",
            body={"spec": {"replicas": replicas}}
        )
        
        logger.info(f"Scaled workers to {replicas} replicas: {reason}")
        return {"success": True, "replicas": replicas, "reason": reason}
        
    except Exception as e:
        logger.error(f"Scale failed: {e}")
        return {"success": False, "error": str(e)}


@app.get("/validation/workers/metrics")
async def get_worker_metrics(hours: int = Query(24, ge=1, le=168)):
    """Get worker performance metrics."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    from datetime import datetime, timedelta
    
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Get completed runs in period
        completed = db.query(func.count(db_models.Bat3Run.id)).filter(
            db_models.Bat3Run.status == "completed",
            db_models.Bat3Run.completed_at >= cutoff
        ).scalar() or 0
        
        failed = db.query(func.count(db_models.Bat3Run.id)).filter(
            db_models.Bat3Run.status == "failed",
            db_models.Bat3Run.completed_at >= cutoff
        ).scalar() or 0
        
        total = completed + failed
        error_rate = (failed / total * 100) if total > 0 else 0
        avg_per_hour = total / hours
        
        return {
            "period_hours": hours,
            "metrics": [],
            "summary": {
                "total_tasks": total,
                "failed_tasks": failed,
                "error_rate_percent": error_rate,
                "avg_tasks_per_hour": round(avg_per_hour, 1)
            }
        }
    finally:
        db.close()


@app.get("/validation/stats/failure-analysis")
async def get_failure_analysis():
    """Get failure analysis summary."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    
    db = SessionLocal()
    try:
        failed_runs = db.query(func.count(db_models.Bat3Run.id)).filter(
            db_models.Bat3Run.status == "failed"
        ).scalar() or 0
        
        return {
            "analyzed_at": datetime.utcnow().isoformat(),
            "database": {
                "total_failed_runs": failed_runs,
                "with_results_json": 0,
                "without_results_json": failed_runs,
                "error_categories": {},
                "recent_failures": []
            },
            "results_files": {
                "runs_analyzed": 0,
                "task_failures": {},
                "task_warnings": {},
                "error_codes": {},
                "failure_points": {}
            },
            "summary": {
                "total_db_failures": failed_runs,
                "total_failed_runs": failed_runs,
                "hung_before_completion": 0,
                "completed_with_errors": 0,
                "most_common_error_category": None,
                "most_failing_task": None,
                "primary_failure_point": None
            },
            "recommendations": []
        }
    finally:
        db.close()


@app.get("/validation/activity-log/stream")
async def get_activity_log():
    """Get activity log stream."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    from datetime import datetime
    
    db = SessionLocal()
    try:
        events = []
        
        # Recent queue items
        queue_items = db.query(db_models.ValidationQueue).order_by(
            db_models.ValidationQueue.created_at.desc()
        ).limit(50).all()
        
        for item in queue_items:
            events.append({
                "id": item.id,
                "job_id": str(item.entry_id),
                "activity_type": "queue_item",
                "message": f"Entry {item.entry_id} {item.status}",
                "severity": "error" if item.status == "failed" else ("success" if item.status == "completed" else "info"),
                "created_at": str(item.created_at) if item.created_at else None
            })
        
        # Return array directly for UI compatibility
        return events
    finally:
        db.close()


@app.post("/validation/queue/start-processing")
async def start_processing():
    """Start queue processing via the CANONICAL dispatcher (F-26 reroute, 2026-10-06).

    Previously dispatched legacy schedule_validation directly (20 rows, NO
    Bat3Run bookkeeping, NULL queue linkage, and an UNSERVED SPLIT-BRAIN
    layout /data/validation/entries/<id> + /data/validation/results/<id>/ -
    the path that produced the only 3 unlinked queue rows in the campaign).
    Now delegates to queue_processor.process_validation_queue: real Bat3Run
    (validation-<eid>-<14ts>, servable), exact FK linkage, retry budget.
    External contract preserved: {"success", "message", "dispatched"}.
    """
    import models as db_models

    db = SessionLocal()
    try:
        from queue_processor import process_validation_queue
        concurrency = int(os.environ.get("VALIDATION_MANUAL_DISPATCH_CONCURRENCY", "20"))
        dispatched = process_validation_queue(db, concurrency=concurrency)
        logger.info(f"Dispatched {dispatched} validation tasks (canonical, F-26)")

        return {"success": True, "message": "Processing started", "dispatched": dispatched, "path": "canonical process_validation_queue (F-26)"}
    except Exception as e:
        db.rollback()
        logger.error(f"Error starting processing: {e}")
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@app.post("/validation/queue/bulk-action")
async def bulk_action(request: dict):
    """Perform bulk action on queue items (pause, resume, clear, retry, queue_all_pending)."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    
    action = request.get("action")
    queue_item_ids = request.get("queue_item_ids", [])
    
    db = SessionLocal()
    try:
        if action == "clear":
            deleted = db.query(db_models.ValidationQueue).filter(
                db_models.ValidationQueue.id.in_(queue_item_ids)
            ).delete(synchronize_session=False)
            db.commit()
            return {"success": True, "action": action, "affected": deleted}
        
        elif action == "queue_all_pending":
            pending_entries = db.query(db_models.MddbEntry).filter(
                db_models.MddbEntry.status == "pending"
            ).all()
            added = 0
            for entry in pending_entries:
                existing = db.query(db_models.ValidationQueue).filter(
                    db_models.ValidationQueue.entry_id == entry.id,
                    db_models.ValidationQueue.status.in_(['queued', 'processing'])
                ).first()
                if not existing:
                    db.add(db_models.ValidationQueue(entry_id=entry.id, status="queued"))
                    added += 1
            db.commit()
            return {"success": True, "action": action, "affected": added}
        
        elif action == "queue_all_failed":
            updated = db.query(db_models.ValidationQueue).filter(
                db_models.ValidationQueue.status == "failed"
            ).update({"status": "queued"}, synchronize_session=False)
            db.commit()
            return {"success": True, "action": action, "affected": updated}
        
        elif action == "queue_all_cancelled":
            # Get cancelled queue items
            cancelled = db.query(db_models.ValidationQueue).filter(
                db_models.ValidationQueue.status == "cancelled"
            ).all()
            
            requeued = 0
            for queue_item in cancelled:
                # Check if there's already an active queue entry for this MddbEntry
                existing = db.query(db_models.ValidationQueue).filter(
                    db_models.ValidationQueue.entry_id == queue_item.entry_id,
                    db_models.ValidationQueue.status.in_(['queued', 'processing'])
                ).first()
                
                if not existing:
                    queue_item.status = "queued"
                    requeued += 1
            
            db.commit()
            return {"success": True, "action": action, "affected": requeued}
        
        elif action == "clear_completed":
            deleted = db.query(db_models.ValidationQueue).filter(
                db_models.ValidationQueue.status == "completed"
            ).delete(synchronize_session=False)
            db.commit()
            return {"success": True, "action": action, "affected": deleted}
        
        elif action == "clear_all":
            deleted = db.query(db_models.ValidationQueue).delete(synchronize_session=False)
            db.commit()
            return {"success": True, "action": action, "affected": deleted}
        
        elif action in ["pause", "resume"]:
            new_status = "paused" if action == "pause" else "queued"
            updated = db.query(db_models.ValidationQueue).filter(
                db_models.ValidationQueue.id.in_(queue_item_ids)
            ).update({"status": new_status}, synchronize_session=False)
            db.commit()
            return {"success": True, "action": action, "affected": updated}
        
        elif action == "retry":
            updated = db.query(db_models.ValidationQueue).filter(
                db_models.ValidationQueue.id.in_(queue_item_ids)
            ).update({"status": "queued"}, synchronize_session=False)
            db.commit()
            return {"success": True, "action": action, "affected": updated}
        
        elif action == "clear_all":
            deleted = db.query(db_models.ValidationQueue).delete(synchronize_session=False)
            db.commit()
            return {"success": True, "action": action, "affected": deleted}
        
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

@app.post("/validation/queue/pause-processing")
async def pause_processing():
    """Pause queue processing."""
    logger.info("Pausing queue processing")
    # Mark all queued items as paused
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    db = SessionLocal()
    try:
        updated = db.query(db_models.ValidationQueue).filter(
            db_models.ValidationQueue.status == "queued"
        ).update({"status": "paused"}, synchronize_session=False)
        db.commit()
        return {"success": True, "message": f"Paused {updated} queue items"}
    finally:
        db.close()


@app.post("/validation/queue/resume-processing")
async def resume_processing():
    """Resume queue processing."""
    logger.info("Resuming queue processing")
    # Mark all paused items as queued
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    db = SessionLocal()
    try:
        updated = db.query(db_models.ValidationQueue).filter(
            db_models.ValidationQueue.status == "paused"
        ).update({"status": "queued"}, synchronize_session=False)
        db.commit()
        return {"success": True, "message": f"Resumed {updated} queue items"}
    finally:
        db.close()


@app.post("/validation/queue/stop-processing")
async def stop_processing():
    """Stop queue processing (cancel all queued items)."""
    logger.info("Stopping queue processing")
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    db = SessionLocal()
    try:
        updated = db.query(db_models.ValidationQueue).filter(
            db_models.ValidationQueue.status.in_(["queued", "processing"])
        ).update({"status": "cancelled"}, synchronize_session=False)
        db.commit()
        return {"success": True, "message": f"Stopped {updated} queue items"}
    finally:
        db.close()

@app.post("/validation/queue/clear")
async def clear_queue():
    """Clear all queued items."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    
    db = SessionLocal()
    try:
        deleted = db.query(db_models.ValidationQueue).filter(
            db_models.ValidationQueue.status == "queued"
        ).delete()
        db.commit()
        return {"success": True, "cleared": deleted}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@app.post("/runs/rerun-all")
async def rerun_all():
    """Retry all failed runs."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    
    db = SessionLocal()
    try:
        failed = db.query(db_models.Bat3Run).filter(
            db_models.Bat3Run.status == "failed"
        ).update({"status": "pending"})
        db.commit()
        return {"success": True, "rerun_count": failed}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


@app.post("/validation/workers/{worker_name}/restart")
async def restart_worker(worker_name: str):
    """Restart a specific worker (placeholder - would need K8s integration)."""
    logger.info(f"Restart requested for worker: {worker_name}")
    return {"success": True, "worker": worker_name, "message": "Restart requested"}


@app.get("/batch-runs")
async def list_batch_runs(limit: int = Query(100, ge=1, le=1000)):
    """List batch runs."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    
    db = SessionLocal()
    try:
        runs = db.query(db_models.BatchRun).order_by(
            db_models.BatchRun.created_at.desc()
        ).limit(limit).all()
        
        return {
            "batches": [
                {
                    "batch_id": run.batch_id,
                    "status": run.status,
                    "total_entries": run.total_entries or 0,
                    "completed_entries": run.completed_entries or 0,
                    "failed_entries": run.failed_entries or 0,
                    "created_at": str(run.created_at) if run.created_at else None,
                }
                for run in runs
            ]
        }
    finally:
        db.close()


@app.get("/batch-runs/{batch_id}")
async def get_batch_run(batch_id: str):
    """Get specific batch run."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    
    db = SessionLocal()
    try:
        run = db.query(db_models.BatchRun).filter(
            db_models.BatchRun.batch_id == batch_id
        ).first()
        
        if not run:
            raise HTTPException(status_code=404, detail="Batch not found")
        
        return {
            "batch_id": run.batch_id,
            "status": run.status,
            "total_entries": run.total_entries or 0,
            "completed_entries": run.completed_entries or 0,
            "failed_entries": run.failed_entries or 0,
            
            "created_at": str(run.created_at) if run.created_at else None,
        }
    finally:
        db.close()


@app.post("/batch-runs")
async def create_batch_run(request: dict):
    """Create new batch run."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    from datetime import datetime
    import uuid
    
    db = SessionLocal()
    try:
        entry_ids = request.get("entry_ids", [])
        batch_id = f"batch_{uuid.uuid4().hex[:8]}"
        
        # Create batch run record
        batch_run = db_models.BatchRun(
            batch_id=batch_id,
            status="pending",
            total_entries=len(entry_ids),
            created_at=datetime.utcnow()
        )
        db.add(batch_run)
        
        # Add entries to queue
        for entry_id in entry_ids:
            queue_item = db_models.ValidationQueue(
                entry_id=entry_id,
                batch_id=batch_id,
                status="queued"
            )
            db.add(queue_item)
        
        db.commit()
        
        return {"success": True, "batch_id": batch_id, "entries": len(entry_ids)}
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()

# Temporary endpoint to test queue_all_cancelled

@app.post("/batch-runs/{batch_id}/cancel")
async def cancel_batch_run(batch_id: str):
    """Cancel a batch run."""
    logger.info(f"Cancelling batch {batch_id}")
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    db = SessionLocal()
    try:
        batch = db.query(db_models.BatchRun).filter(
            db_models.BatchRun.batch_id == batch_id
        ).first()
        
        if not batch:
            return {"success": False, "error": "Batch not found"}
        
        batch.status = "cancelled"
        db.commit()
        
        # Also cancel associated queue items
        cancelled = db.query(db_models.ValidationQueue).filter(
            db_models.ValidationQueue.batch_id == batch_id,
            db_models.ValidationQueue.status.in_(["queued", "processing"])
        ).update({"status": "cancelled"}, synchronize_session=False)
        db.commit()
        
        return {"success": True, "message": f"Cancelled batch {batch_id} and {cancelled} queue items"}
    finally:
        db.close()


@app.post("/validation/queue/test-cancelled")
async def test_cancelled():
    """Test endpoint to check cancelled entries."""
    import sys
    sys.path.insert(0, '/app')
    import models as db_models
    from sqlalchemy import func
    
    db = SessionLocal()
    try:
        cancelled = db.query(func.count(db_models.ValidationQueue.id)).filter(
            db_models.ValidationQueue.status == "cancelled"
        ).scalar()
        
        return {"cancelled_count": cancelled}
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Published schema (/docs, /openapi.json). The public API is /api/v1 (the
# BioID host routes only /api, /files and /health here). The root-level
# duplicates, the validation-campaign control plane, the batch routes and the
# UI-internal helpers stay callable in-cluster but are left out of the
# schema. Public routes get user-facing summaries (the docstrings are
# developer notes).
# ---------------------------------------------------------------------------
from fastapi.routing import APIRoute  # noqa: E402

_V1 = "/api/v1/runs"
_PUBLIC_ROUTES: dict[tuple[str, str], tuple[str, str, str]] = {
    # (method, path): (tag, summary, description)
    ("POST", _V1): ("Runs", "Submit a run",
        "Upload simulation files as multipart `files` (repeat the field for several files; "
        "GROMACS, AMBER, CHARMM/NAMD, LAMMPS, PDB/mmCIF or a zip/tar bundle; 128 MiB per file). "
        "Optional form fields: `run_name`, `preset` (`balanced`, `quick`, `exact`, `deep`; see "
        "`GET /api/v1/runs/config/options`) and `config_json` (only the fields that differ from the "
        "defaults, e.g. `{\"verification\": {\"verify_top_n\": 50}}`). Returns the `run_id`; the run "
        "is queued and processed in the background. 422 if a file name or the configuration is "
        "not accepted."),
    ("GET", _V1): ("Runs", "List your runs",
        "Runs submitted from your network address, newest first (`mine=1`)."),
    ("GET", f"{_V1}/examples"): ("Runs", "Example runs",
        "Finished example analyses shown on the front page."),
    ("GET", f"{_V1}/{{run_id}}"): ("Runs", "Run summary",
        "Name, status, timestamps and input files of a run."),
    ("GET", f"{_V1}/{{run_id}}/status"): ("Runs", "Run status and progress",
        "Poll this while the run is processing. `pipeline.status` is `queued`, `running`, "
        "`success`, `failed` or `cancelled`; `tasks` lists the pipeline stages, `progress` the "
        "per-molecule identification progress, `warnings` anything worth knowing."),
    ("GET", f"{_V1}/{{run_id}}/queue"): ("Runs", "Queue position",
        "Where a queued run stands in the queue."),
    ("POST", f"{_V1}/{{run_id}}/cancel"): ("Runs", "Cancel a run", "Stops a queued or running run."),
    ("POST", f"{_V1}/{{run_id}}/rerun"): ("Runs", "Run again",
        "Starts a new run with the same input files and configuration; returns the new `run_id`."),
    ("DELETE", f"{_V1}/{{run_id}}"): ("Runs", "Delete a run", "Removes the run and its files."),
    ("GET", f"{_V1}/{{run_id}}/molecules"): ("Results", "Molecules",
        "The molecules found in the system: unique molecules with their copies, counts by kind "
        "and per-segment metadata."),
    ("GET", f"{_V1}/{{run_id}}/molecules/{{segment}}/info"): ("Results", "One molecule",
        "Composition and identification summary of one molecule (segment)."),
    ("GET", f"{_V1}/{{run_id}}/verification"): ("Results", "Identifications (verified hits)",
        "For every molecule, the database candidates after verification, with their confidence "
        "(0–100), the three confidence terms and whether each was verified. This is the main result."),
    ("GET", f"{_V1}/{{run_id}}/identifiers"): ("Results", "Database hits",
        "Every raw hit from every database search, before verification."),
    ("GET", f"{_V1}/{{run_id}}/signatures"): ("Results", "Signatures",
        "The descriptions generated for each molecule and used as search queries: sequences, "
        "SMILES, InChIKeys, formulas, structures."),
    ("GET", f"{_V1}/{{run_id}}/download/results.json"): ("Results", "Download results.json",
        "The complete results document. Its structure is described at /documentation/results-json/."),
    ("GET", f"{_V1}/{{run_id}}/download/results.csv"): ("Results", "Download results.csv",
        "One row per molecule: best identification, database, identifier, confidence and alternatives."),
    ("GET", f"{_V1}/{{run_id}}/download/topology-less-pdb"): ("Results", "Download topology-less PDB",
        "The system as a PDB file without topology records."),
    ("GET", f"{_V1}/{{run_id}}/download/ca-only-pdb"): ("Results", "Download Cα-only PDB",
        "Protein Cα trace of the system."),
    ("GET", f"{_V1}/{{run_id}}/files"): ("Results", "Run files",
        "Files of the run (inputs and outputs), served under `/files/{run_id}/…`."),
    ("GET", f"{_V1}/{{run_id}}/logs"): ("Results", "Run log", "The pipeline log of the run."),
    ("GET", f"{_V1}/config/options"): ("Configuration", "Presets and settings",
        "The presets and every setting a run may change, with the server defaults. Post only "
        "the settings you change, as `config_json`."),
    ("GET", "/api/v1/health"): ("Service", "Health", "Liveness of the API."),
    ("GET", "/api/v1/capabilities"): ("Service", "Capabilities",
        "API features available on this server and the code version."),
}

for _route in app.routes:
    if not isinstance(_route, APIRoute):
        continue
    _meta = next((_PUBLIC_ROUTES[(m, _route.path)] for m in _route.methods
                  if (m, _route.path) in _PUBLIC_ROUTES), None)
    if _meta is None:
        _route.include_in_schema = False
        continue
    _route.tags, _route.summary, _route.description = [_meta[0]], _meta[1], _meta[2]

