"""Pydantic v2 models for BAT3 Pipeline API responses."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# 2026-11-21 (mdval audit item 7): next to `status` (which stays "success"
# for a partial run) in the status, summary and run list (completeness.state).
COMPLETENESS = ("How complete a successful run is: complete, partial (a stage ran out of time, "
                "see partial_stages) or incomplete (remote lookups failed, see incomplete); "
                "null until the run has succeeded")
PARTIAL_STAGES = "Stages that ran out of their time budget; their results are partial"


class PipelineStatusResponse(BaseModel):
    """Response model for pipeline status."""

    run_id: str = Field(..., description="The run id")
    pipeline_name: str = Field(..., description="Always BAT3")
    status: str = Field(..., description="queued, running, success, failed or cancelled")
    started_at: Optional[str] = Field(None, description="ISO 8601 timestamp when pipeline started")
    finished_at: Optional[str] = Field(None, description="ISO 8601 timestamp when pipeline finished")
    input_kind: Optional[str] = Field(None, description="How the input was read: tpr, gro, amber, charmm, lammps, pdb, cif, ...")
    completeness: Optional[str] = Field(None, description=COMPLETENESS)
    partial_stages: List[str] = Field(default_factory=list, description=PARTIAL_STAGES)
    input_files: Optional[Dict[str, str]] = Field(None, description="The input files by role (topology, coordinates, ...)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Working directories on the server")


class TaskInfo(BaseModel):
    """Information about a single task in the pipeline."""

    task_id: str = Field(..., description="Stage id, e.g. load_simulation, identify_molecules")
    name: str = Field(..., description="Stage name for display")
    status: str = Field(..., description="Task status: pending/running/success/failed/warning/skipped")
    started_at: Optional[str] = Field(None, description="ISO 8601 timestamp when task started")
    finished_at: Optional[str] = Field(None, description="ISO 8601 timestamp when task finished")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Stage results in brief (counts, choices made)")
    artifacts: List[str] = Field(default_factory=list, description="Names of the results this stage stored")


class WarningItem(BaseModel):
    """A warning recorded during pipeline execution."""

    code: str = Field(..., description="Stable code; explained at docs_url")
    message: str = Field(..., description="Warning message")
    step_id: Optional[str] = Field(None, description="Stage that recorded it")
    details: Dict[str, Any] = Field(default_factory=dict, description="Context, often segment (the molecule) and service (the database or search)")
    recorded_at: Optional[str] = Field(None, description="ISO 8601 timestamp when warning was recorded")
    docs_url: Optional[str] = Field(None, description="Path on the BioID host of the documentation section explaining this code")


class ErrorItem(BaseModel):
    """An error recorded during pipeline execution."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    step_id: Optional[str] = Field(None, description="Stage that recorded it")
    details: Dict[str, Any] = Field(default_factory=dict, description="Context, often segment and service")
    critical: bool = Field(default=False, description="Whether this is a critical error")
    exception_type: Optional[str] = Field(None, description="Exception class, for bug reports")
    recorded_at: Optional[str] = Field(None, description="ISO 8601 timestamp when error was recorded")
    docs_url: Optional[str] = Field(None, description="Path on the BioID host of the documentation section explaining this code")


class EventItem(BaseModel):
    """An event recorded during pipeline execution."""

    kind: str = Field(..., description="Event kind: log/step_start/step_finish")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    level: Optional[str] = Field(None, description="Log level for log events")
    message: Optional[str] = Field(None, description="Event message")
    task_id: Optional[str] = Field(None, description="Associated task ID")


class RunStageProgress(BaseModel):
    """Per-molecule identification progress (v3.143, BACKEND_GAPS G2).

    Computed read-side from persisted state: a segment is "searched"
    once its identifiers block exists, "searching" while the
    identify_molecules stage is running for a segment that already has
    signatures, and "waiting" otherwise. Only segments the pipeline
    decided to identify (fragments/segments ∪ signature-bearing universe
    segments) participate — checking-only and signature-less molecules
    are excluded and keep the UI's own not_searched rendering.
    """

    molecules_done: int = Field(..., description="Molecules whose database searches have finished")
    molecules_total: int = Field(..., description="Molecules in the system")
    per_segment: Dict[str, str] = Field(
        default_factory=dict,
        description="waiting|searching|searched per segment name",
    )


