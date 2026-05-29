"""Tests for the identifier resolver registry."""

from __future__ import annotations

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolver
from src_new.identification.registry import IdentifierRegistry


class FakeSmilesResolver(IdentifierResolver):
    """Fake resolver that accepts smiles signatures."""
    
    name = "fake_smiles"
    identifier_type = "FAKE_ID"
    accepted_signatures = ["smiles"]
    
    def _is_applicable(self, signature: str) -> bool:
        return len(signature) > 0
    
    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        return ["FAKE_123"]
    
    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        return [("FAKE_123", 95.0)]


class FakeElementResolver(IdentifierResolver):
    """Fake resolver that accepts element signatures."""
    
    name = "fake_element"
    identifier_type = "ELEMENT"
    accepted_signatures = ["element"]
    
    def _is_applicable(self, signature: str) -> bool:
        return True
    
    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        return [signature]
    
    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        return []


@pytest.fixture
def config() -> RunConfig:
    """Create a default RunConfig for tests."""
    return RunConfig()


def test_registry_filters_by_signature_type(config: RunConfig) -> None:
    """Test that registry filters resolvers by signature type."""
    # Create resolvers with different accepted signature types
    smiles_resolver = FakeSmilesResolver(config)
    element_resolver = FakeElementResolver(config)
    
    registry = IdentifierRegistry([smiles_resolver, element_resolver])
    
    # Query for smiles should return only FakeSmilesResolver
    applicable = registry.get_applicable_resolvers("smiles", as_similarity=False)
    assert len(applicable) == 1
    assert applicable[0].name == "fake_smiles"
    
    # Query for element should return only FakeElementResolver
    applicable = registry.get_applicable_resolvers("element", as_similarity=False)
    assert len(applicable) == 1
    assert applicable[0].name == "fake_element"


def test_registry_filters_by_similarity_flag(config: RunConfig) -> None:
    """Test that registry filters resolvers by similarity enablement."""
    # Create resolver and disable similarity
    config.identifiers.fake_smiles_similarity = False
    
    smiles_resolver = FakeSmilesResolver(config)
    
    registry = IdentifierRegistry([smiles_resolver])
    
    # Query for similarity should return empty list (disabled)
    applicable = registry.get_applicable_resolvers("smiles", as_similarity=True)
    assert len(applicable) == 0
    
    # Query for identity should still work (enabled by default)
    applicable = registry.get_applicable_resolvers("smiles", as_similarity=False)
    assert len(applicable) == 1
    assert applicable[0].name == "fake_smiles"
