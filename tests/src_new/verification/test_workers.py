"""Tests for verification workers (no HTTP mocking needed)."""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

# Try to import optional dependencies
try:
    from rdkit import Chem
    _RDKit_AVAILABLE = True
except ImportError:
    _RDKit_AVAILABLE = False

try:
    from Bio.Align import PairwiseAligner
    _BIOPYTHON_ALIGN_AVAILABLE = True
except ImportError:
    _BIOPYTHON_ALIGN_AVAILABLE = False

from src_new.verification.workers import (
    CompoundVerificationWorker,
    SequenceVerificationWorker,
    StructureVerificationWorker,
)


@pytest.mark.skipif(not _RDKit_AVAILABLE, reason="RDKit not installed")
class TestCompoundWorker:
    """Tests for CompoundVerificationWorker."""
    
    def test_compound_worker_identical_smiles(self) -> None:
        """Verify identical larger SMILES -> assert normalized_score >= 95.0."""
        worker = CompoundVerificationWorker()
        # Use a larger molecule (caffeine) for better fingerprint matching
        caffeine = "CN1C=NC2=C1C(=O)N(C(=O)N2C)C"
        score = worker.verify(caffeine, "2519", "PUBCHEM_CID", canonical_signature=caffeine)
        
        assert score is not None
        assert score.normalized_score >= 95.0
        assert score.kind == "similarity"
    
    def test_compound_worker_different_smiles(self) -> None:
        """Verify 'O' against 'CCO' (ethanol) -> assert normalized_score < 50.0."""
        worker = CompoundVerificationWorker()
        score = worker.verify("O", "962", "PUBCHEM_CID", canonical_signature="CCO")
        
        assert score is not None
        assert score.normalized_score < 50.0
    
    def test_compound_worker_no_canonical_returns_none(self) -> None:
        """Pass canonical_signature=None -> assert None."""
        worker = CompoundVerificationWorker()
        score = worker.verify("O", "962", "PUBCHEM_CID", canonical_signature=None)
        
        assert score is None
    
    def test_compound_worker_invalid_smiles(self) -> None:
        """Pass invalid SMILES string -> assert None or normalized_score == 0.0."""
        worker = CompoundVerificationWorker()
        # Invalid SMILES string
        score = worker.verify("INVALID_SMILES_123", "962", "PUBCHEM_CID", canonical_signature="O")
        
        # Should return None or score of 0.0
        if score is not None:
            assert score.normalized_score == 0.0


