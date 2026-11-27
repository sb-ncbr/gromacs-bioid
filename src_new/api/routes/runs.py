"""Router for run-related endpoints."""

from __future__ import annotations
import errno
import functools
import ipaddress
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

from fastapi import APIRouter, Body, File, Form, Header, HTTPException, Request, UploadFile, Query
from fastapi.responses import PlainTextResponse
import csv
import io

from ..models import (
    RerunAllResponse,
    RerunRunItem,
    CancelRunResponse,
    RunFilesResponse,
    PipelineStatusResponse,
    RunStatusResponse,
    RetentionChange,
    ReportCreate,
    RetentionInfo,
    IncompleteItem,
    RetryInfo,
    AttemptInfo,
    RestartInfo,
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
    RenderSegmentSelector,
    ExampleRun,
    ExamplesResponse,
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
    RunQueueResponse,
    RunStageProgress,
    RunSummaryResponse,
)
from ..hit_names import hit_display_name
from ..names import chain_of, segment_display_name, segment_resname, strip_seg
from ..utils import build_database_url, normalize_identifier
from src_new.identification.outcomes import user_warnings
from ..warning_docs import docs_url
from ..tasks import run_pipeline_task
from ..security import (
    MAX_FILES, OWNER_HEADER, RunId, allowed_upload, check_submit_limits, ip_hash,
    new_owner_token, require_owner, run_dir as safe_run_dir, same_submitter,
)

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


@router.get("/config/options", response_model=dict)
async def get_config_options():
    """What a run may change: the tunable fields with their server defaults,
    and the presets (overrides on top of those defaults)."""
    from src_new.config.loader import RunConfig
    from src_new.config.presets import PRESETS, tunable_config
    return {"config": tunable_config(RunConfig.from_default_ini()), "presets": PRESETS}


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


#: GitHub #24: proxies whose X-Forwarded-For entries are believed — the
#: cluster's pod (ingress controller, MCP server) and service ranges and
#: loopback. BAT3_TRUSTED_PROXIES (comma-separated CIDRs) overrides.
_DEFAULT_TRUSTED_PROXIES = "10.42.0.0/16,10.43.0.0/16,127.0.0.0/8,::1/128"


@functools.lru_cache(maxsize=4)
def _trusted_networks(spec: str):
    nets = []
    for part in spec.split(","):
        part = part.strip()
        if part:
            try:
                nets.append(ipaddress.ip_network(part, strict=False))
            except ValueError:
                logger.warning("BAT3_TRUSTED_PROXIES: ignoring %r", part)
    return tuple(nets)


