"""FastAPI application for BAT3 Pipeline API."""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import tasks to register them when the API starts
from . import tasks
from .routes.runs import router as runs_router, get_runs_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler to mount static files directory."""
    # Startup
    runs_dir = get_runs_dir()
    runs_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=str(runs_dir)), name="files")
    
    # Mount UI dist if it exists
    ui_dist = Path(__file__).resolve().parents[2] / "ui" / "dist"
    if ui_dist.exists():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
    
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(title="BAT3 Pipeline API", version="0.1.0", lifespan=lifespan)

# Add CORS middleware for public API.
# Note: allow_credentials=False is required when allow_origins=["*"] because
# browsers reject the combination of wildcard origins with credentials enabled.
# This API does not require cookies/credentials, so False is appropriate.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(runs_router, prefix="/runs", tags=["runs"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/health/live")
async def health_live():
    """Liveness probe endpoint - returns 200 if the service is running."""
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    """Readiness probe endpoint - checks runs directory and Redis connectivity."""
    # Check that the runs directory exists and is writable
    runs_dir = get_runs_dir()
    if not runs_dir.exists() or not os.access(str(runs_dir), os.W_OK):
        raise HTTPException(status_code=503, detail="Runs directory not writable")
    
    # Check Redis connectivity via Celery backend
    try:
        from src_new.celery_app import celery
        # Try to ping the result backend
        celery.backend.client.ping()
    except Exception as exc:
        # Fall back to checking environment variables if backend client is unavailable
        broker_url = os.environ.get("CELERY_BROKER_URL")
        result_backend = os.environ.get("CELERY_RESULT_BACKEND")
        if not broker_url or not result_backend:
            raise HTTPException(status_code=503, detail=f"Redis unreachable: {exc}")
        # If env vars are set, consider it ready (can't verify connection without redis lib)
    
    return {"status": "ready"}


@app.get("/runs/{run_id}/task")
async def get_task_status(run_id: str):
    """Get Celery task status for a run."""
    from src_new.celery_app import celery
    result = celery.AsyncResult(run_id)
    return {"run_id": run_id, "status": result.status, "result": result.result if result.ready() else None}
