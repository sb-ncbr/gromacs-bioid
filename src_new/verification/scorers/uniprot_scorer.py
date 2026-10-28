"""UniProt annotation quality scorer."""

from __future__ import annotations

import requests

from ..base import AnnotationQualityScorer
from ..models import AnnotationQuality


class UniProtAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for UniProt entries (including AlphaFold)."""

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type.

        (v3.142 1c) SWISSPROT_ID added: swiss-prot accessions are UniProt
        accessions — rest.uniprot.org resolves them directly (corpus census
        gap: 64,430 SWISSPROT rows with zero annotation signal).
        """
        return ident_type in ("UNIPROT_ID", "ALPHAFOLD_ID", "SWISSPROT_ID")

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
            # Wrapped form: AF-P04637-F1-model_v4 -> P04637.
            # (v3.142) AlphaFind emits BARE UniProt accessions (live probe
            # 2026-10-19); passthrough instead of failing the split-guard —
            # this is the corpus-reality path (9,161 rows, previously 0 ann).
            parts = identifier.split("-")
            if identifier.upper().startswith("AF-") and len(parts) >= 2:
                uniprot_id = parts[1]
            else:
                uniprot_id = identifier
        else:
            uniprot_id = identifier
        
        try:
            # Red-team batch-4 (D-07): the full entry JSON is hundreds of kB;
            # ask only for the fields the scorer reads (live-validated field
            # names: accession, reviewed, protein_existence, annotation_score,
            # gene_names, go).
            # v3.143 (BACKEND_GAPS G5): + protein_name,organism_name on the
            # SAME single request — display metadata at zero extra fetches.
            url = (f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.json"
                   f"?fields=reviewed,protein_existence,annotation_score,"
                   f"gene_names,go,protein_name,organism_name")
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            entry = response.json()
        except Exception:
            return AnnotationQuality(database="uniprot", score=0.0, signals=[])

        # G5 display metadata (best-effort; absent/{} payloads -> None).
        name: str | None = None
        organism: str | None = None
        try:
            name = (((entry.get("proteinDescription") or {})
                     .get("recommendedName") or {})
                    .get("fullName") or {}).get("value") or None
            organism = (entry.get("organism") or {}).get("scientificName") or None
        except Exception:
            name = None
            organism = None
        
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
        
        # Check protein_existence. D-07: the REST JSON returns the STRING
        # "1: Evidence at protein level" (live-verified 2026-10-23 on P00698),
        # never the integer 1 — the old `== 1` comparison never fired.
        protein_existence = entry.get("proteinExistence")
        if (isinstance(protein_existence, str) and protein_existence.startswith("1:")) \
                or protein_existence == 1:
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
            name=name,
            organism=organism,
        )