def _is_trusted_proxy(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    nets = _trusted_networks(os.environ.get("BAT3_TRUSTED_PROXIES", _DEFAULT_TRUSTED_PROXIES))
    return any(ip.version == n.version and ip in n for n in nets)


def _requester_ip(request: Request) -> Optional[str]:
    """Return the requester's IP address.

    GitHub #24: X-Forwarded-For is believed only as far as trusted proxies
    wrote it. The chain (header hops + the direct peer) is walked from the
    right; the first address that is not a trusted proxy is the requester. A
    client-supplied left-most value (any string) no longer picks the identity
    behind submission limits, attribution and the admin login throttle. An
    untrusted direct peer is the requester regardless of the header; a chain
    of trusted hops only (an in-cluster client) gives its origin. Returns
    ``None`` when no client information is available.
    """
    peer = request.client.host if request.client and request.client.host else None
    if peer is None:
        return None
    if not _is_trusted_proxy(peer):
        return peer
    xff = request.headers.get("x-forwarded-for") or ""
    hops = [h.strip() for h in xff.split(",") if h.strip()] + [peer]
    for hop in reversed(hops):
        if not _is_trusted_proxy(hop):
            return hop
    return hops[0]


def _campaign_input_dir(rel: str) -> Path:
    """A repository-campaign input directory, confined to
    BAT3_CAMPAIGN_INPUT_ROOT (symlinks resolved before the check)."""
    root = Path(os.environ.get("BAT3_CAMPAIGN_INPUT_ROOT", "/data/validation")).resolve()
    rel_path = Path(rel)
    if rel_path.is_absolute() or ".." in rel_path.parts or not rel_path.parts:
        raise HTTPException(status_code=422, detail="campaign_input must be a relative path")
    src = (root / rel_path).resolve()
    if not src.is_relative_to(root) or not src.is_dir():
        raise HTTPException(status_code=422, detail=f"No campaign input directory {rel!r}")
    if not any(p.is_file() for p in src.iterdir()):
        raise HTTPException(status_code=422, detail=f"Campaign input {rel!r} has no files")
    return src


def _link_campaign_input(src: Path, input_dir: Path) -> None:
    """Link the campaign files into the run's own input directory: they are
    read in place, while anything the run writes (unpacked archives) stays
    in the run directory, and deleting the run removes only the links."""
    for entry in sorted(src.iterdir()):
        if entry.name.startswith(".") or not entry.is_file():
            continue
        (input_dir / entry.name).symlink_to(entry)


def load_results_json(run_id: str) -> Dict[str, Any]:
    """Load results.json for a given run_id."""
    results_path = safe_run_dir(get_runs_dir(), run_id) / "results.json"
    
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


def _input_check(input_dir: Path) -> tuple[Optional[str], Optional[str]]:
    """(refusal, note) for the uploaded files, by the worker's own loader rules.

    Refused only when no loading strategy the worker would try can use the
    files (the loader tries every strategy for an unrecognised set, so
    "unrecognised" is not "unloadable"): a trajectory without a topology, an
    archive alone. When the only usable strategy is the topology-free .gro
    fallback, the run is accepted with a note that it will likely be
    incomplete (2026-11-17).
    """
    from src_new.input.discovery import inspect_directory, select_best_file_combination
    from src_new.loader.strategies import LoadStrategy, get_fallback_strategies, validate_for_strategy
    try:
        bundle = inspect_directory(input_dir)
        decision = select_best_file_combination(bundle)
        usable = [s for s in get_fallback_strategies(decision, bundle) if validate_for_strategy(bundle, s).ok]
    except Exception as exc:  # the worker decides; never refuse on a checker error
        logger.warning("input pre-check failed (%s); run accepted", exc)
        return None, None
    if usable and all(s == LoadStrategy.GROMACS_GRO for s in usable):
        return None, ("Only coordinates without a topology (.gro): BioID will guess molecules and bonds, "
                      "so identification will likely be incomplete. Upload the .top (and .itp) or .tpr "
                      "with it for reliable results.")
    if usable and all(s == LoadStrategy.TOPOLOGY_ONLY for s in usable):
        # dm1 audit (L2): accepted, the missing coordinates stated
        return None, ("Only a topology without coordinates: BioID identifies the molecules from the "
                      "topology (sequences, chemistry), but structure searches and stereochemistry are "
                      "skipped. Upload the coordinates (.gro, .pdb, .rst7, .crd, ...) with it for full results.")
    if usable:
        return None, None
    names = sorted(p.name for p in input_dir.iterdir())
    return ("BioID could not find a complete simulation in these files ("
            + ", ".join(names[:10]) + (", …" if len(names) > 10 else "") + "). "
            "Upload a topology together with coordinates, e.g. .tpr (+ .gro), .gro + .top (+ .itp), "
            ".prmtop + .inpcrd/.rst7/.nc/.dcd, .psf + .pdb/.crd/.dcd/.coor/.xtc, a LAMMPS .data file, "
            "a Desmond .cms, or a single .pdb, .gro or .cif (also inside a .zip or .tar.gz)."), None


@router.post("", response_model=RunCreateResponse)
async def create_run(
    request: Request,
    files: Optional[List[UploadFile]] = File(None),
    config_file: Optional[UploadFile] = None,
    config_json: Optional[str] = Form(None),
    run_id: Optional[str] = None,
    run_name: Optional[str] = Form(None),
    preset: Optional[str] = Form(None),
    retention: Optional[str] = Form(None),
    queue: Optional[str] = Form(None),
    campaign_input: Optional[str] = Form(None),
    queue_token: Optional[str] = Header(None, alias="X-Queue-Token"),
) -> RunCreateResponse:
    """
    Create a new run by uploading input files and optionally a config file.

    ``preset`` (see GET /runs/config/options) is applied first, then
    ``config_file`` or ``config_json``; only per-run tunable fields may change.

    ``queue``: "web" (default) or "repository" (campaigns: own workers and
    automatic retries; needs the X-Queue-Token header, issued on the admin page).

    ``campaign_input`` (repository queue only): instead of uploads, a
    directory relative to BAT3_CAMPAIGN_INPUT_ROOT (/data/validation), e.g.
    ``1234/input``; its files are linked into the run's input directory and
    read in place, as the g1 campaign did.
    
    The pipeline runs in the background via Celery. Returns immediately with run status.
    """
    from src_new import retries
    from .. import queue_tokens
    lane = queue or "web"
    if lane not in retries.LANES:
        raise HTTPException(status_code=422, detail=f"Unknown queue {lane!r}: web or repository")
    if lane != "web" and not queue_tokens.check(get_runs_dir(), lane, queue_token):
        raise HTTPException(status_code=403, detail=f"The {lane} queue needs a valid X-Queue-Token header.")
    files = [f for f in (files or []) if f is not None]
    campaign_src = None
    if campaign_input:
        if lane != "repository":
            raise HTTPException(status_code=403, detail="campaign_input needs the repository queue.")
        if files:
            raise HTTPException(status_code=422, detail="Give either files or campaign_input, not both.")
        campaign_src = _campaign_input_dir(campaign_input)
    elif not files:
        raise HTTPException(status_code=422, detail="No files uploaded")

    # Generate run_id if not provided. A client-chosen id becomes a directory
    # name under the runs dir: no separators, no "..".
    if run_id is None:
        run_id = str(uuid.uuid4())
    elif not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id) or ".." in run_id:
        raise HTTPException(status_code=422, detail="Invalid run_id")
    elif (get_runs_dir() / run_id).exists():
        raise HTTPException(status_code=409, detail=f"Run '{run_id}' already exists")
    
    runs_dir = get_runs_dir()
    run_dir = runs_dir / run_id
    input_dir = run_dir / "input"

    # BH-013 (security): sanitise upload names BEFORE anything touches the
    # filesystem. A client-controlled filename with "../" (or an absolute
    # path) wrote outside the run directory; Path(...).name keeps only the
    # final component. Empty/dot-only names and duplicates are rejected.
    # Content is read and size-checked up front too, so a rejected upload
    # (413/422) leaves NO run directory behind.
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=413,
            detail=f"Too many files ({len(files)}): at most {MAX_FILES} per run; "
                   "bundle them as a .zip or .tar.gz."
        )
    # Uploads arrive spooled to temporary files; they are copied to the run
    # directory in chunks below, never read into memory whole.
    sanitised: dict[str, UploadFile] = {}
    for file in files:
        raw_name = file.filename or ""
        name = Path(raw_name).name
        if not name or name in {".", ".."}:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid file name: {raw_name!r}"
            )
        if name in sanitised:
            raise HTTPException(
                status_code=422,
                detail=f"Duplicate file name after sanitisation: {name!r}"
            )
        if not allowed_upload(name):
            raise HTTPException(
                status_code=422,
                detail=f"'{name}' is not a file type BioID reads (simulation, "
                       "structure, config or .zip/.tar archive files)"
            )
        size = file.size
        if size is None:
            file.file.seek(0, os.SEEK_END)
            size = file.file.tell()
        file.file.seek(0)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File '{name}' exceeds 128 MiB limit"
            )
        sanitised[name] = file
    if not sanitised and campaign_src is None:
        raise HTTPException(
            status_code=422,
            detail="No files with usable names were uploaded"
        )
    
    # Run config: server defaults, then the preset, then the user's
    # overrides (config_file or config_json). Only the fields in
    # presets.TUNABLE may change; executables, database paths and URLs stay
    # the server's. Checked before the run directory is created.
    from src_new.config.presets import (
        ConfigOverrideError, checked_overrides, overrides_from_ini, resolve_run_config,
    )
    from src_new.config.loader import RunConfig
    try:
        base = RunConfig.from_default_ini()
        overrides = None
        if config_file and config_file.filename:
            config_content_bytes = await config_file.read()
            if len(config_content_bytes) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File '{config_file.filename}' exceeds 128 MiB limit"
                )
            overrides = overrides_from_ini(
                config_content_bytes.decode("utf-8", errors="replace"), base)
        elif config_json:
            try:
                overrides_dict = json.loads(config_json)
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=422, detail=f"Invalid config JSON: {e}")
            overrides = checked_overrides(overrides_dict, base, keep_defaults=True)
        config = resolve_run_config(preset or None, overrides)
    except ConfigOverrideError as e:
        raise HTTPException(status_code=422, detail=str(e))
    from src_new.api.retention import RetentionError, parse_retention
    try:
        retention_policy = parse_retention(retention)
    except RetentionError as e:
        raise HTTPException(status_code=422, detail=str(e))
    # Apply quick structure search overrides if enabled
    if config.loader.quick_structure_search:
        config.override("signatures.topology_less_pdb", True)
        config.override("signatures.ca_only_pdb", True)

    creator_ip = _requester_ip(request)
    check_submit_limits(creator_ip)

    # Create run directory structure (after validation)
    input_dir.mkdir(parents=True, exist_ok=True)
    
    if campaign_src is not None:
        _link_campaign_input(campaign_src, input_dir)

    # Save uploaded files to input directory
    saved_files = {}
    for name, file in sanitised.items():
        file_path = input_dir / name
        with open(file_path, "wb") as f:
            # BH-017: strip a UTF-8 BOM so the first record (often ATOM) is
            # not corrupted for downstream parsers.
            head = file.file.read(3)
            if head != b"\xef\xbb\xbf":
                f.write(head)
            shutil.copyfileobj(file.file, f, 1024 * 1024)
        saved_files[name] = str(file_path)

    from ..archives import ArchiveError, unpack as unpack_archives
    try:
        unpack_archives(input_dir)
    except ArchiveError as e:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(e))

    problem, input_note = _input_check(input_dir)
    if problem:
        shutil.rmtree(run_dir, ignore_errors=True)
        raise HTTPException(status_code=422, detail=problem)

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
    if preset:
        initial_results["pipeline"]["preset"] = preset
    if creator_ip:
        initial_results["pipeline"]["creator_ip_hash"] = ip_hash(creator_ip)
    owner_token, initial_results["pipeline"]["owner_token_sha256"] = new_owner_token()
    initial_results["pipeline"]["retention"] = retention_policy
    initial_results["pipeline"]["queue"] = lane
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(initial_results, f, indent=2)
    
    # Enqueue Celery task with run_id as task_id, on the lane's queue
    _celery_queue = retries.celery_queue(lane)
    _ui_opts = {"queue": _celery_queue} if _celery_queue else {}
    run_pipeline_task.apply_async(
        task_id=run_id,
        kwargs={
            "run_id": run_id,
            "input_dir": str(input_dir),
            "results_path": str(results_path),
            "config_path": str(config_path) if config_path else None,
        },
        **_ui_opts,
    )
    
    return RunCreateResponse(
        run_id=run_id,
        status="queued",
        message=f"Run {run_id} queued successfully" + (f". Note: {input_note}" if input_note else ""),
        results_url=f"/api/v1/runs/{run_id}/status",
        owner_token=owner_token,
    )


