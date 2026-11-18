"""Where each warning and error code is explained (docs/site/docs/warnings.md).

The status endpoint gives every warning and error a docs_url, so people and
agents can look a code up instead of guessing; tests keep this list and the
page's headings in step.
"""
from __future__ import annotations

PAGE = "/documentation/warnings/"

#: Codes with their own section (heading text = code = anchor).
DOCUMENTED = frozenset({
    "identifier_resolver_failed", "stage_time_budget", "structure_search_unavailable",
    "identification_groups_unresolved", "verification_failed", "annotation_fetch_failed",
    "signature_generator_failed", "chemistry_skipped_size", "pbc_jumps_detected", "pbc_unwrap_applied", "pbc_unwrap_failed",
    "pbc_unwrap_incomplete", "insufficient_bonds", "coords_rescaled_nm_to_angstrom",
    "coords_rescaled_unexpected", "geometry_scale_anomalous", "system_export_failed",
    "segment_export_failed",
    "missing_input", "load_failed", "worker_lost", "timeout", "pipeline_child_crashed",
})
#: Codes explained together in one section.
GROUPED = {
    "render": ("render_",),
    "internal": ("missing_universe", "missing_facade", "unhandled_exception",
                 "pipeline_execution_failed", "file_missing", "file_empty_or_missing",
                 "artifact_missing", "result_is_none"),
}


def docs_url(code: str) -> str:
    """Path (on the BioID host) of the section explaining `code`; the page itself if none."""
    if code in DOCUMENTED:
        return f"{PAGE}#{code}"
    for anchor, codes in GROUPED.items():
        if any(code == c or (c.endswith("_") and code.startswith(c)) for c in codes):
            return f"{PAGE}#{anchor}"
    return PAGE
