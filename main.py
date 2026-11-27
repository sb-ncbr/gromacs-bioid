"""Validation API - FastAPI application for BAT3 validation scheduling and tracking."""

import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session

import models

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="BAT3 Validation API",
    description="API for scheduling and tracking BAT3 validation runs",
    version="1.0.0",
    redirect_slashes=False,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models for request/response
class EntryResponse(BaseModel):
    id: int
    local_accession: str
    project_name: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RunResponse(BaseModel):
    id: int
    entry_id: int
    run_id: str
    celery_task_id: Optional[str] = None
    status: str
    input_dir: Optional[str] = None
    results_path: Optional[str] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ValidationResultResponse(BaseModel):
    id: int
    entry_id: int
    run_id: Optional[int] = None
    result_type: Optional[str] = None
    status: str
    details: Optional[str] = None
    metrics: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    entries_total: int
    entries_pending: int
    entries_processing: int
    entries_completed: int
    entries_failed: int
    runs_total: int
    runs_completed: int
    runs_pending: int
    runs_failed: int
    queue_pending: int


class IndexingJobResponse(BaseModel):
    id: int
    job_id: str
    job_type: str
    status: str
    total_items: int
    processed_items: int
    failed_items: int
    created_at: datetime

    class Config:
        from_attributes = True


class IndexingStatsResponse(BaseModel):
    total_entries: int
    indexed_entries: int
    total_references: int
    total_filenotes: int
    completeness_percentage: float
    last_indexed_at: Optional[datetime] = None


class GroundTruthStatsResponse(BaseModel):
    total_entries: int
    entries_with_ground_truth: int
    entries_without_ground_truth: int
    breakdown_by_type: Dict[str, int]
    missing_entries_count: int


class GroundTruthMissingEntry(BaseModel):
    id: int
    local_accession: str
    project_name: Optional[str] = None
    reference_count: int


class DatabaseStatsResponse(BaseModel):
    table_counts: Dict[str, int]
    total_storage_bytes: int
    index_count: int


# Dependency
def get_db():
    """Get database session."""
    db = models.SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Health check
@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# Statistics
@app.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    """Get validation statistics."""
    try:
        # Entry stats
        entries_total = db.query(func.count(models.MddbEntry.id)).scalar() or 0
        entries_pending = db.query(func.count(models.MddbEntry.id)).filter(
            models.MddbEntry.status == "pending"
        ).scalar() or 0
        entries_processing = db.query(func.count(models.MddbEntry.id)).filter(
            models.MddbEntry.status == "processing"
        ).scalar() or 0
        entries_completed = db.query(func.count(models.MddbEntry.id)).filter(
            models.MddbEntry.status == "completed"
        ).scalar() or 0
        entries_failed = db.query(func.count(models.MddbEntry.id)).filter(
            models.MddbEntry.status == "failed"
        ).scalar() or 0

        # Run stats
        runs_total = db.query(func.count(models.Bat3Run.id)).scalar() or 0
        runs_completed = db.query(func.count(models.Bat3Run.id)).filter(
            models.Bat3Run.status == "completed"
        ).scalar() or 0
        runs_pending = db.query(func.count(models.Bat3Run.id)).filter(
            models.Bat3Run.status == "pending"
        ).scalar() or 0
        runs_failed = db.query(func.count(models.Bat3Run.id)).filter(
            models.Bat3Run.status == "failed"
        ).scalar() or 0

        # Queue stats
        queue_pending = db.query(func.count(models.ValidationQueue.id)).filter(
            models.ValidationQueue.status == "queued"
        ).scalar() or 0

        return StatsResponse(
            entries_total=entries_total,
            entries_pending=entries_pending,
            entries_processing=entries_processing,
            entries_completed=entries_completed,
            entries_failed=entries_failed,
            runs_total=runs_total,
            runs_completed=runs_completed,
            runs_pending=runs_pending,
            runs_failed=runs_failed,
            queue_pending=queue_pending,
        )
    finally:
        db.close()


# List entries
@app.get("/entries", response_model=List[EntryResponse])
def list_entries(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum entries to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    db: Session = Depends(get_db),
):
    """List MDDB entries with optional filtering."""
    try:
        query = db.query(models.MddbEntry)
        if status:
            query = query.filter(models.MddbEntry.status == status)
        entries = query.order_by(models.MddbEntry.created_at.desc()).offset(offset).limit(limit).all()
        return entries
    finally:
        db.close()


