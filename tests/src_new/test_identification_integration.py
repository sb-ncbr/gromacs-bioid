"""Integration tests for signature generation and identification."""

import pytest
import json
from pathlib import Path

from src_new.results.results_manager import ResultsManager
from src_new.config.loader import RunConfig
from src_new.identification.registry import get_default_resolvers, IdentifierRegistry
from src_new.identification.resolution_manager import IdentifierResolutionManager


@pytest.fixture
def config(tmp_path):
    cfg = RunConfig()
    cfg.identifiers_cache.directory = str(tmp_path)
    cfg.identifiers_cache.file = "test_cache.sqlite3"
    cfg.names.ccd_db = str(tmp_path / "ccd.json")
    # Write a fake name DB
    (tmp_path / "ccd.json").write_text(json.dumps({"WAT": "XLYOFNOQVPJJNP-UHFFFAOYSA-N"}))
    return cfg


# Simple signature type map for testing without rdkit dependencies
SIMPLE_SIG_TYPE_MAP = {
    "atom": "element",
    "name_chain": "name",
    "name_segment": "name",
    "name_molecule": "name",
    "inchikey": "inchikey",
    "formula": "formula",
}


def test_identification_reads_signatures_from_correct_path(tmp_path, config):
    """Verify that identification reads signatures stored by the pipeline schema."""
    results = ResultsManager(tmp_path / "results.json")
    
    # Store signatures using the pipeline schema (generated/ subpath)
    results.set_data("signatures/seg1/generated/atom", "Na")
    results.set_data("signatures/seg1/generated/name_chain", "WAT")
    results.set_data("signatures/seg1/attempted", ["atom", "name_chain"])
    
    # Build identification manager
    resolvers = get_default_resolvers(config)
    registry = IdentifierRegistry(resolvers)
    manager = IdentifierResolutionManager(registry, config, signature_type_map=SIMPLE_SIG_TYPE_MAP)
    
    # Run identification
    manager.resolve_all(results)
    
    # Atom resolver should produce ELEMENT hit
    assert results.data_exists("identifiers/seg1/atom/atom")
    atom_hits = results.get_data("identifiers/seg1/atom/atom")
    assert atom_hits["hits"] == ["Na"]
    
    # Name resolver should produce INCHIKEY hit for WAT
    assert results.data_exists("identifiers/seg1/name_chain/name_ccd")
    name_hits = results.get_data("identifiers/seg1/name_chain/name_ccd")
    assert name_hits["hits"] == ["XLYOFNOQVPJJNP-UHFFFAOYSA-N"]
    
    # Attempted resolvers should be recorded
    attempted = results.get_data("identifiers/seg1/atom/attempted")
    assert "atom" in attempted


def test_identification_skips_existing_when_no_overwrite(tmp_path, config):
    """Verify overwrite_existing=False skips already-identified signatures."""
    config.identifiers.overwrite_existing = False
    
    results = ResultsManager(tmp_path / "results.json")
    results.set_data("signatures/seg1/generated/atom", "Na")
    results.set_data("identifiers/seg1/atom/atom", {"signature": "Na", "hit_type": "identity", "hits": ["Na"]})
    
    resolvers = get_default_resolvers(config)
    registry = IdentifierRegistry(resolvers)
    manager = IdentifierResolutionManager(registry, config, signature_type_map=SIMPLE_SIG_TYPE_MAP)
    
    manager.resolve_all(results)
    
    # Should still have the original hit
    atom_hits = results.get_data("identifiers/seg1/atom/atom")
    assert atom_hits["hits"] == ["Na"]


def test_identification_handles_empty_signatures_gracefully(tmp_path, config):
    """Verify identification does not crash when no signatures exist."""
    results = ResultsManager(tmp_path / "results.json")
    
    resolvers = get_default_resolvers(config)
    registry = IdentifierRegistry(resolvers)
    manager = IdentifierResolutionManager(registry, config, signature_type_map=SIMPLE_SIG_TYPE_MAP)
    
    # Should not raise
    manager.resolve_all(results)
    
    # No identifier data should be written
    assert not results.data_exists("identifiers")
