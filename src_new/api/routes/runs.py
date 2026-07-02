"""Router for run-related endpoints."""

from __future__ import annotations
import errno
import time

import re
import shutil
import json
import os
import uuid
from datetime import datetime, timezone

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from ..models import (
    RerunAllResponse,
    RerunRunItem,
    CancelRunResponse,
    RunFilesResponse,
    PipelineStatusResponse,
    RunStatusResponse,
    TaskInfo,
    WarningItem,
    ErrorItem,
    EventItem,
    LoadingInfoResponse,
    LoadingAttemptInfo,
    MoleculeSummaryResponse,
    MoleculeInstanceInfo,
    MoleculeInfoResponse,
    RenderPathsResponse,
    SignaturesResponse,
    SignatureInfo,
    IdentifiersResponse,
    IdentifierHit,
    ResolverErrorItem,
    VerificationResponse,
    VerifiedHitItem,
    RunCreateResponse,
    RunListItem,
    RunListResponse,
    RunSummaryResponse,
)
from ..utils import build_database_url
from ..tasks import run_pipeline_task

router = APIRouter()

# Maximum upload size: 128 MiB (matches ingress limit)
MAX_UPLOAD_BYTES = 128 * 1024 * 1024


@router.get("/config/default", response_model=dict)
async def get_default_config():
    """Get the default configuration as a JSON dict."""
    try:
        from src_new.config.loader import RunConfig
        return RunConfig.from_default_ini().to_dict()
    except Exception as e:
        return {"error": str(e), "config": RunConfig().to_dict()}


@router.get("/config/parallel-default", response_model=dict)
async def get_parallel_default_config():
    """Get the default configuration with parallelism enabled."""
    from src_new.config.loader import RunConfig
    config = RunConfig.from_default_ini()
    config.executor.signatures_parallel = True
    config.executor.identifiers_parallel = True
    config.executor.verification_parallel = True
    return config.to_dict()


def get_runs_dir() -> Path:
    """Get the runs directory from environment or default."""
    return Path(os.environ.get("BAT3_RUNS_DIR", "./runs"))


def load_results_json(run_id: str) -> Dict[str, Any]:
    """Load results.json for a given run_id."""
    runs_dir = get_runs_dir()
    results_path = runs_dir / run_id / "results.json"
    
    if not results_path.exists():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    
    # Retry on ESTALE (stale NFS file handle) up to 3 times
    max_retries = 3
    last_exception: Optional[Exception] = None
    for attempt in range(max_retries):
        try:
            content = results_path.read_text(encoding="utf-8")
            return json.loads(content)
        except OSError as e:
            last_exception = e
            if e.errno == errno.ESTALE:
                if attempt < max_retries - 1:
                    time.sleep(0.1 * (attempt + 1))
                    continue
            raise
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"Invalid JSON in results file: {e}")
    
    # All retries exhausted (should not reach here)
    if isinstance(last_exception, json.JSONDecodeError):
        raise HTTPException(status_code=500, detail=f"Invalid JSON in results file: {last_exception}")
    raise last_exception

def resolve_artifact_paths(artifacts_dict: Dict[str, Any], run_id: str) -> Dict[str, Any]:
    """Resolve artifact paths to full paths with descriptions."""
    resolved = {}
    runs_dir = get_runs_dir()
    
    for key, artifact in artifacts_dict.items():
        path = artifact.get("path", "")
        if path and not Path(path).is_absolute():
            # Make path relative to run directory
            full_path = str(runs_dir / run_id / path)
        else:
            full_path = path
        
        resolved[key] = {
            **artifact,
            "full_path": full_path,
        }
    
    return resolved


