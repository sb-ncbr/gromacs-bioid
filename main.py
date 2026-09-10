"""Validation API - FastAPI application for BAT3 validation scheduling and tracking."""

import logging
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Query, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import func, text
from sqlalchemy.orm import Session

import models
from tasks import schedule_validation
from mddbr_client import MddbrClient, fetch_all_projects, fetch_project_full

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


class EntryCreateRequest(BaseModel):
    local_accession: str
    project_name: Optional[str] = None


class ValidateRequest(BaseModel):
    input_dir: Optional[str] = None
    config_path: Optional[str] = None


class BatchValidateRequest(BaseModel):
    count: int = 10
    status_filter: Optional[str] = "pending"


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


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None


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


class FetchMissingRequest(BaseModel):
    entry_ids: Optional[List[int]] = None


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


class GroundTruthFetchRequest(BaseModel):
    entry_ids: List[int]


class GroundTruthFetchResponse(BaseModel):
    fetched_count: int
    failed_count: int
    results: List[Dict[str, Any]]


class DatabaseStatsResponse(BaseModel):
    table_counts: Dict[str, int]
    total_storage_bytes: int
    index_count: int


class SqliteImportRequest(BaseModel):
    source_path: str = "/data/mddb_index.db"
    tables: Optional[List[str]] = None
    conflict_strategy: str = "skip"  # skip, overwrite


class ImportJobResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    source_path: str
    tables_requested: List[str]
    total_items: int
    processed_items: int
    failed_items: int
    conflict_strategy: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class ImportStatusResponse(BaseModel):
    job_id: str
    status: str
    progress_percentage: float
    total_items: int
    processed_items: int
    failed_items: int
    current_table: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


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
@app.post("/entries", response_model=EntryResponse, status_code=201)
def create_entry(entry: EntryCreateRequest, db: Session = Depends(get_db)):
    """Create a new MDDB entry."""
    try:
        # Check for existing entry
        existing = db.query(models.MddbEntry).filter(
            models.MddbEntry.local_accession == entry.local_accession
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail="Entry with this local_accession already exists")

        db_entry = models.MddbEntry(
            local_accession=entry.local_accession,
            project_name=entry.project_name,
            status="pending",
        )
        db.add(db_entry)
        db.commit()
        db.refresh(db_entry)
        return db_entry
    finally:
        db.close()


# Schedule validation for entry
@app.post("/entries/{entry_id}/validate", response_model=RunResponse)
def validate_entry(
    entry_id: int,
    request: Optional[ValidateRequest] = None,
    db: Session = Depends(get_db),
):
    """Schedule validation for an entry."""
    try:
        # Get entry
        entry = db.query(models.MddbEntry).filter(models.MddbEntry.id == entry_id).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")

        # Generate paths
        run_id = f"validation-{entry_id}-{uuid.uuid4().hex[:8]}"
        input_dir = request.input_dir if request and request.input_dir else f"/data/validation/{entry_id}/input"
        results_path = request.results_path if request and hasattr(request, 'results_path') else f"/data/validation/{entry_id}/results.json"
        config_path = request.config_path if request and request.config_path else f"/data/validation/{entry_id}/config.ini"

        # Create run record
        run = models.Bat3Run(
            entry_id=entry_id,
            run_id=run_id,
            status="pending",
            input_dir=input_dir,
            results_path=results_path,
            config_path=config_path,
        )
        db.add(run)

        # Update entry status
        entry.status = "processing"

        db.commit()
        db.refresh(run)

        # Schedule Celery task
        try:
            task_result = schedule_validation.delay(
                entry_id=entry_id,
                input_dir=input_dir,
                results_path=results_path,
                config_path=config_path,
            )
            run.celery_task_id = task_result.id  # Extract task ID string from AsyncResult
            run.status = "running"
            run.started_at = datetime.utcnow()
            db.commit()
            db.refresh(run)
        except Exception as e:
            logger.error(f"Failed to schedule Celery task: {e}")
            # Keep run in pending state if Celery fails
            pass

        # Create response model before session close to avoid DetachedInstanceError
        response = RunResponse(
            id=run.id,
            entry_id=run.entry_id,
            run_id=run.run_id,
            celery_task_id=run.celery_task_id,
            status=run.status,
            input_dir=run.input_dir,
            results_path=run.results_path,
            error_message=run.error_message,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
        )
        return response
    finally:
        db.close()


