"""End-to-end tests for BLAST resolution → verification → API response path."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager
from src_new.identification.base import IdentifierResolutionError
from src_new.verification.registry import VerificationRegistry, get_default_registry
from src_new.verification.manager import VerificationManager
from src_new.verification.base import AnnotationQualityScorer
from src_new.verification.models import AnnotationQuality


# =============================================================================
# Helper functions for creating mock BLAST output
# =============================================================================


def make_blast_json(hits: list[dict], query_len: int) -> dict:
    """Create a realistic BLAST outfmt-15 JSON result."""
    blast_hits = []
    for hit in hits:
        blast_hits.append({
            "description": [{"accession": hit["accession"]}],
            "hsps": [{
                "bit_score": hit["bit_score"],
                "evalue": hit["evalue"],
                "align_len": hit["align_len"],
                "identity": hit["identity"],
            }]
        })
    
    return {
        "BlastOutput2": {
            "report": {
                "results": {
                    "search": {
                        "query_len": query_len,
                        "hits": blast_hits
                    }
                }
            }
        }
    }


def _mock_subprocess_run_factory(query_sequence: str, hit_accession: str):
    """Create a mock subprocess.run function for BLAST."""
    def mock_run(cmd, input=None, text=False, capture_output=False, timeout=None):
        if "blastp" in str(cmd) or "blastn" in str(cmd):
            query_len = len(query_sequence.replace("\n", "").strip())
            hit_data = {
                "accession": hit_accession,
                "identity": query_len,
                "align_len": query_len,
                "bit_score": 200.0,
                "evalue": 1e-100,
            }
            blast_output = make_blast_json([hit_data], query_len)
            
            output_path = None
            for i, arg in enumerate(cmd):
                if arg == "-out" and i + 1 < len(cmd):
                    output_path = cmd[i + 1]
                    break
            
            if output_path:
                with open(output_path, "w") as f:
                    json.dump(blast_output, f)
            
            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result
        
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result
    
    return mock_run


def _mock_requests_get_factory(query_sequence: str):
    """Create a mock requests.get function for PDB API responses."""
    def mock_get(url, timeout=None):
        response = MagicMock()
        
        if "/core/entry/" in url:
            response.json.return_value = {
                "rcsb_entry_container_identifiers": {
                    "polymer_entity_ids": ["1"]
                }
            }
            response.raise_for_status = MagicMock()
            response.text = ""
            return response
        
        if "/core/polymer_entity/" in url:
            response.json.return_value = {
                "entity_poly": {
                    "pdbx_seq_one_letter_code_can": query_sequence
                }
            }
            response.raise_for_status = MagicMock()
            response.text = ""
            return response
        
        import requests
        response.raise_for_status = MagicMock(side_effect=requests.exceptions.RequestException("Mocked network error"))
        response.text = ""
        return response
    
    return mock_get


# =============================================================================
# Test 1: Full happy path - BLAST identity → verification → API
# =============================================================================


def test_blast_identity_to_verification_to_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the full pipeline: FASTA signature → BLAST resolution → verification → API response."""
    
    # -------------------------------------------------------------------------
    # Setup - configure BEFORE creating resolvers
    # -------------------------------------------------------------------------
    
    config = RunConfig.from_default_ini()
    config.override("identifiers_cache.directory", str(tmp_path))
    config.override("identifiers_cache.file", "test_cache.sqlite3")
    
    # Disable all BLAST resolvers except blast_pdb_protein
    config.identifiers.blast_pdb_protein = True
    config.identifiers.blast_pdb_nucleic = False
    config.identifiers.blast_uniprot = False
    config.identifiers.blast_uniprot_similarity = False
    config.identifiers.blast_nr_protein = False
    config.identifiers.blast_nr_protein_similarity = False
    config.identifiers.blast_swissprot_protein = False
    config.identifiers.blast_swissprot_protein_similarity = False
    config.identifiers.blast_core_nt = False
    config.identifiers.blast_core_nt_similarity = False
    config.identifiers.blast_nt = False
    config.identifiers.blast_nt_similarity = False
    
    # Create run directory structure
    run_id = "test-run-001"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    results_path = run_dir / "results.json"
    results = ResultsManager(results_path)
    
    # Store signature - short alpha-globin-like protein sequence (~50 residues)
    query_sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLS"
    results.set_data("signatures/seg1/generated/fasta_map_protein", query_sequence)
    results.set_data("signatures/seg1/attempted", ["fasta_map_protein"])
    
    # -------------------------------------------------------------------------
    # Resolution phase
    # -------------------------------------------------------------------------
    
    mock_subprocess = _mock_subprocess_run_factory(query_sequence, "2HHB_A")
    monkeypatch.setattr("subprocess.run", mock_subprocess)
    
    from src_new.identification.resolvers.blast import BLASTResolverPDBAA
    from src_new.identification.registry import get_default_resolvers, IdentifierRegistry
    from src_new.identification.resolution_manager import IdentifierResolutionManager
    
    monkeypatch.setattr(BLASTResolverPDBAA, "_preflight_check", lambda self: None)
    
    resolvers = get_default_resolvers(config)
    registry = IdentifierRegistry(resolvers)
    manager = IdentifierResolutionManager(registry, config)
    manager.resolve_all(results, working_directory=str(run_dir))
    
    # -------------------------------------------------------------------------
    # Assertions after resolution
    # -------------------------------------------------------------------------
    
    assert results.data_exists("identifiers/seg1/fasta_map_protein/blast_pdb_protein")
    
    blast_result = results.get_data("identifiers/seg1/fasta_map_protein/blast_pdb_protein")
    assert blast_result is not None
    assert blast_result.get("signature_type") == "residue_sequence_protein"
    assert blast_result.get("ident_type") == "PDB_ID"
    
    hits = blast_result.get("hits", [])
    assert "2HHB_A" in hits
    
    warnings = results.get_data("warnings", [])
    assert len(warnings) == 0
    
    # -------------------------------------------------------------------------
    # Verification phase
    # -------------------------------------------------------------------------
    
    mock_requests_get = _mock_requests_get_factory(query_sequence)
    
    class NoOpScorer(AnnotationQualityScorer):
        def supports(self, ident_type: str) -> bool:
            return True
        def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
            return None
    
    default_registry = get_default_registry()
    custom_registry = VerificationRegistry(
        workers=default_registry._workers,
        fetchers=default_registry._fetchers,
        scorers=[NoOpScorer()],
    )
    
    with patch("src_new.verification.fetchers.sequence_fetcher.requests.get", mock_requests_get):
        verification_manager = VerificationManager(config, registry=custom_registry)
        verification_manager.verify_all(results)
    
    # -------------------------------------------------------------------------
    # Assertions after verification
    # -------------------------------------------------------------------------
    
    assert results.data_exists("verification/seg1/verified_hits")
    
    verified_hits = results.get_data("verification/seg1/verified_hits")
    assert verified_hits is not None
    assert len(verified_hits) > 0
    
    first_hit = verified_hits[0]
    # Note: verification normalizes PDB IDs (2HHB_A -> 2HHB)
    assert first_hit.get("identifier") == "2HHB"
    assert first_hit.get("ident_type") == "PDB_ID"
    assert first_hit.get("is_verified") is True
    assert first_hit.get("final_confidence") > 0
    assert first_hit.get("similarity_score") is not None
    
    # -------------------------------------------------------------------------
    # API phase
    # -------------------------------------------------------------------------
    
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    
    import importlib
    from src_new.api import main as api_main
    importlib.reload(api_main)
    from src_new.api.main import app
    
    client = TestClient(app)
    
    # -------------------------------------------------------------------------
    # Test /runs/{run_id}/identifiers endpoint
    # -------------------------------------------------------------------------
    
    identifiers_response = client.get(f"/runs/{run_id}/identifiers?segment=seg1")
    assert identifiers_response.status_code == 200
    
    identifiers_data = identifiers_response.json()
    assert identifiers_data.get("segment") == "seg1"
    
    # API returns raw identifiers (not normalized)
    hits_from_api = identifiers_data.get("hits", [])
    hhb_hit = None
    for hit in hits_from_api:
        if hit.get("identifier") == "2HHB_A":
            hhb_hit = hit
            break
    
    assert hhb_hit is not None
    assert hhb_hit.get("identifier") == "2HHB_A"
    assert hhb_hit.get("segment") == "seg1"
    assert hhb_hit.get("ident_type") == "PDB_ID"
    assert hhb_hit.get("database_url") is not None
    
    attempted_resolvers = identifiers_data.get("attempted_resolvers", [])
    assert "blast_pdb_protein" in attempted_resolvers
    
    # -------------------------------------------------------------------------
    # Test /runs/{run_id}/verification endpoint
    # -------------------------------------------------------------------------
    
    verification_response = client.get(f"/runs/{run_id}/verification?segment=seg1")
    assert verification_response.status_code == 200
    
    verification_data = verification_response.json()
    assert verification_data.get("segment") == "seg1"
    
    # API returns normalized identifiers for verification
    verified_hits_from_api = verification_data.get("hits", [])
    hhb_verified = None
    for hit in verified_hits_from_api:
        if hit.get("identifier") == "2HHB":
            hhb_verified = hit
            break
    
    assert hhb_verified is not None
    assert hhb_verified.get("identifier") == "2HHB"
    assert hhb_verified.get("is_verified") is True
    assert hhb_verified.get("final_confidence") > 0