@router.get("", response_model=RunListResponse)
async def list_runs(request: Request, mine: int = Query(1)) -> RunListResponse:
    """Runs submitted from the caller's network address, with basic metadata.

    Other people's runs are never listed (``mine`` is accepted for
    compatibility and ignored).
    """
    runs_dir = get_runs_dir()

    if not runs_dir.exists():
        return RunListResponse(runs=[])

    requester_ip = _requester_ip(request)
    if requester_ip is None:
        return RunListResponse(runs=[])

    from src_new import retries
    from src_new.api.run_index import summaries
    runs = [
        RunListItem(
            run_id=r["run_id"],
            status=retries.client_status({"status": r["status"]}),
            created_at=r["created_at"],
            input_kind=r["input_kind"],
            run_name=r["run_name"],
            queue=r.get("queue") or "web",
            completeness=r.get("completeness"),
            partial_stages=r.get("partial_stages") or [],
        )
        for r in summaries(runs_dir)
        if same_submitter(r["_pipeline"], requester_ip)
    ]
    runs.sort(key=lambda r: r.created_at or "", reverse=True)
    return RunListResponse(runs=runs)

#: finished runs (a rerun may link them to the new run)
TERMINAL_STATUSES = frozenset({"success", "failed", "cancelled", "timeout", "error"})

# ---------------------------------------------------------------------------
# Landing-page example cards (v3.137)
# ---------------------------------------------------------------------------

TITLE_DESC_SEP = ">"      # run_name convention: "My Title>Some description"
_EXAMPLE_IMAGE = "render/system.png"


def parse_run_title(run_name: Optional[str], run_id: str) -> tuple:
    """Split 'Title>Description'; missing '>' -> description None; missing name -> run id."""
    name = (run_name or "").strip()
    if not name:
        return run_id[:8], None
    title, _, desc = name.partition(TITLE_DESC_SEP)
    return title.strip() or run_id[:8], (desc.strip() or None)


