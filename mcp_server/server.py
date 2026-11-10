"""BioID MCP server: tools over the BioID REST API.

Served over Streamable HTTP at /mcp (stateless, JSON responses: every tool
call is a short request; long runs are handled by submit-then-poll), with
/healthz for Kubernetes probes.
"""
from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import shlex
from pathlib import PurePosixPath
from typing import Annotated, Any, Optional

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import __version__
from . import format as fmt
from .client import BioIDClient, BioIDError, check_run_id
from .config import Settings
from .fetch import ACCEPTED_SUFFIXES, accepted_name, fetch_pdb_entry, fetch_url

log = logging.getLogger("bioid_mcp")

INSTRUCTIONS = """\
BioID identifies the molecules in a molecular-dynamics simulation or structure
file (proteins, nucleic acids, ligands, lipids, glycans, ions, water) by
searching public databases and verifying every hit against the simulated
molecule.

Workflow: submit (submit_structure for a PDB id or public https URL,
submit_files for small file content; for files on the user's machine or
larger than a few MB, call prepare_upload and run the command it returns, which
sends the files straight to the BioID REST API) -> you get a run_id -> poll
get_run_status every 1-2 minutes (runs take a few minutes up to about an hour)
-> when status is "success", call get_results, then get_molecule_details for
one molecule. Always give the user the results_page link. list_examples gives
finished demo runs to explore without submitting anything. Read the resource
bioid://guide for how to interpret confidence and verification. For the full
record of a run, get_results_json gives the results.json link, its documented
structure (resource bioid://results-json) and can extract one part of it.
"""

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True,
                            openWorldHint=True)
SUBMIT = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False,
                         openWorldHint=True)
CANCEL = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True,
                         openWorldHint=True)

MAX_FILES = 20


class InputFile(BaseModel):
    """One input file; give exactly one of `text` or `content_base64`."""

    name: str = Field(description="File name with its extension, e.g. 'protein.pdb', 'topol.tpr'.")
    text: Optional[str] = Field(
        None, description="File content as plain text (text formats: .pdb .cif .gro .top .itp "
                          ".psf .crd .data .prmtop .inpcrd .rst7).")
    content_base64: Optional[str] = Field(
        None, description="File content, base64-encoded (binary formats: .tpr .nc .dcd .xtc "
                          ".trr .zip .tar .tar.gz).")


def _dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, default=str)


def _fail(e: Exception) -> ToolError:
    return ToolError(str(e))


def _client_ip(ctx: Optional[Context]) -> Optional[str]:
    """X-Forwarded-For to pass on, so the API records the real requester
    (the API keeps the first hop) rather than this pod."""
    try:
        request = ctx.request_context.request if ctx is not None else None
    except (ValueError, AttributeError):
        return None
    if request is None or not hasattr(request, "headers"):
        return None
    hops = []
    xff = request.headers.get("x-forwarded-for")
    if xff:
        hops.append(xff.strip())
    client = getattr(request, "client", None)
    if client and client.host:
        hops.append(client.host)
    return ", ".join(hops) or None


