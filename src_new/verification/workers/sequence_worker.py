"""Sequence verification worker for proteins/nucleic acids using sequence alignment."""

from __future__ import annotations

import logging

from ..base import VerificationWorker
from ..models import VerificationScore, ref_seq_sha1
from ..fetchers.sequence_fetcher import SequenceSignatureFetcher
from ..alignment import local_identity_coverage
from ...molecules.nucleic_acid import sequence_orientation_variants

logger = logging.getLogger(__name__)


class SequenceVerificationWorker(VerificationWorker):
    """Verifies protein/nucleic acid identifications using sequence alignment."""
    
    SUPPORTED_IDENT_TYPES = {"PDB_ID", "UNIPROT_ID", "ALPHAFOLD_ID", "NR_ID", "SWISSPROT_ID", "NT_ID", "CORE_NT_ID"}
    
    def is_applicable(self, signature_type: str, ident_type: str) -> bool:
        """Check if this worker can verify the given signature and identifier types."""
        return (
            "residue_sequence" in signature_type.lower() and
            ident_type in self.SUPPORTED_IDENT_TYPES
        )
    
    # DP-matrix cell cap for alignment (lenA * lenB). Above this the pairwise
    # enumeration/matrix gets pathological (titin-vs-titin class pairs were
    # observed burning hours per call in production; see wave-3 postmortem).
    # 25M cells covers all sane protein/PDB entity pairs (5k x 5k).
    MAX_ALIGN_MATRIX_CELLS = 25_000_000

    def _compute_alignment_score(self, signature: str, canonical_signature: str) -> VerificationScore | None:
        """Compute alignment score between query and canonical sequence.

        Red-team batch-4 (D-01): local BLOSUM62 alignment via the shared
        helper (verification/alignment.py). Score = identity * coverage;
        both raw numbers are persisted in details. The old global alignment
        diluted length differences (correct full-length entries scored below
        random sequences) and reported coverage == 1.0 by construction.

        Args:
            signature: The query sequence.
            canonical_signature: The canonical/reference sequence.

        Returns:
            VerificationScore or None if alignment fails or is unsafe to attempt.
        """
        try:
            # Pre-guard: refuse pathological matrix sizes (DP cost + memory).
            if len(signature) * len(canonical_signature) > self.MAX_ALIGN_MATRIX_CELLS:
                logger.warning(
                    f"Sequence alignment skipped: matrix too large "
                    f"({len(signature)} x {len(canonical_signature)})"
                )
                return None

            out = local_identity_coverage(signature, canonical_signature)
            if out is None:
                return None
            identity, coverage = out

            # Final score = identity * coverage * 100.0, capped at 100
            raw_score = identity * coverage
            normalized_score = min(raw_score * 100.0, 100.0)

            return VerificationScore(
                kind="similarity",
                metric_name="seq_identity_coverage",
                raw_score=raw_score,
                normalized_score=normalized_score,
                details={
                    "alignment_identity": round(identity * 100.0, 2),
                    "query_coverage": round(coverage * 100.0, 2),
                    # D-06: equivalence classes are keyed on the reference
                    # content that produced this score (best-matching
                    # candidate at the caller's multi-entity loop).
                    "ref_seq_sha1": ref_seq_sha1(canonical_signature),
                },
            )

        except Exception as e:
            logger.warning(f"Sequence alignment failed: {e}")
            return None
    
    def _score_best_orientation(
        self, signature: str, canonical_signature: str, try_revcomp: bool
    ) -> VerificationScore | None:
        """Best alignment score over orientation variants.

        For nucleotide queries (try_revcomp), all four orientation senses
        are scored and the maximum wins; the result is therefore never
        lower than forward-only scoring (no-regression property). For
        proteins the input is scored unchanged.
        """
        variants = (
            sequence_orientation_variants(signature) if try_revcomp else [signature]
        )
        best: VerificationScore | None = None
        for variant in variants:
            score = self._compute_alignment_score(variant, canonical_signature)
            if score is not None and (
                best is None or score.normalized_score > best.normalized_score
            ):
                best = score
        return best

    def verify(
        self,
        signature: str,
        identifier: str,
        ident_type: str,
        canonical_signature: str | None = None,
        signature_type: str | None = None,
    ) -> VerificationScore | None:
        """Verify a sequence hit by comparing using global alignment.
        
        For PDB_ID identifiers, fetches all polymer entity sequences and picks
        the best-matching entity for scoring. This handles multi-entity PDB entries
        where different chains may have different sequences.
        
        Args:
            signature: The residue sequence extracted from simulation.
            identifier: The identifier (e.g., "1ABC" for PDB).
            ident_type: The type of identifier.
            canonical_signature: The canonical sequence from database. Required.
            
        Returns:
            VerificationScore if verification was performed, None if not applicable.
        """
        # Cannot verify without canonical sequence
        if canonical_signature is None:
            return None

        # Wave-7 C1: duplex NA orientation is unconstrained at generation
        # time, so nucleotide queries score all orientation variants.
        try_revcomp = (
            signature_type is not None and "nucleotide" in signature_type.lower()
        )

        try:
            # For PDB_ID, try all polymer entities and pick the best match
            if ident_type == "PDB_ID":
                fetcher = SequenceSignatureFetcher()
                entity_sequences = fetcher._fetch_pdb_entities(identifier)

                # Include the provided canonical_signature as fallback
                candidate_sequences = list(entity_sequences)
                if canonical_signature not in candidate_sequences:
                    candidate_sequences.append(canonical_signature)

                # Try each candidate and pick the best score
                best_score: VerificationScore | None = None
                for candidate_seq in candidate_sequences:
                    score = self._score_best_orientation(signature, candidate_seq, try_revcomp)
                    if score is not None:
                        if best_score is None or score.normalized_score > best_score.normalized_score:
                            best_score = score

                return best_score

            # For non-PDB identifiers, use single canonical sequence
            return self._score_best_orientation(signature, canonical_signature, try_revcomp)
            
        except Exception as e:
            logger.warning(f"Sequence verification failed: {e}")
            return None
