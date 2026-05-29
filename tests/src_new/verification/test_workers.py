"""Tests for verification workers (no HTTP mocking needed)."""

from __future__ import annotations

import pytest

# Try to import optional dependencies
try:
    from rdkit import Chem
    _RDKit_AVAILABLE = True
except ImportError:
    _RDKit_AVAILABLE = False

try:
    from Bio import pairwise2
    _BIOPYTHON_AVAILABLE = True
except ImportError:
    _BIOPYTHON_AVAILABLE = False

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
        """Pass invalid SMILES -> assert None or normalized_score == 0.0."""
        worker = CompoundVerificationWorker()
        # Invalid SMILES string
        score = worker.verify("INVALID_SMILES_123", "962", "PUBCHEM_CID", canonical_signature="O")
        
        # Should return None or score of 0.0
        if score is not None:
            assert score.normalized_score == 0.0


@pytest.mark.skipif(not _BIOPYTHON_AVAILABLE, reason="Biopython not installed")
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
    
    def test_sequence_worker_no_canonical_returns_none(self) -> None:
        """Pass canonical_signature=None -> assert None."""
        worker = SequenceVerificationWorker()
        score = worker.verify("MVLSPADK", "P04637", "UNIPROT_ID", canonical_signature=None)
        
        assert score is None


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
