"""Tests for the base identifier resolver class."""

from __future__ import annotations

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolver, IdentifierResolutionError
from src_new.identification.cache_manager import ResolverCache


class FakeResolver(IdentifierResolver):
    """Fake resolver for testing purposes."""
    
    name = "fake"
    identifier_type = "FAKE_ID"
    accepted_signatures = ["smiles"]
    
    def _is_applicable(self, signature: str) -> bool:
        return len(signature) > 0
    
    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        return ["FAKE_123"]
    
    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        return [("FAKE_123", 95.0)]


@pytest.fixture
def config() -> RunConfig:
    """Create a default RunConfig for tests."""
    return RunConfig()


@pytest.fixture
def fake_resolver(config: RunConfig) -> FakeResolver:
    """Create a FakeResolver instance."""
    return FakeResolver(config)


def test_resolver_is_applicable_respects_signature_type(config: RunConfig) -> None:
    """Test that is_applicable respects signature type."""
    resolver = FakeResolver(config)
    
    # smiles should be OK (in accepted_signatures)
    assert resolver.is_applicable("CCO", "smiles", as_similarity=False) is True
    
    # inchikey should not be OK (not in accepted_signatures)
    assert resolver.is_applicable("UHFFFAOYSA-N", "inchikey", as_similarity=False) is False


def test_resolver_is_applicable_respects_enabled_flags(config: RunConfig) -> None:
    """Test that is_applicable respects enabled flags."""
    # Disable identity for fake resolver
    config.identifiers.fake = False
    
    resolver = FakeResolver(config)
    
    # Should return False when identity is disabled
    assert resolver.is_applicable("CCO", "smiles", as_similarity=False) is False
    
    # Similarity should still work (not disabled)
    assert resolver.is_applicable("CCO", "smiles", as_similarity=True) is True


def test_resolver_identity_returns_cached_result(config: RunConfig, tmp_path: str) -> None:
    """Test that identity resolution returns cached result without calling _resolve_identity."""
    resolver = FakeResolver(config)
    
    # Create cache and pre-populate it
    cache_config = RunConfig()
    cache_config.identifiers_cache.directory = str(tmp_path)
    cache_config.identifiers_cache.file = "test_cache.sqlite3"
    cache = ResolverCache(cache_config)
    
    # Pre-populate cache
    cache.save_identity_identifiers("fake", "CCO", ["CACHED_ID"])
    
    # Resolve should return cached value
    result = resolver.resolve("CCO", as_similarity=False, cache=cache)
    
    assert result == ["CACHED_ID"]


def test_resolver_similarity_returns_cached_result(config: RunConfig, tmp_path: str) -> None:
    """Test that similarity resolution returns cached result without calling _resolve_similarity."""
    resolver = FakeResolver(config)
    
    # Create cache and pre-populate it
    cache_config = RunConfig()
    cache_config.identifiers_cache.directory = str(tmp_path)
    cache_config.identifiers_cache.file = "test_cache.sqlite3"
    cache = ResolverCache(cache_config)
    
    # Pre-populate cache with similarity data
    cache.save_similarity_identifiers("fake", "CCO", [("CACHED_ID", 90.0)])
    
    # Resolve should return cached value
    result = resolver.resolve("CCO", as_similarity=True, cache=cache)
    
    assert result == [("CACHED_ID", 90.0)]


def test_resolver_catches_resolution_error_and_returns_none(config: RunConfig) -> None:
    """Test that IdentifierResolutionError is caught and resolve returns None."""
    
    class ErrorResolver(IdentifierResolver):
        name = "error_resolver"
        identifier_type = "ERROR_ID"
        accepted_signatures = ["smiles"]
        
        def _is_applicable(self, signature: str) -> bool:
            return True
        
        def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
            raise IdentifierResolutionError("Intentional error")
        
        def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
            raise IdentifierResolutionError("Intentional error")
    
    resolver = ErrorResolver(config)
    
    # Should return None, not raise
    result = resolver.resolve("CCO", as_similarity=False)
    assert result is None


def test_resolver_catches_unexpected_error_and_returns_none(config: RunConfig) -> None:
    """Test that unexpected errors are caught and resolve returns None."""
    
    class CrashResolver(IdentifierResolver):
        name = "crash_resolver"
        identifier_type = "CRASH_ID"
        accepted_signatures = ["smiles"]
        
        def _is_applicable(self, signature: str) -> bool:
            return True
        
        def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
            raise RuntimeError("Unexpected crash")
        
        def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
            raise RuntimeError("Unexpected crash")
    
    resolver = CrashResolver(config)
    
    # Should return None, not raise
    result = resolver.resolve("CCO", as_similarity=False)
    assert result is None