def build_server(settings: Optional[Settings] = None, *,
                 api_transport: Optional[httpx.AsyncBaseTransport] = None,
                 fetch_transport: Optional[httpx.AsyncBaseTransport] = None) -> FastMCP:
    """Build the FastMCP server. Transports are injectable for tests."""
    settings = settings or Settings.from_env()
    client = BioIDClient(settings, transport=api_transport)
    # base64 inflates by 4/3, plus JSON-RPC framing
    body_limit = int(settings.max_upload_bytes * 4 / 3) + 1024 * 1024

    mcp = FastMCP(
        name="BioID",
        instructions=INSTRUCTIONS,
        website_url=settings.public_url,
        host=settings.host,
        port=settings.port,
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        max_request_body_size=body_limit,
    )
    mcp._mcp_server.version = __version__
    mcp.bioid_client = client  # type: ignore[attr-defined]  (tests / shutdown)

    # -- helpers ---------------------------------------------------------

    async def check_preset(preset: Optional[str]) -> Optional[str]:
        preset = (preset or "").strip() or None
        if preset is None:
            return None
        options = await client.config_options()
        if options is None:
            if preset == "balanced":
                return None  # the server default anyway
            raise BioIDError("This BioID server does not support presets yet; "
                             "omit 'preset' to run with the default settings.")
        ids = [p.get("id") for p in options.get("presets", []) if isinstance(p, dict)]
        if preset not in ids:
            raise BioIDError(f"Unknown preset '{preset}'. Available presets: {', '.join(map(str, ids))}.")
        return preset

    async def duration_hint() -> str:
        caps = await client.capabilities()
        rng = caps.get("typical_duration_minutes") if isinstance(caps, dict) else None
        if isinstance(rng, dict) and rng.get("min") is not None and rng.get("max") is not None:
            return (f"Typical runs take {rng['min']}-{rng['max']} minutes; large systems or the "
                    "'deep' preset can take up to about an hour.")
        return "Runs take from a few minutes up to about an hour for large systems."

    async def submit(files: list[tuple[str, bytes]], preset: Optional[str], run_name: Optional[str],
                     ctx: Optional[Context]) -> dict[str, Any]:
        total = sum(len(c) for _, c in files)
        if total > settings.max_upload_bytes:
            raise BioIDError(f"The files total {total / 1e6:.1f} MB; the limit here is "
                             f"{settings.max_upload_bytes / 1e6:.0f} MB. Call prepare_upload and run "
                             "its command to send the files straight to the BioID API "
                             "(128 MiB per file).")
        preset = await check_preset(preset)
        run_name = (run_name or "").strip()[:200] or None
        created = await client.create_run(files, run_name=run_name, preset=preset,
                                          client_ip=_client_ip(ctx))
        run_id = created.get("run_id")
        if not run_id:
            raise BioIDError(f"The BioID API did not return a run id: {_dumps(created)[:200]}")
        return {
            "run_id": run_id,
            "status": created.get("status", "queued"),
            "preset": preset or "balanced",
            "files": [{"name": n, "bytes": len(c)} for n, c in files],
            "results_page": settings.results_page(run_id),
            "next": "Call get_run_status with this run_id in 1-2 minutes. " + await duration_hint(),
        }

    # -- tools -------------------------------------------------------------

    @mcp.tool(annotations=READ_ONLY)
    async def list_presets() -> str:
        """List the run presets (named settings bundles) and what each changes
        relative to the server defaults. Pass a preset id to submit_structure or
        submit_files; without one, 'balanced' (the defaults) is used."""
        try:
            options = await client.config_options()
        except BioIDError as e:
            raise _fail(e)
        if options is None:
            return _dumps({
                "presets": [],
                "note": "This BioID server does not offer presets yet; runs use the server defaults.",
            })
        defaults = options.get("config") if isinstance(options.get("config"), dict) else None
        presets = []
        for p in options.get("presets", []):
            if not isinstance(p, dict):
                continue
            changes = fmt.summarize_overrides(p.get("overrides") or {}, defaults)
            presets.append({
                "id": p.get("id"),
                "title": p.get("title"),
                "description": p.get("description"),
                "changes": changes or ["none (server defaults)"],
            })
        return _dumps({"presets": presets, "default": "balanced"})

    @mcp.tool(annotations=SUBMIT)
    async def submit_structure(
        pdb_id: Annotated[Optional[str], Field(
            description="PDB entry id, e.g. '3PTB'. Downloaded from RCSB (PDB format, or mmCIF "
                        "for entries too large for PDB format).")] = None,
        url: Annotated[Optional[str], Field(
            description="Public https URL of one input file BioID can read (e.g. a .pdb, .cif, "
                        ".tpr or a .zip/.tar.gz bundle of topology + coordinates, such as a "
                        "Zenodo file link).")] = None,
        filename: Annotated[Optional[str], Field(
            description="Name (with extension) to give the downloaded file, when the URL "
                        "does not end in one.")] = None,
        preset: Annotated[Optional[str], Field(
            description="Preset id from list_presets: 'balanced' (default), 'quick', "
                        "'exact' or 'deep'.")] = None,
        run_name: Annotated[Optional[str], Field(description="Optional label for the run.")] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Start a BioID identification run for a PDB entry or a file at a public
        https URL (give exactly one of pdb_id or url). Returns a run_id at once;
        the run itself takes minutes, so poll get_run_status."""
        try:
            if bool(pdb_id) == bool(url):
                raise BioIDError("Give exactly one of 'pdb_id' or 'url'.")
            if pdb_id:
                name, content = await fetch_pdb_entry(
                    pdb_id, cap=settings.max_upload_bytes, timeout=settings.fetch_timeout_s,
                    transport=fetch_transport)
                default_name = f"PDB {name.rsplit('.', 1)[0]}>Fetched from RCSB PDB via the BioID MCP server"
            else:
                name, content = await fetch_url(
                    url, cap=settings.max_upload_bytes, timeout=settings.fetch_timeout_s,
                    filename=filename, transport=fetch_transport)
                name = PurePosixPath(name).name
                if not accepted_name(name):
                    raise BioIDError(
                        f"The downloaded file is named '{name}', which is not a format BioID reads "
                        f"({', '.join(ACCEPTED_SUFFIXES)}). Pass 'filename' with the right extension "
                        "if the URL hides it.")
                default_name = f"{name}>Fetched from a URL via the BioID MCP server"
            return _dumps(await submit([(name, content)], preset, run_name or default_name, ctx))
        except BioIDError as e:
            raise _fail(e)

    @mcp.tool(annotations=SUBMIT)
    async def submit_files(
        files: Annotated[list[InputFile], Field(
            description="The input files of one system, e.g. [topol.tpr] or [system.top, "
                        "system.gro, ligand.itp] or [complex.prmtop, complex.inpcrd].")],
        preset: Annotated[Optional[str], Field(
            description="Preset id from list_presets: 'balanced' (default), 'quick', "
                        "'exact' or 'deep'.")] = None,
        run_name: Annotated[Optional[str], Field(description="Optional label for the run.")] = None,
        ctx: Optional[Context] = None,
    ) -> str:
        """Start a BioID identification run from file content you provide (text or
        base64). Accepted: GROMACS .tpr or .top+.itp+.gro; AMBER .prmtop/.parm7 with
        .rst7/.inpcrd/.nc/.mdcrd; CHARMM/NAMD .psf with .pdb/.crd/.dcd; LAMMPS .data;
        .pdb/.cif structures; .zip/.tar/.tar.gz bundles. All files of one system go
        in one call. Returns a run_id at once; poll get_run_status."""
        try:
            if not files:
                raise BioIDError("No files given.")
            if len(files) > MAX_FILES:
                raise BioIDError(f"At most {MAX_FILES} files per run; bundle more as a .zip.")
            prepared: list[tuple[str, bytes]] = []
            seen: set[str] = set()
            for f in files:
                name = PurePosixPath((f.name or "").replace("\\", "/")).name.strip()
                if not name or name in (".", ".."):
                    raise BioIDError(f"Invalid file name {f.name!r}.")
                if not accepted_name(name):
                    raise BioIDError(f"'{name}' is not a format BioID reads "
                                     f"({', '.join(ACCEPTED_SUFFIXES)}).")
                if name in seen:
                    raise BioIDError(f"Duplicate file name '{name}'.")
                seen.add(name)
                if (f.text is None) == (f.content_base64 is None):
                    raise BioIDError(f"'{name}': give exactly one of 'text' or 'content_base64'.")
                if f.text is not None:
                    content = f.text.encode("utf-8")
                else:
                    try:
                        content = base64.b64decode(f.content_base64 or "", validate=False)
                    except (binascii.Error, ValueError) as e:
                        raise BioIDError(f"'{name}': content_base64 is not valid base64.") from e
                if not content:
                    raise BioIDError(f"'{name}' is empty.")
                prepared.append((name, content))
            return _dumps(await submit(prepared, preset, run_name, ctx))
        except BioIDError as e:
            raise _fail(e)

    @mcp.tool(annotations=READ_ONLY)
    async def get_run_status(
        run_id: Annotated[str, Field(description="Run id returned by a submit tool.")],
    ) -> str:
        """Progress of a run: queued/running/success/failed/cancelled, the current
        stage, molecules searched so far, failed database searches, and errors.
        Poll every 1-2 minutes until the status is final."""
        try:
            run_id = check_run_id(run_id)
            data = await client.status(run_id)
            pipeline = data.get("pipeline") or {}
            status = pipeline.get("status") or "unknown"
            out: dict[str, Any] = {"run_id": run_id, "status": status}
            summary = None
            try:
                summary = await client.summary(run_id)
            except BioIDError:
                pass
            title, desc = fmt.split_run_name((summary or {}).get("run_name"))
            if title:
                out["title"] = title
            if desc:
                out["description"] = desc
            if pipeline.get("input_kind"):
                out["input_kind"] = pipeline["input_kind"]
            if pipeline.get("started_at"):
                out["started_at"] = pipeline["started_at"]
            if pipeline.get("finished_at"):
                out["finished_at"] = pipeline["finished_at"]
            minutes = fmt.elapsed_minutes(pipeline.get("started_at"), pipeline.get("finished_at"))
            if minutes is not None:
                out["elapsed_minutes"] = minutes

            tasks = data.get("tasks") or []
            done = [t for t in tasks if t.get("status") in ("success", "warning", "skipped")]
            running = [t for t in tasks if t.get("status") == "running"]
            if tasks:
                out["stages_done"] = f"{len(done)}/{len(tasks)}"
                out["stages"] = [f"{t.get('name') or t.get('task_id')}: {t.get('status')}" for t in tasks]
            if running:
                out["current_stage"] = running[0].get("name") or running[0].get("task_id")
            progress = data.get("progress")
            if isinstance(progress, dict) and progress.get("molecules_total"):
                out["molecules_searched"] = f"{progress.get('molecules_done', 0)}/{progress['molecules_total']}"

            if status in ("queued", "pending", "created"):
                try:
                    q = await client.queue(run_id)
                    if q.get("position") is not None:
                        out["queue_position"] = q["position"]
                        out["runs_ahead"] = q.get("ahead")
                except BioIDError:
                    pass

            errors = [e.get("message") for e in data.get("critical_errors") or [] if e.get("message")]
            if errors:
                out["errors"] = [m[:400] for m in errors[:5]]
            warnings = data.get("warnings") or []
            failed_searches: list[str] = []
            other: dict[str, int] = {}
            for w in warnings:
                if w.get("code") == "identifier_resolver_failed":
                    details = w.get("details") or {}
                    msg = (w.get("message") or "")
                    reason = msg.split(": ", 1)[1] if ": " in msg else msg
                    reason = reason.split(". ", 1)[0]  # drop server paths etc.
                    item = f"{details.get('service') or msg.split(' ', 1)[0]}" \
                           f"{' [' + details['segment'] + ']' if details.get('segment') else ''}: {reason[:120]}"
                    if item not in failed_searches:
                        failed_searches.append(item)
                else:
                    other[w.get("code") or "warning"] = other.get(w.get("code") or "warning", 0) + 1
            if failed_searches:
                out["failed_searches"] = failed_searches[:10]
                if len(failed_searches) > 10:
                    out["failed_searches_more"] = len(failed_searches) - 10
            if other:
                out["warnings"] = other

            if status == "failed":
                try:
                    loading = await client.loading(run_id)
                    failure = loading.get("failure_summary")
                    if failure:
                        out["load_failure"] = failure
                except BioIDError:
                    pass

            out["results_page"] = settings.results_page(run_id)
            if status == "success":
                out["next"] = "Finished. Call get_results."
            elif status == "failed":
                out["next"] = "The run failed; explain the errors above to the user. Fixing the input and resubmitting may help."
            elif status == "cancelled":
                out["next"] = "The run was cancelled."
            else:
                out["next"] = "Still in progress; check again in 1-2 minutes. " + await duration_hint()
            return _dumps(out)
        except BioIDError as e:
            raise _fail(e)

    @mcp.tool(annotations=READ_ONLY)
    async def get_results(
        run_id: Annotated[str, Field(description="Run id returned by a submit tool or list_examples.")],
        max_molecules: Annotated[int, Field(ge=1, le=500, description="Cap on molecules listed.")] = 100,
    ) -> str:
        """Identification results of a run: for each molecule (segment) its kind,
        copies, and best verified database match (name, database id, confidence,
        evidence) plus the other databases that also matched. Use
        get_molecule_details for all hits of one molecule."""
        try:
            run_id = check_run_id(run_id)
            summary, molecules, verification = await asyncio.gather(
                client.summary(run_id), client.molecules(run_id), client.verification(run_id))
            status = summary.get("status") or "unknown"
            title, desc = fmt.split_run_name(summary.get("run_name"))
            by_seg = fmt.hits_by_segment(verification)
            finished = status in fmt.TERMINAL
            rows = []
            states: dict[str, int] = {}
            for seg, meta in fmt.molecule_rows(molecules):
                row = fmt.molecule_head(seg, meta)
                hits = by_seg.get(seg)
                if hits is None and status != "success":
                    # failed/cancelled before verifying it, or not there yet
                    row["state"] = "not_searched" if finished else "pending"
                else:
                    # a finished run without hits for a molecule searched it
                    # and verified nothing (as the web UI shows it)
                    row.update(fmt.identification(hits or []))
                states[row["state"]] = states.get(row["state"], 0) + 1
                rows.append(row)
            out: dict[str, Any] = {"run_id": run_id, "status": status}
            if title:
                out["title"] = title
            if desc:
                out["description"] = desc
            if summary.get("input_kind"):
                out["input_kind"] = summary["input_kind"]
            out["summary"] = {"molecules": len(rows), **states}
            out["molecules"] = rows[:max_molecules]
            if len(rows) > max_molecules:
                out["truncated"] = f"{len(rows) - max_molecules} more molecules not shown; raise max_molecules."
            if status in ("queued", "running", "created", "pending"):
                out["note"] = ("The run is still in progress: identifications appear once the "
                               "'Verify Results' stage is done. Check get_run_status.")
            elif status == "failed":
                out["note"] = "The run failed; results may be incomplete. See get_run_status for the error."
            elif status == "cancelled":
                out["note"] = "The run was cancelled; results may be incomplete."
            out["how_to_read"] = ("confidence 0-100 (>=80 high, 50-80 medium, <50 low = 'lead'); only "
                                  "verified hits count; state 'exact' = element match; 'not_identified' = "
                                  "nothing passed verification. Resource bioid://guide has details.")
            out["results_page"] = settings.results_page(run_id)
            out["results_csv"] = settings.results_csv(run_id)
            out["results_json"] = settings.results_json(run_id)
            out["results_json_docs"] = settings.results_json_docs
            return _dumps(out)
        except BioIDError as e:
            raise _fail(e)

    @mcp.tool(annotations=READ_ONLY)
    async def get_molecule_details(
        run_id: Annotated[str, Field(description="Run id.")],
        molecule: Annotated[str, Field(
            description="The 'molecule' value from get_results (segment id, e.g. 'A' or "
                        "'A__v1'); a unique display name such as 'BEN' also works.")],
        max_hits: Annotated[int, Field(ge=1, le=100, description="Cap on verified hits listed.")] = 10,
    ) -> str:
        """Everything BioID found for one molecule of a run: its descriptors
        (sequence, SMILES, formula, InChIKey, residue name), the verified database
        hits ranked by confidence, rejected hits with the reason, and database
        searches that failed for it."""
        try:
            run_id = check_run_id(run_id)
            molecules = await client.molecules(run_id)
            rows = fmt.molecule_rows(molecules)
            wanted = (molecule or "").strip()
            seg = next((s for s, _ in rows if s == wanted), None)
            if seg is None:
                low = wanted.lower()
                matches = [s for s, m in rows
                           if s.lower() == low or str(m.get("display_name") or "").lower() == low]
                if len(matches) == 1:
                    seg = matches[0]
                elif len(matches) > 1:
                    raise BioIDError(f"'{wanted}' matches several molecules ({', '.join(matches[:20])}); "
                                     "use the 'molecule' value from get_results.")
                else:
                    names = [f"{s} ({m.get('display_name')})" if m.get("display_name") not in (None, s) else s
                             for s, m in rows[:40]]
                    raise BioIDError(f"Run '{run_id}' has no molecule '{wanted}'. Molecules: "
                                     f"{', '.join(names) or 'none yet'}.")
            meta = dict(rows)[seg]
            verification, signatures, status = await asyncio.gather(
                client.verification(run_id, seg), client.signatures(run_id, seg), client.status(run_id))

            out: dict[str, Any] = {"run_id": run_id, **fmt.molecule_head(seg, meta)}
            descriptors = _descriptors(signatures.get("signatures") or [])
            if descriptors:
                out["descriptors"] = descriptors
            hits = [h for h in verification.get("hits") or [] if (h.get("segment") or seg) == seg]
            ident = fmt.identification(hits)
            out["state"] = ident["state"]
            verified = fmt.sorted_verified(hits)
            out["verified"] = [fmt.hit_view(h, full=True) for h in verified[:max_hits]]
            if len(verified) > max_hits:
                out["verified_more"] = len(verified) - max_hits
            per_db: dict[str, int] = {}
            for h in verified:
                label = fmt.db_label(h.get("database"))
                per_db[label] = per_db.get(label, 0) + 1
            if per_db:
                out["verified_by_database"] = per_db
            rejected = [h for h in hits if not h.get("is_verified")]
            if rejected:
                out["rejected"] = [
                    {k: v for k, v in {
                        "database": fmt.db_label(h.get("database")),
                        "id": h.get("identifier"),
                        "name": h.get("name"),
                        "reason": fmt.rejection_clause(h.get("rejection_reason")),
                        "raw_reason": h.get("rejection_reason"),
                    }.items() if v is not None}
                    for h in rejected[:5]
                ]
                out["rejected_total"] = len(rejected)
            failed = []
            for w in status.get("warnings") or []:
                details = w.get("details") or {}
                if w.get("code") == "identifier_resolver_failed" and details.get("segment") == seg:
                    msg = (w.get("message") or "").split(". ", 1)[0][:160]
                    if msg not in failed:
                        failed.append(msg)
            if failed:
                out["failed_searches"] = failed[:10]
            if not hits and (status.get("pipeline") or {}).get("status") not in fmt.TERMINAL:
                out["note"] = "The run is still in progress; hits appear after verification."
            out["results_page"] = settings.results_page(run_id)
            return _dumps(out)
        except BioIDError as e:
            raise _fail(e)

    @mcp.tool(annotations=READ_ONLY)
    async def list_examples(
        limit: Annotated[int, Field(ge=1, le=10, description="How many examples.")] = 5,
    ) -> str:
        """Finished example runs shown on the BioID front page (e.g. a crystal
        structure, a GROMACS membrane protein, an AMBER protein-DNA complex). Use
        their run_id with get_results to see what BioID output looks like
        without submitting anything."""
        try:
            data = await client.examples(limit)
        except BioIDError as e:
            raise _fail(e)
        out = []
        for ex in data.get("examples") or []:
            run_id = ex.get("run_id")
            if not run_id:
                continue
            item = {"run_id": run_id, "title": ex.get("title")}
            if ex.get("description"):
                item["description"] = ex["description"]
            if ex.get("created_at"):
                item["created_at"] = ex["created_at"]
            item["results_page"] = settings.results_page(run_id)
            if ex.get("image_url"):
                item["image"] = settings.public_url + ex["image_url"] if ex["image_url"].startswith("/") else ex["image_url"]
            out.append(item)
        return _dumps({"examples": out})

    @mcp.tool(annotations=READ_ONLY)
    async def prepare_upload(
        file_paths: Annotated[list[str], Field(
            description="Paths of the input files of one system on the machine where the "
                        "command will run, e.g. ['md/topol.tpr'] or ['sys.prmtop', 'sys.inpcrd'].")],
        preset: Annotated[Optional[str], Field(
            description="Preset id from list_presets: 'balanced' (default), 'quick', "
                        "'exact' or 'deep'.")] = None,
        run_name: Annotated[Optional[str], Field(description="Optional label for the run.")] = None,
    ) -> str:
        """For files on the user's machine, or too large to pass as content: returns a
        ready curl command (and a Python equivalent) that uploads the files straight
        to the BioID REST API (128 MiB per file) and prints the new run's id as JSON.
        Run it with your shell tool (or give it to the user), then poll
        get_run_status with the run_id it prints. Nothing is submitted by this tool."""
        try:
            if not file_paths:
                raise BioIDError("No files given.")
            if len(file_paths) > MAX_FILES:
                raise BioIDError(f"At most {MAX_FILES} files per run; bundle more as a .zip.")
            for path in file_paths:
                name = PurePosixPath(path.replace("\\", "/")).name
                if not accepted_name(name):
                    raise BioIDError(f"'{name}' is not a format BioID reads "
                                     f"({', '.join(ACCEPTED_SUFFIXES)}).")
            preset = await check_preset(preset)
            run_name = (run_name or "").strip()[:200] or None
            fields = [f"files=@{p}" for p in file_paths]
            if preset:
                fields.append(f"preset={preset}")
            if run_name:
                fields.append(f"run_name={run_name}")
            curl = " ".join(["curl", "-sS", "--fail-with-body"]
                            + [f"-F {shlex.quote(f)}" for f in fields] + [settings.runs_api])
            data = {k: v for k, v in (("preset", preset), ("run_name", run_name)) if v}
            python = (
                "import requests\n"
                f"paths = {file_paths!r}\n"
                "files = [('files', open(p, 'rb')) for p in paths]\n"
                f"r = requests.post({settings.runs_api!r}, files=files, data={data!r}, timeout=600)\n"
                "r.raise_for_status(); print(r.json()['run_id'])"
            )
            return _dumps({
                "curl": curl,
                "python": python,
                "returns": '{"run_id": "...", "status": "queued", ...}',
                "next": "Run the command where the files are, then call get_run_status with the run_id.",
                "limits": "128 MiB per file; GROMACS, AMBER, CHARMM/NAMD, LAMMPS, PDB/mmCIF or a zip/tar bundle.",
                "api_docs": settings.api_docs,
            })
        except BioIDError as e:
            raise _fail(e)

    @mcp.tool(annotations=READ_ONLY)
    async def get_results_json(
        run_id: Annotated[str, Field(description="Run id.")],
        path: Annotated[Optional[str], Field(
            description="Optional slash-separated path into results.json to return, e.g. "
                        "'data/verification/A' or 'data/fragments/segments' or 'warnings'. "
                        "Omit to get the download link and the structure guide.")] = None,
        max_kb: Annotated[int, Field(ge=1, le=1000,
                                     description="Cap on the returned JSON size, in kB.")] = 100,
    ) -> str:
        """The complete record of a run (results.json): without `path`, its download
        URL, documentation link and a guide to its structure; with `path`, that part
        of the document as JSON (truncated to max_kb). Fetch the URL yourself if you
        need the whole file (1-5 MB)."""
        try:
            run_id = check_run_id(run_id)
            links = {"run_id": run_id, "download_url": settings.results_json(run_id),
                     "documentation": settings.results_json_docs}
            if not path or not path.strip("/"):
                await client.summary(run_id)  # 404 early for a wrong id
                return _dumps({**links, "structure": fmt.RESULTS_JSON_GUIDE.format(
                    docs=settings.results_json_docs, api=settings.runs_api)})
            node: Any = await client.results_json(run_id)
            walked: list[str] = []
            for part in [p for p in path.strip("/").split("/") if p]:
                if isinstance(node, dict) and part in node:
                    node = node[part]
                elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                    node = node[int(part)]
                else:
                    keys = list(node)[:50] if isinstance(node, dict) else (
                        f"list of {len(node)}" if isinstance(node, list) else type(node).__name__)
                    raise BioIDError(f"'{part}' not found under '/{'/'.join(walked)}'. "
                                     f"Available: {keys}")
                walked.append(part)
            text = json.dumps(node, ensure_ascii=False, default=str)
            limit = max_kb * 1024
            out: dict[str, Any] = {**links, "path": "/".join(walked)}
            if len(text) > limit:
                out["truncated"] = (f"{len(text) // 1024} kB, showing the first {max_kb} kB; "
                                    "narrow the path, raise max_kb or download the file.")
                if isinstance(node, dict):
                    out["keys"] = list(node)[:200]
                out["json_prefix"] = text[:limit]
            else:
                out["value"] = node
            return _dumps(out)
        except BioIDError as e:
            raise _fail(e)

    @mcp.tool(annotations=CANCEL)
    async def cancel_run(
        run_id: Annotated[str, Field(description="Run id to cancel.")],
    ) -> str:
        """Cancel a queued or running run (for example one submitted by mistake).
        Finished runs cannot be cancelled."""
        try:
            run_id = check_run_id(run_id)
            try:
                result = await client.cancel(run_id)
            except BioIDError as e:
                if "terminal state" in str(e):
                    state = str(e).rsplit(":", 1)[-1].strip().rstrip(".")
                    raise BioIDError(f"Run '{run_id}' has already finished ({state}); nothing to cancel.") from e
                raise
            return _dumps({"run_id": run_id, "status": result.get("status", "cancelled"),
                           "results_page": settings.results_page(run_id)})
        except BioIDError as e:
            raise _fail(e)

    # -- resource / prompt -------------------------------------------------

    @mcp.resource("bioid://guide", name="bioid-guide", title="How to read BioID results",
                  mime_type="text/plain")
    def guide() -> str:
        """How to interpret BioID confidence, verification and result states."""
        return fmt.GUIDE

    @mcp.resource("bioid://results-json", name="bioid-results-json",
                  title="Structure of results.json", mime_type="text/plain")
    def results_json_guide() -> str:
        """Where things are in a run's results.json, with the documentation link."""
        return fmt.RESULTS_JSON_GUIDE.format(docs=settings.results_json_docs, api=settings.runs_api)

    @mcp.prompt(name="explain_run", title="Explain a BioID run")
    def explain_run(run_id: str) -> str:
        """Explain the results of a BioID run to the user."""
        return (
            f"Use the BioID tools to explain run {run_id}. Call get_run_status first; if it "
            "has finished, call get_results and, for proteins/nucleic acids and ligands, "
            "get_molecule_details. Summarise what the simulated system contains, how confident "
            "each identification is and why (evidence), point out molecules that were not "
            "identified or only weakly (leads), and any failed database searches. End with the "
            "results_page link.\n\n" + fmt.GUIDE
        )

    # -- probes -------------------------------------------------------------

    @mcp.custom_route("/healthz", methods=["GET"], include_in_schema=False)
    async def healthz(_request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok", "version": __version__})

    return mcp


_SEQUENCE_GENERATORS = ("fasta_map_protein", "fasta_resname_protein")


def _descriptors(signatures: list[dict[str, Any]]) -> dict[str, Any]:
    """The readable signatures (no coordinate blobs or fingerprints)."""
    by_gen = {s.get("generator"): s.get("signature") for s in signatures if isinstance(s, dict)}
    out: dict[str, Any] = {}

    def text(v: Any) -> Optional[str]:
        if isinstance(v, str):
            return v
        if isinstance(v, dict):
            for k in ("sequence", "fasta", "value", "text"):
                if isinstance(v.get(k), str):
                    return v[k]
        return None

    seq_gen = next((g for g in _SEQUENCE_GENERATORS if g in by_gen), None) or next(
        (g for g in by_gen if isinstance(g, str) and g.startswith("fasta")), None)
    if seq_gen:
        seq = text(by_gen[seq_gen])
        if seq:
            seq = "".join(line for line in seq.splitlines() if not line.startswith(">")).strip()
            out["sequence_length"] = len(seq)
            out["sequence"] = seq if len(seq) <= 3000 else seq[:3000] + "...(truncated)"
    smiles = text(by_gen.get("smiles_not_sanitized")) or text(by_gen.get("smiles"))
    if smiles:
        out["smiles"] = smiles[:2000]
        out["smiles_note"] = ("connectivity from the simulation topology; bond orders and "
                              "hydrogens may be missing")
    for gen, key in (("inchi_key", "inchi_key"), ("molecular_formula_heavy", "formula_heavy_atoms"),
                     ("resname", "residue_name")):
        val = text(by_gen.get(gen))
        if val:
            out[key] = val[:300]
    return out


def create_app():
    """ASGI app for uvicorn (``uvicorn --factory mcp_server.server:create_app``)."""
    return build_server().streamable_http_app()
