"""Additive-only schema contract guard for the public API response models.

UI BACKEND_GAPS Item 0: the redesigned /runs/:id page (ui/BACKEND_GAPS.md)
depends on an additive-only contract — fields may be ADDED but never
renamed, removed, or retyped. This test enforces it mechanically:

  - BASELINE: the exact field set of each response model at the start of
    the B1 wave (2026-10-28, commit 1 of the UI gaps work).
  - REGISTERED_ADDITIONS: fields added later, keyed by the gap item that
    added them. A model may only carry fields from BASELINE plus fields
    registered here — any unregistered change FAILS this test, forcing
    the author to consciously register additions (and their motivation).

Registered additions so far:
  - g1_run_name (BACKEND_GAPS G1): run_name on RunSummaryResponse.
"""

from __future__ import annotations

from src_new.api.models import (
    MoleculeInstanceInfo,
    MoleculeSummaryResponse,
    RenderPathsResponse,
    RenderSegmentSelector,
    RunStatusResponse,
    RunSummaryResponse,
    VerifiedHitItem,
)

BASELINE: dict[str, set[str]] = {
    "RunSummaryResponse": {
        "error_count", "finished_at", "input_kind", "pipeline_name",
        "run_id", "started_at", "status", "task_count", "warning_count",
    },
    "MoleculeSummaryResponse": {
        "run_id", "segment_meta", "segments", "total_fragment_count",
        "type_counts", "unique_molecules",
    },
    "RunStatusResponse": {
        "critical_errors", "events", "pipeline", "run_id", "tasks",
        "updated_at", "warnings",
    },
    "VerifiedHitItem": {
        "annotation_quality_score", "belief", "database", "database_url",
        "equivalence_class_id", "final_confidence", "ground_truth_override",
        "ident_type", "identifier", "is_verified", "rejection_reason",
        "resolver_score", "segment", "similarity_score", "skeleton_sim",
        "supporting_evidence_count",
    },
    "MoleculeInstanceInfo": {
        "segment_ids", "molecule_type", "atom_count", "residue_count",
        "smiles",
    },
    "RenderPathsResponse": {
        "geometry", "run_id", "segment_pngs", "segments", "system_mmcif",
        "system_png", "total_atom_count",
    },
    # Added wholesale by G9 (nested selector model); its fields are their
    # own baseline from the moment the model exists.
    "RenderSegmentSelector": {
        "chains", "atom_index_ranges", "atom_count",
    },
}

# gap item -> {model: fields added by that item}
REGISTERED_ADDITIONS: dict[str, dict[str, set[str]]] = {
    "g1_run_name": {"RunSummaryResponse": {"run_name"}},
    "g2_segment_progress": {"RunStatusResponse": {"progress"}},
    "g5_hit_name_organism": {"VerifiedHitItem": {"name", "organism"}},
    "g7_unique_segment_names": {"MoleculeInstanceInfo": {"segment_names"}},
    "g9_render_selectors": {"RenderPathsResponse": {"segment_selectors"}},
}

_MODELS = {
    "RunSummaryResponse": RunSummaryResponse,
    "MoleculeSummaryResponse": MoleculeSummaryResponse,
    "RunStatusResponse": RunStatusResponse,
    "VerifiedHitItem": VerifiedHitItem,
    "MoleculeInstanceInfo": MoleculeInstanceInfo,
    "RenderPathsResponse": RenderPathsResponse,
    "RenderSegmentSelector": RenderSegmentSelector,
}


def _registered_fields(model_name: str) -> set[str]:
    merged: set[str] = set()
    for items in REGISTERED_ADDITIONS.values():
        merged |= items.get(model_name, set())
    return merged


class TestAdditiveContract:
    def test_no_field_removals(self) -> None:
        """Every baseline field must still exist in the model."""
        for name, model in _MODELS.items():
            current = set(model.model_fields)
            missing = BASELINE[name] - current
            assert not missing, (
                f"{name}: fields removed (violates additive-only "
                f"contract): {sorted(missing)}"
            )

    def test_all_additions_registered(self) -> None:
        """New fields must be registered with the gap item that added them."""
        for name, model in _MODELS.items():
            current = set(model.model_fields)
            added = current - BASELINE[name]
            unregistered = added - _registered_fields(name)
            assert not unregistered, (
                f"{name}: unregistered field additions: {sorted(unregistered)} "
                f"— add them to REGISTERED_ADDITIONS with the gap item as key"
            )

    def test_registered_fields_are_new_only(self) -> None:
        """Guard against baseline drift: registered additions must not
        overlap the baseline (a re-registration of an old field hides a
        past contract violation)."""
        for name in _MODELS:
            overlap = _registered_fields(name) & BASELINE[name]
            assert not overlap, (
                f"{name}: registered additions re-list baseline fields: "
                f"{sorted(overlap)}"
            )
