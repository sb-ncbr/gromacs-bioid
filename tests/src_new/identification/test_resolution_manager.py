"""Tests for the identifier resolution manager."""

from __future__ import annotations

from pathlib import Path

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.base import IdentifierResolver
from src_new.identification.registry import IdentifierRegistry
from src_new.identification.resolution_manager import IdentifierResolutionManager
from src_new.results.results_manager import ResultsManager


class MockResolver(IdentifierResolver):
    """Mock resolver for testing with controllable behavior."""
    
    name = "mock_resolver"
    identifier_type = "MOCK_ID"
    accepted_signatures = ["smiles"]
    
    def __init__(self, config: RunConfig, identity_result: list[str] | None = None, 
                 similarity_result: list[tuple[str, float]] | None = None) -> None:
        super().__init__(config)
        self._identity_result = identity_result or []
        self._similarity_result = similarity_result or []
        self.call_count = 0
    
    def _is_applicable(self, signature: str) -> bool:
        return len(signature) > 0
    
    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        self.call_count += 1
        return self._identity_result
    
    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        self.call_count += 1
        return self._similarity_result


@pytest.fixture
def config(tmp_path: Path) -> RunConfig:
    """Create a RunConfig with isolated cache for each test."""
    cfg = RunConfig()
    # Use isolated cache path to avoid cross-test contamination
    cfg.identifiers_cache.directory = str(tmp_path / "cache")
    cfg.identifiers_cache.file = "test_cache.sqlite3"
    return cfg


@pytest.fixture
def results_manager(tmp_path: Path) -> ResultsManager:
    """Create a ResultsManager instance."""
    results_path = tmp_path / "results.json"
    return ResultsManager(results_path, pipeline_name="test_pipeline")


def test_resolution_manager_uses_signature_type_map(tmp_path: Path, config: RunConfig) -> None:
    """Test that resolution manager uses signature_type_map to determine signature type."""
    # Create signature type map
    signature_type_map = {
        "smiles": "smiles",
        "smiles_not_sanitized": "smiles",
    }
    
    # Create mock resolver that accepts smiles
    mock_resolver = MockResolver(config, identity_result=["MOCK_123"])
    registry = IdentifierRegistry([mock_resolver])
    
    resolution_manager = IdentifierResolutionManager(
        registry, config, signature_type_map=signature_type_map
    )
    
    # Create results with signatures under both generators
    results = ResultsManager(tmp_path / "results.json")
    results.start_run(
        step_definitions=[{"step_id": "signatures", "name": "Signatures"}],
        input_kind="pdb",
        input_files={"structure": str(tmp_path / "input.pdb")},
    )
    
    # Add signatures for both generators
    results.set_data("signatures/frag1/generated/smiles", "CCO")
    results.set_data("signatures/frag1/generated/smiles_not_sanitized", "CCO")
    
    # Resolve - both should use smiles type and be resolved
    resolution_manager.resolve_all(results)
    
    # Verify both were attempted
    attempted_smiles = results.get_data("identifiers/frag1/smiles/attempted")
    attempted_not_sanitized = results.get_data("identifiers/frag1/smiles_not_sanitized/attempted")
    
    assert attempted_smiles is not None
    assert attempted_not_sanitized is not None


def test_resolution_manager_skips_existing_when_no_overwrite(tmp_path: Path, config: RunConfig) -> None:
    """Test that resolution manager skips resolvers when hits exist and overwrite_existing=False."""
    config.identifiers.overwrite_existing = False
    
    mock_resolver = MockResolver(config, identity_result=["MOCK_123"])
    registry = IdentifierRegistry([mock_resolver])
    
    resolution_manager = IdentifierResolutionManager(registry, config)
    
    results = ResultsManager(tmp_path / "results.json")
    results.start_run(
        step_definitions=[{"step_id": "signatures", "name": "Signatures"}],
        input_kind="pdb",
        input_files={"structure": str(tmp_path / "input.pdb")},
    )
    
    # Pre-populate with existing hits
    results.set_data("signatures/frag1/generated/fake", "CCO")
    results.set_data("identifiers/frag1/fake/mock_resolver", {
        "signature": "CCO",
        "hit_type": "identity",
        "hits": ["EXISTING_ID"]
    })
    
    # Resolve - should skip because hits already exist
    resolution_manager.resolve_all(results)
    
    # Resolver should not have been called
    assert mock_resolver.call_count == 0


