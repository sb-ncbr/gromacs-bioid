"""Structure verification worker for PDB structures using TM-score or sequence proxy."""

from __future__ import annotations

import logging
import tempfile
import os

import numpy as np
from Bio.Align import PairwiseAligner
from Bio.PDB import PDBParser, Polypeptide

from ..base import VerificationWorker
from ..models import VerificationScore

logger = logging.getLogger(__name__)


# Try to import tmtools, fall back to sequence-based comparison if not available.
# NOTE (v3.138): `from tmtools import tmscore` used to bind the tmtools
# *submodule* (not a callable), so this worker silently fell back to the
# sequence proxy in every environment where tmtools was installed. The real
# entry point is tm_align(x, y, seqx, seqy) — coordinates first, then
# one-letter sequences; requires BOTH, aligned index-for-index.
try:
    from tmtools import tm_align
    _TMTOOLS_AVAILABLE = True
except ImportError:
    _TMTOOLS_AVAILABLE = False
    tm_align = None


class StructureVerificationWorker(VerificationWorker):
    """Verifies structural identifications using TM-score or sequence alignment proxy."""
    
    SUPPORTED_IDENT_TYPES = {"PDB_ID", "ALPHAFIND_ID", "ALPHAFOLD_ID"}
    SUPPORTED_SIGNATURE_TYPES = {"pdb_protein", "pdb_nucleic", "ca_only_pdb"}
    
    # TM-score threshold for "same fold"
    TM_SCORE_THRESHOLD = 0.5
    
    def is_applicable(self, signature_type: str, ident_type: str) -> bool:
        """Check if this worker can verify the given signature and identifier types."""
        return (
            signature_type.lower() in self.SUPPORTED_SIGNATURE_TYPES and
            ident_type in self.SUPPORTED_IDENT_TYPES
        )
    
    def verify(
        self,
        signature: str,
        identifier: str,
        ident_type: str,
        canonical_signature: str | None = None,
        signature_type: str | None = None,
    ) -> VerificationScore | None:
        """Verify a structural hit by comparing PDB structures.
        
        Args:
            signature: The PDB structure string extracted from simulation.
            identifier: The identifier (not used directly, canonical_signature is used).
            ident_type: The type of identifier.
            canonical_signature: The canonical PDB structure string from database. Required.
            
        Returns:
            VerificationScore if verification was performed, None if not applicable.
        """
        # Cannot verify without canonical structure
        if canonical_signature is None:
            return None
        
        try:
            # Try primary method: TM-score via tmtools
            if _TMTOOLS_AVAILABLE:
                score = self._verify_with_tmscore(signature, canonical_signature)
                if score is not None:
                    return score
            
            # Fallback: sequence-based comparison
            return self._verify_with_sequence_proxy(signature, canonical_signature)
            
        except Exception as e:
            logger.warning(f"Structure verification failed: {e}")
            return None
    
    def _extract_ca_chain(self, pdb_string: str) -> tuple[str, np.ndarray] | None:
        """Extract the CA chain (one-letter sequence + coordinates) from a PDB string.

        Sequence and coordinates are collected in the SAME residue iteration,
        so they are aligned index-for-index — tm_align requires exactly that.

        Returns:
            (sequence, (N, 3) float64 coords), or None on failure.
        """
        try:
            from Bio.SeqUtils import seq1

            # Write to temp file for parsing
            fd, temp_path = tempfile.mkstemp(suffix=".pdb")
            try:
                os.write(fd, pdb_string.encode('utf-8'))
                os.close(fd)

                parser = PDBParser(QUIET=True)
                structure = parser.get_structure("temp", temp_path)

                seq_chars: list[str] = []
                ca_coords = []
                for model in structure:
                    for chain in model:
                        for residue in chain:
                            if "CA" in residue:
                                ca_coords.append(residue["CA"].coord)
                                try:
                                    seq_chars.append(seq1(residue.get_resname()))
                                except (KeyError, ValueError):
                                    seq_chars.append("X")

                if not ca_coords:
                    return None

                return "".join(seq_chars), np.array(ca_coords, dtype=np.float64)

            finally:
                os.unlink(temp_path)

        except Exception as e:
            logger.warning(f"Failed to extract CA chain: {e}")
            return None
    
    def _verify_with_tmscore(
        self, 
        signature: str, 
        canonical_signature: str
    ) -> VerificationScore | None:
        """Verify using TM-score via tmtools.
        
        Returns:
            VerificationScore with tm_score metric, or None on failure.
        """
        try:
            chain1 = self._extract_ca_chain(signature)
            chain2 = self._extract_ca_chain(canonical_signature)

            if chain1 is None or chain2 is None:
                logger.warning("Could not extract CA chains for TM-score")
                return None
            seq1, coords1 = chain1
            seq2, coords2 = chain2

            # Check for NaN in coordinates
            if np.any(np.isnan(coords1)) or np.any(np.isnan(coords2)):
                logger.warning("NaN detected in CA coordinates")
                return None

            # Compute TM-score. tm_norm_chain2 is normalized by the canonical
            # (target) length — matches the AlphaFind/MVS "tm_score_target"
            # convention (live probe: 0.9589 for 1CRN vs AF-P01542-F1).
            result = tm_align(coords1, coords2, seq1, seq2)
            tm_score = float(result.tm_norm_chain2)
            
            # Check for NaN result
            if np.isnan(tm_score):
                logger.warning("TM-score returned NaN")
                return None
            
            # TM-score is 0-1, scale to 0-100
            normalized_score = min(tm_score * 100.0, 100.0)
            
            return VerificationScore(
                kind="similarity",
                metric_name="tm_score",
                raw_score=tm_score,
                normalized_score=normalized_score,
            )
            
        except Exception as e:
            logger.warning(f"TM-score computation failed: {e}")
            return None
    
    def _extract_sequence_from_pdb(self, pdb_string: str) -> str | None:
        """Extract residue sequence from a PDB string.
        
        Uses CA atom presence to determine residues.
        Maps 3-letter codes to 1-letter codes where possible.
        
        Returns:
            Sequence string (one letter per residue), or None on failure.
        """
        try:
            fd, temp_path = tempfile.mkstemp(suffix=".pdb")
            try:
                os.write(fd, pdb_string.encode('utf-8'))
                os.close(fd)
                
                parser = PDBParser(QUIET=True)
                structure = parser.get_structure("temp", temp_path)
                
                sequence = []
                for model in structure:
                    for chain in model:
                        for residue in chain:
                            # Check if residue has CA atom
                            if "CA" not in residue:
                                continue
                            
                            resname = residue.resname
                            # Try to map 3-letter to 1-letter code
                            try:
                                one_letter = Polypeptide.protein_letters_3to1.get(resname, 'X')
                            except (KeyError, TypeError):
                                one_letter = 'X'
                            
                            sequence.append(one_letter)
                
                return ''.join(sequence) if sequence else None
                
            finally:
                os.unlink(temp_path)
                
        except Exception as e:
            logger.warning(f"Failed to extract sequence from PDB: {e}")
            return None
    
    def _verify_with_sequence_proxy(
        self, 
        signature: str, 
        canonical_signature: str
    ) -> VerificationScore:
        """Verify using sequence alignment as a proxy for structural similarity.
        
        This is the fallback when tmtools is not available.
        
        Returns:
            VerificationScore with structure_sequence_proxy metric.
        """
        try:
            seq1 = self._extract_sequence_from_pdb(signature)
            seq2 = self._extract_sequence_from_pdb(canonical_signature)
            
            if seq1 is None or seq2 is None:
                logger.warning("Could not extract sequences for proxy comparison")
                return VerificationScore(
                    kind="similarity",
                    metric_name="structure_sequence_proxy",
                    raw_score=0.0,
                    normalized_score=0.0,
                )
            
            if len(seq1) == 0 or len(seq2) == 0:
                return VerificationScore(
                    kind="similarity",
                    metric_name="structure_sequence_proxy",
                    raw_score=0.0,
                    normalized_score=0.0,
                )
            
            # Use PairwiseAligner with same parameters as SequenceVerificationWorker
            # match=2, mismatch=-1, gap_open=-0.5, gap_extend=-0.1
            aligner = PairwiseAligner()
            aligner.mode = "global"
            aligner.match_score = 2
            aligner.mismatch_score = -1
            aligner.open_gap_score = -0.5
            aligner.extend_gap_score = -0.1
            
            alignments = aligner.align(seq1, seq2)
            
            if not alignments:
                logger.warning(f"No alignment found for structure sequences")
                return VerificationScore(
                    kind="similarity",
                    metric_name="structure_sequence_proxy",
                    raw_score=0.0,
                    normalized_score=0.0,
                )
            
            aln = alignments[0]
            
            # For PairwiseAligner, alignment sequences are accessed via aln[0] and aln[1]
            aln_seq1 = str(aln[0])
            aln_seq2 = str(aln[1])
            
            # Compute identity = matches / len(alignment.seqA)
            matches = sum(a == b for a, b in zip(aln_seq1, aln_seq2))
            identity = matches / len(aln_seq1) if len(aln_seq1) > 0 else 0.0
            
            # Compute coverage = aligned_positions / len(seq1)
            aligned_positions = sum(1 for a in aln_seq1 if a != '-')
            coverage = aligned_positions / len(seq1) if len(seq1) > 0 else 0.0
            
            # Final score = identity * coverage * 100.0, capped at 100
            raw_score = identity * coverage
            normalized_score = min(raw_score * 100.0, 100.0)
            
            return VerificationScore(
                kind="similarity",
                metric_name="structure_sequence_proxy",
                raw_score=raw_score,
                normalized_score=normalized_score,
            )
            
        except Exception as e:
            logger.warning(f"Sequence proxy verification failed: {e}")
            return VerificationScore(
                kind="similarity",
                metric_name="structure_sequence_proxy",
                raw_score=0.0,
                normalized_score=0.0,
            )