@pytest.mark.skipif(not _BIOPYTHON_ALIGN_AVAILABLE, reason="Biopython not installed")
class TestSequenceWorker:
    """Tests for SequenceVerificationWorker."""
    
    def test_sequence_worker_identical_sequences(self) -> None:
        """Identical beta-globin fragment -> assert normalized_score >= 95.0."""
        worker = SequenceVerificationWorker()
        beta_fragment = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR"
        
        score = worker.verify(
            beta_fragment, 
            "P04637", 
            "UNIPROT_ID", 
            canonical_signature=beta_fragment
        )
        
        assert score is not None
        assert score.normalized_score >= 95.0
        assert score.kind == "similarity"
    
    def test_sequence_worker_different_sequences(self) -> None:
        """Verify full beta-globin against a short unrelated sequence -> assert normalized_score < 50.0."""
        worker = SequenceVerificationWorker()
        beta_globin = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR"
        unrelated = "AAAAA"
        
        score = worker.verify(
            unrelated,
            "P04637",
            "UNIPROT_ID",
            canonical_signature=beta_globin
        )
        
        assert score is not None
        assert score.normalized_score < 50.0
    
    def test_sequence_worker_matrix_cap_skips_alignment(self) -> None:
        """title: titin-class pairs must not run the DP matrix at all.

        Patch PairwiseAligner to explode if constructed; a pair whose length
        product exceeds MAX_ALIGN_MATRIX_CELLS must return None without it.
        """
        worker = SequenceVerificationWorker()
        huge_a = "A" * 6000
        huge_b = "G" * 5000  # 30M cells > 25M cap
        with patch.object(
            __import__("src_new.verification.workers.sequence_worker", fromlist=["PairwiseAligner"]),
            "PairwiseAligner",
            side_effect=AssertionError("aligner must not be constructed"),
        ):
            score = worker._compute_alignment_score(huge_a, huge_b)
        assert score is None

    def test_sequence_worker_no_count_materialization(self) -> None:
        """len(alignments) must never be requested (count-overflow pathology)."""
        worker = SequenceVerificationWorker()
        seq = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHF"

        class _ExplodingAlignments:
            def __len__(self):
                raise AssertionError("len() must not be materialized")

            def __bool__(self):
                raise AssertionError("bool() must not be used (triggers len)")

            def __iter__(self):
                fake = MagicMock()
                fake.__getitem__ = lambda self_, i: seq if i == 0 else seq
                yield fake

        with patch(
            "src_new.verification.workers.sequence_worker.PairwiseAligner"
        ) as mock_cls:
            inst = mock_cls.return_value
            inst.mode = None
            inst.match_score = None
            inst.mismatch_score = None
            inst.open_gap_score = None
            inst.extend_gap_score = None
            inst.align.return_value = _ExplodingAlignments()
            score = worker._compute_alignment_score(seq, seq)
        assert score is not None
        assert score.normalized_score >= 99.0

    def test_sequence_worker_no_canonical_returns_none(self) -> None:
        """Pass canonical_signature=None -> assert None."""
        worker = SequenceVerificationWorker()
        score = worker.verify("MVLSPADK", "P04637", "UNIPROT_ID", canonical_signature=None)
        
        assert score is None
    
    def test_sequence_worker_is_applicable_new_types(self) -> None:
        """Test is_applicable for new identifier types (NR_ID, SWISSPROT_ID, NT_ID, CORE_NT_ID)."""
        worker = SequenceVerificationWorker()
        
        # All new types should be applicable for residue_sequence signatures
        assert worker.is_applicable("residue_sequence_protein", "NR_ID") is True
        assert worker.is_applicable("residue_sequence_protein", "SWISSPROT_ID") is True
        assert worker.is_applicable("residue_sequence_nucleotide", "NT_ID") is True
        assert worker.is_applicable("residue_sequence_nucleotide", "CORE_NT_ID") is True
        
        # Old types should still work
        assert worker.is_applicable("residue_sequence_protein", "PDB_ID") is True
        assert worker.is_applicable("residue_sequence_protein", "UNIPROT_ID") is True
        assert worker.is_applicable("residue_sequence_protein", "ALPHAFOLD_ID") is True
        
        # Unsupported types should return False
        assert worker.is_applicable("residue_sequence_protein", "PUBCHEM_CID") is False
    
    def test_sequence_worker_pairwise_aligner_used(self) -> None:
        """Test that PairwiseAligner is used instead of deprecated pairwise2."""
        worker = SequenceVerificationWorker()
        seq = "MVLSPADK"
        
        # Mock PairwiseAligner to verify it's called
        with patch('src_new.verification.workers.sequence_worker.PairwiseAligner') as mock_aligner_class:
            mock_aligner = MagicMock()
            mock_aligner_class.return_value = mock_aligner
            
            # Create a mock alignment result
            mock_alignment = MagicMock()
            mock_alignment.__getitem__.side_effect = lambda idx: seq if idx == 0 else seq
            mock_aligner.align.return_value = [mock_alignment]
            
            worker.verify(seq, "TEST", "UNIPROT_ID", canonical_signature=seq)
            
            # Verify PairwiseAligner was instantiated and configured
            mock_aligner_class.assert_called_once()
            assert mock_aligner.mode == "global"
            assert mock_aligner.match_score == 2
            assert mock_aligner.mismatch_score == -1
            assert mock_aligner.open_gap_score == -0.5
            assert mock_aligner.extend_gap_score == -0.1
            mock_aligner.align.assert_called_once()
    
    @patch("src_new.verification.fetchers.sequence_fetcher.SequenceSignatureFetcher._fetch_pdb_entities")
    def test_sequence_worker_pdb_multi_entity_best_match(self, mock_fetch_entities) -> None:
        """Test that SequenceVerificationWorker picks best-matching PDB entity.
        
        When given a query sequence matching the second entity (not the first),
        the worker should return a high score by selecting the correct entity.
        """
        # Mock _fetch_pdb_entities to return two sequences
        # First entity: "AAAA" (won't match query)
        # Second entity: "MVLSPADKT" (will match query)
        mock_fetch_entities.return_value = ["AAAA", "MVLSPADKT"]
        
        worker = SequenceVerificationWorker()
        query_seq = "MVLSPADKT"
        
        # The canonical_signature provided is the first entity (mismatch)
        # but the worker should fetch entities and pick the best match
        score = worker.verify(
            query_seq,
            "1ABC",
            "PDB_ID",
            canonical_signature="AAAA"  # This is the "wrong" entity
        )
        
        # Should get high score because worker picked the matching entity
        assert score is not None
        assert score.normalized_score >= 95.0, f"Expected high score for matching entity, got {score.normalized_score}"
        
        # Verify _fetch_pdb_entities was called
        mock_fetch_entities.assert_called_once_with("1ABC")
    
    @patch("src_new.verification.fetchers.sequence_fetcher.SequenceSignatureFetcher._fetch_pdb_entities")
    def test_sequence_worker_pdb_fallback_to_canonical(self, mock_fetch_entities) -> None:
        """Test fallback when _fetch_pdb_entities returns empty list."""
        # Mock empty entity list
        mock_fetch_entities.return_value = []
        
        worker = SequenceVerificationWorker()
        seq = "MVLSPADK"
        
        # Should fall back to provided canonical_signature
        score = worker.verify(
            seq,
            "1ABC",
            "PDB_ID",
            canonical_signature=seq
        )
        
        assert score is not None
        assert score.normalized_score >= 95.0