def _example_candidates(runs_dir: Path) -> List[dict]:
    """Successful runs that have render/system.png on disk (newest first)."""
    out = []
    if not runs_dir.is_dir():
        return out
    for entry in runs_dir.iterdir():
        results_path = entry / "results.json"
        if not (results_path.is_file() and (entry / _EXAMPLE_IMAGE).is_file()):
            continue
        try:
            with open(results_path, encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            continue
        pipeline = payload.get("pipeline", {}) or {}
        if pipeline.get("status") != "success":
            continue
        out.append({
            "run_id": entry.name,
            "run_name": pipeline.get("run_name"),
            "created_at": payload.get("created_at", "") or str(results_path.stat().st_mtime_ns / 1e9),
        })
    out.sort(key=lambda r: r["created_at"], reverse=True)
    return out


def get_example_runs(runs_dir: Path, limit: int, explicit_ids: Optional[List[str]] = None) -> List[dict]:
    """Pick up to `limit` examples: the explicit ids (in order) when configured
    — only those, never padded with other runs — else the newest."""
    candidates = _example_candidates(runs_dir)
    by_id = {c["run_id"]: c for c in candidates}
    picked: List[dict] = []
    for rid in explicit_ids or []:
        if rid in by_id and len(picked) < limit:
            picked.append(by_id.pop(rid))
    if explicit_ids:
        return picked
    for cand in candidates:
        if len(picked) >= limit:
            break
        if cand["run_id"] in by_id:
            picked.append(cand)
    return picked


_example_ids_cache: tuple[float, Optional[set]] = (0.0, None)


def example_ids(runs_dir: Path) -> set:
    """Example run ids for request handlers: never scans the runs folder there.

    With BAT3_EXAMPLE_RUNS set (production) it is that list, a superset of
    the examples the endpoint serves. Otherwise the served examples, cached
    10 minutes. Finding served examples reads every run's results.json:
    over slow NFS that took a minute and, done inside requests (every run
    deletion, every status poll), it blocked the API's event loops until
    the readiness probe failed and the ingress dropped the API (2026-11-17).
    The retention sweep keeps its own full check (protected_run_ids).
    """
    global _example_ids_cache
    explicit = _explicit_examples()
    if explicit:
        return set(explicit)
    at, ids = _example_ids_cache
    if ids is None or time.time() - at > 600:
        ids = served_example_ids(runs_dir)
        _example_ids_cache = (time.time(), ids)
    return ids


def _explicit_examples() -> Optional[List[str]]:
    """BAT3_EXAMPLE_RUNS (JSON list of run ids), or None."""
    raw = os.environ.get("BAT3_EXAMPLE_RUNS")
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None
    return [str(x) for x in parsed] if isinstance(parsed, list) else None


def served_example_ids(runs_dir: Path) -> set:
    """Every run the examples endpoint can show (protected from deletion)."""
    explicit = _explicit_examples() or []
    return set(explicit) | {p["run_id"] for p in get_example_runs(runs_dir, 10, explicit or None)}


@router.get("/examples", response_model=ExamplesResponse)
async def get_run_examples(limit: int = 3) -> ExamplesResponse:
    """Landing-page example cards (v3.137).

    Auto: newest *successful* runs that have render/system.png. Override for
    curated cards: env BAT3_EXAMPLE_RUNS as JSON list of run ids (deploy-time
    changeable, no code edit). Titles parse from run_name 'Title>Description'.
    """
    explicit = _explicit_examples()
    limit = max(1, min(limit, 10))
    picks = get_example_runs(get_runs_dir(), limit, explicit)
    examples = [
        ExampleRun(
            run_id=p["run_id"],
            title=parse_run_title(p["run_name"], p["run_id"])[0],
            description=parse_run_title(p["run_name"], p["run_id"])[1],
            image_url=f"/files/{p['run_id']}/{_EXAMPLE_IMAGE}",
            created_at=str(p["created_at"]),
        )
        for p in picks
    ]
    return ExamplesResponse(examples=examples)



@router.delete("/{run_id}")
async def delete_run(
    run_id: RunId,
    owner_token: Optional[str] = Header(None, alias=OWNER_HEADER),
) -> dict:
    """Delete a run and its associated directory (owner token required)."""
    run_dir = safe_run_dir(get_runs_dir(), run_id)
    if not run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    if run_id in example_ids(get_runs_dir()):
        raise HTTPException(status_code=403, detail="Example runs cannot be deleted.")
    pipeline = load_results_json(run_id).get("pipeline", {})
    require_owner(pipeline, owner_token, "deleted")
    # A queued or running run's worker would write results.json again after
    # the delete and leave a half run behind (2026-11-17): cancel it first.
    # 2026-11-23: once cancelled it may be deleted even while its worker is
    # still stopping (the status can read "running" for a few seconds); the
    # worker then writes nothing more and removes its leftovers.
    from src_new import cancellation
    if pipeline.get("status") in ("queued", "running", "pending", "created", "retry_scheduled") \
            and not cancellation.is_cancelled(run_id, run_dir, fresh=True):
        raise HTTPException(status_code=409, detail="This run is still queued or running: cancel it first, then delete it.")
    # 2026-11-23: a worker still on this run stops (cancellation.py)
    cancellation.request_cancel(run_id, run_dir)
    shutil.rmtree(run_dir)
    return {"message": f"Run '{run_id}' deleted successfully"}

@router.get("/{run_id}", response_model=RunSummaryResponse)
async def get_run_summary(run_id: RunId) -> RunSummaryResponse:
    """Get a summary of a specific run."""
    data = load_results_json(run_id)
    
    pipeline_data = data.get("pipeline", {})
    tasks_data = data.get("tasks", {})
    warnings_data = user_warnings(data.get("warnings", []))
    errors_data = data.get("critical_errors", [])
    
    from src_new import completeness, retries
    return RunSummaryResponse(
        run_id=run_id,
        pipeline_name=pipeline_data.get("name", ""),
        status=retries.client_status(pipeline_data) if pipeline_data.get("status") else "unknown",
        started_at=pipeline_data.get("started_at"),
        finished_at=pipeline_data.get("finished_at"),
        input_kind=pipeline_data.get("input_kind"),
        run_name=pipeline_data.get("run_name"),
        task_count=len(tasks_data),
        warning_count=len(warnings_data),
        error_count=len(errors_data),
        retention=_retention_info(run_id, data),
        incomplete_count=sum(g["count"] for g in completeness.gaps(data)),
        **completeness.state(data),
        queue=retries.lane_of(pipeline_data),
        attempt=len(pipeline_data.get("attempts") or []) + 1,
        rerun_of=pipeline_data.get("rerun_of"),
        superseded_by=pipeline_data.get("superseded_by"),
    )


def _retention_info(run_id: str, data: Dict[str, Any]) -> RetentionInfo:
    from .. import retention
    if retention.is_example(get_runs_dir(), run_id):
        return RetentionInfo(policy="preserve", days=None, expires_at=None, example=True)
    info = retention.describe(data)
    status = (data.get("pipeline") or {}).get("status")
    choices = (list(retention.OWNER_CHOICES)
               if info["expires_at"] and status in retention.TERMINAL else [])
    return RetentionInfo(**info, owner_choices=choices)


@router.post("/{run_id}/reports", status_code=201)
async def report_identification(run_id: RunId, body: ReportCreate, request: Request) -> Dict[str, Any]:
    """Report that a molecule's identification looks wrong. Anyone may report;
    at most 20 reports per address per hour (429)."""
    from .. import reports
    data = load_results_json(run_id)
    who = ip_hash(_requester_ip(request))
    try:
        reports.check_rate(who)
    except reports.ReportError as e:
        raise HTTPException(status_code=429, detail=str(e), headers={"Retry-After": "3600"})
    try:
        report = reports.create(get_runs_dir(), run_id, data, body.segment, body.note, body.suggestion, who)
    except reports.ReportError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"id": report["id"], "message": "Thank you. The BioID team will look at it."}


@router.post("/{run_id}/retention", response_model=RetentionInfo)
async def keep_run_longer(
    run_id: RunId,
    body: RetentionChange,
    owner_token: Optional[str] = Header(None, alias=OWNER_HEADER),
) -> RetentionInfo:
    """Keep a finished run longer: 30, 90, 180 or 365 days from now (owner only).

    403 without the owner token; 409 when the run is not finished, is kept
    permanently, or already expires later than the choice.
    """
    from .. import retention
    data = load_results_json(run_id)
    require_owner(data.get("pipeline", {}), owner_token, "kept longer")
    if retention.is_example(get_runs_dir(), run_id):
        raise HTTPException(status_code=409, detail="Examples are kept permanently.")
    try:
        retention.keep_for(safe_run_dir(get_runs_dir(), run_id), body.days)
    except retention.RetentionError as e:
        status = 400 if body.days not in retention.OWNER_CHOICES else 409
        raise HTTPException(status_code=status, detail=str(e))
    return _retention_info(run_id, load_results_json(run_id))


logger = logging.getLogger(__name__)


def _parse_iso_datetime(dt_str: str) -> datetime:
    """Parse an ISO 8601 date or date-time; without a zone it is UTC.

    Always timezone-aware, so stored and requested times compare (a naive
    ?since= used to raise TypeError: 500)."""
    dt = datetime.fromisoformat(dt_str.strip().replace(" ", "+"))  # "+" arrives as " " when not URL-encoded
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


