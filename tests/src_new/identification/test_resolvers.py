"""Tests for individual identifier resolvers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.atom import AtomResolver
from src_new.identification.resolvers.name import NameResolverCCD
from src_new.identification.resolvers.inchikey import InchiKeyResolver
from src_new.identification.resolvers.formula import FormulaResolver


@pytest.fixture
def config() -> RunConfig:
    """Create a default RunConfig for tests."""
    return RunConfig()


def test_atom_resolver_returns_signature_as_identity(config: RunConfig) -> None:
    """Test that AtomResolver returns the signature as identity."""
    resolver = AtomResolver(config)
    
    result = resolver.resolve("Na", as_similarity=False)
    
    assert result == ["Na"]


def test_atom_similarity_returns_empty(config: RunConfig) -> None:
    """Test that AtomResolver returns empty list for similarity."""
    resolver = AtomResolver(config)
    
    result = resolver.resolve("Na", as_similarity=True)
    
    assert result == []


def test_name_resolver_caches_db(tmp_path: Path, config: RunConfig) -> None:
    """Test that NameResolver caches the database and reads only once."""
    # Create fake CCD JSON
    ccd_db = tmp_path / "ccd.json"
    ccd_db.write_text(json.dumps({"WAT": "XLYOFNOQVPJJNP-UHFFFAOYSA-N"}))
    
    config.names.ccd_db = str(ccd_db)
    
    resolver = NameResolverCCD(config)
    
    # Track file opens
    open_count = 0
    original_open = open
    
    def counting_open(*args, **kwargs):
        nonlocal open_count
        if len(args) > 0 and str(args[0]) == str(ccd_db):
            open_count += 1
        return original_open(*args, **kwargs)
    
    # First resolve - should read file
    with patch("builtins.open", side_effect=counting_open):
        result1 = resolver.resolve("WAT", as_similarity=False)
        assert result1 == ["XLYOFNOQVPJJNP-UHFFFAOYSA-N"]
        first_count = open_count
    
    # Second resolve - should use cache, no additional file read
    with patch("builtins.open", side_effect=counting_open):
        result2 = resolver.resolve("WAT", as_similarity=False)
        assert result2 == ["XLYOFNOQVPJJNP-UHFFFAOYSA-N"]
    
    # File should only be read once
    assert open_count == first_count


def test_name_resolver_returns_hit_when_name_in_db(tmp_path: Path, config: RunConfig) -> None:
    """Test that NameResolver returns InChIKey when name is in database."""
    # Create fake CCD JSON
    ccd_db = tmp_path / "ccd.json"
    ccd_db.write_text(json.dumps({"WAT": "XLYOFNOQVPJJNP-UHFFFAOYSA-N"}))
    
    config.names.ccd_db = str(ccd_db)
    
    resolver = NameResolverCCD(config)
    
    result = resolver.resolve("WAT", as_similarity=False)
    
    assert result == ["XLYOFNOQVPJJNP-UHFFFAOYSA-N"]


def test_name_resolver_returns_empty_when_name_missing(tmp_path: Path, config: RunConfig) -> None:
    """Test that NameResolver returns empty list when name is not in database."""
    # Create empty CCD JSON
    ccd_db = tmp_path / "ccd.json"
    ccd_db.write_text(json.dumps({}))
    
    config.names.ccd_db = str(ccd_db)
    
    resolver = NameResolverCCD(config)
    
    result = resolver.resolve("MISSING_NAME", as_similarity=False)
    
    assert result == []


def test_inchikey_resolver_not_applicable_for_smiles(config: RunConfig) -> None:
    """Test that InchiKeyResolver is not applicable for smiles signatures."""
    resolver = InchiKeyResolver(config)
    
    # CCO is a SMILES string, not an InChIKey
    result = resolver.is_applicable("CCO", "smiles")
    
    assert result is False


def test_formula_resolver_not_applicable_for_smiles(config: RunConfig) -> None:
    """Test that FormulaResolver is not applicable for smiles signatures."""
    resolver = FormulaResolver(config)
    
    # CCO is a SMILES string, not a formula
    result = resolver.is_applicable("CCO", "smiles")
    
    assert result is False
