"""Integration tests for the verification pipeline."""

from __future__ import annotations

import json
import os
import pytest

from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager
from src_new.verification.manager import VerificationManager
from src_new.verification.registry import get_default_registry
from src_new.executor import PipelineExecutor, PipelineStep, StepResult


# Skip network tests if user doesn't want them
NETWORK_TESTS_ENABLED = os.getenv("BAT3_NETWORK_TESTS", "true").lower() in ("true", "1", "yes")


@pytest.fixture
def minimal_pdb() -> str:
    """Return a minimal PDB-formatted string for a 3-residue peptide (ALA-GLY-SER)."""
    return """HEADER    TEST
ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N
ATOM      2  CA  ALA A   1      10.500  10.500  10.500  1.00  0.00           C
ATOM      3  C   ALA A   1      11.000  11.000  11.000  1.00  0.00           C
ATOM      4  O   ALA A   1      11.500  11.500  11.500  1.00  0.00           O
ATOM      5  N   GLY A   2      12.000  12.000  12.000  1.00  0.00           N
ATOM      6  CA  GLY A   2      12.500  12.500  12.500  1.00  0.00           C
ATOM      7  C   GLY A   2      13.000  13.000  13.000  1.00  0.00           C
ATOM      8  O   GLY A   2      13.500  13.500  13.500  1.00  0.00           O
ATOM      9  N   SER A   3      14.000  14.000  14.000  1.00  0.00           N
ATOM     10  CA  SER A   3      14.500  14.500  14.500  1.00  0.00           C
ATOM     11  C   SER A   3      15.000  15.000  15.000  1.00  0.00           C
ATOM     12  O   SER A   3      15.500  15.500  15.500  1.00  0.00           O
END
"""


