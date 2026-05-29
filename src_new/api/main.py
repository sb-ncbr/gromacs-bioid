"""FastAPI application for BAT3 Pipeline API."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
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
    import os
    ui_dist = Path(__file__).resolve().parents[2] / "ui" / "dist"
    if ui_dist.exists():
        app.mount("/", StaticFiles(directory=str(ui_dist), html=True), name="ui")
    
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(title="BAT3 Pipeline API", version="0.1.0", lifespan=lifespan)

# Add CORS middleware (dev-friendly)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(runs_router, prefix="/runs", tags=["runs"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/runs/{run_id}/task")
async def get_task_status(run_id: str):
    """Get Celery task status for a run."""
    from src_new.celery_app import celery
    result = celery.AsyncResult(run_id)
    return {"run_id": run_id, "status": result.status, "result": result.result if result.ready() else None}