class RetentionInfo(BaseModel):
    """How long a run is kept."""

    policy: str = Field(..., description="default, days or preserve")
    days: Optional[int] = Field(None, description="Retention period in days (null when preserved)")
    expires_at: Optional[str] = Field(None, description="ISO 8601 time the run is deleted; null = never or not finished")
    example: bool = Field(False, description="An example run: never deleted")
    owner_choices: List[int] = Field(default_factory=list, description="Days the owner may choose with POST /runs/{id}/retention")


class ReportCreate(BaseModel):
    """'This identification looks wrong' for one molecule of a run."""

    segment: str = Field(..., description="The molecule's segment name, as in results.json")
    note: str = Field("", max_length=2000, description="What looks wrong (optional)")
    suggestion: str = Field("", max_length=200, description="What the molecule really is, if known (optional)")


class RetentionChange(BaseModel):
    """Keep a finished run longer (owner only)."""

    days: int = Field(..., description="Keep the run this many days from now: 30, 90, 180 or 365")


class IncompleteItem(BaseModel):
    """Lookups a run lacks for a reason another attempt could fix (POST /rerun repeats them)."""

    code: str = Field(..., description="Warning code that records the gap")
    service: str = Field(..., description="The database, service or stage that failed")
    reason: str = Field(..., description="server_error, rate_limited, timeout, connection or budget")
    segments: List[str] = Field(default_factory=list, description="Molecules (segments) affected")
    count: int = Field(..., description="Number of failed lookups")
    example: str = Field("", description="One of the recorded messages")


class RetryInfo(BaseModel):
    """The next automatic attempt of a run (queues with automatic retries)."""

    attempt: int = Field(..., description="Number of the attempt that just finished")
    max_attempts: int = Field(..., description="Attempts allowed in all")
    reason: str = Field(..., description="incomplete or worker_lost")
    at: float = Field(..., description="When the next attempt is queued (unix seconds)")


class AttemptInfo(BaseModel):
    """An earlier attempt of an automatically retried run."""

    attempt: int
    reason: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    gaps: List[Dict[str, Any]] = Field(default_factory=list)


class RestartInfo(BaseModel):
    """2026-11-23: a time the run's worker shut down mid-run (redeploy,
    scale-down) and the run was queued again under the same run id. Not an
    attempt: it is not counted against the automatic retries."""

    restart: int
    reason: str = Field("worker_restart", description="worker_restart")
    started_at: Optional[str] = Field(None, description="When the interrupted execution started (null: before it did)")
    stopped_at: Optional[str] = Field(None, description="When it was stopped and the run queued again")


class RunStatusResponse(BaseModel):
    """Full run status response."""

    run_id: str = Field(..., description="The run id")
    pipeline: PipelineStatusResponse = Field(..., description="Pipeline status information")
    tasks: List[TaskInfo] = Field(default_factory=list, description="List of task information")
    warnings: List[WarningItem] = Field(default_factory=list, description="List of warnings")
    critical_errors: List[ErrorItem] = Field(default_factory=list, description="List of critical errors")
    events: List[EventItem] = Field(default_factory=list, description="List of events")
    updated_at: Optional[str] = Field(None, description="ISO 8601 timestamp when results were last updated")
    # v3.143 (BACKEND_GAPS G2): additive — null while identification has
    # no segments planned yet (pre-analysis / no identifiable molecules).
    progress: Optional[RunStageProgress] = Field(
        None, description="Per-segment identification progress")
    retention: Optional[RetentionInfo] = Field(None, description="How long the run is kept")
    incomplete: List[IncompleteItem] = Field(
        default_factory=list, description="Lookups that failed for reasons a rerun could fix")
    queue: str = Field("web", description="Queue the run was submitted to: web or repository")
    retry: Optional[RetryInfo] = Field(
        None, description="Set while the run waits for its next automatic attempt (status shows queued)")
    attempts: List[AttemptInfo] = Field(default_factory=list, description="Earlier automatic attempts")
    restarts: List[RestartInfo] = Field(
        default_factory=list,
        description="Times the run's worker restarted mid-run and the run was queued again under the same id")
    rerun_of: Optional[str] = Field(None, description="Run this one re-runs")
    superseded_by: Optional[str] = Field(None, description="Newer run of the same input, by its owner")


