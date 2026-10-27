"""PDB annotation quality scorer."""

from __future__ import annotations

from ..base import AnnotationQualityScorer
from ..models import AnnotationQuality
from ..fetchers import rcsb_cache


class PDBAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for PDB entries."""

    def __init__(self):
        self._memo: dict[str, AnnotationQuality | None] = {}

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        return ident_type == "PDB_ID"

    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a PDB identifier.

        Args:
            identifier: PDB identifier (e.g., "1ABC", "6VXX_entity_1").
            ident_type: Should be "PDB_ID".

        Returns:
            AnnotationQuality with score 0-100 and signals found.
            None when the annotation is UNKNOWN (fetch or parse failure) —
            an unknown annotation must never be reported as a real low
            score; the confidence composition re-weights over measured
            terms for None (see manager).
        """
        if not self.supports(ident_type):
            return None

        # Strip _entity suffix and uppercase
        pdb_id = identifier.split("_")[0].upper()

        # Instance-level memoization for repeated calls
        memo_key = pdb_id
        if memo_key in self._memo:
            return self._memo[memo_key]

        try:
            url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
            response = rcsb_cache.get_cached(url, timeout=30)
            if response is None:
                self._memo[memo_key] = None
                return None
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError(f"unexpected payload root: {type(data).__name__}")

            signals = []
            score = 20.0  # Base points for having the entry

            info = data.get("rcsb_entry_info")
            if not isinstance(info, dict):
                info = {}

            # Check resolution (rcsb_entry_info.resolution_combined is a list)
            resolution = info.get("resolution_combined")
            if isinstance(resolution, list) and len(resolution) > 0:
                signals.append("resolution")
                score += 20.0

            # Check r_free. Red-team wave-2 (item 1): RCSB `refine` is a LIST
            # of objects (like `exptl`), one per refinement range — the old
            # code called .get() on it, raised AttributeError outside the try,
            # and the manager swallowed it: every X-ray entry (any entry with
            # a refine block) silently lost its annotation score.
            refine = data.get("refine")
            if isinstance(refine, dict):
                refine_list = [refine]
            elif isinstance(refine, list):
                refine_list = [r for r in refine if isinstance(r, dict)]
            else:
                refine_list = []
            if any(r.get("ls_rfactor_rfree") is not None for r in refine_list):
                signals.append("r_free")
                score += 20.0

            # Check experimental_method (exptl.method is a list of dicts)
            exptl = data.get("exptl")
            if isinstance(exptl, dict):
                exptl_list = [exptl]
            elif isinstance(exptl, list):
                exptl_list = [e for e in exptl if isinstance(e, dict)]
            else:
                exptl_list = []
            if any(e.get("method") for e in exptl_list):
                signals.append("experimental_method")
                score += 20.0

            # Check deposited_model_count > 1
            deposited_count = info.get("deposited_model_count")
            if isinstance(deposited_count, (int, float)) and deposited_count > 1:
                signals.append("deposited_model_count")
                score += 10.0

            # Check polymer_entity_count > 0
            polymer_count = info.get("polymer_entity_count")
            if isinstance(polymer_count, (int, float)) and polymer_count > 0:
                signals.append("polymer_entity_count")
                score += 10.0

            result = AnnotationQuality(
                database="pdb",
                score=min(score, 100.0),
                signals=signals,
            )
        except Exception:
            # Fetch failure, JSON decode error, or a payload shape the parser
            # cannot handle — all the same class: annotation UNKNOWN.
            result = None

        self._memo[memo_key] = result
        return result
