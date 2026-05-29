"""Sequence verification worker for proteins/nucleic acids using sequence alignment."""

from __future__ import annotations

import logging

from Bio import pairwise2

from ..base import VerificationWorker
from ..models import VerificationScore

logger = logging.getLogger(__name__)


class SequenceVerificationWorker(VerificationWorker):
    """Verifies protein/nucleic acid identifications using sequence alignment."""
    
    SUPPORTED_IDENT_TYPES = {"PDB_ID", "UNIPROT_ID", "ALPHAFOLD_ID"}
    
    def is_applicable(self, signature_type: str, ident_type: str) -> bool:
        """Check if this worker can verify the given signature and identifier types."""
        return (
            "residue_sequence" in signature_type.lower() and
            ident_type in self.SUPPORTED_IDENT_TYPES
        )
    
    def verify(
        self,
        signature: str,
        identifier: str,
        ident_type: str,
        canonical_signature: str | None = None,
    ) -> VerificationScore | None:
        """Verify a sequence hit by comparing using global alignment.
        
        Args:
            signature: The residue sequence extracted from simulation.
            identifier: The identifier (not used directly, canonical_signature is used).
            ident_type: The type of identifier.
            canonical_signature: The canonical sequence from database. Required.
            
        Returns:
            VerificationScore if verification was performed, None if not applicable.
        """
        # Cannot verify without canonical sequence
        if canonical_signature is None:
            return None
        
        try:
            # Use globalms alignment with parameters from original protein_nucleic_worker.py
            # match=2, mismatch=-1, gap_open=-0.5, gap_extend=-0.1
            # Note: positional arguments required for globalms
            alignments = pairwise2.align.globalms(
                signature, 
                canonical_signature,
                2,   # match
                -1,  # mismatch
                -0.5,  # gap_open
                -0.1,  # gap_extend
                one_alignment_only=True
            )
            
            if not alignments:
                logger.warning(f"No alignment found for sequences of length {len(signature)} and {len(canonical_signature)}")
                return None
            
            aln = alignments[0]
            
            # Compute identity = matches / len(alignment.seqA)
            matches = sum(a == b for a, b in zip(aln.seqA, aln.seqB))
            identity = matches / len(aln.seqA) if len(aln.seqA) > 0 else 0.0
            
            # Compute coverage = aligned_positions / len(signature)
            aligned_positions = sum(1 for a in aln.seqA if a != '-')
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
            logger.warning(f"Sequence verification failed: {e}")
            return None