class LoadingAttemptInfo(BaseModel):
    """Information about a loading attempt."""

    strategy: str = Field(..., description="Loading strategy name")
    success: bool = Field(..., description="Whether the attempt succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[str] = Field(None, description="Stable code of the failure, if it failed")


class LoadingInfoResponse(BaseModel):
    """Response model for loading information."""

    run_id: str = Field(..., description="The run id")
    input_kind: Optional[str] = Field(None, description="How the input was read: tpr, gro, amber, charmm, lammps, pdb, cif, ...")
    selected_strategy: Optional[str] = Field(None, description="Selected loading strategy")
    topology_files: List[str] = Field(default_factory=list, description="Topology files found")
    attempts: List[LoadingAttemptInfo] = Field(default_factory=list, description="Loading attempts")
    final_strategy: Optional[str] = Field(None, description="Final successful strategy")
    success: bool = Field(default=False, description="Whether loading succeeded")
    warnings: List[str] = Field(default_factory=list, description="Loading warnings")
    failure_summary: Optional[dict] = Field(None, description="Why loading failed: reason, message, details (null when it worked)")


class MoleculeInstanceInfo(BaseModel):
    """Information about a molecule instance."""

    segment_ids: List[str] = Field(default_factory=list, description="Segment ids of the copies")
    # v3.143 (BACKEND_GAPS G7): additive — the full segment list of the
    # unique group (all identical instances, e.g. chains A–D), as stored
    # under fragments/unique/<key>/segment_names. segment_ids remains the
    # representative instance's segments for legacy consumers; empty on
    # runs written before the store recorded the group.
    segment_names: List[str] = Field(default_factory=list, description="All identical segments in the unique group")
    molecule_type: Optional[str] = Field(None, description="Molecule type")
    atom_count: int = Field(..., description="Number of atoms")
    residue_count: int = Field(..., description="Number of residues")
    smiles: Optional[str] = Field(None, description="SMILES string if available")


class MoleculeSummaryResponse(BaseModel):
    """Response model for molecule summary."""

    run_id: str = Field(..., description="The run id")
    unique_molecules: Dict[str, MoleculeInstanceInfo] = Field(
        default_factory=dict, description="Unique molecules by key"
    )
    type_counts: Dict[str, int] = Field(default_factory=dict, description="Number of distinct molecules per type (protein, nucleic, small_molecule, lipid, glycan, ion, water)")
    total_fragment_count: int = Field(default=0, description="Number of molecules counting every copy (62 waters count 62)")
    segments: List[str] = Field(default_factory=list, description="The molecules, by segment name (use these with ?segment=)")
    segment_meta: Optional[Dict[str, Any]] = Field(
        default=None, description="Metadata for each segment (type, atom_count, etc.)"
    )


class RenderSegmentSelector(BaseModel):
    """Per-segment selector into the system mmCIF (BACKEND_GAPS G9, additive).

    Persisted at export under ``render/segment_selectors``.
    ``atom_index_ranges`` are merged ``[start, end_exclusive)`` ranges of
    the segment's rows in the exported file's atom_site loop (0-based;
    ``_atom_site.id`` = row + 1, MMCIFIO numbering). Exact even for
    virtual minority segments whose atoms share the parent
    ``auth_asym_id`` chain (``chains``)."""

    chains: List[str] = Field(default_factory=list, description="Chains (mmCIF auth_asym_id) of the molecule in system.mmcif")
    atom_index_ranges: List[List[int]] = Field(default_factory=list, description="Where the molecule's atoms are in system.mmcif: [start, end) atom rows, 0-based (atom id = row + 1)")
    atom_count: int = Field(0, description="Atoms in those ranges")
    residue_ranges: Optional[List[List[Union[str, int]]]] = Field(
        None,
        description="All copies as [auth_asym_id, beg_auth_seq_id, end_auth_seq_id] "
                    "ranges (inclusive), exact: no other segment has a residue "
                    "inside them; absent when numbers are shared (use the atom ranges)")


class RenderPathsResponse(BaseModel):
    """Structure files and pictures of a run, and where each molecule is in the system structure."""

    run_id: str = Field(..., description="The run id")
    system_mmcif: Optional[str] = Field(None, description="Path to system mmCIF file")
    segments: Dict[str, str] = Field(
        default_factory=dict, description="Mapping of segment name to mmCIF path"
    )
    system_png: Optional[str] = Field(
        None, description="Static system PNG (path relative to run dir, served under /files/)"
    )
    segment_pngs: Dict[str, str] = Field(
        default_factory=dict, description="Mapping of segment name to static PNG path"
    )
    total_atom_count: Optional[int] = Field(
        None, description="System-wide atom count incl. solvent (UI interactivity gate)"
    )
    geometry: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Geometry status of the exported system mmCIF (v3.139). Keys: status "
            "('ok'|'degenerate'|'unknown'), density_a3_per_atom, atom_count, span. "
            "Absent for runs predating the scale-guard wave — the UI falls back "
            "to its client-side probe."
        ),
    )
    # v3.143 (BACKEND_GAPS G9, additive): per-segment selectors into the
    # system mmCIF, persisted at export. Empty for runs predating the
    # selector export — the UI keeps its chain-id highlight fallback.
    segment_selectors: Dict[str, RenderSegmentSelector] = Field(
        default_factory=dict, description="Per-segment selectors into the system mmCIF"
    )