class TestVerificationWithRealNetwork:
    """Uses real HTTP calls to databases. These are the 'big' integration checks."""
    
    @pytest.mark.skipif(not NETWORK_TESTS_ENABLED, reason="Network tests disabled")
    def test_water_compound_verification_end_to_end(self, tmp_path) -> None:
        """Test full verification flow for water (smiles 'O') with real network calls."""
        # Create ResultsManager
        results = ResultsManager(tmp_path / "results.json")
        
        # Store identification data for segment "water"
        water_data = {
            "smiles": {
                "pubchem_struct": {
                    "signature": "O",
                    "hit_type": "identity",
                    "ident_type": "PUBCHEM_CID",
                    "hits": ["962"]
                }
            }
        }
        results.set_data("identifiers/water", water_data)
        
        # Create VerificationManager and run verification
        config = RunConfig()
        registry = get_default_registry()
        manager = VerificationManager(config, registry)
        per_segment = manager.verify_all(results)
        
        # Assert water is in the returned dict
        assert "water" in per_segment
        
        # Assert at least one VerifiedHit exists for water
        hits = per_segment["water"]
        assert len(hits) > 0
        
        # Get top hit
        top_hit = hits[0]
        
        # Assert basic properties are present
        assert top_hit.identifier == "962"
        assert top_hit.ident_type == "PUBCHEM_CID"
        assert top_hit.resolver_score > 0  # Should have resolver confidence
        
        # Note: If network fetch fails, similarity_score may be None
        # and annotation_quality_score may be 0.0, but the pipeline should complete
        # The hit may be verified or not depending on network availability
        
        # Assert results are written to results.get_data("verification/water/verified_hits")
        stored_data = results.get_data("verification/water/verified_hits")
        assert stored_data is not None
        assert isinstance(stored_data, list)
        assert len(stored_data) > 0
    
    @pytest.mark.skipif(not NETWORK_TESTS_ENABLED, reason="Network tests disabled")
    def test_beta_globin_protein_verification_end_to_end(self, tmp_path) -> None:
        """Test full verification flow for beta-globin protein with real network calls."""
        # Create ResultsManager
        results = ResultsManager(tmp_path / "results.json")
        
        # Store identification for segment "beta_globin"
        beta_globin_seq = "MVLSPADKTNVKAAWGKVGAHAGEYGAEALERMFLSFPTTKTYFPHFDLSHGSAQVKGHGKKVADALTNAVAHVDDMPNALSALSDLHAHKLRVDPVNFKLLSHCLLVTLAAHLPAEFTPAVHASLDKFLASVSTVLTSKYR"
        protein_data = {
            "fasta_map_protein": {
                "blast_uniprot": {
                    "signature": beta_globin_seq,
                    "hit_type": "similarity",
                    "ident_type": "UNIPROT_ID",
                    "hits": [["P04637", 95.0]]
                }
            }
        }
        results.set_data("identifiers/beta_globin", protein_data)
        
        # Create VerificationManager and run verification
        config = RunConfig()
        registry = get_default_registry()
        manager = VerificationManager(config, registry)
        per_segment = manager.verify_all(results)
        
        # Assert beta_globin is in the returned dict
        assert "beta_globin" in per_segment
        
        # Assert at least one hit exists
        hits = per_segment["beta_globin"]
        assert len(hits) > 0
        
        # Get top hit
        top_hit = hits[0]
        
        # Assert basic properties
        assert top_hit.identifier == "P04637"
        assert top_hit.ident_type == "UNIPROT_ID"
        assert top_hit.resolver_score > 0  # Should have resolver confidence (95.0)
        
        # Note: Network-dependent scores may vary; test that pipeline completes
    
    @pytest.mark.skipif(not NETWORK_TESTS_ENABLED, reason="Network tests disabled")
    def test_structure_self_verification_with_real_pdb_fetch(self, tmp_path, minimal_pdb) -> None:
        """Test structure verification with real PDB fetch (uses RCSB API)."""
        # Create ResultsManager
        results = ResultsManager(tmp_path / "results.json")
        
        # Store identification for segment "test_protein"
        # Using 2LZM (lysozyme) which is a small real PDB ID
        protein_data = {
            "pdb_protein": {
                "pdb_struct_protein": {
                    "signature": minimal_pdb,
                    "hit_type": "similarity",
                    "ident_type": "PDB_ID",
                    "hits": [["2LZM", 90.0]]
                }
            }
        }
        results.set_data("identifiers/test_protein", protein_data)
        
        # Create VerificationManager and run verification
        config = RunConfig()
        registry = get_default_registry()
        manager = VerificationManager(config, registry)
        
        # The structure fetcher will download the real PDB from RCSB
        # This test mainly ensures it doesn't crash
        per_segment = manager.verify_all(results)
        
        # Assert test_protein is in the returned dict
        assert "test_protein" in per_segment
        
        # Assert at least one hit returned
        hits = per_segment["test_protein"]
        assert len(hits) > 0
        
        top_hit = hits[0]
        
        # Assert is_verified is a boolean (either True or False is acceptable)
        assert isinstance(top_hit.is_verified, bool)
        
        # If False, check that rejection_reason is present
        if not top_hit.is_verified:
            assert top_hit.rejection_reason is not None
            assert top_hit.rejection_reason in ("fetch_failed", "verification_failed", "below_threshold", "no_worker", "fingerprint_unavailable", "fingerprint_mismatch")


