"""ChEMBL annotation quality scorer."""

from __future__ import annotations

import requests

from ..base import AnnotationQualityScorer
from ..models import AnnotationQuality


class ChemblAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for ChEMBL compounds."""

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        return ident_type == "CHEMBL_ID"

    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a ChEMBL identifier.
        
        Args:
            identifier: ChEMBL identifier (e.g., "CHEMBL25" or "25").
            ident_type: Should be "CHEMBL_ID".
            
        Returns:
            AnnotationQuality with score 0-100 and signals found.
            Returns low score (0.0) on any failure without raising.
        """
        if not self.supports(ident_type):
            return None
        
        # Canonicalize: strip CHEMBL prefix if present, then prepend it back
        chembl_id = identifier.upper()
        if chembl_id.startswith("CHEMBL"):
            chembl_id = chembl_id[6:]  # Strip prefix
        chembl_id = f"CHEMBL{chembl_id}"
        
        try:
            url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return AnnotationQuality(database="chembl", score=0.0, signals=[])
        
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