class ExampleRun(BaseModel):
    """One landing-page example card (v3.137)."""

    run_id: str
    title: str
    description: Optional[str] = None
    image_url: str
    created_at: str = ""


class ExamplesResponse(BaseModel):
    examples: List[ExampleRun] = []


class SignatureInfo(BaseModel):
    """Information about a generated signature."""

    segment: str = Field(..., description="Segment name")
    generator: str = Field(..., description="Kind of description: smiles, inchi_key, molecular_formula, fasta_map_protein, mmcif, ...")
    signature: Any = Field(..., description="The value: a SMILES, sequence, formula, or a whole structure file")


class SignaturesResponse(BaseModel):
    """Response model for signatures."""

    run_id: str = Field(..., description="The run id")
    signatures: List[SignatureInfo] = Field(default_factory=list, description="List of signatures")
    attempted_generators: Dict[str, List[str]] = Field(
        default_factory=dict, description="Generators attempted per segment"
    )


class IdentifierHit(BaseModel):
    """An identifier hit from resolution."""

    identifier: str = Field(..., description="Identifier in its database, e.g. P00760, 3PTB, 2332")
    ident_type: str = Field(..., description="Kind of identifier: PDB_ID, UNIPROT_ID, PUBCHEM_CID, INCHIKEY, CHEMBL_ID, ...")
    hit_type: str = Field(..., description="identity (exact match) or similarity")
    resolver_name: str = Field(..., description="The search that found it; @sim marks a similarity search")
    segment: Optional[str] = Field(None, description="The molecule it was found for")
    score: Optional[float] = Field(None, description="Score of the search (null for searches without one)")
    database_url: Optional[str] = Field(None, description="URL to the database entry")
    evalue: Optional[float] = Field(None, description="BLAST e-value")
    bit_score: Optional[float] = Field(None, description="BLAST bit score")
    identity_percent: Optional[float] = Field(None, description="Identity percentage (0-100)")
    coverage_percent: Optional[float] = Field(None, description="Coverage percentage (0-100)")


class ResolverErrorItem(BaseModel):
    """A resolver failure item."""

    resolver_name: str = Field(..., description="The search that failed")
    generator: Optional[str] = Field(None, description="The kind of description it searched with")
    message: str = Field(..., description="Error message")


class IdentifiersResponse(BaseModel):
    """Response model for identifiers."""

    run_id: str = Field(..., description="The run id")
    segment: Optional[str] = Field(None, description="The molecule asked for with ?segment=; null when the hits of every molecule are listed (each hit carries its own segment)")
    hits: List[IdentifierHit] = Field(default_factory=list, description="List of identifier hits")
    attempted_resolvers: List[str] = Field(
        default_factory=list, description="Resolvers that were attempted"
    )
    failed_resolvers: List[ResolverErrorItem] = Field(
        default_factory=list, description="Resolvers that failed with error messages"
    )


