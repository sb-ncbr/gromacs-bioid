"""UniProt annotation quality scorer."""

from __future__ import annotations

import requests

from ..base import AnnotationQualityScorer
from ..models import AnnotationQuality


class UniProtAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for UniProt entries (including AlphaFold)."""

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        return ident_type in ("UNIPROT_ID", "ALPHAFOLD_ID")

    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a UniProt identifier.
        
        Args:
            identifier: UniProt identifier (e.g., "P04637") or AlphaFold ID.
            ident_type: Should be "UNIPROT_ID" or "ALPHAFOLD_ID".
            
        Returns:
            AnnotationQuality with score 0-100 and signals found.
            Returns low score (0.0) on any failure without raising.
        """
        if not self.supports(ident_type):
            return None
        
        # For AlphaFold IDs, extract the UniProt ID
        if ident_type == "ALPHAFOLD_ID":
            # AlphaFold ID format: AF-P04637-F1-model_v4
            # Extract UniProt ID from second part after splitting by '-'
            parts = identifier.split("-")
            if len(parts) >= 2:
                uniprot_id = parts[1]
            else:
                return AnnotationQuality(database="uniprot", score=0.0, signals=[])
        else:
            uniprot_id = identifier
        
        try:
            url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            entry = response.json()
        except Exception:
            return AnnotationQuality(database="uniprot", score=0.0, signals=[])
        
        signals = []
        score = 10.0  # Base points for having the entry
        
        # Check reviewed status (Swiss-Prot)
        entry_type = entry.get("entryType", "")
        if entry_type == "UniProtKB reviewed (Swiss-Prot)":
            signals.append("reviewed")
            score += 30.0
        
        # Check annotation_score (1-5 scale)
        annotation_score = entry.get("annotationScore")
        if annotation_score is not None:
            signals.append("annotation_score")
            score += annotation_score * 4  # 4-20 points
        
        # Check protein_existence == 1 (Evidence at protein level)
        protein_existence = entry.get("proteinExistence")
        if protein_existence == 1:
            signals.append("protein_existence")
            score += 20.0
        
        # Check gene_names present
        genes = entry.get("genes", [])
        if genes and len(genes) > 0:
            signals.append("gene_names")
            score += 10.0
        
        # Check GO terms in cross-references
        cross_refs = entry.get("uniProtKBCrossReferences", [])
        has_go_terms = any(
            ref.get("database") == "GO" 
            for ref in cross_refs 
            if isinstance(ref, dict)
        )
        if has_go_terms:
            signals.append("go_terms")
            score += 10.0
        
        return AnnotationQuality(
            database="uniprot",
            score=min(score, 100.0),
            signals=signals,
        )