class TestStructureWorker:
    """Tests for StructureVerificationWorker."""
    
    def test_structure_worker_is_applicable(self) -> None:
        """is_applicable('pdb_protein', 'PDB_ID') -> True, is_applicable('smiles', 'PDB_ID') -> False."""
        worker = StructureVerificationWorker()
        
        assert worker.is_applicable("pdb_protein", "PDB_ID") is True
        assert worker.is_applicable("pdb_nucleic", "PDB_ID") is True
        assert worker.is_applicable("smiles", "PDB_ID") is False
        assert worker.is_applicable("pdb_protein", "PUBCHEM_CID") is False
    
    def test_structure_worker_identical_pdb(self, minimal_pdb) -> None:
        """Verify two copies of the minimal PDB fixture against each other -> assert normalized_score >= 95.0."""
        worker = StructureVerificationWorker()
        
        score = worker.verify(
            minimal_pdb,
            "1ABC",
            "PDB_ID",
            canonical_signature=minimal_pdb
        )
        
        assert score is not None
        # With sequence proxy (fallback when tmtools unavailable), identical sequences should score high
        assert score.normalized_score >= 95.0
    
    def test_structure_worker_different_pdb(self, minimal_pdb) -> None:
        """Verify minimal PDB against a 2-residue variant (remove SER) -> assert normalized_score < 80.0."""
        worker = StructureVerificationWorker()
        
        # Create a 2-residue variant by removing SER residues (lines 9-12)
        variant_pdb = """HEADER    TEST
ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N
ATOM      2  CA  ALA A   1      10.500  10.500  10.500  1.00  0.00           C
ATOM      3  C   ALA A   1      11.000  11.000  11.000  1.00  0.00           C
ATOM      4  O   ALA A   1      11.500  11.500  11.500  1.00  0.00           O
ATOM      5  N   GLY A   2      12.000  12.000  12.000  1.00  0.00           N
ATOM      6  CA  GLY A   2      12.500  12.500  12.500  1.00  0.00           C
ATOM      7  C   GLY A   2      13.000  13.000  13.000  1.00  0.00           C
ATOM      8  O   GLY A   2      13.500  13.500  13.500  1.00  0.00           O
END
"""
        
        score = worker.verify(
            variant_pdb,
            "1ABC",
            "PDB_ID",
            canonical_signature=minimal_pdb
        )
        
        assert score is not None
        # Different structures should have lower score
        assert score.normalized_score < 80.0
    
    def test_structure_worker_no_canonical_returns_none(self, minimal_pdb) -> None:
        """Pass canonical_signature=None -> assert None."""
        worker = StructureVerificationWorker()
        
        score = worker.verify(
            minimal_pdb,
            "1ABC",
            "PDB_ID",
            canonical_signature=None
        )
        
        assert score is None
    
    def test_structure_worker_pairwise_aligner_used(self, minimal_pdb) -> None:
        """Test that PairwiseAligner is used instead of deprecated pairwise2 in sequence proxy."""
        worker = StructureVerificationWorker()
        
        # Mock PairwiseAligner to verify it's called in the sequence proxy fallback
        with patch('src_new.verification.workers.structure_worker.PairwiseAligner') as mock_aligner_class:
            mock_aligner = MagicMock()
            mock_aligner_class.return_value = mock_aligner
            
            # Create a mock alignment result
            mock_alignment = MagicMock()
            mock_alignment.__getitem__.side_effect = lambda idx: "AA" if idx == 0 else "AA"
            mock_aligner.align.return_value = [mock_alignment]
            
            worker.verify(minimal_pdb, "1ABC", "PDB_ID", canonical_signature=minimal_pdb)
            
            # Verify PairwiseAligner was called (in sequence proxy fallback)
            mock_aligner.align.assert_called()
