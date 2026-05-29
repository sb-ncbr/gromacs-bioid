"""PDB annotation quality scorer."""

from __future__ import annotations

import requests

from ..base import AnnotationQualityScorer
from ..models import AnnotationQuality


class PDBAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for PDB entries."""

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
            Returns low score (0.0) on any failure without raising.
        """
        if not self.supports(ident_type):
            return None
        
        # Strip _entity suffix and uppercase
        pdb_id = identifier.split("_")[0].upper()
        
        try:
            url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return AnnotationQuality(database="pdb", score=0.0, signals=[])
        
        signals = []
        score = 20.0  # Base points for having the entry
        
        # Check resolution (rcsb_entry_info.resolution_combined is a list)
        rcsb_info = data.get("rcsb_entry_info", {})
        resolution = rcsb_info.get("resolution_combined")
        if resolution is not None and isinstance(resolution, list) and len(resolution) > 0:
            signals.append("resolution")
            score += 20.0
        
        # Check r_free (refine.ls_rfactor_rfree)
        refine = data.get("refine")
        if refine is not None:
            r_free = refine.get("ls_rfactor_rfree")
            if r_free is not None:
                signals.append("r_free")
                score += 20.0
        
        # Check experimental_method (exptl.method is a list of dicts)
        exptl = data.get("exptl", [])
        if exptl and isinstance(exptl, list) and len(exptl) > 0:
            method = exptl[0].get("method") if isinstance(exptl[0], dict) else None
            if method is not None:
                signals.append("experimental_method")
                score += 20.0
        
        # Check deposited_model_count > 1
        deposited_count = rcsb_info.get("deposited_model_count")
        if deposited_count is not None and deposited_count > 1:
            signals.append("deposited_model_count")
            score += 10.0
        
        # Check polymer_entity_count > 0
        polymer_count = rcsb_info.get("polymer_entity_count")
        if polymer_count is not None and polymer_count > 0:
            signals.append("polymer_entity_count")
            score += 10.0
        
        return AnnotationQuality(
            database="pdb",
            score=min(score, 100.0),
            signals=signals,
        )
