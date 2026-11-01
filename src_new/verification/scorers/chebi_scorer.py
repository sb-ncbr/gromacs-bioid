"""ChEBI annotation quality scorer."""

from __future__ import annotations

import logging

import requests

from ..base import AnnotationQualityScorer, fetch_failure_reason
from ..models import AnnotationQuality

logger = logging.getLogger("annotation")


class ChebiAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for ChEBI compounds."""

    def __init__(self) -> None:
        # W3.3 item 2 (determinism): successful scores cached per numeric
        # ChEBI id; transient failures (None) are never cached.
        self._score_cache: dict[str, AnnotationQuality] = {}

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        return ident_type in ("CHEBI_ID", "CHEBI")

    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a ChEBI identifier (cached).

        W3.3 item 2: fetch failure -> None (annotation UNKNOWN; the blend
        re-weights), never a real 0.0/lower score.
        """
        if not self.supports(ident_type):
            return None

        # Strip CHEBI: prefix if present
        chebi_num = identifier.upper()
        if chebi_num.startswith("CHEBI:"):
            chebi_num = chebi_num[6:]  # Strip prefix

        cached = self._score_cache.get(chebi_num)
        if cached is not None:
            return cached
        result = self._score_uncached(chebi_num)
        if result is not None:
            self._score_cache[chebi_num] = result
        return result

    def _score_uncached(self, chebi_num: str) -> AnnotationQuality | None:
        """Fetch + score one ChEBI numeric id. None on fetch failure."""
        try:
            url = f"https://www.ebi.ac.uk/chebi/backend/api/public/compound/{chebi_num}/"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("ann_fetch_failed service=chebi id=%s reason=%s",
                           chebi_num, fetch_failure_reason(exc))
            return None
        
        signals = []
        score = 20.0  # Base points for having the entry
        
        # Check definition
        definition = data.get("definition", "")
        if definition:
            signals.append("definition")
            score += 20.0
        
        # Check smiles from default_structure
        default_structure = data.get("default_structure", {})
        if default_structure:
            smiles = default_structure.get("smiles", "")
            if smiles:
                signals.append("smiles")
                score += 20.0
            
            # Check inchi_key. D-07: the API exposes it as
            # 'standard_inchi_key' (live-verified 2026-10-23 on CHEBI:15377);
            # the old 'inchi_key' read never fired.
            inchi_key = (default_structure.get("standard_inchi_key")
                         or default_structure.get("inchi_key", ""))
            if inchi_key:
                signals.append("inchi_key")
                score += 20.0
        
        # Check stars == 3 (manually curated)
        stars = data.get("stars")
        if stars == 3:
            signals.append("stars")
            score += 20.0
        
        # Check name is non-empty
        name = data.get("name", "")
        if name:
            # Name is implicitly checked as part of having the entry
            # but we can add it as a signal if we want
            pass
        
        return AnnotationQuality(
            database="chebi",
            score=min(score, 100.0),
            signals=signals,
        )