def test_resolution_manager_writes_attempted_and_hits(tmp_path: Path, config: RunConfig) -> None:
    """Test that resolution manager writes attempted resolvers and hits."""
    mock_resolver = MockResolver(config, identity_result=["MOCK_123"])
    registry = IdentifierRegistry([mock_resolver])
    
    # Use signature type map to map "smiles" generator to "smiles" signature type
    signature_type_map = {"smiles": "smiles"}
    resolution_manager = IdentifierResolutionManager(registry, config, signature_type_map=signature_type_map)
    
    results = ResultsManager(tmp_path / "results.json")
    results.start_run(
        step_definitions=[{"step_id": "signatures", "name": "Signatures"}],
        input_kind="pdb",
        input_files={"structure": str(tmp_path / "input.pdb")},
    )
    
    # Add a signature using "smiles" as generator name (maps to "smiles" type)
    results.set_data("signatures/frag1/generated/smiles", "CCO")
    
    # Resolve
    resolution_manager.resolve_all(results)
    
    # Verify attempted was written
    attempted = results.get_data("identifiers/frag1/smiles/attempted")
    assert attempted is not None
    assert "mock_resolver" in attempted
    
    # Verify hits were written
    hits_data = results.get_data("identifiers/frag1/smiles/mock_resolver")
    assert hits_data is not None
    assert hits_data["hit_type"] == "identity"
    assert "MOCK_123" in hits_data["hits"]


def test_resolution_manager_two_phase_identity_then_similarity(tmp_path: Path, config: RunConfig) -> None:
    """Test that resolution manager runs both identity and similarity phases."""
    # Mock resolver where identity returns empty but similarity returns hits
    mock_resolver = MockResolver(
        config, 
        identity_result=[],  # Empty identity
        similarity_result=[("SIM_ID", 90.0)]  # Similarity has hits
    )
    registry = IdentifierRegistry([mock_resolver])
    
    # Use signature type map
    signature_type_map = {"smiles": "smiles"}
    resolution_manager = IdentifierResolutionManager(registry, config, signature_type_map=signature_type_map)
    
    results = ResultsManager(tmp_path / "results.json")
    results.start_run(
        step_definitions=[{"step_id": "signatures", "name": "Signatures"}],
        input_kind="pdb",
        input_files={"structure": str(tmp_path / "input.pdb")},
    )
    
    # Add a signature
    results.set_data("signatures/frag1/generated/smiles", "CCO")
    
    # Resolve - should run both phases
    resolution_manager.resolve_all(results)
    
    # Verify both phases were called
    assert mock_resolver.call_count == 2
    
    # Verify similarity hits were stored
    hits_data = results.get_data("identifiers/frag1/smiles/mock_resolver")
    assert hits_data is not None
    assert hits_data["hit_type"] == "similarity"
    assert ("SIM_ID", 90.0) in hits_data["hits"]


def test_resolution_manager_handles_missing_signatures_data(tmp_path: Path, config: RunConfig) -> None:
    """Test that resolve_all handles missing signatures data gracefully."""
    mock_resolver = MockResolver(config, identity_result=["MOCK_123"])
    registry = IdentifierRegistry([mock_resolver])
    
    resolution_manager = IdentifierResolutionManager(registry, config)
    
    # Create empty results manager (no signatures data)
    results = ResultsManager(tmp_path / "results.json")
    results.start_run(
        step_definitions=[{"step_id": "signatures", "name": "Signatures"}],
        input_kind="pdb",
        input_files={"structure": str(tmp_path / "input.pdb")},
    )
    
    # Should not crash, just log warning and return
    resolution_manager.resolve_all(results)
    
    # No identifiers data should be written
    identifiers_data = results.get_data("identifiers")
    assert identifiers_data is None or identifiers_data == {}
