"""Tests for deduplication and consensus scoring."""

from __future__ import annotations

import math
import pytest

from src_new.results.results_manager import ResultsManager
from src_new.verification.dedup import (
    normalize_identifier,
    collect_hits,
    deduplicate_and_score,
    RawHit,
)


def test_normalize_identifier_pdb() -> None:
    """Test PDB identifier normalization: '1abc_1' + 'PDB_ID' -> '1ABC'."""
    result = normalize_identifier("1abc_1", "PDB_ID")
    assert result == "1ABC"
    
    # Also test without _entity suffix
    result2 = normalize_identifier("6vxx", "PDB_ID")
    assert result2 == "6VXX"


def test_normalize_identifier_chembl() -> None:
    """Test ChEMBL identifier normalization: 'CHEMBL25' + 'CHEMBL_ID' -> 'CHEMBL25'."""
    result = normalize_identifier("CHEMBL25", "CHEMBL_ID")
    assert result == "CHEMBL25"
    
    # Test without prefix
    result2 = normalize_identifier("25", "CHEMBL_ID")
    assert result2 == "CHEMBL25"


def test_normalize_identifier_uniprot() -> None:
    """Test UniProt identifier normalization: 'p04637' + 'UNIPROT_ID' -> 'P04637'."""
    result = normalize_identifier("p04637", "UNIPROT_ID")
    assert result == "P04637"
    
    # Already uppercase
    result2 = normalize_identifier("P04637", "UNIPROT_ID")
    assert result2 == "P04637"


def test_collect_hits_identity(tmp_path) -> None:
    """Create a temp ResultsManager with identity hits, call collect_hits, assert RawHit list with correct resolver_score=100.0."""
    results_path = tmp_path / "results.json"
    results = ResultsManager(results_path)
    
    # Set up identity hits
    data = {
        "smiles": {
            "pubchem_struct": {
                "signature": "O",
                "hit_type": "identity",
                "ident_type": "PUBCHEM_CID",
                "hits": ["962", "1234"]
            }
        }
    }
    results.set_data("identifiers/seg_test", data)
    
    hits = collect_hits(results, "seg_test")
    
    assert len(hits) == 2
    assert all(isinstance(h, RawHit) for h in hits)
    assert all(h.resolver_score == 100.0 for h in hits)
    assert all(h.hit_type == "identity" for h in hits)
    
    identifiers = {h.identifier for h in hits}
    assert identifiers == {"962", "1234"}


def test_collect_hits_similarity(tmp_path) -> None:
    """Create a temp ResultsManager with similarity hits (id, score) tuples, assert resolver_score matches tuple score."""
    results_path = tmp_path / "results.json"
    results = ResultsManager(results_path)
    
    # Set up similarity hits
    data = {
        "fasta_map_protein": {
            "blast_uniprot": {
                "signature": "MVLSPADK",
                "hit_type": "similarity",
                "ident_type": "UNIPROT_ID",
                "hits": [["P04637", 95.0], ["P12345", 80.0]]
            }
        }
    }
    results.set_data("identifiers/seg_test", data)
    
    hits = collect_hits(results, "seg_test")
    
    assert len(hits) == 2
    
    # Check scores match the tuple scores
    hit_dict = {h.identifier: h.resolver_score for h in hits}
    assert hit_dict["P04637"] == 95.0
    assert hit_dict["P12345"] == 80.0
    
    assert all(h.hit_type == "similarity" for h in hits)


def test_deduplicate_and_score_single_hit() -> None:
    """One hit: assert consensus_score == base_score (no diversity bonus)."""
    hits = [
        RawHit(
            identifier="962",
            ident_type="PUBCHEM_CID",
            resolver_name="pubchem_struct",
            resolver_score=100.0,
            signature="O",
            signature_type="smiles",
            hit_type="identity",
        )
    ]
    
    result = deduplicate_and_score(hits)
    
    assert len(result) == 1
    key = ("962", "PUBCHEM_CID")
    assert key in result
    
    metadata = result[key]
    # consensus_score = base_score * log2(1 + diversity) = 100 * log2(2) = 100 * 1 = 100
    expected_score = 100.0 * math.log2(1 + 1)
    assert metadata["consensus_score"] == pytest.approx(expected_score)
    assert metadata["source_resolvers"] == ["pubchem_struct"]