class VerifiedHitItem(BaseModel):
    """A verified hit with confidence scores."""

    identifier: str = Field(..., description="Identifier in its database, e.g. P00760, 3PTB, 2332")
    ident_type: str = Field(..., description="Kind of identifier: PDB_ID, UNIPROT_ID, PUBCHEM_CID, INCHIKEY, CHEMBL_ID, ELEMENT, ...")
    database: str = Field(..., description="Database: pdb, uniprot, pubchem, chembl, chebi, lipidmaps, alphafold, element, ...")
    resolver_score: Optional[float] = Field(None, description="0-100: how well the database search matched")
    similarity_score: Optional[float] = Field(None, description="0-100: how well the record's own structure or sequence matches the molecule")
    annotation_quality_score: Optional[float] = Field(
        None, description="0-100: how well the record is annotated (names, organism, references)"
    )
    final_confidence: Optional[float] = Field(None, description="0-100: how sure BioID is that this record is this molecule (>= 80 high, >= 50 medium)")
    # v3.143 (D-17): additive — without a segment filter the endpoint
    # concatenates all segments' hits into one list; each item now carries
    # its own segment (None for legacy single-segment payloads).
    segment: Optional[str] = Field(None, description="The molecule it identifies")
    is_verified: bool = Field(..., description="Passed verification; rejected hits say why in rejection_reason")
    rejection_reason: Optional[str] = Field(None, description="Why verification rejected it")
    # v3.143 (BACKEND_GAPS G5): additive — display metadata threaded by the
    # verification manager from already-fetched annotation payloads; null
    # for older runs and unsupported ident types (UI falls back to db+id).
    name: Optional[str] = Field(None, description="What the record is, e.g. the protein or compound name")
    organism: Optional[str] = Field(None, description="Source organism (scientific name), for biopolymers")
    supporting_evidence_count: int = Field(default=0, description="Number of independent searches that found this record")
    database_url: Optional[str] = Field(None, description="URL to the database entry")
    ground_truth_override: Optional[str] = Field(
        None, description="Set for exact answers that need no weighing, e.g. element_monoatomic for single-atom ions"
    )
    skeleton_sim: Optional[float] = Field(
        None, description="0-1: similarity of the record's heavy-atom skeleton to the molecule's (small molecules only)"
    )
    belief: Optional[float] = Field(
        None, description="0-100: how strongly the searches agree on this record; part of final_confidence"
    )
    equivalence_class_id: Optional[str] = Field(
        None, description="Records with the same id describe the same verified structure (e.g. one compound in PubChem and ChEMBL)"
    )


class VerificationResponse(BaseModel):
    """Response model for verification results."""

    run_id: str = Field(..., description="The run id")
    segment: Optional[str] = Field(None, description="The molecule asked for with ?segment=; null when the hits of every molecule are listed (each hit carries its own segment)")
    hits: List[VerifiedHitItem] = Field(default_factory=list, description="List of verified hits")


class RunCreateResponse(BaseModel):
    """Response model for creating a new run."""

    run_id: str = Field(..., description="The run id")
    status: str = Field(..., description="Always queued")
    message: str = Field(..., description="Confirmation, with a note when the input looks incomplete")
    results_url: str = Field(..., description="Where to follow the run (GET)")
    owner_token: Optional[str] = Field(
        None, description="Secret for deleting or cancelling this run (X-Owner-Token header); "
                          "shown only once, keep it")


class RunQueueResponse(BaseModel):
    """Response model for a run's queue position."""

    state: str = Field(..., description="queued, running or done")
    position: Optional[int] = Field(None, description="Place in the queue while queued (1 = next)")
    ahead: Optional[int] = Field(None, description="Number of queued runs ahead of this run")


class RunListItem(BaseModel):
    """Summary of a run for list view."""

    run_id: str = Field(..., description="The run id")
    status: str = Field(..., description="queued, running, success, failed or cancelled")
    created_at: str = Field(..., description="ISO 8601 timestamp when run was created")
    input_kind: Optional[str] = Field(None, description="How the input was read: tpr, gro, amber, charmm, lammps, pdb, cif, ...")
    run_name: Optional[str] = Field(None, description="Name given at submission")
    creator_ip: Optional[str] = Field(None, description="Always null (addresses are not stored)")
    queue: str = Field("web", description="Queue the run was submitted to: web or repository")
    completeness: Optional[str] = Field(None, description=COMPLETENESS)
    partial_stages: List[str] = Field(default_factory=list, description=PARTIAL_STAGES)


