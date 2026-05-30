"""Pydantic v2 models for BAT3 Pipeline API responses."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PipelineStatusResponse(BaseModel):
    """Response model for pipeline status."""

    run_id: str = Field(..., description="Unique run identifier")
    pipeline_name: str = Field(..., description="Name of the pipeline")
    status: str = Field(..., description="Pipeline status: created/running/success/failed")
    started_at: Optional[str] = Field(None, description="ISO 8601 timestamp when pipeline started")
    finished_at: Optional[str] = Field(None, description="ISO 8601 timestamp when pipeline finished")
    input_kind: Optional[str] = Field(None, description="Type of input data")
    input_files: Optional[Dict[str, str]] = Field(None, description="Input files mapping")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Pipeline metadata")


class TaskInfo(BaseModel):
    """Information about a single task in the pipeline."""

    task_id: str = Field(..., description="Task identifier")
    name: str = Field(..., description="Task name")
    status: str = Field(..., description="Task status: pending/running/success/failed/warning/skipped")
    started_at: Optional[str] = Field(None, description="ISO 8601 timestamp when task started")
    finished_at: Optional[str] = Field(None, description="ISO 8601 timestamp when task finished")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Task summary data")
    artifacts: List[str] = Field(default_factory=list, description="List of artifact UUIDs")


class WarningItem(BaseModel):
    """A warning recorded during pipeline execution."""

    code: str = Field(..., description="Warning code")
    message: str = Field(..., description="Warning message")
    step_id: Optional[str] = Field(None, description="Task/step ID that generated the warning")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional warning details")


class ErrorItem(BaseModel):
    """An error recorded during pipeline execution."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    step_id: Optional[str] = Field(None, description="Task/step ID that generated the error")
    details: Dict[str, Any] = Field(default_factory=dict, description="Additional error details")
    critical: bool = Field(default=False, description="Whether this is a critical error")
    exception_type: Optional[str] = Field(None, description="Type of exception if applicable")


class EventItem(BaseModel):
    """An event recorded during pipeline execution."""

    kind: str = Field(..., description="Event kind: log/step_start/step_finish")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    level: Optional[str] = Field(None, description="Log level for log events")
    message: Optional[str] = Field(None, description="Event message")
    task_id: Optional[str] = Field(None, description="Associated task ID")


class RunStatusResponse(BaseModel):
    """Full run status response."""

    run_id: str = Field(..., description="Unique run identifier")
    pipeline: PipelineStatusResponse = Field(..., description="Pipeline status information")
    tasks: List[TaskInfo] = Field(default_factory=list, description="List of task information")
    warnings: List[WarningItem] = Field(default_factory=list, description="List of warnings")
    critical_errors: List[ErrorItem] = Field(default_factory=list, description="List of critical errors")
    events: List[EventItem] = Field(default_factory=list, description="List of events")


class LoadingAttemptInfo(BaseModel):
    """Information about a loading attempt."""

    strategy: str = Field(..., description="Loading strategy name")
    success: bool = Field(..., description="Whether the attempt succeeded")
    error: Optional[str] = Field(None, description="Error message if failed")


class LoadingInfoResponse(BaseModel):
    """Response model for loading information."""

    run_id: str = Field(..., description="Unique run identifier")
    input_kind: Optional[str] = Field(None, description="Type of input data")
    selected_strategy: Optional[str] = Field(None, description="Selected loading strategy")
    topology_files: List[str] = Field(default_factory=list, description="Topology files found")
    attempts: List[LoadingAttemptInfo] = Field(default_factory=list, description="Loading attempts")
    final_strategy: Optional[str] = Field(None, description="Final successful strategy")
    success: bool = Field(default=False, description="Whether loading succeeded")
    warnings: List[str] = Field(default_factory=list, description="Loading warnings")


class MoleculeInstanceInfo(BaseModel):
    """Information about a molecule instance."""

    segment_ids: List[str] = Field(default_factory=list, description="Segment IDs")
    molecule_type: Optional[str] = Field(None, description="Molecule type")
    atom_count: int = Field(..., description="Number of atoms")
    residue_count: int = Field(..., description="Number of residues")
    smiles: Optional[str] = Field(None, description="SMILES string if available")


class MoleculeSummaryResponse(BaseModel):
    """Response model for molecule summary."""

    run_id: str = Field(..., description="Unique run identifier")
    unique_molecules: Dict[str, MoleculeInstanceInfo] = Field(
        default_factory=dict, description="Unique molecules by key"
    )
    type_counts: Dict[str, int] = Field(default_factory=dict, description="Counts by molecule type")
    total_fragment_count: int = Field(default=0, description="Total number of fragments")
    segments: List[str] = Field(default_factory=list, description="List of segment names")
    segment_meta: Optional[Dict[str, Any]] = Field(
        default=None, description="Metadata for each segment (type, atom_count, etc.)"
    )