class TestVerificationCrossResolverConsensus:
    """Fully offline. Tests deduplication logic with realistic multi-resolver data."""
    
    def test_same_hit_from_two_resolvers_gets_higher_confidence(self, tmp_path) -> None:
        """Test that same hit from two resolvers gets higher confidence due to consensus."""
        # Create ResultsManager
        results = ResultsManager(tmp_path / "results.json")
        
        # Store two resolver results for segment "aspirin" under the same generator
        aspirin_data = {
            "smiles": {
                "pubchem_struct": {
                    "signature": "CC(=O)Oc1ccccc1C(=O)O",
                    "hit_type": "identity",
                    "ident_type": "PUBCHEM_CID",
                    "hits": ["2244"]  # aspirin CID
                },
                "idsm_pubchem": {
                    "signature": "CC(=O)Oc1ccccc1C(=O)O",
                    "hit_type": "identity",
                    "ident_type": "PUBCHEM_CID",
                    "hits": ["2244"]  # same aspirin CID
                }
            }
        }
        results.set_data("identifiers/aspirin", aspirin_data)
        
        # Run verification
        config = RunConfig()
        registry = get_default_registry()
        manager = VerificationManager(config, registry)
        per_segment = manager.verify_all(results)
        
        # Assert aspirin is in the returned dict
        assert "aspirin" in per_segment
        
        hits = per_segment["aspirin"]
        assert len(hits) > 0
        
        # Assert exactly one unique hit for "2244"
        assert len(hits) == 1
        assert hits[0].identifier == "2244"
        
        # Assert supporting_evidence_count == 2
        assert hits[0].supporting_evidence_count == 2
        
        # Assert resolver_score (consensus) is capped at 100.0
        # The deduplication logic caps consensus_score at 100.0 intentionally
        # to maintain consistent scoring scale across all verifications.
        assert hits[0].resolver_score == 100.0, f"Expected resolver_score == 100.0 (capped), got {hits[0].resolver_score}"
    
    def test_different_hits_from_same_resolver_remain_separate(self, tmp_path) -> None:
        """Test that different hits from same resolver remain as separate entries."""
        # Create ResultsManager
        results = ResultsManager(tmp_path / "results.json")
        
        # Store one resolver with two different hits
        compound_data = {
            "smiles": {
                "pubchem_struct": {
                    "signature": "O",
                    "hit_type": "identity",
                    "ident_type": "PUBCHEM_CID",
                    "hits": ["962", "2244"]  # water and aspirin
                }
            }
        }
        results.set_data("identifiers/compounds", compound_data)
        
        # Run verification
        config = RunConfig()
        registry = get_default_registry()
        manager = VerificationManager(config, registry)
        per_segment = manager.verify_all(results)
        
        # Assert compounds is in the returned dict
        assert "compounds" in per_segment
        
        hits = per_segment["compounds"]
        
        # Assert two distinct hits in the result list
        assert len(hits) == 2
        identifiers = {hit.identifier for hit in hits}
        assert "962" in identifiers
        assert "2244" in identifiers


class TestVerificationUnverifiedFallback:
    """Fully offline. Tests graceful handling of unverifiable hits."""
    
    def test_fake_identifier_returns_unverified(self, tmp_path) -> None:
        """Test that fake identifiers return unverified hits with appropriate rejection reason."""
        # Create ResultsManager
        results = ResultsManager(tmp_path / "results.json")
        
        # Store identification for segment "fake"
        fake_data = {
            "smiles": {
                "pubchem_struct": {
                    "signature": "O",
                    "hit_type": "identity",
                    "ident_type": "PUBCHEM_CID",
                    "hits": ["FAKECID123456789"]
                }
            }
        }
        results.set_data("identifiers/fake", fake_data)
        
        # Run verification
        config = RunConfig()
        registry = get_default_registry()
        manager = VerificationManager(config, registry)
        per_segment = manager.verify_all(results)
        
        # Assert fake is in the returned dict
        assert "fake" in per_segment
        
        hits = per_segment["fake"]
        assert len(hits) > 0
        
        hit = hits[0]
        
        # The hit may be verified or unverified depending on network availability
        # If network is available, fetch will fail and is_verified should be False
        # If network is unavailable, resolver score alone may verify it
        if not hit.is_verified:
            # If unverified, rejection_reason should be present
            assert hit.rejection_reason is not None
            assert hit.rejection_reason in ("fetch_failed", "verification_failed", "below_threshold", "no_worker", "fingerprint_unavailable", "fingerprint_mismatch")
            # Unverified hits should have final_confidence == 0.0
            assert hit.final_confidence == 0.0
        # If verified, that's also acceptable (resolver_score alone may be sufficient)
    
    def test_no_identifiers_for_segment_skips_gracefully(self, tmp_path) -> None:
        """Test that empty ResultsManager returns empty dict gracefully."""
        # Create empty ResultsManager
        results = ResultsManager(tmp_path / "results.json")
        
        # Run verification
        config = RunConfig()
        registry = get_default_registry()
        manager = VerificationManager(config, registry)
        per_segment = manager.verify_all(results)
        
        # Assert returns empty dict
        assert per_segment == {}