# Batch validation
@app.post("/runs/batch", response_model=dict)
def batch_validate(
    request: BatchValidateRequest,
    db: Session = Depends(get_db),
):
    """Start a batch validation run for N entries."""
    try:
        # Get pending entries
        query = db.query(models.MddbEntry).filter(
            models.MddbEntry.status == (request.status_filter or "pending")
        )
        entries = query.order_by(models.MddbEntry.created_at).limit(request.count).all()

        if not entries:
            return {
                "batch_id": None,
                "message": "No entries found matching criteria",
                "scheduled_count": 0,
            }

        batch_id = f"batch-{uuid.uuid4().hex[:8]}"

        # Create batch record
        batch = models.BatchRun(
            batch_id=batch_id,
            total_entries=len(entries),
            status="running",
        )
        db.add(batch)
        db.commit()

        # Schedule validation for each entry
        scheduled = 0
        failed = 0
        for entry in entries:
            try:
                run_id = f"validation-{entry.id}-{uuid.uuid4().hex[:8]}"
                input_dir = f"/data/validation/{entry.id}/input"
                results_path = f"/data/validation/{entry.id}/results.json"
                config_path = f"/data/validation/{entry.id}/config.ini"

                run = models.Bat3Run(
                    entry_id=entry.id,
                    run_id=run_id,
                    status="pending",
                    input_dir=input_dir,
                    results_path=results_path,
                    config_path=config_path,
                )
                db.add(run)
                entry.status = "processing"
                scheduled += 1
            except Exception as e:
                logger.error(f"Failed to schedule entry {entry.id}: {e}")
                failed += 1

        db.commit()

        # Schedule Celery tasks asynchronously
        for entry in entries[:scheduled]:
            try:
                schedule_validation.delay(
                    entry_id=entry.id,
                    input_dir=f"/data/validation/{entry.id}/input",
                    results_path=f"/data/validation/{entry.id}/results.json",
                    config_path=f"/data/validation/{entry.id}/config.ini",
                )
            except Exception as e:
                logger.error(f"Failed to queue Celery task for entry {entry.id}: {e}")

        return {
            "batch_id": batch_id,
            "message": f"Batch validation started",
            "scheduled_count": scheduled,
            "failed_count": failed,
            "total_entries": len(entries),
        }
    finally:
        db.close()


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
        
        # Get batch info if available
        batch = db.query(models.BatchRun).filter(
            models.BatchRun.id == active_run.id
        ).first()
        
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
@app.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str):
    """Get Celery task status."""
    from celery.result import AsyncResult

    try:
        task_result = AsyncResult(task_id, app=schedule_validation.app)
        return TaskStatusResponse(
            task_id=task_id,
            status=task_result.status,
            result=task_result.result if task_result.ready() else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task status: {e}")


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
def _index_projects_background(limit: int, job_id: str):
    """Background task for indexing MDDBR projects."""
    db = models.SessionLocal()
    try:
        logger.info(f"Starting indexing job {job_id} with limit {limit}")
        
        # Update job status
        job = db.query(models.IndexingJob).filter(models.IndexingJob.job_id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        
        client = MddbrClient()
        projects = fetch_all_projects(limit=limit)
        
        job.total_items = len(projects)
        db.commit()
        
        success_count = 0
        fail_count = 0
        
        for proj_data in projects:
            try:
                local_accession = proj_data.get("accession")
                if not local_accession:
                    fail_count += 1
                    continue
                
                # Fetch full project data
                full_data = fetch_project_full(local_accession)
                project = full_data.get("project", {})
                references = full_data.get("references", [])
                filenotes = full_data.get("filenotes", [])
                
                # Create or update MddbProject (required for FK constraints on references/filenotes)
                mddb_project = db.query(models.MddbProject).filter(
                    models.MddbProject.local_accession == local_accession
                ).first()
                
                project_name = project.get("metadata", {}).get("NAME") or project.get("title") or project.get("name")
                
                if not mddb_project:
                    mddb_project = models.MddbProject(
                        local_accession=local_accession,
                        title=project_name,
                        description=project.get("metadata", {}).get("DESCRIPTION"),
                        status="indexed",
                        last_synced_at=datetime.utcnow(),
                    )
                    db.add(mddb_project)
                    db.flush()
                else:
                    mddb_project.title = project_name
                    mddb_project.description = project.get("metadata", {}).get("DESCRIPTION")
                    mddb_project.status = "indexed"
                    mddb_project.last_synced_at = datetime.utcnow()
                    mddb_project.updated_at = datetime.utcnow()
                
                db.commit()
                
                # Also create/update MddbEntry for validation workflow
                entry = db.query(models.MddbEntry).filter(
                    models.MddbEntry.local_accession == local_accession
                ).first()
                
                if not entry:
                    entry = models.MddbEntry(
                        local_accession=local_accession,
                        project_name=project_name,
                        status="pending",
                        is_complete=True,
                    )
                    db.add(entry)
                    db.commit()
                else:
                    entry.project_name = project_name
                    entry.is_complete = True
                    entry.updated_at = datetime.utcnow()
                    db.commit()
                
                # Store references (FK to mddb_projects.id)
                for ref in references:
                    existing_ref = db.query(models.MddbReference).filter(
                        models.MddbReference.project_id == mddb_project.id,
                        models.MddbReference.ref_url == ref.get("url"),
                    ).first()
                    
                    
                    if not existing_ref:
                        # Construct URL from reference data
                        ref_url = ref.get("url")
                        if not ref_url:
                            ref_type = ref.get("ref_type", "")
                            if ref_type == "proteins":
                                # Construct UniProt URL
                                uniprot_id = ref.get("uniprot")
                                if uniprot_id:
                                    ref_url = f"https://www.uniprot.org/uniprot/{uniprot_id}"
                            elif ref_type == "pdbs":
                                # Construct PDB URL
                                pdb_id = ref.get("id")
                                if pdb_id:
                                    ref_url = f"https://www.rcsb.org/structure/{pdb_id}"
                        
                        db_ref = models.MddbReference(
                            project_id=mddb_project.id,
                            ref_type=ref.get("ref_type"),
                            ref_url=ref_url,
                            ref_text=ref.get("name") or ref.get("title"),
                        )
                        db.add(db_ref)
                
                for note in filenotes:
                    existing_note = db.query(models.MddbFilenote).filter(
                        models.MddbFilenote.project_id == mddb_project.id,
                        models.MddbFilenote.filename == note.get("filename"),
                    ).first()
                    
                    if not existing_note:
                        db_note = models.MddbFilenote(
                            project_id=mddb_project.id,
                            filename=note.get("filename"),
                            file_type=note.get("file_type"),
                            file_size=note.get("file_size"),
                            file_url=note.get("file_url"),
                            checksum=note.get("checksum"),
                        )
                        db.add(db_note)
                
                db.commit()
                success_count += 1
                
                # Update progress after each item
                job.processed_items = success_count
                job.failed_items = fail_count
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to index project: {e}")
                fail_count += 1
                job.failed_items = fail_count
                db.commit()
        
        # Update job status
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Indexing job {job_id} completed: {success_count} success, {fail_count} failed")
        
    except Exception as e:
        logger.error(f"Indexing job {job_id} failed: {e}")
        job = db.query(models.IndexingJob).filter(models.IndexingJob.job_id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@app.post("/index/mddbr", response_model=IndexingJobResponse)
async def start_indexing(
    limit: int = Query(1000, ge=1, le=10000, description="Maximum projects to index"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Start MDDBR project indexing in background."""
    try:
        job_id = f"index-{uuid.uuid4().hex[:8]}"
        
        job = models.IndexingJob(
            job_id=job_id,
            job_type="mddbr_index",
            status="pending",
            total_items=0,
            processed_items=0,
            failed_items=0,
        )
        db.add(job)
        db.commit()
        
        # Start background task
        background_tasks.add_task(_index_projects_background, limit, job_id)
        
        return IndexingJobResponse(
            id=job.id,
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            total_items=job.total_items,
            processed_items=job.processed_items,
            failed_items=job.failed_items,
            created_at=job.created_at,
        )
    finally:
        db.close()


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


def _fetch_missing_background(entry_ids: List[int], job_id: str):
    """Background task for fetching missing metadata."""
    db = models.SessionLocal()
    try:
        client = MddbrClient()
        success_count = 0
        fail_count = 0
        
        job = db.query(models.IndexingJob).filter(
            models.IndexingJob.job_id == job_id
        ).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        
        for entry_id in entry_ids:
            try:
                entry = db.query(models.MddbEntry).filter(
                    models.MddbEntry.id == entry_id
                ).first()
                
                if not entry:
                    fail_count += 1
                    continue
                
                full_data = fetch_project_full(entry.local_accession)
                project_data = full_data.get("project", {})
                references = full_data.get("references", [])
                filenotes = full_data.get("filenotes", [])
                
                # Get or create MddbProject (required for FK constraints on references/filenotes)
                mddb_project = db.query(models.MddbProject).filter(
                    models.MddbProject.local_accession == entry.local_accession
                ).first()
                
                project_name = project_data.get("metadata", {}).get("NAME") or project_data.get("title") or project_data.get("name")
                
                if not mddb_project:
                    mddb_project = models.MddbProject(
                        local_accession=entry.local_accession,
                        title=project_name,
                        description=project_data.get("metadata", {}).get("DESCRIPTION"),
                        status="indexed",
                        last_synced_at=datetime.utcnow(),
                    )
                    db.add(mddb_project)
                    db.flush()
                else:
                    mddb_project.title = project_name
                    mddb_project.description = project_data.get("metadata", {}).get("DESCRIPTION")
                    mddb_project.status = "indexed"
                    mddb_project.last_synced_at = datetime.utcnow()
                    mddb_project.updated_at = datetime.utcnow()
                
                db.commit()
                
                # Update entry
                entry.project_name = project_name
                entry.is_complete = True
                entry.updated_at = datetime.utcnow()
                db.commit()
                
                # Store references (FK to mddb_projects.id)
                for ref in references:
                    existing_ref = db.query(models.MddbReference).filter(
                        models.MddbReference.project_id == mddb_project.id,
                        models.MddbReference.ref_url == ref.get("url"),
                    ).first()
                    
                    if not existing_ref:
                        db_ref = models.MddbReference(
                            project_id=mddb_project.id,
                            ref_type=ref.get("type"),
                            ref_url=ref.get("url"),
                            ref_text=ref.get("text"),
                        )
                        db.add(db_ref)
                
                # Store filenotes (FK to mddb_projects.id)
                for note in filenotes:
                    existing_note = db.query(models.MddbFilenote).filter(
                        models.MddbFilenote.project_id == mddb_project.id,
                        models.MddbFilenote.filename == note.get("filename"),
                    ).first()
                    
                    if not existing_note:
                        db_note = models.MddbFilenote(
                            project_id=mddb_project.id,
                            filename=note.get("filename"),
                            file_type=note.get("file_type"),
                            file_size=note.get("file_size"),
                            file_url=note.get("file_url"),
                            checksum=note.get("checksum"),
                        )
                        db.add(db_note)
                
                db.commit()
                success_count += 1
                
                # Update progress after each item
                job.processed_items = success_count
                job.failed_items = fail_count
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to fetch metadata for entry {entry_id}: {e}")
                fail_count += 1
                job.failed_items = fail_count
                db.commit()
        
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        logger.error(f"Fetch missing job {job_id} failed: {e}")
        job = db.query(models.IndexingJob).filter(models.IndexingJob.job_id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@app.post("/index/fetch-missing", response_model=IndexingJobResponse)
async def fetch_missing_metadata(
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Fetch metadata for incomplete entries."""
    try:
        job_id = f"fetch-missing-{uuid.uuid4().hex[:8]}"
        
        job = models.IndexingJob(
            job_id=job_id,
            job_type="fetch_missing",
            status="pending",
            total_items=0,
            processed_items=0,
            failed_items=0,
        )
        db.add(job)
        db.commit()
        
        # Get incomplete entries
        incomplete_entries = db.query(models.MddbEntry).filter(
            models.MddbEntry.is_complete == False
        ).all()
        
        job.total_items = len(incomplete_entries)
        db.commit()
        
        # Schedule background task
        entry_ids = [e.id for e in incomplete_entries]
        background_tasks.add_task(_fetch_missing_background, entry_ids, job_id)
        
        return IndexingJobResponse(
            id=job.id,
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            total_items=job.total_items,
            processed_items=job.processed_items,
            failed_items=job.failed_items,
            created_at=job.created_at,
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


def _fetch_ground_truth_background(entry_ids: List[int], job_id: str):
    """Background task for fetching ground truth signatures."""
    db = models.SessionLocal()
    try:
        job = db.query(models.IndexingJob).filter(models.IndexingJob.job_id == job_id).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        job.total_items = len(entry_ids)
        db.commit()
        
        success_count = 0
        fail_count = 0
        
        for entry_id in entry_ids:
            try:
                entry = db.query(models.MddbEntry).filter(
                    models.MddbEntry.id == entry_id
                ).first()
                
                if not entry:
                    fail_count += 1
                    continue
                
                # Get the MddbProject for this entry (references are linked to project, not entry)
                mddb_project = db.query(models.MddbProject).filter(
                    models.MddbProject.local_accession == entry.local_accession
                ).first()
                
                if not mddb_project:
                    logger.warning(f"No project found for entry {entry_id} ({entry.local_accession})")
                    fail_count += 1
                    continue
                
                # Fetch references for this project
                references = db.query(models.MddbReference).filter(
                    models.MddbReference.project_id == mddb_project.id
                ).all()
                
                for ref in references:
                    ref_type = ref.ref_type or ""
                    ref_url = ref.ref_url or ""
                    
                    signature_type = None
                    signature_value = None
                    
                    # Determine signature type from reference
                    if "uniprot" in ref_url.lower() or "uniprot" in ref_type.lower():
                        signature_type = "uniprot"
                        # Extract UniProt ID from URL
                        if "uniprot.org/uniprot/" in ref_url:
                            signature_value = ref_url.split("uniprot.org/uniprot/")[-1].split("/")[0]
                    elif "pdb" in ref_url.lower() or "rcsb" in ref_url.lower():
                        signature_type = "pdb"
                        # Extract PDB ID from URL
                        if "rcsb.org/structure/" in ref_url:
                            signature_value = ref_url.split("rcsb.org/structure/")[-1].split("/")[0]
                    elif "inchi" in ref_type.lower() or "inchi" in ref_url.lower():
                        signature_type = "inchi"
                        signature_value = ref_url
                    
                    if signature_type and signature_value:
                        # Check if signature already exists
                        existing = db.query(models.GroundTruthSignature).filter(
                            models.GroundTruthSignature.entry_id == entry_id,
                            models.GroundTruthSignature.signature_type == signature_type,
                            models.GroundTruthSignature.signature_value == signature_value,
                        ).first()
                        
                        if not existing:
                            gt_sig = models.GroundTruthSignature(
                                entry_id=entry_id,
                                signature_type=signature_type,
                                signature_value=signature_value,
                                source_url=ref_url,
                                raw_data=None,
                            )
                            db.add(gt_sig)
                            db.commit()
                
                success_count += 1
                
                # Update progress after each entry
                job.processed_items = success_count
                job.failed_items = fail_count
                db.commit()
                
            except Exception as e:
                logger.error(f"Failed to fetch ground truth for entry {entry_id}: {e}")
                fail_count += 1
                job.failed_items = fail_count
                db.commit()
        
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
        
    except Exception as e:
        logger.error(f"Ground truth fetch job {job_id} failed: {e}")
        job = db.query(models.IndexingJob).filter(models.IndexingJob.job_id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@app.post("/ground-truth/fetch", response_model=IndexingJobResponse)
async def fetch_ground_truth(
    request: GroundTruthFetchRequest,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Fetch ground truth signatures for specified entries."""
    try:
        job_id = f"gt-fetch-{uuid.uuid4().hex[:8]}"
        
        job = models.IndexingJob(
            job_id=job_id,
            job_type="ground_truth_fetch",
            status="pending",
            total_items=len(request.entry_ids),
            processed_items=0,
            failed_items=0,
        )
        db.add(job)
        db.commit()
        
        background_tasks.add_task(_fetch_ground_truth_background, request.entry_ids, job_id)
        
        return IndexingJobResponse(
            id=job.id,
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            total_items=job.total_items,
            processed_items=job.processed_items,
            failed_items=job.failed_items,
            created_at=job.created_at,
        )
    finally:
        db.close()


@app.post("/ground-truth/fetch-all", response_model=IndexingJobResponse)
async def fetch_all_missing_ground_truth(
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Fetch ground truth signatures for all entries missing them."""
    try:
        job_id = f"gt-fetch-all-{uuid.uuid4().hex[:8]}"
        
        job = models.IndexingJob(
            job_id=job_id,
            job_type="ground_truth_fetch_all",
            status="pending",
            total_items=0,
            processed_items=0,
            failed_items=0,
        )
        db.add(job)
        db.commit()
        
        # Get entries that have references but no ground truth signatures
        # Join through MddbProject since references link to projects, not entries
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
        ).all()
        
        entry_ids = [e[0] for e in subquery]
        job.total_items = len(entry_ids)
        db.commit()
        
        # Schedule background task
        background_tasks.add_task(_fetch_ground_truth_background, entry_ids, job_id)
        
        return IndexingJobResponse(
            id=job.id,
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            total_items=job.total_items,
            processed_items=job.processed_items,
            failed_items=job.failed_items,
            created_at=job.created_at,
        )
    finally:
        db.close()


# Retry endpoints
@app.post("/runs/{run_id}/retry")
async def retry_validation_run(run_id: int, db: Session = Depends(get_db)):
    """Retry a failed validation run."""
    try:
        # Get the run
        run = db.query(models.Bat3Run).filter(models.Bat3Run.id == run_id).first()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")
        
        if run.status != "failed":
            raise HTTPException(status_code=400, detail=f"Run status is '{run.status}', only failed runs can be retried")
        
        # Get the entry
        entry = db.query(models.MddbEntry).filter(models.MddbEntry.id == run.entry_id).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        # Generate new run ID
        new_run_id = f"validation-{entry.id}-{uuid.uuid4().hex[:8]}"
        
        # Create new run record
        new_run = models.Bat3Run(
            entry_id=entry.id,
            run_id=new_run_id,
            status="pending",
            input_dir=run.input_dir,
            results_path=run.results_path,
            config_path=run.config_path,
        )
        db.add(new_run)
        
        # Update entry status
        entry.status = "processing"
        
        db.commit()
        db.refresh(new_run)
        
        # Schedule Celery task
        try:
            task_result = schedule_validation.delay(
                entry_id=entry.id,
                input_dir=run.input_dir,
                results_path=run.results_path,
                config_path=run.config_path,
            )
            new_run.celery_task_id = task_result.id
            new_run.status = "running"
            new_run.started_at = datetime.utcnow()
            db.commit()
            db.refresh(new_run)
        except Exception as e:
            logger.error(f"Failed to schedule Celery task: {e}")
            # Keep run in pending state if Celery fails
            pass
        
        return RunResponse(
            id=new_run.id,
            entry_id=new_run.entry_id,
            run_id=new_run.run_id,
            celery_task_id=new_run.celery_task_id,
            status=new_run.status,
            input_dir=new_run.input_dir,
            results_path=new_run.results_path,
            error_message=new_run.error_message,
            started_at=new_run.started_at,
            completed_at=new_run.completed_at,
            created_at=new_run.created_at,
        )
    finally:
        db.close()


@app.post("/entries/{entry_id}/retry")
async def retry_entry_validation(entry_id: int, db: Session = Depends(get_db)):
    """Retry validation for a specific entry."""
    try:
        # Get entry
        entry = db.query(models.MddbEntry).filter(models.MddbEntry.id == entry_id).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Entry not found")
        
        # Generate paths
        run_id = f"validation-{entry_id}-{uuid.uuid4().hex[:8]}"
        input_dir = f"/data/validation/{entry_id}/input"
        results_path = f"/data/validation/{entry_id}/results.json"
        config_path = f"/data/validation/{entry_id}/config.ini"
        
        # Create run record
        run = models.Bat3Run(
            entry_id=entry_id,
            run_id=run_id,
            status="pending",
            input_dir=input_dir,
            results_path=results_path,
            config_path=config_path,
        )
        db.add(run)
        
        # Update entry status
        entry.status = "processing"
        
        db.commit()
        db.refresh(run)
        
        # Schedule Celery task
        try:
            task_result = schedule_validation.delay(
                entry_id=entry_id,
                input_dir=input_dir,
                results_path=results_path,
                config_path=config_path,
            )
            run.celery_task_id = task_result.id
            run.status = "running"
            run.started_at = datetime.utcnow()
            db.commit()
            db.refresh(run)
        except Exception as e:
            logger.error(f"Failed to schedule Celery task: {e}")
            # Keep run in pending state if Celery fails
            pass
        
        return RunResponse(
            id=run.id,
            entry_id=run.entry_id,
            run_id=run.run_id,
            celery_task_id=run.celery_task_id,
            status=run.status,
            input_dir=run.input_dir,
            results_path=run.results_path,
            error_message=run.error_message,
            started_at=run.started_at,
            completed_at=run.completed_at,
            created_at=run.created_at,
        )
    finally:
        db.close()


@app.post("/index/jobs/{job_id}/retry")
async def retry_indexing_job(job_id: int, db: Session = Depends(get_db), background_tasks: BackgroundTasks = None):
    """Retry a failed indexing job."""
    try:
        # Get job
        job = db.query(models.IndexingJob).filter(models.IndexingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        if job.status != "failed":
            raise HTTPException(status_code=400, detail=f"Job status is '{job.status}', only failed jobs can be retried")
        
        # Create new job record with same parameters
        new_job_id = f"{job.job_type}-{uuid.uuid4().hex[:8]}"
        new_job = models.IndexingJob(
            job_id=new_job_id,
            job_type=job.job_type,
            status="pending",
            total_items=job.total_items,
            processed_items=0,
            failed_items=0,
        )
        db.add(new_job)
        db.commit()
        db.refresh(new_job)
        
        # Restart indexing based on job type
        if job.job_type == "mddbr_index":
            # Start new indexing job with same limit
            background_tasks.add_task(_index_projects_background, job.total_items, new_job_id)
        elif job.job_type == "fetch_missing":
            # Get incomplete entries
            incomplete_entries = db.query(models.MddbEntry).filter(
                models.MddbEntry.is_complete == False
            ).all()
            entry_ids = [e.id for e in incomplete_entries]
            
            # Use the standalone _fetch_missing_background function
            background_tasks.add_task(_fetch_missing_background, entry_ids, new_job_id)
        elif job.job_type in ("ground_truth_fetch", "ground_truth_fetch_all"):
            # Get entries that need ground truth
            # Join through MddbProject since references link to projects, not entries
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
            ).all()
            entry_ids = [e[0] for e in subquery]
            background_tasks.add_task(_fetch_ground_truth_background, entry_ids, new_job_id)
        
        return IndexingJobResponse(
            id=new_job.id,
            job_id=new_job.job_id,
            job_type=new_job.job_type,
            status=new_job.status,
            total_items=new_job.total_items,
            processed_items=new_job.processed_items,
            failed_items=new_job.failed_items,
            created_at=new_job.created_at,
        )
    finally:
        db.close()


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


@app.delete("/index/jobs/{job_id}")
async def delete_indexing_job(job_id: int, db: Session = Depends(get_db)):
    """Delete an indexing job by ID."""
    try:
        job = db.query(models.IndexingJob).filter(models.IndexingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        db.delete(job)
        db.commit()
        
        return {"message": "Job deleted successfully", "job_id": job.job_id}
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
def _import_sqlite_background(source_path: str, tables: List[str], job_id: str, conflict_strategy: str):
    """Background task for importing data from SQLite database."""
    import sqlite3
    
    db = models.SessionLocal()
    try:
        job = db.query(models.IndexingJob).filter(models.IndexingJob.job_id == job_id).first()
        if not job:
            logger.error(f"Import job {job_id} not found")
            return
        
        job.status = "running"
        job.started_at = datetime.utcnow()
        db.commit()
        
        # Connect to source SQLite database
        try:
            src_conn = sqlite3.connect(source_path)
            src_conn.row_factory = sqlite3.Row
            src_cursor = src_conn.cursor()
        except Exception as e:
            logger.error(f"Failed to connect to SQLite database: {e}")
            job.status = "failed"
            job.error_message = f"Failed to connect to source database: {e}"
            job.completed_at = datetime.utcnow()
            db.commit()
            return
        
        success_count = 0
        fail_count = 0
        current_table = None
        
        # Table mapping: source table -> target model
        table_models = {
            "mddb_entries": models.MddbEntry,
            "mddb_references": models.MddbReference,
            "mddb_filenotes": models.MddbFilenote,
            "mddb_projects": models.MddbProject,
            "bat3_runs": models.Bat3Run,
            "validation_queue": models.ValidationQueue,
            "validation_results": models.ValidationResult,
            "ground_truth_signatures": models.GroundTruthSignature,
            "indexing_jobs": models.IndexingJob,
            "batch_runs": models.BatchRun,
            "audit_log": models.AuditLog,
        }
        
        # Filter to requested tables or use all
        tables_to_import = tables if tables else list(table_models.keys())
        
        job.total_items = len(tables_to_import)
        db.commit()
        
        for table_name in tables_to_import:
            current_table = table_name
            logger.info(f"Importing table: {table_name}")
            
            if table_name not in table_models:
                logger.warning(f"Unknown table: {table_name}, skipping")
                fail_count += 1
                continue
            
            try:
                # Check if source table exists
                src_cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                if not src_cursor.fetchone():
                    logger.warning(f"Table {table_name} not found in source database")
                    fail_count += 1
                    continue
                
                # Get all rows from source table
                src_cursor.execute(f"SELECT * FROM {table_name}")
                rows = src_cursor.fetchall()
                
                if not rows:
                    logger.info(f"Table {table_name} is empty")
                    success_count += 1
                    job.processed_items = success_count
                    db.commit()
                    continue
                
                # Get column names
                columns = [desc[0] for desc in src_cursor.description]
                
                imported_rows = 0
                skipped_rows = 0
                
                for row in rows:
                    try:
                        row_dict = dict(row)
                        
                        # Remove 'id' from row_dict to avoid conflicts (let target DB assign new ID)
                        if 'id' in row_dict:
                            del row_dict['id']
                        
                        # Handle conflict strategy for unique fields
                        if conflict_strategy == "skip":
                            # Check for existing record based on unique fields
                            existing = None
                            if table_name == "mddb_entries" and "local_accession" in row_dict:
                                existing = db.query(models.MddbEntry).filter(
                                    models.MddbEntry.local_accession == row_dict["local_accession"]
                                ).first()
                            elif table_name == "mddb_projects" and "local_accession" in row_dict:
                                existing = db.query(models.MddbProject).filter(
                                    models.MddbProject.local_accession == row_dict["local_accession"]
                                ).first()
                            elif table_name == "bat3_runs" and "run_id" in row_dict:
                                existing = db.query(models.Bat3Run).filter(
                                    models.Bat3Run.run_id == row_dict["run_id"]
                                ).first()
                            
                            if existing:
                                skipped_rows += 1
                                continue
                        
                        # Create model instance dynamically
                        model_class = table_models[table_name]
                        
                        # Filter out columns that don't exist in target model
                        valid_columns = {k: v for k, v in row_dict.items() if hasattr(model_class, k)}
                        
                        if not valid_columns:
                            logger.warning(f"No valid columns for {table_name}")
                            continue
                        
                        # Create and add new record
                        new_record = model_class(**valid_columns)
                        db.add(new_record)
                        imported_rows += 1
                        
                    except Exception as e:
                        logger.error(f"Failed to import row in {table_name}: {e}")
                        db.rollback()
                        fail_count += 1
                        continue
                
                db.commit()
                logger.info(f"Imported {imported_rows} rows from {table_name}, skipped {skipped_rows}")
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to import table {table_name}: {e}")
                fail_count += 1
                db.rollback()
            
            # Update progress
            job.processed_items = success_count + fail_count
            db.commit()
        
        src_conn.close()
        
        # Update job status
        job.processed_items = success_count + fail_count
        job.failed_items = fail_count
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Import job {job_id} completed: {success_count} tables success, {fail_count} tables failed")
        
    except Exception as e:
        logger.error(f"Import job {job_id} failed: {e}")
        job = db.query(models.IndexingJob).filter(models.IndexingJob.job_id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


@app.post("/import/sqlite", response_model=ImportJobResponse)
async def import_from_sqlite(
    request: SqliteImportRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Import data from SQLite database."""
    try:
        job_id = f"sqlite-import-{uuid.uuid4().hex[:8]}"
        
        # Default tables if not specified
        default_tables = [
            "mddb_entries",
            "mddb_references",
            "mddb_filenotes",
            "mddb_projects",
            "bat3_runs",
            "validation_queue",
            "validation_results",
            "ground_truth_signatures",
            "indexing_jobs",
            "batch_runs",
            "audit_log",
        ]
        
        tables_to_import = request.tables if request.tables else default_tables
        
        # Create import job record
        job = models.IndexingJob(
            job_id=job_id,
            job_type="sqlite_import",
            status="pending",
            total_items=len(tables_to_import),
            processed_items=0,
            failed_items=0,
        )
        db.add(job)
        db.commit()
        
        # Start background task
        background_tasks.add_task(
            _import_sqlite_background,
            request.source_path,
            tables_to_import,
            job_id,
            request.conflict_strategy,
        )
        
        return ImportJobResponse(
            job_id=job.job_id,
            job_type=job.job_type,
            status=job.status,
            source_path=request.source_path,
            tables_requested=tables_to_import,
            total_items=job.total_items,
            processed_items=job.processed_items,
            failed_items=job.failed_items,
            conflict_strategy=request.conflict_strategy,
            created_at=job.created_at,
        )
    finally:
        db.close()


@app.get("/import/status/{job_id}", response_model=ImportStatusResponse)
async def get_import_status(job_id: int, db: Session = Depends(get_db)):
    """Get import job status and progress."""
    try:
        job = db.query(models.IndexingJob).filter(models.IndexingJob.id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Import job not found")
        
        if job.job_type != "sqlite_import":
            raise HTTPException(status_code=400, detail="Job is not a SQLite import job")
        
        progress_percentage = 0.0
        if job.total_items > 0:
            progress_percentage = round((job.processed_items / job.total_items) * 100, 2)
        
        return ImportStatusResponse(
            job_id=job.job_id,
            status=job.status,
            progress_percentage=progress_percentage,
            total_items=job.total_items,
            processed_items=job.processed_items,
            failed_items=job.failed_items,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
        )
    finally:
        db.close()


@app.get("/import/jobs", response_model=List[IndexingJobResponse])
async def list_import_jobs(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List recent SQLite import jobs."""
    try:
        jobs = db.query(models.IndexingJob).filter(
            models.IndexingJob.job_type == "sqlite_import"
        ).order_by(models.IndexingJob.created_at.desc()).limit(limit).all()
        
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


# Startup event

# =============================================================================
# VALIDATION API ENDPOINTS (for UI)
# =============================================================================

from fastapi.responses import StreamingResponse
import json
from tasks import celery

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

@app.get("/validation/queue/workers")
async def get_queue_workers():
    """Get list of active Celery workers."""
    try:
        
        inspect = celery.control.inspect()
        active_workers = inspect.active() or {}
        registered = inspect.registered() or {}
        stats = inspect.stats() or {}
        workers = []
        for worker_name, tasks in active_workers.items():
            worker_info = {"worker_name": worker_name, "active_tasks": len(tasks) if tasks else 0, "registered_tasks": len(registered.get(worker_name, [])), "status": "online"}
            if worker_name in stats:
                worker_info["pool_size"] = stats[worker_name].get("pool", {}).get("max-concurrency", 0)
            workers.append(worker_info)
        return {"workers": workers}
    except Exception as e:
        logger.error(f"Error getting workers: {e}")
        return {"workers": [], "error": str(e)}

@app.post("/api/validation/queue/workers/ping")
async def ping_worker(request: dict):
    """Ping a specific worker."""
    try:
        worker_name = request.get("worker_name")
        if not worker_name:
            return {"error": "worker_name required"}, 400
        
        result = celery.control.ping(destination=[worker_name], timeout=2.0)
        if result:
            return {"status": "pong", "worker_name": worker_name}
        else:
            return {"status": "no_response", "worker_name": worker_name}, 408
    except Exception as e:
        logger.error(f"Error pinging worker: {e}")
        return {"error": str(e)}, 500

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

@app.get("/validation/stats/failure-analysis")
async def get_failure_analysis_stats():
    """Get failure analysis statistics."""
    import sys
    sys.path.insert(0, "/home/tomsko/work/bat3")
    from api.failure_analysis import analyze_failures_api
    try:
        results = analyze_failures_api(file_limit=500)
        return results
    except Exception as e:
        logger.error(f"Failure analysis failed: {e}")
        return {"error": str(e), "analyzed_at": datetime.utcnow().isoformat()}

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
            yield f": heartbeat\n\n"
            await asyncio.sleep(30)
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})



@app.post("/validation/queue/start-processing")
async def start_queue_processing():
    """Start processing all queued items by dispatching Celery tasks."""
    db = next(get_db())
    try:
        queued_items = db.query(models.ValidationQueue).filter(
            models.ValidationQueue.status == "queued"
        ).limit(100).all()
        
        dispatched = 0
        for item in queued_items:
            try:
                entry = db.query(models.MddbEntry).filter(models.MddbEntry.id == item.entry_id).first()
                if not entry:
                    item.status = "failed"
                    item.last_error = "Entry not found"
                    db.commit()
                    continue
                
                input_dir = f"/data/validation/{entry.id}/input"
                results_path = f"/data/validation/{entry.id}/results.json"
                config_path = f"/data/validation/{entry.id}/config.ini"
                
                task_result = schedule_validation.delay(
                    entry_id=entry.id, input_dir=input_dir, results_path=results_path, config_path=config_path
                )
                
                item.status = "processing"
                item.started_at = datetime.utcnow()
                db.commit()
                dispatched += 1
            except Exception as e:
                logger.error(f"Failed to dispatch task for entry {item.entry_id}: {e}")
                item.status = "failed"
                item.last_error = str(e)
                db.commit()
        
        remaining = db.query(func.count(models.ValidationQueue.id)).filter(models.ValidationQueue.status == "queued").scalar()
        return {"message": f"Dispatched {dispatched} tasks", "dispatched": dispatched, "remaining_queued": remaining}
    except Exception as e:
        db.rollback()
        logger.error(f"Start processing failed: {e}")
        return {"error": str(e)}, 500
    finally:
        db.close()

@app.post("/validation/queue/bulk-action")
async def handle_bulk_action(request: dict):
    """Handle bulk queue actions: queue_all_pending, queue_all_failed, clear_completed, retry."""
    db = next(get_db())
    try:
        action = request.get("action")
        queue_item_ids = request.get("queue_item_ids", [])
        
        if action == "queue_all_pending":
            # Queue all pending entries
            pending_items = db.query(models.ValidationQueue).filter(
                models.ValidationQueue.status.in_(["pending", "failed"])
            ).all()
            for item in pending_items:
                item.status = "queued"
            db.commit()
            return {"message": f"Queued {len(pending_items)} pending items", "count": len(pending_items)}
        
        elif action == "queue_all_failed":
            # Queue all failed entries
            failed_items = db.query(models.ValidationQueue).filter(
                models.ValidationQueue.status == "failed"
            ).all()
            for item in failed_items:
                item.status = "queued"
            db.commit()
            return {"message": f"Queued {len(failed_items)} failed items", "count": len(failed_items)}
        
        elif action == "clear_completed":
            # Clear completed entries
            completed_items = db.query(models.ValidationQueue).filter(
                models.ValidationQueue.status == "completed"
            ).all()
            for item in completed_items:
                item.status = "cleared"
            db.commit()
            return {"message": f"Cleared {len(completed_items)} completed items", "count": len(completed_items)}
        
        elif action == "retry" and queue_item_ids:
            # Retry specific items
            items = db.query(models.ValidationQueue).filter(
                models.ValidationQueue.id.in_(queue_item_ids)
            ).all()
            for item in items:
                item.status = "queued"
                item.last_error = None
            db.commit()
            return {"message": f"Retrying {len(items)} items", "count": len(items)}
        
        elif action == "clear" and queue_item_ids:
            # Clear specific items
            items = db.query(models.ValidationQueue).filter(
                models.ValidationQueue.id.in_(queue_item_ids)
            ).all()
            for item in items:
                item.status = "cleared"
            db.commit()
            return {"message": f"Cleared {len(items)} items", "count": len(items)}
        
        else:
            return {"error": f"Unknown action: {action}"}, 400
            
    except Exception as e:
        db.rollback()
        logger.error(f"Bulk action failed: {e}")
        return {"error": str(e)}, 500
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    logger.info("Initializing database tables...")
    models.init_db()
    logger.info("Database initialized successfully")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

# =============================================================================
# FAILURE ANALYSIS API
# =============================================================================

@app.get("/api/failure-analysis")
async def get_failure_analysis():
    """
    Analyze failure patterns across all failed validation runs.
    
    Returns comprehensive statistics about:
    - Database failures vs results.json failures
    - Error categories
    - Task failure points
    - Actionable recommendations
    """
    import sys
    sys.path.insert(0, '/home/tomsko/work/bat3')
    
    from api.failure_analysis import analyze_failures_api
    
    try:
        results = analyze_failures_api(file_limit=500)
        return results
    except Exception as e:
        logger.error(f"Failure analysis failed: {e}")
        return {
            "error": str(e),
            "analyzed_at": datetime.utcnow().isoformat()
        }



from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from queue_processor import check_task_completions
from sqlalchemy import create_engine
from config import DATABASE_URL

bg_engine = create_engine(DATABASE_URL)
scheduler = BackgroundScheduler()

@scheduler.scheduled_job(IntervalTrigger(seconds=30))
def periodic_completion_check():
    try:
        from sqlalchemy.orm import sessionmaker
        db = sessionmaker(autocommit=False, autoflush=False, bind=bg_engine)()
        try:
            updated = check_task_completions(db)
            if updated > 0:
                logger.info(f"Completion check: Updated {updated} items")

            # Reconcile zombie runs/queue entries (expired celery results)
            from queue_processor import sweep_stale_validations
            sweep = sweep_stale_validations(db)
            if any(sweep.values()):
                logger.info(f"Stale sweep reconciled: {sweep}")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in completion check: {e}")


# Dispatch is gated: only claims 'queued' rows when VALIDATION_DISPATCH_ENABLED=1
@scheduler.scheduled_job(IntervalTrigger(seconds=15))
def periodic_dispatch_check():
    import os as _os
    if _os.environ.get("VALIDATION_DISPATCH_ENABLED", "0") != "1":
        return
    try:
        from sqlalchemy.orm import sessionmaker
        from queue_processor import process_validation_queue
        db = sessionmaker(autocommit=False, autoflush=False, bind=bg_engine)()
        try:
            started = process_validation_queue(db=db, concurrency=5)
            if started > 0:
                logger.info(f"Dispatch: started {started} validations")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Error in dispatch check: {e}")

scheduler.start()


# Enhanced Worker Management Endpoints

class WorkerScalingRequest(BaseModel):
    replicas: int = Field(..., ge=0, le=50, description="Number of worker replicas (0-50)")
    reason: str = Field(default="Manual scaling", description="Reason for scaling")

class WorkerPoolUpdateRequest(BaseModel):
    concurrency: int = Field(..., ge=1, le=16, description="Tasks per worker (1-16)")

@app.get("/validation/workers/status")
async def get_worker_status():
    """
    Get comprehensive worker status including K8s deployment info.
    
    Returns:
    - Total workers and capacity
    - Active vs idle workers
    - Queue depth and utilization
    - Scaling recommendations
    """
    from kubernetes import client as k8s_client, config
    from config import CELERY_BROKER_URL
    
    db = next(get_db())
    try:
        # Get K8s deployment info
        config.load_incluster_config()
        k8s_apps = k8s_client.AppsV1Api()
        deployment = k8s_apps.read_namespaced_deployment("validation-worker", "ceitec-biodata-ns")
        
        current_replicas = deployment.status.replicas or 0
        ready_replicas = deployment.status.ready_replicas or 0
        available_replicas = deployment.status.available_replicas or 0
        
        # Get Celery worker info
        inspect = celery.control.inspect()
        active = inspect.active() or {}
        stats = inspect.stats() or {}
        
        # Calculate worker metrics
        total_workers = len(active)
        total_pool_capacity = sum(s.get("pool", {}).get("max-concurrency", 0) for s in stats.values())
        total_active_tasks = sum(len(t) for t in active.values())
        idle_workers = sum(1 for t in active.values() if len(t) == 0)
        busy_workers = total_workers - idle_workers
        
        # Get queue info
        queued = db.query(func.count(models.ValidationQueue.id)).filter(
            models.ValidationQueue.status == "queued"
        ).scalar()
        processing = db.query(func.count(models.ValidationQueue.id)).filter(
            models.ValidationQueue.status == "processing"
        ).scalar()
        
        # Calculate utilization
        utilization = (total_active_tasks / total_pool_capacity * 100) if total_pool_capacity > 0 else 0
        
        # Scaling recommendation
        recommendation = "stable"
        if utilization > 80 and queued > 100:
            recommendation = "scale_up"
        elif utilization < 20 and queued < 50 and current_replicas > 2:
            recommendation = "scale_down"
        
        return {
            "deployment": {
                "name": "validation-worker",
                "current_replicas": current_replicas,
                "ready_replicas": ready_replicas,
                "available_replicas": available_replicas,
            },
            "capacity": {
                "total_workers": total_workers,
                "total_pool_capacity": total_pool_capacity,
                "tasks_per_worker": 4,  # Fixed in deployment
                "active_tasks": total_active_tasks,
                "idle_workers": idle_workers,
                "busy_workers": busy_workers,
                "utilization_percent": round(utilization, 1),
            },
            "queue": {
                "queued": queued,
                "processing": processing,
                "estimated_wait_minutes": round(queued / total_pool_capacity * 2, 1) if total_pool_capacity > 0 else 0,
            },
            "recommendation": {
                "action": recommendation,
                "suggested_replicas": min(current_replicas + 2, 50) if recommendation == "scale_up" else max(current_replicas - 2, 2) if recommendation == "scale_down" else current_replicas,
                "reason": f"Utilization {utilization:.1f}%, {queued} queued tasks" if recommendation != "stable" else "System operating normally"
            }
        }
    finally:
        db.close()


@app.post("/validation/workers/scale")
async def scale_workers(request: WorkerScalingRequest):
    """
    Scale worker deployment up or down.
    
    Requires K8s access. Will update deployment replicas.
    """
    from kubernetes import client as k8s_client, config
    
    try:
        config.load_incluster_config()
        k8s_apps = k8s_client.AppsV1Api()
        
        # Get current deployment
        deployment = k8s_apps.read_namespaced_deployment("validation-worker", "ceitec-biodata-ns")
        old_replicas = deployment.spec.replicas or 10
        
        # Update replicas
        deployment.spec.replicas = request.replicas
        k8s_apps.patch_namespaced_deployment("validation-worker", "ceitec-biodata-ns", deployment)
        
        logger.info(f"Scaled workers from {old_replicas} to {request.replicas}: {request.reason}")
        
        return {
            "success": True,
            "old_replicas": old_replicas,
            "new_replicas": request.replicas,
            "reason": request.reason,
            "message": f"Scaling from {old_replicas} to {request.replicas} workers. This may take 1-2 minutes."
        }
    except Exception as e:
        logger.error(f"Failed to scale workers: {e}")
        return {"success": False, "error": str(e)}


@app.get("/validation/workers/metrics")
async def get_worker_metrics(hours: int = Query(24, ge=1, le=168)):
    """
    Get worker performance metrics over time.
    
    Returns historical data on:
    - Task completion rate
    - Average task duration
    - Worker utilization
    - Error rate
    """
    db = next(get_db())
    try:
        from datetime import datetime, timedelta
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        # Get completed runs in time period
        result = db.query(
            func.date_trunc('hour', models.Bat3Run.completed_at).label('hour'),
            func.count().label('completed'),
            func.avg(models.Bat3Run.completed_at - models.Bat3Run.started_at).label('avg_duration')
        ).filter(
            models.Bat3Run.status == 'completed',
            models.Bat3Run.completed_at >= cutoff
        ).group_by('hour').order_by('hour').all()
        
        metrics = []
        for row in result:
            metrics.append({
                "timestamp": row.hour.isoformat() if row.hour else None,
                "tasks_completed": row.completed,
                "avg_duration_seconds": float(row.avg_duration.total_seconds()) if row.avg_duration else 0
            })
        
        # Get error rate
        total = db.query(func.count(models.Bat3Run.id)).filter(
            models.Bat3Run.completed_at >= cutoff
        ).scalar()
        failed = db.query(func.count(models.Bat3Run.id)).filter(
            models.Bat3Run.status == 'failed',
            models.Bat3Run.completed_at >= cutoff
        ).scalar()
        
        return {
            "period_hours": hours,
            "metrics": metrics,
            "summary": {
                "total_tasks": total or 0,
                "failed_tasks": failed or 0,
                "error_rate_percent": round(failed / total * 100, 2) if total > 0 else 0,
                "avg_tasks_per_hour": round((total or 0) / hours, 1)
            }
        }
    finally:
        db.close()


@app.post("/validation/workers/{worker_name}/restart")
async def restart_worker(worker_name: str):
    """
    Restart a specific worker pod by deleting it (K8s will recreate).
    """
    from kubernetes import client as k8s_client, config
    
    try:
        config.load_incluster_config()
        k8s_core = k8s_client.CoreV1Api()
        
        # Extract pod name from worker name (celery@validation-worker-xxx-yyy -> validation-worker-xxx-yyy)
        pod_name = worker_name.replace("celery@", "")
        
        # Delete pod
        k8s_core.delete_namespaced_pod(pod_name, "ceitec-biodata-ns", grace_period_seconds=30)
        
        logger.info(f"Restarted worker pod: {pod_name}")
        
        return {
            "success": True,
            "pod_name": pod_name,
            "message": f"Worker {pod_name} is being restarted. New pod will be ready in ~30 seconds."
        }
    except Exception as e:
        logger.error(f"Failed to restart worker: {e}")
        return {"success": False, "error": str(e)}