@router.get("/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(run_id: RunId, since: Optional[str] = None) -> RunStatusResponse:
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
    from src_new import completeness, retries
    pipeline_data = data.get("pipeline", {})
    pipeline = PipelineStatusResponse(
        run_id=run_id,
        pipeline_name=pipeline_data.get("name", ""),
        status=retries.client_status(pipeline_data),
        started_at=pipeline_data.get("started_at"),
        finished_at=pipeline_data.get("finished_at"),
        input_kind=pipeline_data.get("input_kind"),
        input_files=pipeline_data.get("input_files"),
        metadata=pipeline_data.get("metadata", {}),
        **completeness.state(data),
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
    warnings_data = user_warnings(data.get("warnings", []))
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
            docs_url=docs_url(w.get("code", "")),
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
            docs_url=docs_url(e.get("code", "")),
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
        progress=_segment_progress(data, tasks_data),
        retention=_retention_info(run_id, data),
        incomplete=[IncompleteItem(**g) for g in completeness.gaps(data)],
        queue=retries.lane_of(pipeline_data),
        retry=(RetryInfo(**{k: pipeline_data["retry"][k] for k in RetryInfo.model_fields})
               if pipeline_data.get("status") == retries.STATUS and pipeline_data.get("retry") else None),
        attempts=[AttemptInfo(**{k: a.get(k) for k in AttemptInfo.model_fields if k in a})
                  for a in pipeline_data.get("attempts") or [] if isinstance(a, dict)],
        # 2026-11-23: worker restarts (retries.restart)
        restarts=[RestartInfo(**{k: r.get(k) for k in RestartInfo.model_fields if k in r})
                  for r in pipeline_data.get("restarts") or [] if isinstance(r, dict) and "restart" in r],
        rerun_of=pipeline_data.get("rerun_of"),
        superseded_by=pipeline_data.get("superseded_by"),
    )


def _segment_progress(data: Dict[str, Any],
                      tasks_data: Dict[str, Any]) -> Optional[RunStageProgress]:
    """v3.143 (BACKEND_GAPS G2): read-side identification progress.

    Mirrors the identify stage's own enumeration (pipeline_steps
    _identify_molecules iterates signatures keys with non-empty
    `generated`): a segment participates iff it has generated
    signatures — fragments-mode runs (one entry per instance) and
    universe-mode runs (chain segments + virtual water rows) alike;
    checking-only molecules without signatures are excluded. A segment
    is "searched" once its identifiers block is persisted,
    "searching" while identify_molecules is running, otherwise
    "waiting". Null when nothing is identifiable yet (pre-analysis /
    no identifiable molecules). For terminal runs the block reflects
    the last recorded state; live views should only consume it while
    the run is in progress.
    """
    payload_data = data.get("data", {}) or {}
    signatures = payload_data.get("signatures") or {}
    identifiers = payload_data.get("identifiers") or {}
    identify_running = (
        (tasks_data.get("identify_molecules") or {}).get("status") == "running"
    )

    identified = sorted(
        seg for seg, seg_data in signatures.items()
        if isinstance(seg_data, dict) and seg_data.get("generated")
    )
    if not identified:
        return None

    per_segment: Dict[str, str] = {}
    done = 0
    for seg in identified:
        if seg in identifiers:
            per_segment[seg] = "searched"
            done += 1
        elif identify_running:
            per_segment[seg] = "searching"
        else:
            per_segment[seg] = "waiting"
    return RunStageProgress(
        molecules_done=done,
        molecules_total=len(identified),
        per_segment=per_segment,
    )




@router.post("/{run_id}/cancel", response_model=CancelRunResponse)
async def cancel_run(
    run_id: RunId,
    owner_token: Optional[str] = Header(None, alias=OWNER_HEADER),
) -> CancelRunResponse:
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
    require_owner(pipeline_data, owner_token, "cancelled")
    current_status = pipeline_data.get("status", "unknown")
    
    # Cannot cancel if already in a terminal state
    terminal_states = {"success", "failed", "cancelled"}
    if current_status in terminal_states:
        raise HTTPException(
            status_code=400,
            detail=f"Run is already in terminal state: {current_status}"
        )
    
    # Waiting for an automatic retry: stop retrying, keep this attempt's results.
    if current_status == "retry_scheduled":
        results_manager = ResultsManager(str(get_runs_dir() / run_id / "results.json"))
        results_manager._payload["pipeline"].setdefault("retry", {})["cancelled"] = True
        results_manager.finish_run("success")
        return CancelRunResponse(run_id=run_id, status="success")

    # 2026-11-23: the threads pool cannot terminate a task (revoke below only
    # drops a queued message): the running pipeline stops itself
    # (cancellation.py).
    from src_new import cancellation
    cancellation.request_cancel(run_id, get_runs_dir() / run_id)

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
async def get_loading_info(run_id: RunId) -> LoadingInfoResponse:
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
    
    # Get attempts (bughunt BH-014: the loader persists `status` /
    # `error_code` / `error_message` per attempt — the endpoint used to
    # read `success`/`error`, so the UI always showed error=None)
    attempts_data = loading_data.get("attempts", [])
    attempts = [
        LoadingAttemptInfo(
            strategy=a.get("strategy", ""),
            success=a.get("status", a.get("success", False)) == "success",
            error=a.get("error_message") or a.get("error"),
            error_code=a.get("error_code"),
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
    
    # bughunt BH-014: structured failure reason (None on success)
    failure_summary = loading_data.get("failure_summary")
    
    return LoadingInfoResponse(
        run_id=run_id,
        input_kind=input_kind,
        selected_strategy=selected_strategy,
        topology_files=topology_files,
        attempts=attempts,
        final_strategy=final_strategy,
        success=success,
        warnings=warnings,
        failure_summary=failure_summary,
    )


@router.get("/{run_id}/molecules", response_model=MoleculeSummaryResponse)
async def get_molecules(run_id: RunId) -> MoleculeSummaryResponse:
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
            # v3.143 (BACKEND_GAPS G7 additive): full unique-group segments
            segment_names=mol_info.get("segment_names", []),
            molecule_type=mol_info.get("molecule_type"),
            atom_count=mol_info.get("atom_count", 0),
            # fragments store the residues as indices, not a count (always 0 before)
            residue_count=mol_info.get("residue_count") or len(mol_info.get("residue_indices") or []),
            smiles=mol_info.get("smiles"),
        )
    
    # Get type counts
    type_counts = fragments_data.get("type_counts", {})
    
    # Molecules counting every copy (stored as total_fragment_count; the
    # old "total_count" key never existed, so this was always 0)
    total_fragment_count = fragments_data.get("total_fragment_count", fragments_data.get("total_count", 0))
    
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
        # v3.143 (BACKEND_GAPS G3): additive — per-instance copy count
        # plus the server-side mirror of the UI's display-name derivation.
        try:
            seg_props["copies"] = int(seg_from_fragments.get("copies") or 1)
        except (TypeError, ValueError):
            seg_props["copies"] = 1
        seg_props["display_name"] = segment_display_name(
            seg_name, segment_resname(data.get("data", {}) or {}, seg_name))
        seg_props["chain"] = chain_of(strip_seg(seg_name))
        # 2026-11-21 (mdval audit item 8b): additive — {"model", "residue",
        # "by_name"?} for a coarse-grained molecule (ui derive.ts stateOf)
        from src_new.api.best_hit import coarse_grained_of
        cg = coarse_grained_of(data, seg_name)
        if cg is not None:
            seg_props["coarse_grained"] = cg
        segment_meta[seg_name] = seg_props
    
    return MoleculeSummaryResponse(
        run_id=run_id,
        unique_molecules=unique_molecules,
        type_counts=type_counts,
        total_fragment_count=total_fragment_count,
        segments=segments,
        segment_meta=segment_meta,
    )


@router.get("/{run_id}/download/results.json")
async def download_results_json(run_id: RunId):
    """The run's complete results document (documented at
    /documentation/results-json/), without the submitter's address."""
    from fastapi.responses import JSONResponse
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id) or ".." in run_id:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    data = load_results_json(run_id)
    if isinstance(data.get("pipeline"), dict):
        for key in ("creator_ip", "creator_ip_hash", "owner_token_sha256"):
            data["pipeline"].pop(key, None)
    return JSONResponse(data, headers={
        "Content-Disposition": f'attachment; filename="bioid-{run_id[:8]}-results.json"'})


@router.get("/{run_id}/download/results.csv")
async def download_results_csv(run_id: RunId) -> PlainTextResponse:
    """v3.143 (BACKEND_GAPS G6): run-level CSV export — one clean row per
    leaderboard molecule (every fragments/segments entry). Confidence
    label thresholds match the UI exactly (>=80 high, >=50 medium);
    Alternatives = top-3 verified hits after the best, as db:id. Empty
    cells (never resolver names or internal chains) for unverified
    molecules; `identified_name` fills in once G5 lands server-side.
    """
    data = load_results_json(run_id)
    payload_data = data.get("data", {}) or {}
    fragments_data = payload_data.get("fragments", {}) or {}
    fragments_segments = fragments_data.get("segments") or []
    verification_data = payload_data.get("verification", {}) or {}

    from src_new.api.best_hit import coarse_grained_of, molecule_result

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "Segment", "Display Name", "Kind", "Copies", "Atoms", "Result",
        "Identified Name", "Best Database", "Best Identifier", "Database URL",
        "Confidence", "Confidence Label", "Alternatives",
    ])

    for entry in fragments_segments:
        if not isinstance(entry, dict):
            continue
        seg = entry.get("segment")
        if not seg:
            continue
        copies = entry.get("copies")
        try:
            copies = int(copies) if copies is not None else 1
        except (TypeError, ValueError):
            copies = 1
        atoms = entry.get("atoms_per_copy", 0) or 0

        seg_ver = verification_data.get(seg) or {}
        r = molecule_result(seg_ver.get("verified_hits") or [], coarse_grained_of(data, seg))
        best = r["best"] or {}
        writer.writerow([
            seg,
            segment_display_name(seg, segment_resname(payload_data, seg)),
            entry.get("type") or "unknown",
            copies,
            atoms,
            r["state_label"],
            (hit_display_name(best) if best else "") or r.get("name") or "",
            r["database"],
            r["identifier"],
            r["url"],
            "" if r["confidence"] is None else str(round(float(r["confidence"]), 1)),
            r["confidence_label"] or "",
            " ".join(r["alternatives"]),
        ])

    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{run_id}_results.csv"'},
    )