@router.post("", response_model=RunCreateResponse)
async def create_run(
    files: List[UploadFile],
    config_file: Optional[UploadFile] = None,
    config_json: Optional[str] = Form(None),
    run_id: Optional[str] = None,
    run_name: Optional[str] = Form(None),
) -> RunCreateResponse:
    """
    Create a new run by uploading input files and optionally a config file.
    
    The pipeline runs in the background via Celery. Returns immediately with run status.
    """
    # Generate run_id if not provided
    if run_id is None:
        run_id = str(uuid.uuid4())
    
    runs_dir = get_runs_dir()
    run_dir = runs_dir / run_id
    input_dir = run_dir / "input"
    
    # Create run directory structure
    input_dir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded files to input directory with size validation
    saved_files = {}
    for file in files:
        if file.filename:
            file_content = await file.read()
            if len(file_content) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File '{file.filename}' exceeds 128 MiB limit"
                )
            file_path = input_dir / file.filename
            with open(file_path, "wb") as f:
                f.write(file_content)
            saved_files[file.filename] = str(file_path)
    
    # Handle config: uploaded file, JSON overrides, or default
    config_path: Optional[Path] = None
    if config_file and config_file.filename:
        # Use uploaded config file with size validation
        config_content_bytes = await config_file.read()
        if len(config_content_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{config_file.filename}' exceeds 128 MiB limit"
            )
        config_path = run_dir / "config.ini"
        with open(config_path, "wb") as f:
            f.write(config_content_bytes)
        # Apply quick structure search overrides if enabled
        from src_new.config.loader import RunConfig
        config = RunConfig.from_ini_path(config_path)
        if config.loader.quick_structure_search:
            config.override("loader.guess_missing_bonds", False)
            config.override("signatures.topology_less_pdb", True)
            config.override("signatures.ca_only_pdb", True)
            config.to_ini_path(config_path)
    elif config_json:
        # Parse JSON overrides and write customized config
        import json as json_module
        try:
            overrides_dict = json_module.loads(config_json)
        except json_module.JSONDecodeError as e:
            raise HTTPException(status_code=422, detail=f"Invalid config JSON: {e}")
        
        # Validate top-level keys against RunConfig sections
        from src_new.config.loader import RunConfig
        valid_sections = set(RunConfig.__dataclass_fields__.keys())
        for key in overrides_dict.keys():
            if key not in valid_sections:
                raise HTTPException(status_code=422, detail=f"Unknown config section: {key}")
        
        config = RunConfig.from_default_ini()
        config.apply_nested_overrides(overrides_dict)
        # Apply quick structure search overrides if enabled
        if config.loader.quick_structure_search:
            config.override("loader.guess_missing_bonds", False)
            config.override("signatures.topology_less_pdb", True)
            config.override("signatures.ca_only_pdb", True)
        config_path = run_dir / "config.ini"
        config.to_ini_path(config_path)
    else:
        # Copy default config
        from src_new.config.loader import RunConfig
        config = RunConfig.from_default_ini()
        # Apply quick structure search overrides if enabled
        if config.loader.quick_structure_search:
            config.override("loader.guess_missing_bonds", False)
            config.override("signatures.topology_less_pdb", True)
            config.override("signatures.ca_only_pdb", True)
        config_path = run_dir / "config.ini"
        config.to_ini_path(config_path)
    
    # Create results manager and write initial "queued" status
    results_path = run_dir / "results.json"
    initial_results = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pipeline": {
            "name": "BAT3",
            "status": "queued",
            "run_id": run_id,
        },
    }
    if run_name:
        initial_results["pipeline"]["run_name"] = run_name
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(initial_results, f, indent=2)
    
    # Enqueue Celery task with run_id as task_id
    run_pipeline_task.apply_async(
        task_id=run_id,
        kwargs={
            "run_id": run_id,
            "input_dir": str(input_dir),
            "results_path": str(results_path),
            "config_path": str(config_path) if config_path else None,
        },
    )
    
    return RunCreateResponse(
        run_id=run_id,
        status="queued",
        message=f"Run {run_id} queued successfully",
        results_url=f"/runs/{run_id}/status",
    )


@router.get("", response_model=RunListResponse)
async def list_runs() -> RunListResponse:
    """List all runs with basic metadata."""
    runs_dir = get_runs_dir()
    
    if not runs_dir.exists():
        return RunListResponse(runs=[])
    
    runs = []
    for entry in runs_dir.iterdir():
        if not entry.is_dir():
            continue
        
        results_path = entry / "results.json"
        if not results_path.exists():
            continue
        
        try:
            # Retry once on ESTALE
            data = None
            for retry_attempt in range(2):
                try:
                    file_content = results_path.read_text(encoding="utf-8")
                    data = json.loads(file_content)
                    break
                except OSError as e:
                    if e.errno == errno.ESTALE and retry_attempt == 0:
                        time.sleep(0.1)
                        continue
                    raise
            
            pipeline_data = data.get("pipeline", {})
            created_at = data.get("created_at", "")
            
            runs.append(RunListItem(
                run_id=entry.name,
                status=pipeline_data.get("status", "unknown"),
                created_at=created_at,
                input_kind=pipeline_data.get("input_kind"),
                run_name=pipeline_data.get("run_name"),
            ))
        except (json.JSONDecodeError, IOError):
            # Skip malformed results files
            continue
    
    return RunListResponse(runs=runs)

@router.delete("/{run_id}")
async def delete_run(run_id: str) -> dict:
    """Delete a run and its associated directory."""
    runs_dir = get_runs_dir()
    run_dir = runs_dir / run_id
    
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    
    shutil.rmtree(run_dir)
    return {"message": f"Run '{run_id}' deleted successfully"}

@router.get("/{run_id}", response_model=RunSummaryResponse)
async def get_run_summary(run_id: str) -> RunSummaryResponse:
    """Get a summary of a specific run."""
    data = load_results_json(run_id)
    
    pipeline_data = data.get("pipeline", {})
    tasks_data = data.get("tasks", {})
    warnings_data = data.get("warnings", [])
    errors_data = data.get("critical_errors", [])
    
    return RunSummaryResponse(
        run_id=run_id,
        pipeline_name=pipeline_data.get("name", ""),
        status=pipeline_data.get("status", "unknown"),
        started_at=pipeline_data.get("started_at"),
        finished_at=pipeline_data.get("finished_at"),
        input_kind=pipeline_data.get("input_kind"),
        task_count=len(tasks_data),
        warning_count=len(warnings_data),
        error_count=len(errors_data),
    )


logger = logging.getLogger(__name__)