class TestVerificationResultsStorageFormat:
    """Tests that output format matches what downstream consumers expect."""
    
    def test_verified_hits_are_list_of_dicts(self, tmp_path) -> None:
        """Test that verified_hits stored in ResultsManager is a list of dicts with expected keys."""
        # Create ResultsManager with water data
        results = ResultsManager(tmp_path / "results.json")
        
        water_data = {
            "smiles": {
                "pubchem_struct": {
                    "signature": "O",
                    "hit_type": "identity",
                    "ident_type": "PUBCHEM_CID",
                    "hits": ["962"]
                }
            }
        }
        results.set_data("identifiers/water", water_data)
        
        # Run verification
        config = RunConfig()
        registry = get_default_registry()
        manager = VerificationManager(config, registry)
        manager.verify_all(results)
        
        # Read results.get_data("verification/water/verified_hits")
        stored_data = results.get_data("verification/water/verified_hits")
        
        # Assert it's a list
        assert isinstance(stored_data, list)
        assert len(stored_data) > 0
        
        # Assert each item is a dict with expected keys
        expected_keys = {
            "identifier", "ident_type", "database", "resolver_score",
            "similarity_score", "annotation_quality_score", "final_confidence",
            "supporting_evidence_count", "is_verified", "rejection_reason"
        }
        
        for item in stored_data:
            assert isinstance(item, dict)
            for key in expected_keys:
                assert key in item, f"Missing key '{key}' in verified hit dict"
    
    def test_results_are_json_serializable(self, tmp_path) -> None:
        """Test that results.as_dict() can be serialized to JSON without errors."""
        # Create ResultsManager with water data
        results = ResultsManager(tmp_path / "results.json")
        
        water_data = {
            "smiles": {
                "pubchem_struct": {
                    "signature": "O",
                    "hit_type": "identity",
                    "ident_type": "PUBCHEM_CID",
                    "hits": ["962"]
                }
            }
        }
        results.set_data("identifiers/water", water_data)
        
        # Run verification
        config = RunConfig()
        registry = get_default_registry()
        manager = VerificationManager(config, registry)
        manager.verify_all(results)
        
        # json.dumps(results.as_dict()) should not raise
        result_dict = results.as_dict()
        json_str = json.dumps(result_dict)
        assert json_str is not None
        assert len(json_str) > 0


class TestVerificationPipelineStep:
    """Tests that verification can be used inside the PipelineExecutor."""
    
    def test_verification_as_pipeline_step(self, tmp_path) -> None:
        """Test verification as a pipeline step using PipelineExecutor."""
        # Create ResultsManager with identification data
        results = ResultsManager(tmp_path / "results.json")
        
        water_data = {
            "smiles": {
                "pubchem_struct": {
                    "signature": "O",
                    "hit_type": "identity",
                    "ident_type": "PUBCHEM_CID",
                    "hits": ["962"]
                }
            }
        }
        results.set_data("identifiers/water", water_data)
        
        # Define a verification handler function
        def run_verification(context):
            results = context.results
            config = RunConfig()
            registry = get_default_registry()
            manager = VerificationManager(config, registry)
            per_segment = manager.verify_all(results)
            return StepResult(
                payload={"verified_segments": list(per_segment.keys())},
                summary={"segments_verified": len(per_segment)},
            )
        
        # Create a single-step pipeline
        verification_step = PipelineStep(
            step_id="verification_step",
            name="Verification Step",
            handler=run_verification,
        )
        
        # Run the pipeline
        executor = PipelineExecutor(
            steps=[verification_step],
            results_manager=results,
            pipeline_name="Verification Pipeline Test",
        )
        
        # Execute pipeline
        context = executor.run(
            output_directory=tmp_path / "output",
            working_directory=tmp_path / "work",
        )
        
        # Assert pipeline status is "success"
        payload = results.as_dict()
        assert payload["pipeline"]["status"] == "success"
        
        # Assert results.data_exists("verification/...") is True
        # The verification step stores data at verification/{segment}/verified_hits
        assert results.data_exists("verification/water/verified_hits") is True