@router.get("/{run_id}/molecules/{segment}/info", response_model=MoleculeInfoResponse)
async def get_molecule_info(run_id: RunId, segment: str) -> MoleculeInfoResponse:
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
    
    # Confidence and name as the results page and results.csv show them:
    # the best verified hit (none for exact answers such as ions and water).
    from src_new.api.best_hit import coarse_grained_of, molecule_result
    seg_ver = verification_data.get(segment) or {}
    confidence = molecule_result(seg_ver.get("verified_hits") or [],
                                 coarse_grained_of(data, segment))["confidence"]
    name = segment_display_name(segment, segment_resname(data.get("data", {}) or {}, segment))

    return MoleculeInfoResponse(
        segment=segment,
        name=name,
        type=seg_type,
        atom_count=atom_count,
        residue_count=residue_count,
        confidence=confidence,
    )


@router.get("/{run_id}/render", response_model=RenderPathsResponse)
async def get_render_paths(run_id: RunId) -> RenderPathsResponse:
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
    
    # v3.143 (BACKEND_GAPS G9, additive): typed passthrough of the
    # export-side render/segment_selectors record; empty on older runs.
    segment_selectors = {}
    selectors_raw = render_data.get("segment_selectors")
    if isinstance(selectors_raw, dict):
        for name, info in selectors_raw.items():
            if not isinstance(info, dict):
                continue
            segment_selectors[name] = RenderSegmentSelector(
                chains=list(info.get("chains") or []),
                atom_index_ranges=[list(r) for r in (info.get("atom_index_ranges") or [])],
                atom_count=int(info.get("atom_count") or 0),
                residue_ranges=([list(r) for r in info["residue_ranges"]]
                                if isinstance(info.get("residue_ranges"), list) else None),
            )

    return RenderPathsResponse(
        run_id=run_id,
        system_mmcif=system_mmcif,
        segments=segments,
        system_png=_relativize_run_path(render_data.get("system_png"), run_id),
        segment_pngs=_extract_segment_pngs(render_data.get("segments", {}), run_id),
        total_atom_count=(data.get("data", {}).get("simulation", {}) or {}).get("n_atoms"),
        geometry=render_data.get("geometry") if isinstance(render_data.get("geometry"), dict) else None,
        segment_selectors=segment_selectors,
    )


def _relativize_run_path(path: Optional[str], run_id: str) -> Optional[str]:
    """Render paths are absolute in results.json; /files serves them relative to run dir."""
    if not path:
        return None
    runs_dir = get_runs_dir()
    run_dir = runs_dir / run_id
    if Path(path).is_absolute() and str(path).startswith(str(runs_dir)):
        return str(Path(path).relative_to(run_dir))
    return path


def _extract_segment_pngs(segments_data: Dict[str, Any], run_id: str) -> Dict[str, str]:
    """Pair recorded render.segments.<seg>.png paths with the /files form."""
    out = {}
    if not isinstance(segments_data, dict):
        return out
    for name, info in segments_data.items():
        if isinstance(info, dict):
            png = _relativize_run_path(info.get("png"), run_id)
            if png:
                out[name] = png
    return out