class RunListResponse(BaseModel):
    """Response model for listing runs."""

    runs: List[RunListItem] = Field(default_factory=list, description="List of runs")


class CapabilitiesResponse(BaseModel):
    """Features of this deployment, so clients can detect what it supports.

    `api_version_marker` increases when features are added; `additions` names
    every feature this deployment has."""

    api_version_marker: int = Field(..., description="Increases when features are added")
    additions: List[str] = Field(default_factory=list, description="Features this deployment has")
    typical_duration_minutes: Optional[Dict[str, int]] = Field(
        None, description="Deployment-level typical wall-clock range; null when unset")
    code_version: str = Field(..., description="Deployed code version")


class RunSummaryResponse(BaseModel):
    """Response model for run summary."""

    run_id: str = Field(..., description="The run id")
    pipeline_name: str = Field(..., description="Always BAT3")
    status: str = Field(..., description="queued, running, success, failed or cancelled")
    started_at: Optional[str] = Field(None, description="ISO 8601 timestamp when pipeline started")
    finished_at: Optional[str] = Field(None, description="ISO 8601 timestamp when pipeline finished")
    input_kind: Optional[str] = Field(None, description="How the input was read: tpr, gro, amber, charmm, lammps, pdb, cif, ...")
    # v3.143 (BACKEND_GAPS G1): additive — passthrough of the custom run
    # name persisted in results.json since v3.137; null for older runs.
    run_name: Optional[str] = Field(None, description="Custom run name provided at submission")
    task_count: int = Field(..., description="Number of pipeline stages")
    warning_count: int = Field(..., description="Number of warnings (see /status)")
    error_count: int = Field(..., description="Number of critical errors")
    retention: Optional[RetentionInfo] = Field(None, description="How long the run is kept")
    incomplete_count: int = Field(0, description="Failed lookups a rerun could fix (see status.incomplete)")
    completeness: Optional[str] = Field(None, description=COMPLETENESS)
    partial_stages: List[str] = Field(default_factory=list, description=PARTIAL_STAGES)
    queue: str = Field("web", description="Queue the run was submitted to: web or repository")
    attempt: int = Field(1, description="Automatic attempt number (1 = first)")
    rerun_of: Optional[str] = Field(None, description="Run this one re-runs")
    superseded_by: Optional[str] = Field(None, description="Newer run of the same input, by its owner")


class RunFilesResponse(BaseModel):
    """Response model for listing files in a run directory."""

    run_id: str = Field(..., description="The run id")
    files: List[str] = Field(default_factory=list, description="Paths to fetch from /files/{run_id}/<path>")

class MoleculeInfoResponse(BaseModel):
    """Response model for single molecule info endpoint."""

    segment: str = Field(..., description="The molecule's segment name")
    name: str = Field(..., description="Display name (residue name for small molecules)")
    type: str = Field(..., description="protein, nucleic, small_molecule, lipid, glycan, ion or water")
    atom_count: int = Field(..., description="Number of atoms")
    residue_count: int = Field(..., description="Number of residues")
    confidence: Optional[float] = Field(None, description="Confidence (0-100) of the best verified identification; null for exact answers and when nothing was verified")



class RerunRunItem(BaseModel):
    """Item in the re-run all response representing a single re-queued run."""

    new_run_id: str = Field(..., description="New run identifier created for the re-run")
    old_run_id: str = Field(..., description="Original run identifier that was re-queued")
    status: str = Field(..., description="Status of the newly queued run")


class RerunAllResponse(BaseModel):
    """Response model for the re-run all endpoint."""

    new_runs: List[RerunRunItem] = Field(default_factory=list, description="List of successfully re-queued runs")
    skipped: List[str] = Field(default_factory=list, description="List of old run_ids that were skipped (missing input)")
    count: int = Field(..., description="Number of new runs queued")


class CancelRunResponse(BaseModel):
    """Response model for cancelling a run."""

    run_id: str = Field(..., description="The run id")
    status: str = Field(..., description="cancelled (success for a run that was waiting for an automatic retry)")
