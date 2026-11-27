"""FastAPI application for BAT3 Pipeline API."""

import os
import time
import re
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from . import tasks  # noqa: F401  (registers the Celery tasks in this process)
from .routes.runs import router as runs_router, get_runs_dir
from .models import CapabilitiesResponse

logger = logging.getLogger(__name__)

# GitHub #29: the root-level campaign control plane (/validation/*,
# /batch-runs*, /runs/rerun-all, /stats, worker scale/restart) was removed
# with its database session; the admin API (/api/v1/admin, token) is the
# only operator surface. Campaign runs go through the repository queue.


@asynccontextmanager
async def lifespan(app: FastAPI):
    runs_dir = get_runs_dir()
    runs_dir.mkdir(parents=True, exist_ok=True)
    app.mount("/files", StaticFiles(directory=str(runs_dir)), name="files")
    # Zombie-run reconciler (OQ-16): marks runs failed whose celery task
    # vanished (worker hard-kill). Redis leader-locked inside; one sweeper
    # cluster-wide despite --workers 4. BAT3_RUN_REAPER=0 disables.
    from src_new.celery_app import celery as celery_app
    from src_new.api.run_reaper import start_reaper
    reaper_task = start_reaper(celery_app, runs_dir)
    # Warm the run-summary cache (run list, admin page) off the request path.
    import threading
    from src_new.api.run_index import summaries
    threading.Thread(target=summaries, args=(runs_dir,), daemon=True).start()
    # Traffic statistics: GeoIP database present and fresh (background).
    from src_new.api import traffic
    if traffic.enabled():
        threading.Thread(target=traffic.refresh_geoip, daemon=True).start()
    yield
    traffic.flush()
    if reaper_task is not None:
        reaper_task.cancel()


from src_new.api.openapi_docs import API_DESCRIPTION  # noqa: E402

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
    # 429 answers say when to retry; downloads name their file
    expose_headers=["Retry-After", "Content-Disposition"],
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
async def record_traffic(request, call_next):
    """Traffic statistics (src_new/api/traffic.py): meaningful API calls."""
    started = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/"):
        try:
            from src_new.api import traffic
            route = getattr(request.scope.get("route"), "path", None) or "(unmatched)"
            client = request.headers.get("x-bioid-client", "")
            if traffic.worth_recording(request.method, route, response.status_code,
                                       traffic.client_kind(request.headers.get("user-agent", ""), client)):
                from src_new.api.routes.runs import _requester_ip
                traffic.record("request", ip=_requester_ip(request), route=route,
                               status=response.status_code, method=request.method,
                               ms=(time.perf_counter() - started) * 1000,
                               user_agent=request.headers.get("user-agent", ""), client=client)
        except Exception as exc:  # statistics must never break a request
            logger.debug("traffic: not recorded: %s", exc)
    return response


@app.post("/api/v1/events/pageview", include_in_schema=False, status_code=204)
async def pageview(request: Request):
    """Page-view beacon of the web app and the documentation. Honours
    Do-Not-Track; never counts the admin page."""
    from fastapi import Response
    from src_new.api import traffic
    from src_new.api.routes.runs import _requester_ip
    if request.headers.get("dnt") == "1" or request.headers.get("sec-gpc") == "1":
        return Response(status_code=204)
    try:
        body = await request.json()
    except Exception:
        body = {}
    page = traffic.page_route(str(body.get("path") or "")) if isinstance(body, dict) else None
    if page:
        traffic.record("pageview", ip=_requester_ip(request), route=page,
                       user_agent=request.headers.get("user-agent", ""),
                       client=request.headers.get("x-bioid-client", "") or "web",
                       referrer=str(body.get("referrer") or "")[:500] or None)
    return Response(status_code=204)


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
    "run_retention",           # 2026-11-17 — retention on status/summary; owner POST /retention
    "warning_docs_url",        # 2026-11-17 — docs_url on warnings and errors
    "run_incomplete",          # 2026-11-18 — incomplete gaps; rerun_of / superseded_by
    "run_queues",              # 2026-11-18 — queue field; repository queue (X-Queue-Token)
    "automatic_retries",       # 2026-11-18 — retry/attempts while a run waits (reads "queued")
    "run_completeness",        # 2026-11-21 — completeness/partial_stages next to status (mdval audit item 7)
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


# ============== VALIDATION ENDPOINTS ==============

# Temporary endpoint to test queue_all_cancelled

# ---------------------------------------------------------------------------
# Published schema (/docs, /openapi.json): the public /api/v1 routes, with the
# descriptions, errors and examples of src_new/api/openapi_docs.py. The
# root-level duplicates, the campaign control plane, the batch routes and the
# UI-internal helpers stay callable in-cluster but are left out.
# ---------------------------------------------------------------------------
from src_new.api import openapi_docs  # noqa: E402

openapi_docs.publish(app)