def _parse_iso_datetime(dt_str: str) -> datetime:
    """Parse ISO 8601 datetime string, handling various formats."""
    # Try common formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unable to parse datetime: {dt_str}")


@router.get("/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(run_id: str, since: Optional[str] = None) -> RunStatusResponse:
    """Get full run status including pipeline, tasks, warnings, errors, and events.
    
    Args:
        run_id: The run identifier
        since: Optional ISO 8601 timestamp to filter events/warnings/errors. Only items
               with timestamp >= since will be returned. Invalid timestamps are ignored.
    """
    data = load_results_json(run_id)
    
    # Parse since parameter if provided
    since_dt = None
    if since:
        try:
            since_dt = _parse_iso_datetime(since)
        except ValueError as e:
            logger.warning(f"Invalid 'since' parameter '{since}': {e}")
            # Ignore invalid since parameter
    
    # Build pipeline status
    pipeline_data = data.get("pipeline", {})
    pipeline = PipelineStatusResponse(
        run_id=run_id,
        pipeline_name=pipeline_data.get("name", ""),
        status=pipeline_data.get("status", "created"),
        started_at=pipeline_data.get("started_at"),
        finished_at=pipeline_data.get("finished_at"),
        input_kind=pipeline_data.get("input_kind"),
        input_files=pipeline_data.get("input_files"),
        metadata=pipeline_data.get("metadata", {}),
    )
    
    # Build task list (always return all tasks)
    tasks_data = data.get("tasks", {})
    tasks = []
    for task_id, task_info in tasks_data.items():
        tasks.append(TaskInfo(
            task_id=task_id,
            name=task_info.get("name", ""),
            status=task_info.get("status", "pending"),
            started_at=task_info.get("started_at"),
            finished_at=task_info.get("finished_at"),
            summary=task_info.get("summary", {}),
            artifacts=task_info.get("artifacts", []),
        ))
    
    # Build warnings list (filter by since if provided)
    warnings_data = data.get("warnings", [])
    warnings = []
    for w in warnings_data:
        if since_dt:
            recorded_at = w.get("recorded_at")
            if recorded_at:
                try:
                    w_dt = _parse_iso_datetime(recorded_at)
                    if w_dt < since_dt:
                        continue
                except ValueError:
                    pass  # Include items with unparseable timestamps
        warnings.append(WarningItem(
            code=w.get("code", ""),
            message=w.get("message", ""),
            step_id=w.get("step_id"),
            details=w.get("details", {}),
            recorded_at=w.get("recorded_at"),
        ))
    
    # Build errors list (filter by since if provided)
    errors_data = data.get("critical_errors", [])
    errors = []
    for e in errors_data:
        if since_dt:
            recorded_at = e.get("recorded_at")
            if recorded_at:
                try:
                    e_dt = _parse_iso_datetime(recorded_at)
                    if e_dt < since_dt:
                        continue
                except ValueError:
                    pass  # Include items with unparseable timestamps
        errors.append(ErrorItem(
            code=e.get("code", ""),
            message=e.get("message", ""),
            step_id=e.get("step_id"),
            details=e.get("details", {}),
            critical=e.get("critical", False),
            exception_type=e.get("exception_type"),
            recorded_at=e.get("recorded_at"),
        ))
    
    # Build events list (filter by since if provided)
    events_data = data.get("events", [])
    events = []
    for e in events_data:
        if since_dt:
            timestamp = e.get("timestamp")
            if timestamp:
                try:
                    e_dt = _parse_iso_datetime(timestamp)
                    if e_dt < since_dt:
                        continue
                except ValueError:
                    pass  # Include items with unparseable timestamps
        events.append(EventItem(
            kind=e.get("kind", ""),
            timestamp=e.get("timestamp", ""),
            level=e.get("level"),
            message=e.get("message"),
            task_id=e.get("task_id"),
        ))
    
    # Get updated_at from results.json
    updated_at = data.get("updated_at")
    if not updated_at:
        # Fallback to pipeline finished_at or started_at
        updated_at = pipeline_data.get("finished_at") or pipeline_data.get("started_at")
    
    return RunStatusResponse(
        run_id=run_id,
        pipeline=pipeline,
        tasks=tasks,
        warnings=warnings,
        critical_errors=errors,
        events=events,
        updated_at=updated_at,
    )




@router.post("/{run_id}/cancel", response_model=CancelRunResponse)
async def cancel_run(run_id: str) -> CancelRunResponse:
    """Cancel a running or queued run.
    
    Revokes the Celery task and sets pipeline status to "cancelled".
    
    Args:
        run_id: The run identifier
        
    Returns:
        CancelRunResponse with run_id and status
        
    Raises:
        HTTPException: 404 if run not found, 400 if run is already finished
    """
    from src_new.celery_app import celery
    from src_new.results.results_manager import ResultsManager
    
    # Verify run exists by loading results.json
    data = load_results_json(run_id)
    
    # Check current pipeline status
    pipeline_data = data.get("pipeline", {})
    current_status = pipeline_data.get("status", "unknown")
    
    # Cannot cancel if already in a terminal state
    terminal_states = {"success", "failed", "cancelled"}
    if current_status in terminal_states:
        raise HTTPException(
            status_code=400,
            detail=f"Run is already in terminal state: {current_status}"
        )
    
    # Get Celery task result and revoke if running/pending
    result = celery.AsyncResult(run_id)
    if result.status in {"PENDING", "STARTED", "RETRY"}:
        from celery.exceptions import SoftTimeLimitExceeded, TimeLimitExceeded
        result.revoke(terminate=True)
    
    # Update results.json to mark as cancelled
    results_manager = ResultsManager(str(get_runs_dir() / run_id / "results.json"))
    results_manager.finish_run("cancelled")
    
    return CancelRunResponse(run_id=run_id, status="cancelled")


@router.get("/{run_id}/loading", response_model=LoadingInfoResponse)
async def get_loading_info(run_id: str) -> LoadingInfoResponse:
    """Get loading information including strategy, attempts, and topology files."""
    data = load_results_json(run_id)
    
    # Get loading data from data.loading.*
    loading_data = data.get("data", {}).get("loading", {})
    
    # Get input kind from pipeline metadata
    pipeline_data = data.get("pipeline", {})
    input_kind = pipeline_data.get("input_kind")
    
    # Get topology files from input decision if available
    input_decision = loading_data.get("decision", {})
    topology_files = []
    if "topology_files" in input_decision:
        topology_files = input_decision["topology_files"]
    elif "bundle" in loading_data:
        bundle = loading_data.get("bundle", {})
        topology_files = bundle.get("topology_files", [])
    
    # Get attempts
    attempts_data = loading_data.get("attempts", [])
    attempts = [
        LoadingAttemptInfo(
            strategy=a.get("strategy", ""),
            success=a.get("success", False),
            error=a.get("error"),
        )
        for a in attempts_data
    ]
    
    # Get final strategy and success
    final_strategy = loading_data.get("final_strategy")
    success = loading_data.get("success", False)
    
    # Get selected strategy (first successful or final)
    selected_strategy = final_strategy
    if not selected_strategy and attempts:
        for a in attempts:
            if a.success:
                selected_strategy = a.strategy
                break
    
    # Get warnings
    warnings = loading_data.get("warnings", [])
    
    return LoadingInfoResponse(
        run_id=run_id,
        input_kind=input_kind,
        selected_strategy=selected_strategy,
        topology_files=topology_files,
        attempts=attempts,
        final_strategy=final_strategy,
        success=success,
        warnings=warnings,
    )


@router.get("/{run_id}/molecules", response_model=MoleculeSummaryResponse)
async def get_molecules(run_id: str) -> MoleculeSummaryResponse:
    """Get molecule summary including unique molecules and type counts."""
    data = load_results_json(run_id)
    
    # Get fragments data from data.fragments.*
    fragments_data = data.get("data", {}).get("fragments", {})
    
    # Get universe segments for metadata
    universe_data = data.get("data", {}).get("universe", {})
    segments_universe = universe_data.get("segments", {})
    
    # Get verification data for confidence calculation
    verification_data = data.get("data", {}).get("verification", {})
    
    # Build unique molecules dict
    unique_molecules = {}
    for key, mol_info in fragments_data.get("unique", {}).items():
        unique_molecules[key] = MoleculeInstanceInfo(
            segment_ids=mol_info.get("segment_ids", []),
            molecule_type=mol_info.get("molecule_type"),
            atom_count=mol_info.get("atom_count", 0),
            residue_count=mol_info.get("residue_count", 0),
            smiles=mol_info.get("smiles"),
        )
    
    # Get type counts
    type_counts = fragments_data.get("type_counts", {})
    
    # Get total fragment count
    total_fragment_count = fragments_data.get("total_count", 0)
    
    # Get segments list — try fragments/segments list first, then universe/segment_list
    segments = []
    fragments_segments = fragments_data.get("segments", [])
    if fragments_segments:
        segments = [s.get("segment") for s in fragments_segments if s.get("segment")]
    if not segments:
        segments = list(universe_data.get("segment_list", []))
    
    # Build segment metadata from universe.segments.{segment}.properties
    # Use fragments/segments data as primary source for molecule type
    segment_meta = {}
    for seg_name in segments:
        seg_props = {}
        # Look up segment in fragments/segments first for type
        seg_from_fragments = next(
            (s for s in fragments_segments if s.get("segment") == seg_name), {}
        )
        mol_type_fragments = seg_from_fragments.get("type", "")
        
        if seg_name in segments_universe:
            props = segments_universe[seg_name].get("properties", {})
            # Determine type: fragments data is primary source
            if mol_type_fragments:
                seg_props["type"] = mol_type_fragments
            elif props.get("is_protein", False):
                seg_props["type"] = "protein"
            elif props.get("is_nucleic", False):
                seg_props["type"] = "nucleic"
            else:
                seg_props["type"] = "unknown"
            seg_props["atom_count"] = props.get("atom_count_fragment", props.get("atom_count_total", 0))
            seg_props["residue_count"] = props.get("residue_count", 0)
        else:
            # Fallback: use fragments.segments data
            if seg_from_fragments:
                seg_props["type"] = mol_type_fragments if mol_type_fragments else "unknown"
                seg_props["atom_count"] = seg_from_fragments.get("atoms_per_copy", 0)
                seg_props["residue_count"] = seg_from_fragments.get("residue_count", 0)
            else:
                seg_props["type"] = "unknown"
                seg_props["atom_count"] = 0
                seg_props["residue_count"] = 0
        segment_meta[seg_name] = seg_props
    
    return MoleculeSummaryResponse(
        run_id=run_id,
        unique_molecules=unique_molecules,
        type_counts=type_counts,
        total_fragment_count=total_fragment_count,
        segments=segments,
        segment_meta=segment_meta,
    )


@router.get("/{run_id}/molecules/{segment}/info", response_model=MoleculeInfoResponse)
async def get_molecule_info(run_id: str, segment: str) -> MoleculeInfoResponse:
    """Get detailed info for a specific molecule segment."""
    data = load_results_json(run_id)
    
    # Get universe segments for metadata
    universe_data = data.get("data", {}).get("universe", {})
    segments_universe = universe_data.get("segments", {})
    
    # Get verification data for confidence
    verification_data = data.get("data", {}).get("verification", {})
    
    # Get fragments data
    fragments_data = data.get("data", {}).get("fragments", {})
    
    # Check if segment exists
    fragments_segments = fragments_data.get("segments", [])
    fragment_segment_names = [s.get("segment") for s in fragments_segments if s.get("segment")]
    if segment not in segments_universe and segment not in fragment_segment_names:
        raise HTTPException(status_code=404, detail=f"Segment '{segment}' not found")
    
    # Get segment properties
    props = {}
    if segment in segments_universe:
        props = segments_universe[segment].get("properties", {})
    else:
        seg_from_fragments = next(
            (s for s in fragments_segments if s.get("segment") == segment), {}
        )
        props = seg_from_fragments
    
    # Determine type from fragments/segments data as primary source
    seg_from_fragments = next(
        (s for s in fragments_segments if s.get("segment") == segment), {}
    )
    mol_type_fragments = seg_from_fragments.get("type", "")
    
    if mol_type_fragments:
        seg_type = mol_type_fragments
    elif props.get("is_protein", False):
        seg_type = "protein"
    elif props.get("is_nucleic", False):
        seg_type = "nucleic"
    else:
        seg_type = "unknown"
    
    if segment in segments_universe:
        atom_count = props.get("atom_count_fragment", props.get("atom_count_total", 0))
        residue_count = props.get("residue_count", 0)
    else:
        atom_count = props.get("atoms_per_copy", 0)
        residue_count = props.get("residue_count", 0)
    
    # Calculate confidence from verification data
    confidence = None
    if segment in verification_data:
        verified_hits = verification_data[segment].get("verified_hits", [])
        if verified_hits:
            # Get highest final_confidence among verified hits
            confidences = [h.get("final_confidence") for h in verified_hits if h.get("final_confidence") is not None]
            if confidences:
                confidence = max(confidences)
    
    # Name is the segment id itself
    name = segment
    
    return MoleculeInfoResponse(
        segment=segment,
        name=name,
        type=seg_type,
        atom_count=atom_count,
        residue_count=residue_count,
        confidence=confidence,
    )


@router.get("/{run_id}/render", response_model=RenderPathsResponse)
async def get_render_paths(run_id: str) -> RenderPathsResponse:
    """Get render paths for system and segment mmCIF files."""
    data = load_results_json(run_id)
    
    # Get render data from data.render.*
    render_data = data.get("data", {}).get("render", {})
    
    system_mmcif = render_data.get("system_mmcif")
    
    # Relativize system_mmcif if it's an absolute path under runs_dir
    if system_mmcif:
        runs_dir = get_runs_dir()
        run_dir = runs_dir / run_id
        if Path(system_mmcif).is_absolute() and str(system_mmcif).startswith(str(runs_dir)):
            # Make path relative to run directory
            system_mmcif = str(Path(system_mmcif).relative_to(run_dir))
    
    # Get segment paths
    segments_data = render_data.get("segments", {})
    segments = {}
    for segment_name, segment_info in segments_data.items():
        if isinstance(segment_info, dict):
            mmcif_path = segment_info.get("mmcif")
        else:
            mmcif_path = segment_info
        if mmcif_path:
            # Relativize segment mmcif_path if it's an absolute path under runs_dir
            runs_dir = get_runs_dir()
            run_dir = runs_dir / run_id
            if Path(mmcif_path).is_absolute() and str(mmcif_path).startswith(str(runs_dir)):
                mmcif_path = str(Path(mmcif_path).relative_to(run_dir))
            segments[segment_name] = mmcif_path
    
    return RenderPathsResponse(
        run_id=run_id,
        system_mmcif=system_mmcif,
        segments=segments,
    )


@router.get("/{run_id}/signatures", response_model=SignaturesResponse)
async def get_signatures(run_id: str, segment: Optional[str] = None) -> SignaturesResponse:
    """Get signatures for all segments or a specific segment."""
    data = load_results_json(run_id)
    
    # Get signatures data from data.signatures.*
    signatures_data = data.get("data", {}).get("signatures", {})
    
    # Filter by segment if provided
    if segment is not None:
        signatures_data = {segment: signatures_data.get(segment, {})} if segment in signatures_data else {}
    
    # Flatten signatures into a list
    signatures = []
    attempted_generators = {}
    
    for seg_name, seg_data in signatures_data.items():
        # Get attempted generators
        attempted = seg_data.get("attempted", [])
        if attempted:
            attempted_generators[seg_name] = attempted
        
        # Get generated signatures
        generated = seg_data.get("generated", {})
        for generator_name, sig_value in generated.items():
            signatures.append(SignatureInfo(
                segment=seg_name,
                generator=generator_name,
                signature=sig_value,
            ))
    
    return SignaturesResponse(
        run_id=run_id,
        signatures=signatures,
        attempted_generators=attempted_generators,
    )


@router.get("/{run_id}/identifiers", response_model=IdentifiersResponse)
async def get_identifiers(run_id: str, segment: Optional[str] = None) -> IdentifiersResponse:
    """Get identifier hits for all segments or a specific segment."""
    data = load_results_json(run_id)
    
    # Get identifiers data from data.identifiers.*
    identifiers_data = data.get("data", {}).get("identifiers", {})
    
    # Filter by segment if provided
    if segment is not None:
        identifiers_data = {segment: identifiers_data.get(segment, {})} if segment in identifiers_data else {}
    
    # Traverse nested structure: data.identifiers.{segment}.{generator}.{resolver}
    all_hits = []
    all_attempted_resolvers = set()
    primary_segment = ""
    seen_keys = set()  # For deduplication by (identifier, ident_type, resolver_name)
    
    for seg_name, seg_data in identifiers_data.items():
        if not primary_segment:
            primary_segment = seg_name
        
        # Collect attempted resolvers from all generators
        seg_attempted = set()
        for generator_name, generator_data in seg_data.items():
            if generator_name == "attempted":
                continue  # Skip top-level "attempted" if present
            if isinstance(generator_data, dict):
                gen_attempted = generator_data.get("attempted", [])
                if isinstance(gen_attempted, list):
                    seg_attempted.update(gen_attempted)
        all_attempted_resolvers.update(seg_attempted)
        
        # Walk generators and resolvers
        for generator_name, generator_data in seg_data.items():
            if generator_name == "attempted":
                continue  # Skip top-level "attempted"
            if not isinstance(generator_data, dict):
                continue
            
            # Walk resolvers within this generator
            for resolver_name, resolver_data in generator_data.items():
                if resolver_name == "attempted":
                    continue  # Skip "attempted" keys
                if not isinstance(resolver_data, dict):
                    continue
                
                hits_raw = resolver_data.get("hits", [])
                ident_type = resolver_data.get("ident_type", "")
                hit_type_label = resolver_data.get("hit_type", "exact")
                
                if not isinstance(hits_raw, list):
                    continue
                
                for hit in hits_raw:
                    # Handle both string and tuple/list formats
                    if isinstance(hit, str):
                        identifier = hit
                        score = None
                    elif isinstance(hit, (list, tuple)) and len(hit) >= 2:
                        identifier = str(hit[0])
                        try:
                            score = float(hit[1])
                        except (TypeError, ValueError):
                            score = None
                    else:
                        continue
                    
                    # Build database URL
                    db_url = build_database_url(identifier, ident_type)
                    
                    # Look up metadata from hits_metadata
                    metadata = {}
                    hits_metadata = resolver_data.get("hits_metadata", {})
                    if isinstance(hits_metadata, dict):
                        metadata = hits_metadata.get(identifier, {})
                    
                    # Extract metadata fields
                    evalue = metadata.get("evalue")
                    bit_score = metadata.get("bit_score")
                    identity_percent = None
                    if metadata.get("identity_p") is not None:
                        identity_percent = metadata.get("identity_p") * 100.0
                    coverage_percent = None
                    if metadata.get("coverage_p") is not None:
                        coverage_percent = metadata.get("coverage_p") * 100.0
                    
                    # Deduplicate by (identifier, ident_type, resolver_name)
                    dedup_key = (identifier, ident_type, resolver_name)
                    if dedup_key in seen_keys:
                        continue
                    seen_keys.add(dedup_key)
                    
                    all_hits.append(IdentifierHit(
                        identifier=identifier,
                        ident_type=ident_type,
                        hit_type=hit_type_label,
                        resolver_name=resolver_name,
                        segment=seg_name,
                        score=score,
                        database_url=db_url,
                        evalue=evalue,
                        bit_score=bit_score,
                        identity_percent=identity_percent,
                        coverage_percent=coverage_percent,
                    ))
    
    # Parse failed_resolvers from warnings
    failed_resolvers_set = set()  # For deduplication by (resolver_name, generator, message)
    failed_resolvers = []
    warnings = data.get("warnings", [])
    for warning in warnings:
        if warning.get("code") == "identifier_resolver_failed":
            message = warning.get("message", "")
            # Parse message of the form "{resolver_name} ({generator_name}): {error}"
            match = re.match(r"^([^()]+)\s*\(([^)]+)\):\s*(.+)$", message)
            if match:
                resolver_name = match.group(1).strip()
                generator = match.group(2).strip()
                error_msg = match.group(3).strip()
                dedup_key = (resolver_name, generator, error_msg)
                if dedup_key not in failed_resolvers_set:
                    failed_resolvers_set.add(dedup_key)
                    failed_resolvers.append(ResolverErrorItem(
                        resolver_name=resolver_name,
                        generator=generator,
                        message=error_msg,
                    ))
    
    # Use first segment name or "unknown"
    seg = primary_segment or "unknown"
    
    return IdentifiersResponse(
        run_id=run_id,
        segment=seg,
        hits=all_hits,
        attempted_resolvers=list(all_attempted_resolvers),
        failed_resolvers=failed_resolvers,
    )


@router.get("/{run_id}/verification", response_model=VerificationResponse)
async def get_verification(run_id: str, segment: Optional[str] = None) -> VerificationResponse:
    """Get verification results for all segments or a specific segment."""
    data = load_results_json(run_id)
    
    # Get verification data from data.verification.*
    verification_data = data.get("data", {}).get("verification", {})
    
    # Filter by segment if provided
    if segment is not None:
        verification_data = {segment: verification_data.get(segment, {})} if segment in verification_data else {}
    
    # For now, return data for the first segment or aggregate all
    all_hits = []
    primary_segment = ""
    
    for seg_name, seg_data in verification_data.items():
        if not primary_segment:
            primary_segment = seg_name
        
        # Get verified hits
        verified_hits = seg_data.get("verified_hits", [])
        for hit in verified_hits:
            identifier = hit.get("identifier", "")
            ident_type = hit.get("ident_type", "")
            db_url = build_database_url(identifier, ident_type)
            all_hits.append(VerifiedHitItem(
                identifier=identifier,
                ident_type=ident_type,
                database=hit.get("database", ""),
                resolver_score=hit.get("resolver_score"),
                similarity_score=hit.get("similarity_score"),
                annotation_quality_score=hit.get("annotation_quality_score"),
                final_confidence=hit.get("final_confidence", 0.0),
                is_verified=hit.get("is_verified", False),
                rejection_reason=hit.get("rejection_reason"),
                supporting_evidence_count=hit.get("supporting_evidence_count", 0),
                database_url=db_url,
            ))
    
    # Use first segment name or "unknown"
    seg = primary_segment or "unknown"
    
    return VerificationResponse(
        run_id=run_id,
        segment=seg,
        hits=all_hits,
    )


@router.get("/{run_id}/logs")
async def get_run_logs(run_id: str, type: str = "normal") -> PlainTextResponse:
    """Get raw log text for a run. type is 'normal' or 'debug'."""
    runs_dir = get_runs_dir()
    results_path = runs_dir / run_id / "results.json"
    
    # Verify run exists
    if not results_path.exists():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    
    # Determine log file
    if type == "debug":
        log_file = runs_dir / run_id / "results.debug.log"
    else:
        log_file = runs_dir / run_id / "results.log"
    
    # Read log file
    if not log_file.exists():
        return PlainTextResponse("Logs not available yet.")
    
    with open(log_file, "r", encoding="utf-8") as f:
        contents = f.read()
    
    return PlainTextResponse(contents)


@router.get("/{run_id}/files", response_model=RunFilesResponse)
async def get_run_files(run_id: str) -> RunFilesResponse:
    """Get all files in a run directory (recursive), excluding hidden files."""
    
    
    run_dir = get_runs_dir() / run_id
    
    if not run_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    
    files = []
    for f in run_dir.rglob('*'):
        if f.is_file() and not f.name.startswith('.'):
            files.append(str(f.relative_to(run_dir)))
    
    return RunFilesResponse(run_id=run_id, files=sorted(files))


def _extract_pdb_signature(
    data: Dict[str, Any],
    signature_key: str,
    segment: Optional[str] = None,
) -> str:
    """
    Extract a PDB signature from results data.
    
    Args:
        data: Results JSON data
        signature_key: Key for the signature type (e.g., 'topology_less_pdb', 'ca_only_pdb')
        segment: Optional segment name to filter by
    
    Returns:
        The PDB signature string
    
    Raises:
        HTTPException: 404 if no signatures found, 400 if multiple segments and no segment specified
    """
    signatures_data = data.get("data", {}).get("signatures", {})
    
    # Find segments with the requested signature type
    matching_segments = {}
    for seg_name, seg_data in signatures_data.items():
        generated = seg_data.get("generated", {})
        if signature_key in generated:
            matching_segments[seg_name] = generated[signature_key]
    
    if not matching_segments:
        raise HTTPException(
            status_code=404,
            detail=f"No {signature_key.replace('_', '-')} signatures found for this run"
        )
    
    # If segment is specified, return that one
    if segment is not None:
        if segment not in matching_segments:
            raise HTTPException(
                status_code=404,
                detail=f"Segment '{segment}' not found or has no {signature_key.replace('_', '-')} signature"
            )
        return matching_segments[segment]
    
    # If only one segment, return it
    if len(matching_segments) == 1:
        return next(iter(matching_segments.values()))
    
    # Multiple segments and no segment specified
    raise HTTPException(
        status_code=400,
        detail=f"Multiple segments found ({', '.join(sorted(matching_segments.keys()))}), specify segment parameter"
    )


@router.get("/{run_id}/download/topology-less-pdb")
async def download_topology_less_pdb(
    run_id: str,
    segment: Optional[str] = None,
) -> PlainTextResponse:
    """
    Download topology-less PDB signature(s) for a run.
    
    Args:
        run_id: The run identifier
        segment: Optional segment name. Required if multiple segments exist.
    
    Returns:
        Plain text PDB content with media_type='chemical/x-pdb'
    
    Raises:
        404: If run not found or no topology-less PDB signatures exist
        400: If multiple segments exist and segment parameter not specified
    """
    data = load_results_json(run_id)
    
    pdb_content = _extract_pdb_signature(data, "topology_less_pdb", segment)
    
    return PlainTextResponse(pdb_content, media_type="chemical/x-pdb")


@router.get("/{run_id}/download/ca-only-pdb")
async def download_ca_only_pdb(
    run_id: str,
    segment: Optional[str] = None,
) -> PlainTextResponse:
    """
    Download CA-only PDB signature(s) for a run.
    
    Args:
        run_id: The run identifier
        segment: Optional segment name. Required if multiple segments exist.
    
    Returns:
        Plain text PDB content with media_type='chemical/x-pdb'
    
    Raises:
        404: If run not found or no CA-only PDB signatures exist
        400: If multiple segments exist and segment parameter not specified
    """
    data = load_results_json(run_id)
    
    pdb_content = _extract_pdb_signature(data, "ca_only_pdb", segment)
    
    return PlainTextResponse(pdb_content, media_type="chemical/x-pdb")


@router.post("/rerun-all", response_model=RerunAllResponse)
async def rerun_all() -> RerunAllResponse:
    """
    Re-run all existing runs by copying their input files and config into new run directories.
    
    For each existing run:
    - Copies input files from old run to new run directory
    - Copies config.ini if it exists, otherwise uses default config
    - Creates a new results.json with queued status
    - Enqueues a new Celery pipeline task
    
    Old runs are not modified or deleted.
    
    Returns:
        RerunAllResponse with list of new runs, skipped runs, and count
    """
    from src_new.config.loader import RunConfig
    
    runs_dir = get_runs_dir()
    new_runs: List[RerunRunItem] = []
    skipped: List[str] = []
    
    if not runs_dir.exists():
        return RerunAllResponse(new_runs=[], skipped=[], count=0)
    
    for entry in runs_dir.iterdir():
        if not entry.is_dir():
            continue
        
        old_run_id = entry.name
        old_results_path = entry / "results.json"
        old_input_dir = entry / "input"
        old_config_path = entry / "config.ini"
        
        # Skip if results.json doesn't exist
        if not old_results_path.exists():
            skipped.append(old_run_id)
            continue
        
        # Skip if input directory doesn't exist or is empty
        if not old_input_dir.exists() or not any(old_input_dir.iterdir()):
            skipped.append(old_run_id)
            continue
        
        # Read old results to get run_name
        try:
            with open(old_results_path, "r", encoding="utf-8") as f:
                old_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            skipped.append(old_run_id)
            continue
        
        old_run_name = old_data.get("pipeline", {}).get("run_name")
        
        # Generate new run ID
        new_run_id = str(uuid.uuid4())
        new_run_dir = runs_dir / new_run_id
        new_input_dir = new_run_dir / "input"
        
        # Create new run directory structure
        new_input_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy input files
        for file in old_input_dir.iterdir():
            if file.is_file():
                shutil.copy2(str(file), str(new_input_dir / file.name))
        
        # Handle config: copy old or write default
        new_config_path = new_run_dir / "config.ini"
        if old_config_path.exists():
            shutil.copy2(str(old_config_path), str(new_config_path))
        else:
            config = RunConfig.from_default_ini()
            config.to_ini_path(new_config_path)
        
        # Write new results.json
        new_results_path = new_run_dir / "results.json"
        initial_results = {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "pipeline": {
                "name": "BAT3",
                "status": "queued",
                "run_id": new_run_id,
            },
        }
        if old_run_name:
            initial_results["pipeline"]["run_name"] = f"{old_run_name} (re-run)"
        
        with open(new_results_path, "w", encoding="utf-8") as f:
            json.dump(initial_results, f, indent=2)
        
        # Enqueue Celery task with run_id as task_id
        run_pipeline_task.apply_async(
            task_id=new_run_id,
            kwargs={
                "run_id": new_run_id,
                "input_dir": str(new_input_dir),
                "results_path": str(new_results_path),
                "config_path": str(new_config_path),
            },
        )
        
        new_runs.append(RerunRunItem(
            new_run_id=new_run_id,
            old_run_id=old_run_id,
            status="queued",
        ))
    
    return RerunAllResponse(new_runs=new_runs, skipped=skipped, count=len(new_runs))
