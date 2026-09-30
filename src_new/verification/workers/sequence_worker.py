"""Sequence verification worker for proteins/nucleic acids using sequence alignment."""

from __future__ import annotations

import logging

from Bio.Align import PairwiseAligner

from ..base import VerificationWorker
from ..models import VerificationScore
from ..fetchers.sequence_fetcher import SequenceSignatureFetcher
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

            # Use PairwiseAligner with equivalent parameters to old globalms
            # match=2, mismatch=-1, gap_open=-0.5, gap_extend=-0.1
            aligner = PairwiseAligner()
            aligner.mode = "global"
            aligner.match_score = 2
            aligner.mismatch_score = -1
            aligner.open_gap_score = -0.5
            aligner.extend_gap_score = -0.1

            alignments = aligner.align(signature, canonical_signature)

            # IMPORTANT: take the first optimal alignment via the iterator
            # WITHOUT materializing len(alignments). For low-complexity /
            # repetitive sequence pairs the count of optimal alignments
            # explodes combinatorially ("number of optimal alignments is
            # larger than 9223372036854775807") and enumeration burns hours.
            # next(iter(...)) returns the first alignment at DP cost only.
            try:
                aln = next(iter(alignments))
            except StopIteration:
                logger.warning(
                    f"No alignment found for sequences of length {len(signature)} "
                    f"and {len(canonical_signature)}"
                )
                return None
            
            # For PairwiseAligner, alignment sequences are accessed via aln[0] and aln[1]
            # These are aligned strings with gaps represented as '-'
            aln_seq1 = str(aln[0])
            aln_seq2 = str(aln[1])
            
            # Compute identity = matches / len(alignment.seqA)
            matches = sum(a == b for a, b in zip(aln_seq1, aln_seq2))
            identity = matches / len(aln_seq1) if len(aln_seq1) > 0 else 0.0
            
            # Compute coverage = aligned_positions / len(signature)
            aligned_positions = sum(1 for a in aln_seq1 if a != '-')
            coverage = aligned_positions / len(signature) if len(signature) > 0 else 0.0
            
            # Final score = identity * coverage * 100.0, capped at 100
            raw_score = identity * coverage
            normalized_score = min(raw_score * 100.0, 100.0)
            
            return VerificationScore(
                kind="similarity",
                metric_name="seq_identity_coverage",
                raw_score=raw_score,
                normalized_score=normalized_score,
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
