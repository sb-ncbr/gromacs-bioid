"""ChEBI annotation quality scorer."""

from __future__ import annotations

import requests

from ..base import AnnotationQualityScorer
from ..models import AnnotationQuality


class ChebiAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for ChEBI compounds."""

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        return ident_type == "CHEBI_ID"

    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a ChEBI identifier.
        
        Args:
            identifier: ChEBI identifier (e.g., "CHEBI:16236" or "16236").
            ident_type: Should be "CHEBI_ID".
            
        Returns:
            AnnotationQuality with score 0-100 and signals found.
            Returns low score (0.0) on any failure without raising.
        """
        if not self.supports(ident_type):
            return None
        
        # Strip CHEBI: prefix if present
        chebi_num = identifier.upper()
        if chebi_num.startswith("CHEBI:"):
            chebi_num = chebi_num[6:]  # Strip prefix
        
        try:
            url = f"https://www.ebi.ac.uk/chebi/backend/api/public/compound/{chebi_num}/"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return AnnotationQuality(database="chebi", score=0.0, signals=[])
        
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
            
            # Check inchi_key
            inchi_key = default_structure.get("inchi_key", "")
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
