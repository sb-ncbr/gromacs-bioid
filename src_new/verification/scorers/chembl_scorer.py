"""ChEMBL annotation quality scorer."""

from __future__ import annotations

import logging

import requests

from ..base import AnnotationQualityScorer, fetch_failure_reason
from ..models import AnnotationQuality

logger = logging.getLogger("annotation")


class ChemblAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for ChEMBL compounds."""

    def __init__(self) -> None:
        # W3.3 item 2 (determinism): successful scores cached per canonical
        # CHEMBL id; transient failures (None) are never cached.
        self._score_cache: dict[str, AnnotationQuality] = {}

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        return ident_type == "CHEMBL_ID"

    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a ChEMBL identifier (cached).

        W3.3 item 2: fetch failure -> None (annotation UNKNOWN; the blend
        re-weights), never a real 0.0/lower score.
        """
        if not self.supports(ident_type):
            return None

        # Canonicalize: strip CHEMBL prefix if present, then prepend it back
        chembl_id = identifier.upper()
        if chembl_id.startswith("CHEMBL"):
            chembl_id = chembl_id[6:]  # Strip prefix
        chembl_id = f"CHEMBL{chembl_id}"

        cached = self._score_cache.get(chembl_id)
        if cached is not None:
            return cached
        result = self._score_uncached(chembl_id)
        if result is not None:
            self._score_cache[chembl_id] = result
        return result

    def _score_uncached(self, chembl_id: str) -> AnnotationQuality | None:
        """Fetch + score one canonical CHEMBL id. None on fetch failure."""
        try:
            url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("ann_fetch_failed service=chembl id=%s reason=%s",
                           chembl_id, fetch_failure_reason(exc))
            return None
        
        signals = []
        score = 20.0  # Base points for having the entry
        
        # Check canonical_smiles
        mol_structures = data.get("molecule_structures", {})
        if mol_structures:
            canonical_smiles = mol_structures.get("canonical_smiles", "")
            if canonical_smiles:
                signals.append("canonical_smiles")
                score += 20.0
            
            # Check standard_inchi_key
            inchi_key = mol_structures.get("standard_inchi_key", "")
            if inchi_key:
                signals.append("standard_inchi_key")
                score += 15.0
        
        # Check molecule_properties
        mol_properties = data.get("molecule_properties", {})
        if mol_properties and len(mol_properties) > 0:
            signals.append("molecule_properties")
            score += 20.0
        
        # Check molecule_hierarchy (proxy for bioactivity data linkage)
        mol_hierarchy = data.get("molecule_hierarchy")
        if mol_hierarchy is not None:
            signals.append("bioactivities")
            score += 10.0
        
        # Check pref_name
        pref_name = data.get("pref_name", "")
        if pref_name:
            signals.append("pref_name")
            score += 15.0
        
        return AnnotationQuality(
            database="chembl",
            score=min(score, 100.0),
            signals=signals,
        )