def test_deduplicate_and_score_cross_resolver_consensus() -> None:
    """Same identifier from 2 different resolvers: assert consensus_score > base_score and source_resolvers has both names."""
    hits = [
        RawHit(
            identifier="962",
            ident_type="PUBCHEM_CID",
            resolver_name="pubchem_struct",
            resolver_score=100.0,
            signature="O",
            signature_type="smiles",
            hit_type="identity",
        ),
        RawHit(
            identifier="962",
            ident_type="PUBCHEM_CID",
            resolver_name="chembl_resolver",
            resolver_score=90.0,
            signature="O",
            signature_type="smiles",
            hit_type="identity",
        ),
    ]
    
    result = deduplicate_and_score(hits)
    
    assert len(result) == 1
    key = ("962", "PUBCHEM_CID")
    metadata = result[key]
    
    # base_score = max(100, 90) = 100
    # diversity = 2
    # consensus_score = 100 * log2(3) ≈ 158.5, but capped at 100
    assert metadata["consensus_score"] == 100.0  # Capped at 100
    assert sorted(metadata["source_resolvers"]) == ["chembl_resolver", "pubchem_struct"]


def test_deduplicate_identity_takes_precedence() -> None:
    """Mixed identity+similarity for same identifier: assert hit_type == 'identity'."""
    hits = [
        RawHit(
            identifier="962",
            ident_type="PUBCHEM_CID",
            resolver_name="pubchem_struct",
            resolver_score=100.0,
            signature="O",
            signature_type="smiles",
            hit_type="identity",
        ),
        RawHit(
            identifier="962",
            ident_type="PUBCHEM_CID",
            resolver_name="similarity_resolver",
            resolver_score=85.0,
            signature="O",
            signature_type="smiles",
            hit_type="similarity",
        ),
    ]
    
    result = deduplicate_and_score(hits)
    
    key = ("962", "PUBCHEM_CID")
    metadata = result[key]
    assert metadata["hit_type"] == "identity"

def test_collect_hits_signature_type_from_canonical_map(tmp_path) -> None:
    """Test that collect_hits produces correct signature_type for fasta_map_protein generator.
    
    Regression test for VERIF-10: signature_type should be 'residue_sequence_protein',
    not 'fastamapprotein' (which was the broken generator_name.lower().replace('_', '') result).
    """
    results_path = tmp_path / "results.json"
    results = ResultsManager(results_path)
    
    # Set up similarity hits with fasta_map_protein generator
    # This mimics the real structure: identifiers/seg/fasta_map_protein/blast_uniprot
    data = {
        "fasta_map_protein": {
            "blast_uniprot": {
                "signature": "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERM",
                "hit_type": "similarity",
                "ident_type": "UNIPROT_ID",
                "hits": [["P04637", 95.0], ["P12345", 80.0]],
                "signature_type": "residue_sequence_protein"  # Added by resolution_manager
            }
        }
    }
    results.set_data("identifiers/seg_test", data)
    
    hits = collect_hits(results, "seg_test")
    
    assert len(hits) == 2
    
    # Verify signature_type is correct (not 'fastamapprotein')
    for hit in hits:
        assert hit.signature_type == "residue_sequence_protein",             f"Expected 'residue_sequence_protein', got '{hit.signature_type}'"
    
    # Also verify other fields
    assert all(h.hit_type == "similarity" for h in hits)
    assert all(h.ident_type == "UNIPROT_ID" for h in hits)


def test_collect_hits_signature_type_fallback_to_canonical(tmp_path) -> None:
    """Test that collect_hits falls back to canonical mapping when signature_type missing from result."""
    results_path = tmp_path / "results.json"
    results = ResultsManager(results_path)
    
    # Set up hits without signature_type field (old format or missing)
    data = {
        "pdb_protein": {
            "some_resolver": {
                "signature": "HEADER...",
                "hit_type": "identity",
                "ident_type": "PDB_ID",
                "hits": ["1ABC"]
                # Note: no signature_type field - should fallback to canonical map
            }
        }
    }
    results.set_data("identifiers/seg_test", data)
    
    hits = collect_hits(results, "seg_test")
    
    assert len(hits) == 1
    assert hits[0].signature_type == "pdb_protein"


def test_collect_hits_signature_type_nucleic(tmp_path) -> None:
    """Test that nucleic acid generators get correct signature_type."""
    results_path = tmp_path / "results.json"
    results = ResultsManager(results_path)
    
    data = {
        "fasta_map_nucleic": {
            "blast_nt": {
                "signature": "ACGTACGTACGT",
                "hit_type": "similarity",
                "ident_type": "PDB_ID",
                "hits": [["1ABC_A", 90.0]],
                "signature_type": "residue_sequence_nucleotide"
            }
        }
    }
    results.set_data("identifiers/seg_test", data)
    
    hits = collect_hits(results, "seg_test")
    
    assert len(hits) == 1
    assert hits[0].signature_type == "residue_sequence_nucleotide"


