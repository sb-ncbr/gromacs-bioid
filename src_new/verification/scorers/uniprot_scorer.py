"""UniProt annotation quality scorer."""

from __future__ import annotations

import logging

import requests

from ..base import AnnotationQualityScorer, fetch_failure_reason
from ..models import AnnotationQuality

logger = logging.getLogger("annotation")


class UniProtAnnotationScorer(AnnotationQualityScorer):
    """Scores annotation quality for UniProt entries (including AlphaFold)."""

    def __init__(self) -> None:
        # W3.3 item 2 (determinism, same pattern as PubChem D-07): a
        # successful score is cached per RESOLVED UniProt accession and
        # served verbatim on repeats (incl. AF- wrapped aliases) — a record
        # scores once per run instead of re-fetching per window occurrence.
        # Transient failures are never cached (None re-attempts later).
        self._score_cache: dict[str, AnnotationQuality] = {}

    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type.

        (v3.142 1c) SWISSPROT_ID added: swiss-prot accessions are UniProt
        accessions — rest.uniprot.org resolves them directly (corpus census
        gap: 64,430 SWISSPROT rows with zero annotation signal).
        """
        return ident_type in ("UNIPROT_ID", "ALPHAFOLD_ID", "SWISSPROT_ID")

    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for a UniProt identifier (cached)."""
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

        cached = self._score_cache.get(uniprot_id)
        if cached is not None:
            return cached
        result = self._score_uncached(uniprot_id)
        if result is not None:
            self._score_cache[uniprot_id] = result
        return result

    def _score_uncached(self, uniprot_id: str) -> AnnotationQuality | None:
        """Score the annotation quality for a resolved UniProt accession.

        W3.3 item 2 (user directive, re-eval correction 2026-11-01): a
        fetch failure is annotation UNKNOWN — returns None so the
        confidence blend re-weights over the measured terms — never a
        real 0.0/lower score (which silently re-ordered top-1 for the
        same identifier across twin runs, and eroded the b12 fleet gate
        UniProt validated@1 by 16 pp under cold-cache remote storms).
        """
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
        except Exception as exc:
            # W3.3 A.3 (health record): tagged, status-carrying failure line.
            logger.warning("ann_fetch_failed service=uniprot id=%s reason=%s",
                           uniprot_id, fetch_failure_reason(exc))
            return None

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