# =============================================================================
# Test 2: BLAST failure propagates to API warnings
# =============================================================================


def test_blast_failure_propagates_to_api_warnings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a missing BLAST database is surfaced as a warning in the API."""
    
    config = RunConfig.from_default_ini()
    config.override("identifiers_cache.directory", str(tmp_path))
    config.override("identifiers_cache.file", "test_cache.sqlite3")
    
    # Enable only blast_pdb_protein
    config.identifiers.blast_pdb_protein = True
    config.identifiers.blast_pdb_nucleic = False
    config.identifiers.blast_uniprot = False
    config.identifiers.blast_uniprot_similarity = False
    config.identifiers.blast_nr_protein = False
    config.identifiers.blast_nr_protein_similarity = False
    config.identifiers.blast_swissprot_protein = False
    config.identifiers.blast_swissprot_protein_similarity = False
    config.identifiers.blast_core_nt = False
    config.identifiers.blast_core_nt_similarity = False
    config.identifiers.blast_nt = False
    config.identifiers.blast_nt_similarity = False
    
    run_id = "test-run-002"
    run_dir = tmp_path / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    
    results_path = run_dir / "results.json"
    results = ResultsManager(results_path)
    
    query_sequence = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLS"
    results.set_data("signatures/seg1/generated/fasta_map_protein", query_sequence)
    results.set_data("signatures/seg1/attempted", ["fasta_map_protein"])
    
    from src_new.identification.resolvers.blast import BLASTResolverPDBAA
    from src_new.identification.registry import get_default_resolvers, IdentifierRegistry
    from src_new.identification.resolution_manager import IdentifierResolutionManager
    
    def mock_preflight_check(self):
        raise IdentifierResolutionError("Mocked missing DB")
    
    monkeypatch.setattr(BLASTResolverPDBAA, "_preflight_check", mock_preflight_check)
    
    resolvers = get_default_resolvers(config)
    registry = IdentifierRegistry(resolvers)
    manager = IdentifierResolutionManager(registry, config)
    manager.resolve_all(results, working_directory=str(run_dir))
    
    # Manually record warning as the pipeline step would do
    results.record_warning(
        code="identifier_resolver_failed",
        message="blast_pdb_protein (fasta_map_protein): Mocked missing DB",
        step_id="identify",
    )
    
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    
    import importlib
    from src_new.api import main as api_main
    importlib.reload(api_main)
    from src_new.api.main import app
    
    client = TestClient(app)
    
    # -------------------------------------------------------------------------
    # Test /runs/{run_id}/status endpoint for warnings
    # -------------------------------------------------------------------------
    
    status_response = client.get(f"/runs/{run_id}/status")
    assert status_response.status_code == 200
    
    status_data = status_response.json()
    warnings = status_data.get("warnings", [])
    
    resolver_failed_warning = None
    for warning in warnings:
        if warning.get("code") == "identifier_resolver_failed":
            resolver_failed_warning = warning
            break
    
    assert resolver_failed_warning is not None
    assert "blast_pdb_protein" in resolver_failed_warning.get("message", "")
    
    # -------------------------------------------------------------------------
    # Test /runs/{run_id}/identifiers endpoint for failed_resolvers
    # -------------------------------------------------------------------------
    
    identifiers_response = client.get(f"/runs/{run_id}/identifiers?segment=seg1")
    assert identifiers_response.status_code == 200
    
    identifiers_data = identifiers_response.json()
    failed_resolvers = identifiers_data.get("failed_resolvers", [])
    
    blast_failure = None
    for fr in failed_resolvers:
        if fr.get("resolver_name") == "blast_pdb_protein":
            blast_failure = fr
            break
    
    assert blast_failure is not None
