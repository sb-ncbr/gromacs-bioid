"""Tests for the verification registry."""

from __future__ import annotations

from src_new.verification.registry import get_default_registry, VerificationRegistry
from src_new.verification.fetchers import (
    CompoundSignatureFetcher,
    SequenceSignatureFetcher,
    StructureSignatureFetcher,
)
from src_new.verification.scorers import (
    PDBAnnotationScorer,
    UniProtAnnotationScorer,
    PubChemAnnotationScorer,
    ChemblAnnotationScorer,
    ChebiAnnotationScorer,
)
from src_new.verification.workers import (
    CompoundVerificationWorker,
    SequenceVerificationWorker,
    StructureVerificationWorker,
)


def test_registry_get_applicable_workers_compound() -> None:
    """get_applicable_workers('smiles', 'PUBCHEM_CID') returns non-empty list containing CompoundVerificationWorker."""
    registry = get_default_registry()
    workers = registry.get_applicable_workers("smiles", "PUBCHEM_CID")
    
    assert len(workers) > 0
    assert any(isinstance(w, CompoundVerificationWorker) for w in workers)


def test_registry_get_applicable_workers_sequence() -> None:
    """get_applicable_workers('residue_sequence_protein', 'UNIPROT_ID') returns SequenceVerificationWorker."""
    registry = get_default_registry()
    workers = registry.get_applicable_workers("residue_sequence_protein", "UNIPROT_ID")
    
    assert len(workers) > 0
    assert any(isinstance(w, SequenceVerificationWorker) for w in workers)


def test_registry_get_applicable_workers_structure() -> None:
    """get_applicable_workers('pdb_protein', 'PDB_ID') returns StructureVerificationWorker."""
    registry = get_default_registry()
    workers = registry.get_applicable_workers("pdb_protein", "PDB_ID")
    
    assert len(workers) > 0
    assert any(isinstance(w, StructureVerificationWorker) for w in workers)


def test_registry_get_fetcher_pubchem() -> None:
    """get_fetcher('PUBCHEM_CID') returns CompoundSignatureFetcher."""
    registry = get_default_registry()
    fetcher = registry.get_fetcher("PUBCHEM_CID")
    
    assert isinstance(fetcher, CompoundSignatureFetcher)


def test_registry_get_fetcher_chembl() -> None:
    """get_fetcher('CHEMBL_ID') returns CompoundSignatureFetcher."""
    registry = get_default_registry()
    fetcher = registry.get_fetcher("CHEMBL_ID")
    
    assert isinstance(fetcher, CompoundSignatureFetcher)


def test_registry_get_fetcher_uniprot() -> None:
    """get_fetcher('UNIPROT_ID') returns SequenceSignatureFetcher."""
    registry = get_default_registry()
    fetcher = registry.get_fetcher("UNIPROT_ID")
    
    assert isinstance(fetcher, SequenceSignatureFetcher)


def test_registry_get_fetcher_pdb() -> None:
    """get_fetcher('PDB_ID') returns a fetcher that supports PDB (SequenceSignatureFetcher is returned first)."""
    # Note: Both SequenceSignatureFetcher and StructureSignatureFetcher support PDB_ID.
    # The registry returns the first matching fetcher, which is SequenceSignatureFetcher.
    registry = get_default_registry()
    fetcher = registry.get_fetcher("PDB_ID")
    
    # SequenceSignatureFetcher is listed first in the default registry
    assert isinstance(fetcher, SequenceSignatureFetcher)


def test_registry_get_scorer_pdb() -> None:
    """get_scorer('PDB_ID') returns PDBAnnotationScorer."""
    registry = get_default_registry()
    scorer = registry.get_scorer("PDB_ID")
    
    assert isinstance(scorer, PDBAnnotationScorer)


def test_registry_get_scorer_uniprot() -> None:
    """get_scorer('UNIPROT_ID') returns UniProtAnnotationScorer."""
    registry = get_default_registry()
    scorer = registry.get_scorer("UNIPROT_ID")
    
    assert isinstance(scorer, UniProtAnnotationScorer)


def test_registry_get_scorer_pubchem() -> None:
    """get_scorer('PUBCHEM_CID') returns PubChemAnnotationScorer."""
    registry = get_default_registry()
    scorer = registry.get_scorer("PUBCHEM_CID")
    
    assert isinstance(scorer, PubChemAnnotationScorer)


def test_registry_get_scorer_chembl() -> None:
    """get_scorer('CHEMBL_ID') returns ChemblAnnotationScorer."""
    registry = get_default_registry()
    scorer = registry.get_scorer("CHEMBL_ID")
    
    assert isinstance(scorer, ChemblAnnotationScorer)


def test_registry_get_scorer_chebi() -> None:
    """get_scorer('CHEBI_ID') returns ChebiAnnotationScorer."""
    registry = get_default_registry()
    scorer = registry.get_scorer("CHEBI_ID")
    
    assert isinstance(scorer, ChebiAnnotationScorer)


def test_registry_get_fetcher_unknown_returns_none() -> None:
    """get_fetcher('UNKNOWN_ID') returns None."""
    registry = get_default_registry()
    fetcher = registry.get_fetcher("UNKNOWN_ID")
    
    assert fetcher is None


def test_registry_get_scorer_unknown_returns_none() -> None:
    """get_scorer('UNKNOWN_ID') returns None."""
    registry = get_default_registry()
    scorer = registry.get_scorer("UNKNOWN_ID")
    
    assert scorer is None


def test_registry_empty_workers() -> None:
    """get_applicable_workers with no matching type returns empty list."""
    registry = get_default_registry()
    workers = registry.get_applicable_workers("unknown_type", "UNKNOWN_ID")
    
    assert workers == []