# Get single entry
@app.get("/entries/{entry_id}", response_model=EntryResponse)
def get_entry(entry_id: int, db: Session = Depends(get_db)):
    """Get a single entry by ID."""
    try:
        entry = db.query(models.MddbEntry).filter(models.MddbEntry.id == entry_id).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        return entry
    finally:
        db.close()


# Create entry
# Schedule validation for entry
# Batch validation
@app.get("/runs", response_model=List[RunResponse])
def list_runs(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List validation runs with optional filtering."""
    try:
        query = db.query(models.Bat3Run)
        if status:
            query = query.filter(models.Bat3Run.status == status)
        runs = query.order_by(models.Bat3Run.created_at.desc()).offset(offset).limit(limit).all()
        return runs
    finally:
        db.close()


@app.get("/runs/active", response_model=Optional[dict])
def get_active_run(db: Session = Depends(get_db)):
    """Get the currently active (running) validation run."""
    try:
        # Get the most recently started run that's still running
        active_run = db.query(models.Bat3Run).filter(
            models.Bat3Run.status == "running"
        ).order_by(models.Bat3Run.started_at.desc()).first()
        
        if not active_run:
            # If no running run, get the most recent completed one
            active_run = db.query(models.Bat3Run).filter(
                models.Bat3Run.status == "completed"
            ).order_by(models.Bat3Run.completed_at.desc()).first()
        
        if not active_run:
            return None
        
        # GitHub #22: the batch through the queue row that links the run
        # (ValidationQueue.run_id -> Bat3Run.id, .batch_id -> BatchRun.batch_id);
        # BatchRun.id and Bat3Run.id are unrelated primary keys.
        queue_row = db.query(models.ValidationQueue).filter(
            models.ValidationQueue.run_id == active_run.id,
            models.ValidationQueue.batch_id.isnot(None),
        ).order_by(models.ValidationQueue.id.desc()).first()
        batch = (db.query(models.BatchRun).filter(
            models.BatchRun.batch_id == queue_row.batch_id).first()
            if queue_row is not None else None)
        
        return {
            "id": active_run.id,
            "run_id": active_run.run_id,
            "status": active_run.status,
            "entries_processed": 1,  # Each run is one entry
            "entries_total": 1,
            "started_at": active_run.started_at,
            "completed_at": active_run.completed_at,
            "batch_number": batch.batch_id if batch else None,
            "concurrency": 1,
        }
    finally:
        db.close()


# Get run status (must be after /runs and /runs/active to avoid route conflicts)
@app.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    """Get run status by ID."""
    try:
        run = db.query(models.Bat3Run).filter(models.Bat3Run.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        return run
    finally:
        db.close()


# Get Celery task status
# Get validation results
@app.get("/results/{entry_id}", response_model=List[ValidationResultResponse])
def get_results(entry_id: int, db: Session = Depends(get_db)):
    """Get validation results for an entry."""
    try:
        results = db.query(models.ValidationResult).filter(
            models.ValidationResult.entry_id == entry_id
        ).order_by(models.ValidationResult.created_at.desc()).all()
        return results
    finally:
        db.close()


# Indexing endpoints
@app.get("/index/stats", response_model=IndexingStatsResponse)
async def get_indexing_stats(db: Session = Depends(get_db)):
    """Return indexing progress and stats."""
    try:
        total_entries = db.query(func.count(models.MddbEntry.id)).scalar() or 0
        indexed_entries = db.query(func.count(models.MddbEntry.id)).filter(
            models.MddbEntry.is_complete == True
        ).scalar() or 0
        
        total_references = db.query(func.count(models.MddbReference.id)).scalar() or 0
        total_filenotes = db.query(func.count(models.MddbFilenote.id)).scalar() or 0
        
        completeness = (indexed_entries / total_entries * 100) if total_entries > 0 else 0.0
        
        last_job = db.query(models.IndexingJob).filter(
            models.IndexingJob.job_type == "mddbr_index",
            models.IndexingJob.status == "completed"
        ).order_by(models.IndexingJob.completed_at.desc()).first()
        
        last_indexed_at = last_job.completed_at if last_job else None
        
        return IndexingStatsResponse(
            total_entries=total_entries,
            indexed_entries=indexed_entries,
            total_references=total_references,
            total_filenotes=total_filenotes,
            completeness_percentage=round(completeness, 2),
            last_indexed_at=last_indexed_at,
        )
    finally:
        db.close()


# Ground truth endpoints
@app.get("/ground-truth/stats", response_model=GroundTruthStatsResponse)
async def get_ground_truth_stats(db: Session = Depends(get_db)):
    """Return ground truth coverage statistics."""
    try:
        total_entries = db.query(func.count(models.MddbEntry.id)).scalar() or 0
        
        # Count entries with ground truth
        entries_with_gt = db.query(func.count(models.MddbEntry.id)).join(
            models.GroundTruthSignature
        ).distinct().scalar() or 0
        
        entries_without_gt = total_entries - entries_with_gt
        
        # Breakdown by type
        breakdown = {}
        for sig_type in ["uniprot", "pdb", "inchi", "pubchem"]:
            count = db.query(func.count(models.GroundTruthSignature.id)).filter(
                models.GroundTruthSignature.signature_type == sig_type
            ).scalar() or 0
            breakdown[sig_type] = count
        
        return GroundTruthStatsResponse(
            total_entries=total_entries,
            entries_with_ground_truth=entries_with_gt,
            entries_without_ground_truth=entries_without_gt,
            breakdown_by_type=breakdown,
            missing_entries_count=entries_without_gt,
        )
    finally:
        db.close()


@app.get("/ground-truth/missing", response_model=List[GroundTruthMissingEntry])
async def get_missing_ground_truth(
    limit: int = Query(100, ge=1, le=1000, description="Maximum entries to return"),
    db: Session = Depends(get_db),
):
    """List entries lacking ground truth signatures."""
    try:
        # Get entries that have references but no ground truth signatures
        # Join through MddbProject since MddbReference links to MddbProject, not MddbEntry
        subquery = db.query(models.MddbEntry.id).join(
            models.MddbProject,
            models.MddbEntry.local_accession == models.MddbProject.local_accession
        ).join(
            models.MddbReference,
            models.MddbReference.project_id == models.MddbProject.id
        ).filter(
            ~models.MddbEntry.id.in_(
                db.query(models.GroundTruthSignature.entry_id).distinct()
            )
        ).limit(limit).all()
        
        entry_ids = [e[0] for e in subquery]
        entries = db.query(models.MddbEntry).filter(
            models.MddbEntry.id.in_(entry_ids)
        ).all()
        
        # Build a map of entry_id -> MddbProject.id for reference counting
        entry_to_project = {}
        for entry in entries:
            proj = db.query(models.MddbProject.id).filter(
                models.MddbProject.local_accession == entry.local_accession
            ).first()
            if proj:
                entry_to_project[entry.id] = proj[0]
        
        # Count references for each entry
        results = []
        for entry in entries:
            project_id = entry_to_project.get(entry.id)
            if project_id:
                ref_count = db.query(func.count(models.MddbReference.id)).filter(
                    models.MddbReference.project_id == project_id
                ).scalar() or 0
            else:
                ref_count = 0
            
            results.append(GroundTruthMissingEntry(
                id=entry.id,
                local_accession=entry.local_accession,
                project_name=entry.project_name,
                reference_count=ref_count,
            ))
        
        return results
    finally:
        db.close()


# Retry endpoints
@app.get("/entries/failed")
async def get_failed_entries(limit: int = Query(100, ge=1, le=1000), db: Session = Depends(get_db)):
    """List entries with failed validation runs."""
    try:
        # Query bat3_runs where status='failed'
        failed_runs = db.query(models.Bat3Run).filter(
            models.Bat3Run.status == "failed"
        ).order_by(models.Bat3Run.completed_at.desc()).limit(limit).all()
        
        # Return entries with failure info
        results = []
        for run in failed_runs:
            entry = db.query(models.MddbEntry).filter(models.MddbEntry.id == run.entry_id).first()
            if entry:
                results.append({
                    "entry_id": entry.id,
                    "local_accession": entry.local_accession,
                    "project_name": entry.project_name,
                    "run_id": run.id,
                    "run_uuid": run.run_id,
                    "error_message": run.error_message,
                    "failed_at": run.completed_at.isoformat() if run.completed_at else None,
                })
        
        return results
    finally:
        db.close()


@app.get("/index/jobs")
async def list_indexing_jobs(
    limit: int = Query(10, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """List indexing jobs with optional filtering."""
    try:
        query = db.query(models.IndexingJob)
        if status:
            query = query.filter(models.IndexingJob.status == status)
        jobs = query.order_by(models.IndexingJob.created_at.desc()).limit(limit).all()
        return [
            IndexingJobResponse(
                id=job.id,
                job_id=job.job_id,
                job_type=job.job_type,
                status=job.status,
                total_items=job.total_items,
                processed_items=job.processed_items,
                failed_items=job.failed_items,
                created_at=job.created_at,
            )
            for job in jobs
        ]
    finally:
        db.close()


# Database stats endpoint
@app.get("/database/stats", response_model=DatabaseStatsResponse)
async def get_database_stats(db: Session = Depends(get_db)):
    """Return database size and table statistics."""
    try:
        table_counts = {}
        
        # Count rows for each table
        tables = {
            "mddb_entries": models.MddbEntry,
            "mddb_references": models.MddbReference,
            "mddb_filenotes": models.MddbFilenote,
            "bat3_runs": models.Bat3Run,
            "validation_queue": models.ValidationQueue,
            "validation_results": models.ValidationResult,
            "ground_truth_signatures": models.GroundTruthSignature,
            "indexing_jobs": models.IndexingJob,
            "batch_runs": models.BatchRun,
            "audit_log": models.AuditLog,
        }
        
        for table_name, model in tables.items():
            count = db.query(func.count(model.id)).scalar() or 0
            table_counts[table_name] = count
        
        # Get database size (SQLite specific)
        try:
            result = db.execute(text("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")).fetchone()
            total_storage = result[0] if result else 0
        except:
            total_storage = 0
        
        # Get index count
        try:
            result = db.execute(text("SELECT count(*) FROM sqlite_master WHERE type='index'")).fetchone()
            index_count = result[0] if result else 0
        except:
            index_count = 0
        
        return DatabaseStatsResponse(
            table_counts=table_counts,
            total_storage_bytes=total_storage,
            index_count=index_count,
        )
    finally:
        db.close()


# SQLite Import endpoints
# Startup event

# =============================================================================
# VALIDATION API ENDPOINTS (for UI)
# =============================================================================

from fastapi.responses import StreamingResponse
import json

@app.get("/validation/queue/status")
async def get_queue_status():
    """Get validation queue status summary."""
    db = next(get_db())
    try:
        total = db.query(func.count(models.ValidationQueue.id)).scalar()
        queued = db.query(func.count(models.ValidationQueue.id)).filter(models.ValidationQueue.status == "queued").scalar()
        processing = db.query(func.count(models.ValidationQueue.id)).filter(models.ValidationQueue.status == "processing").scalar()
        completed = db.query(func.count(models.ValidationQueue.id)).filter(models.ValidationQueue.status == "completed").scalar()
        failed = db.query(func.count(models.ValidationQueue.id)).filter(models.ValidationQueue.status == "failed").scalar()
        paused = db.query(func.count(models.ValidationQueue.id)).filter(models.ValidationQueue.status == "paused").scalar()
        
        progress_percent = ((completed + failed) / total * 100) if total > 0 else 0
        
        return {
            "queue": {
                "queued": queued,
                "processing": processing,
                "paused": paused,
                "completed": completed,
                "failed": failed,
                "progress_percent": progress_percent
            }
        }
    finally:
        db.close()

@app.get("/validation/queue/list")
async def get_queue_list(status: Optional[str] = None, limit: int = 100, offset: int = 0):
    """Get list of queue items."""
    db = next(get_db())
    try:
        query = db.query(models.ValidationQueue)
        if status:
            query = query.filter(models.ValidationQueue.status == status)
        total = query.count()
        items = query.order_by(models.ValidationQueue.created_at.desc()).offset(offset).limit(limit).all()
        return {"total": total, "items": [{"id": item.id, "entry_id": item.entry_id, "status": item.status, "priority": item.priority, "error_message": None, "created_at": item.created_at.isoformat() if item.created_at else None, "updated_at": item.created_at.isoformat() if item.created_at else None} for item in items]}
    finally:
        db.close()

@app.get("/validation/activity-log/stream")
async def stream_activity_log():
    """Server-Sent Events stream for activity log."""
    async def event_generator():
        last_id = 0
        while True:
            db = next(get_db())
            try:
                recent_items = db.query(models.ValidationQueue).order_by(models.ValidationQueue.created_at.desc()).limit(5).all()
                for item in recent_items:
                    event_id = item.id
                    if event_id > last_id:
                        last_id = event_id
                        event_data = {"id": event_id, "type": "queue_update", "data": {"entry_id": item.entry_id, "status": item.status, "timestamp": item.created_at.isoformat() if item.created_at else None}}
                        yield f"data: {json.dumps(event_data)}\n\n"
            finally:
                db.close()
            yield ": heartbeat\n\n"
            await asyncio.sleep(30)
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})



@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    logger.info("Initializing database tables...")
    models.init_db()
    logger.info("Database initialized successfully")


# GitHub #25/#26/#28/#35: this app is a READ-ONLY view of the campaign
# database. The queue dispatcher, its completion/stale sweeps, the mutating
# entry/run/index/import/ground-truth routes and the worker scale/restart
# handlers are removed; validation campaigns run through the BioID
# repository queue (validation.repo.celery).


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