@router.get("/{run_id}/signatures", response_model=SignaturesResponse)
async def get_signatures(run_id: RunId, segment: Optional[str] = None) -> SignaturesResponse:
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
async def get_identifiers(run_id: RunId, segment: Optional[str] = None) -> IdentifiersResponse:
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
    seen_keys = set()  # For deduplication by (segment, identifier, ident_type, resolver_name)
    
    for seg_name, seg_data in identifiers_data.items():
        
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
                    
                    # Build database URL (canonicalizes PDB chain ids and CHEMBL ids)
                    db_url = build_database_url(identifier, ident_type)
                    display_identifier = normalize_identifier(identifier, ident_type) or identifier
                    
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
                    dedup_key = (seg_name, identifier, ident_type, resolver_name)
                    if dedup_key in seen_keys:
                        continue
                    seen_keys.add(dedup_key)
                    
                    all_hits.append(IdentifierHit(
                        identifier=display_identifier,
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
    warnings = user_warnings(data.get("warnings", []))
    for warning in warnings:
        if warning.get("code") == "identifier_resolver_failed":
            if segment is not None and (warning.get("details") or {}).get("segment") not in (None, segment):
                continue
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
    
    # The molecule asked for; None when the hits of every molecule are listed
    seg = segment
    
    return IdentifiersResponse(
        run_id=run_id,
        segment=seg,
        hits=all_hits,
        attempted_resolvers=sorted(all_attempted_resolvers),
        failed_resolvers=failed_resolvers,
    )


@router.get("/{run_id}/verification", response_model=VerificationResponse)
async def get_verification(run_id: RunId, segment: Optional[str] = None) -> VerificationResponse:
    """Get verification results for all segments or a specific segment."""
    data = load_results_json(run_id)
    
    # Get verification data from data.verification.*
    verification_data = data.get("data", {}).get("verification", {})
    
    # Filter by segment if provided
    if segment is not None:
        verification_data = {segment: verification_data.get(segment, {})} if segment in verification_data else {}
    
    all_hits = []
    
    for seg_name, seg_data in verification_data.items():
        # v3.143 (D-17): `_meta` (written first by verify_all) is bookkeeping,
        # not a segment: its keys must never leak into the hit list.
        if seg_name == "_meta":
            continue
        if not isinstance(seg_data, dict):
            continue
        
        # Get verified hits
        verified_hits = seg_data.get("verified_hits", [])
        for hit in verified_hits:
            identifier = hit.get("identifier", "")
            ident_type = hit.get("ident_type", "")
            db_url = build_database_url(identifier, ident_type)
            display_identifier = normalize_identifier(identifier, ident_type) or identifier
            all_hits.append(VerifiedHitItem(
                identifier=display_identifier,
                ident_type=ident_type,
                database=hit.get("database", ""),
                segment=seg_name,
                resolver_score=hit.get("resolver_score"),
                similarity_score=hit.get("similarity_score"),
                annotation_quality_score=hit.get("annotation_quality_score"),
                final_confidence=hit.get("final_confidence"),
                # v3.142 additive surfaces (Phase 2): skeleton corroboration +
                # calibrated agreement-structure belief (legacy runner rows
                # simply omit both -> None).
                skeleton_sim=hit.get("skeleton_sim"),
                belief=hit.get("belief"),
                equivalence_class_id=hit.get("equivalence_class_id"),
                is_verified=hit.get("is_verified", False),
                rejection_reason=hit.get("rejection_reason"),
                supporting_evidence_count=hit.get("supporting_evidence_count", 0),
                database_url=db_url,
                ground_truth_override=hit.get("ground_truth_override"),
                # v3.143 (BACKEND_GAPS G5): additive — display metadata the
                # scorers thread onto the hit; null for older runs.
                name=hit_display_name(hit),
                organism=hit.get("organism"),
            ))
    
    # The molecule asked for; None when the hits of every molecule are listed
    seg = segment
    
    return VerificationResponse(
        run_id=run_id,
        segment=seg,
        hits=all_hits,
    )


@router.get("/{run_id}/logs")
async def get_run_logs(run_id: RunId, type: str = "normal") -> PlainTextResponse:
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
async def get_run_files(run_id: RunId) -> RunFilesResponse:
    """Get all files in a run directory (recursive), excluding hidden files.

    Only real runs (the runs directory also holds _settings, _reports,
    _expired, ...: none of that is listed)."""
    run_dir = safe_run_dir(get_runs_dir(), run_id)
    if not (run_dir / "results.json").is_file():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    files = []
    for f in run_dir.rglob('*'):
        if f.is_file() and not any(part.startswith('.') for part in f.relative_to(run_dir).parts):
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
    run_id: RunId,
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
    run_id: RunId,
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


def _rerun_name(old_run_name: str) -> str:
    """'Name' -> 'Name (re-run)'; 'Title>Description' keeps its description:
    'Title (re-run)>Description'."""
    title, sep, desc = old_run_name.partition(TITLE_DESC_SEP)
    return f"{title.rstrip()} (re-run){sep}{desc}" if sep else f"{old_run_name} (re-run)"


def _create_single_rerun(old_run_dir: Path, creator_ip: Optional[str] = None,
                         preset: Optional[str] = None,
                         link_old: bool = False) -> Optional[tuple[str, str]]:
    """Create a new run reusing the input and config of an existing run.

    Copies input files and config.ini (or writes the default config) into a
    fresh run directory, writes an initial queued results.json, and enqueues
    a new Celery pipeline task.

    Args:
        old_run_dir: Path to the existing run directory to re-run.
        creator_ip: The requester's IP, recorded like a new submission so the
            rerun appears in their "Your annotations" (GET /runs?mine=1).

    Returns:
        (new run id, its owner token), or None if the run cannot be re-run
        (missing results.json or missing/empty input directory).

    Of the old config.ini only the per-run choices (tunable fields) are
    kept; everything else takes today's server values, so a planted
    executable or URL is dropped and an older run stays re-runnable after a
    server config change. HTTPException 422 for a tunable value that is no
    longer valid.

    The new run records rerun_of. With link_old (the owner asked) it goes to
    the old run's queue and the old run gets superseded_by; otherwise it goes
    to the web queue.
    """
    from src_new.config.loader import RunConfig
    from src_new.config.presets import ConfigOverrideError, overrides_from_ini, resolve_run_config

    old_run_id = old_run_dir.name
    old_results_path = old_run_dir / "results.json"
    old_input_dir = old_run_dir / "input"
    old_config_path = old_run_dir / "config.ini"

    # Skip if results.json doesn't exist
    if not old_results_path.exists():
        return None

    # Skip if input directory doesn't exist or is empty
    if not old_input_dir.exists() or not any(old_input_dir.iterdir()):
        return None

    # Read old results to get run_name
    try:
        with open(old_results_path, "r", encoding="utf-8") as f:
            old_data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None

    old_run_name = old_data.get("pipeline", {}).get("run_name")

    config = None
    if preset:
        # "Run again with <preset>": the preset on today's server settings;
        # the old run's own choices are not carried over (2026-11-17)
        try:
            config = resolve_run_config(preset, None)
        except ConfigOverrideError as e:
            raise HTTPException(status_code=422, detail=str(e))
    elif old_config_path.exists():
        try:
            overrides = overrides_from_ini(old_config_path.read_text(encoding="utf-8"),
                                           RunConfig.from_default_ini(), strict=False)
            # NCBI nr/nt/core_nt were on by default until 2026-11-18 (now Deep
            # search only, up to 12 h per search): an older run's config.ini
            # carries them on even when nobody chose them.
            if (old_data.get("pipeline", {}).get("preset") or "balanced") != "deep":
                from src_new.pipeline_steps import NCBI_DATABASES
                ids = overrides.get("identifiers") or {}
                for name in NCBI_DATABASES:
                    ids.pop(name, None)
                    ids.pop(f"{name}_similarity", None)
                if "identifiers" in overrides and not ids:
                    overrides.pop("identifiers")
            config = resolve_run_config(None, overrides)
        except ConfigOverrideError as e:
            raise HTTPException(status_code=422,
                                detail=f"This run's configuration cannot be re-run: {e}")

    # Generate new run ID
    new_run_id = str(uuid.uuid4())
    new_run_dir = get_runs_dir() / new_run_id
    new_input_dir = new_run_dir / "input"

    # Create new run directory structure
    new_input_dir.mkdir(parents=True, exist_ok=True)

    # Copy input files
    for file in old_input_dir.iterdir():
        if file.is_file():
            shutil.copy2(str(file), str(new_input_dir / file.name))

    # Config: the old run's (re-checked above) or the defaults
    new_config_path = new_run_dir / "config.ini"
    (config or RunConfig.from_default_ini()).to_ini_path(new_config_path)

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
        initial_results["pipeline"]["run_name"] = _rerun_name(old_run_name)
    if creator_ip:
        initial_results["pipeline"]["creator_ip_hash"] = ip_hash(creator_ip)
    owner_token, initial_results["pipeline"]["owner_token_sha256"] = new_owner_token()
    initial_results["pipeline"]["retention"] = {"policy": "default"}
    # The preset the new run stands for: the one asked for, else the old
    # run's (a rerun of a Deep rerun is Deep too, and keeps NCBI on)
    recorded_preset = preset or old_data.get("pipeline", {}).get("preset")
    if recorded_preset:
        initial_results["pipeline"]["preset"] = recorded_preset
    from src_new import retries
    # The old run's queue for its owner; anyone else reruns on the web queue
    # (the repository queue needs a token).
    lane = retries.lane_of(old_data.get("pipeline", {})) if link_old else "web"
    initial_results["pipeline"]["queue"] = lane
    initial_results["pipeline"]["rerun_of"] = old_run_id

    with open(new_results_path, "w", encoding="utf-8") as f:
        json.dump(initial_results, f, indent=2)

    if link_old and (old_data.get("pipeline", {}).get("status") or "") in TERMINAL_STATUSES:
        try:
            old_data.setdefault("pipeline", {})["superseded_by"] = new_run_id
            tmp = old_results_path.with_name(f".results.{os.getpid()}.{os.urandom(4).hex()}.tmp")
            tmp.write_text(json.dumps(old_data, indent=2), encoding="utf-8")
            os.replace(tmp, old_results_path)
        except OSError as exc:
            logger.warning("rerun: could not link %s to %s: %s", old_run_id, new_run_id, exc)

    # Enqueue Celery task with run_id as task_id, on the old run's queue
    _celery_queue = retries.celery_queue(lane)
    _ui_opts = {"queue": _celery_queue} if _celery_queue else {}
    run_pipeline_task.apply_async(
        task_id=new_run_id,
        kwargs={
            "run_id": new_run_id,
            "input_dir": str(new_input_dir),
            "results_path": str(new_results_path),
            "config_path": str(new_config_path),
        },
        **_ui_opts,
    )

    return new_run_id, owner_token


@router.post("/rerun-all", response_model=RerunAllResponse)
async def rerun_all(
    request: Request,
    admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
) -> RerunAllResponse:
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

    Operators only: needs X-Admin-Token equal to BAT3_ADMIN_TOKEN (404 when
    that is unset, as on the public service).
    """
    import hmac as _hmac
    expected = os.environ.get("BAT3_ADMIN_TOKEN", "")
    if not expected or not admin_token or not _hmac.compare_digest(admin_token, expected):
        raise HTTPException(status_code=404, detail="Not Found")
    runs_dir = get_runs_dir()
    new_runs: List[RerunRunItem] = []
    skipped: List[str] = []

    if not runs_dir.exists():
        return RerunAllResponse(new_runs=[], skipped=[], count=0)

    for entry in runs_dir.iterdir():
        if not entry.is_dir():
            continue

        old_run_id = entry.name
        try:
            created = _create_single_rerun(entry, creator_ip=_requester_ip(request))
        except HTTPException:
            created = None
        if created is None:
            skipped.append(old_run_id)
        else:
            new_run_id = created[0]
            new_runs.append(RerunRunItem(
                new_run_id=new_run_id,
                old_run_id=old_run_id,
                status="queued",
            ))

    return RerunAllResponse(new_runs=new_runs, skipped=skipped, count=len(new_runs))


@router.post("/{run_id}/rerun", response_model=RunCreateResponse)
async def rerun_single_run(run_id: RunId, request: Request,
                           body: Optional[Dict[str, Any]] = Body(None),
                           owner_token: Optional[str] = Header(None, alias=OWNER_HEADER)) -> RunCreateResponse:
    """
    Re-run a single existing run by copying its input files and config into a
    new run directory and enqueuing a new Celery pipeline task.

    The original run is not modified or deleted.

    Args:
        run_id: The identifier of the run to re-run.

    Returns:
        RunCreateResponse for the newly queued run.

    Raises:
        404: If the run or its input directory is missing.
    """
    old_run_dir = safe_run_dir(get_runs_dir(), run_id)

    if not old_run_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")

    creator_ip = _requester_ip(request)
    check_submit_limits(creator_ip)
    preset = (body or {}).get("preset") or None
    # The owner's rerun replaces the old run: it links to the new one
    # ("superseded by"); anyone else's rerun is only their own copy.
    link_old = False
    if owner_token:
        try:
            require_owner(load_results_json(run_id).get("pipeline", {}), owner_token, "re-run")
            link_old = True
        except HTTPException:
            link_old = False
    created = _create_single_rerun(old_run_dir, creator_ip=creator_ip,
                                   preset=str(preset) if preset else None, link_old=link_old)
    if created is None:
        raise HTTPException(
            status_code=404,
            detail=f"Run '{run_id}' has no input files to re-run",
        )
    new_run_id, owner_token = created

    return RunCreateResponse(
        run_id=new_run_id,
        status="queued",
        message=f"Run {new_run_id} queued successfully",
        results_url=f"/runs/{new_run_id}/status",
        owner_token=owner_token,
    )


def _queue_state_for(run_data: Dict[str, Any]) -> str:
    """Derive queue state from results.json: queued | running | done.

    A run is "queued" while its run dir exists but results.json has no
    started marker yet (pipeline.started_at missing — same derivation the
    status endpoint uses via pipeline.status/started_at). Once started,
    "running" while pipeline.status == "running"; terminal statuses
    (success/failed/cancelled/...) map to "done".

    bughunt BH-006: TERMINAL status wins over a missing started_at —
    a failed run that never started (e.g. reaped worker_lost) was
    reported "queued" and counted in other runs' `ahead`.
    """
    pipeline = run_data.get("pipeline", {})
    status = pipeline.get("status")
    if status == "retry_scheduled":
        return "queued"  # waiting for its next automatic attempt (retries.py)
    if status and status not in ("queued", "pending", "running", "created"):
        return "done"  # terminal: failed/success/cancelled/timeout/...
    if pipeline.get("status") == "running":
        return "running"
    if not pipeline.get("started_at"):
        return "queued"
    return "done"


@router.get("/{run_id}/queue", response_model=RunQueueResponse)
async def get_run_queue(run_id: RunId) -> RunQueueResponse:
    """Queue state for a single run.

    Returns:
        state: queued | running | done
        position: 1-based position among queued runs ordered by created_at
                  (queued runs only; null otherwise)
        ahead: number of queued runs ahead of this run (null otherwise)

    Raises:
        404: If run not found.
    """
    data = load_results_json(run_id)
    state = _queue_state_for(data)

    position: Optional[int] = None
    ahead: Optional[int] = None
    if state == "queued":
        # The cached run index (re-reads only changed results.json files):
        # reading every run's results here on each poll is the 2026-11-17
        # outage pattern (slow NFS, thousands of campaign runs).
        from src_new.api.run_index import summaries
        queued: List[tuple] = []
        for r in summaries(get_runs_dir()):
            row = {"created_at": r["created_at"],
                   "pipeline": {"status": r["status"], "started_at": r["started_at"]}}
            if _queue_state_for(row) != "queued":
                continue
            queued.append((r["created_at"] or "", r["run_id"]))
        queued.sort(key=lambda item: item[0])
        for idx, (_created, rid) in enumerate(queued, start=1):
            if rid == run_id:
                position = idx
                break
        if position is not None:
            ahead = position - 1

    return RunQueueResponse(state=state, position=position, ahead=ahead)