class RenderPathsResponse(BaseModel):
    """Response model for render paths."""

    run_id: str = Field(..., description="Unique run identifier")
    system_mmcif: Optional[str] = Field(None, description="Path to system mmCIF file")
    segments: Dict[str, str] = Field(
        default_factory=dict, description="Mapping of segment name to mmCIF path"
    )


class SignatureInfo(BaseModel):
    """Information about a generated signature."""

    segment: str = Field(..., description="Segment name")
    generator: str = Field(..., description="Signature generator name")
    signature: Any = Field(..., description="The signature value (SMILES, FASTA, etc.)")


class SignaturesResponse(BaseModel):
    """Response model for signatures."""

    run_id: str = Field(..., description="Unique run identifier")
    signatures: List[SignatureInfo] = Field(default_factory=list, description="List of signatures")
    attempted_generators: Dict[str, List[str]] = Field(
        default_factory=dict, description="Generators attempted per segment"
    )


class IdentifierHit(BaseModel):
    """An identifier hit from resolution."""

    identifier: str = Field(..., description="The identifier value")
    ident_type: str = Field(..., description="Identifier type (e.g., PDB_ID, UNIPROT_ID)")
    hit_type: str = Field(..., description="Hit type: exact/similarity")
    resolver_name: str = Field(..., description="Name of the resolver that found this hit")
    score: Optional[float] = Field(None, description="Resolution score")
    database_url: Optional[str] = Field(None, description="URL to the database entry")


class IdentifiersResponse(BaseModel):
    """Response model for identifiers."""

    run_id: str = Field(..., description="Unique run identifier")
    segment: str = Field(..., description="Segment name")
    hits: List[IdentifierHit] = Field(default_factory=list, description="List of identifier hits")
    attempted_resolvers: List[str] = Field(
        default_factory=list, description="Resolvers that were attempted"
    )


class VerifiedHitItem(BaseModel):
    """A verified hit with confidence scores."""

    identifier: str = Field(..., description="The identifier value")
    ident_type: str = Field(..., description="Identifier type")
    database: str = Field(..., description="Target database name")
    resolver_score: Optional[float] = Field(None, description="Original resolver score")
    similarity_score: Optional[float] = Field(None, description="Similarity verification score")
    annotation_quality_score: Optional[float] = Field(
        None, description="Annotation quality score"
    )
    final_confidence: float = Field(..., description="Final confidence score")
    is_verified: bool = Field(..., description="Whether the hit passed verification")
    rejection_reason: Optional[str] = Field(None, description="Reason for rejection if not verified")
    supporting_evidence_count: int = Field(default=0, description="Number of supporting evidence")
    database_url: Optional[str] = Field(None, description="URL to the database entry")


class VerificationResponse(BaseModel):
    """Response model for verification results."""

    run_id: str = Field(..., description="Unique run identifier")
    segment: str = Field(..., description="Segment name")
    hits: List[VerifiedHitItem] = Field(default_factory=list, description="List of verified hits")


class RunCreateResponse(BaseModel):
    """Response model for creating a new run."""

    run_id: str = Field(..., description="Unique run identifier")
    status: str = Field(..., description="Run status: queued")
    message: str = Field(..., description="Human-readable message")
    results_url: str = Field(..., description="URL to check run status")


class RunListItem(BaseModel):
    """Summary of a run for list view."""

    run_id: str = Field(..., description="Unique run identifier")
    status: str = Field(..., description="Pipeline status")
    created_at: str = Field(..., description="ISO 8601 timestamp when run was created")
    input_kind: Optional[str] = Field(None, description="Type of input data")
    run_name: Optional[str] = Field(None, description="Custom run name")


class RunListResponse(BaseModel):
    """Response model for listing runs."""

    runs: List[RunListItem] = Field(default_factory=list, description="List of runs")


class RunSummaryResponse(BaseModel):
    """Response model for run summary."""

    run_id: str = Field(..., description="Unique run identifier")
    pipeline_name: str = Field(..., description="Name of the pipeline")
    status: str = Field(..., description="Pipeline status")
    started_at: Optional[str] = Field(None, description="ISO 8601 timestamp when pipeline started")
    finished_at: Optional[str] = Field(None, description="ISO 8601 timestamp when pipeline finished")
    input_kind: Optional[str] = Field(None, description="Type of input data")
    task_count: int = Field(..., description="Number of tasks in the pipeline")
    warning_count: int = Field(..., description="Number of warnings")
    error_count: int = Field(..., description="Number of errors")


class RunFilesResponse(BaseModel):
    """Response model for listing files in a run directory."""

    run_id: str = Field(..., description="Unique run identifier")
    files: List[str] = Field(default_factory=list, description="List of file paths relative to run directory")

class MoleculeInfoResponse(BaseModel):
    """Response model for single molecule info endpoint."""

    segment: str = Field(..., description="Segment identifier")
    name: str = Field(..., description="Molecule name")
    type: str = Field(..., description="Molecule type (protein, nucleic, etc.)")
    atom_count: int = Field(..., description="Number of atoms")
    residue_count: int = Field(..., description="Number of residues")
    confidence: Optional[float] = Field(None, description="Highest confidence from verification")

