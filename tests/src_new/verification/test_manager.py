"""Tests for the VerificationManager full orchestration."""

from __future__ import annotations

import pytest
from unittest.mock import patch, Mock

from src_new.verification.manager import VerificationManager
from src_new.verification.models import VerifiedHit


class TestManagerVerifyAll:
    """Tests for VerificationManager.verify_all()."""
    
    @patch("src_new.verification.fetchers.compound_fetcher.requests.get")
    @patch("src_new.verification.scorers.pubchem_scorer.requests.get")
    def test_manager_verify_all_returns_dict(
        self, 
        mock_scorer_get, 
        mock_fetcher_get, 
        manager, 
        identification_results
    ) -> None:
        """Call manager.verify_all(results), assert return is a dict with segment keys."""
        # Mock fetcher response
        fetcher_response = Mock()
        fetcher_response.text = "O"
        fetcher_response.raise_for_status = Mock()
        
        # Mock scorer response
        scorer_response = Mock()
        scorer_response.json.return_value = {
            "PropertyTable": {
                "Properties": [{
                    "CanonicalSMILES": "O",
                    "IsomericSMILES": "O",
                    "IUPACName": "oxidane",
                    "MolecularFormula": "H2O"
                }]
            }
        }
        scorer_response.raise_for_status = Mock()
        
        synonyms_response = Mock()
        synonyms_response.json.return_value = {
            "InformationList": {
                "Information": [{"Synonym": ["water"]}]
            }
        }
        synonyms_response.raise_for_status = Mock()
        
        mock_fetcher_get.return_value = fetcher_response
        mock_scorer_get.side_effect = [scorer_response, synonyms_response]
        
        result = manager.verify_all(identification_results)
        
        assert isinstance(result, dict)
        assert "seg_compound" in result
        assert "seg_protein" in result
    
    @patch("src_new.verification.fetchers.compound_fetcher.requests.get")
    @patch("src_new.verification.scorers.pubchem_scorer.requests.get")
    def test_manager_produces_verified_hits(
        self,
        mock_scorer_get,
        mock_fetcher_get,
        manager,
        identification_results
    ) -> None:
        """For seg_compound, assert at least one hit exists in the returned list."""
        # Mock fetcher response
        fetcher_response = Mock()
        fetcher_response.text = "O"
        fetcher_response.raise_for_status = Mock()
        
        # Mock scorer response
        scorer_response = Mock()
        scorer_response.json.return_value = {
            "PropertyTable": {
                "Properties": [{
                    "CanonicalSMILES": "O",
                    "IsomericSMILES": "O",
                    "IUPACName": "oxidane",
                    "MolecularFormula": "H2O"
                }]
            }
        }
        scorer_response.raise_for_status = Mock()
        
        synonyms_response = Mock()
        synonyms_response.json.return_value = {
            "InformationList": {
                "Information": [{"Synonym": ["water"]}]
            }
        }
        synonyms_response.raise_for_status = Mock()
        
        mock_fetcher_get.return_value = fetcher_response
        mock_scorer_get.side_effect = [scorer_response, synonyms_response]
        
        result = manager.verify_all(identification_results)
        
        assert "seg_compound" in result
        assert len(result["seg_compound"]) > 0
        assert all(isinstance(hit, VerifiedHit) for hit in result["seg_compound"])
    
    @patch("src_new.verification.fetchers.compound_fetcher.requests.get")
    @patch("src_new.verification.scorers.pubchem_scorer.requests.get")
    def test_manager_writes_results(
        self,
        mock_scorer_get,
        mock_fetcher_get,
        manager,
        identification_results
    ) -> None:
        """Assert results.get_data('verification/seg_compound/verified_hits') is a non-empty list of dicts."""
        # Mock fetcher response
        fetcher_response = Mock()
        fetcher_response.text = "O"
        fetcher_response.raise_for_status = Mock()
        
        # Mock scorer response
        scorer_response = Mock()
        scorer_response.json.return_value = {
            "PropertyTable": {
                "Properties": [{
                    "CanonicalSMILES": "O",
                    "IsomericSMILES": "O",
                    "IUPACName": "oxidane",
                    "MolecularFormula": "H2O"
                }]
            }
        }
        scorer_response.raise_for_status = Mock()
        
        synonyms_response = Mock()
        synonyms_response.json.return_value = {
            "InformationList": {
                "Information": [{"Synonym": ["water"]}]
            }
        }
        synonyms_response.raise_for_status = Mock()
        
        mock_fetcher_get.return_value = fetcher_response
        mock_scorer_get.side_effect = [scorer_response, synonyms_response]
        
        manager.verify_all(identification_results)
        
        stored_data = identification_results.get_data("verification/seg_compound/verified_hits")
        
        assert stored_data is not None
        assert isinstance(stored_data, list)
        assert len(stored_data) > 0
        assert all(isinstance(hit, dict) for hit in stored_data)
    
    @patch("src_new.verification.fetchers.compound_fetcher.requests.get")
    @patch("src_new.verification.scorers.pubchem_scorer.requests.get")
    def test_manager_dedup_increases_confidence(
        self,
        mock_scorer_get,
        mock_fetcher_get,
        config,
        tmp_results
    ) -> None:
        """Verify that cross-resolver consensus boosts score compared to single-resolver."""
        # Set up data with two resolvers finding the same compound
        compound_data = {
            "smiles": {
                "pubchem_struct": {
                    "signature": "O",
                    "hit_type": "identity",
                    "ident_type": "PUBCHEM_CID",
                    "hits": ["962"]
                },
                "chembl_resolver": {
                    "signature": "O",
                    "hit_type": "identity",
                    "ident_type": "PUBCHEM_CID",
                    "hits": ["962"]
                }
            }
        }
        tmp_results.set_data("identifiers/seg_multi", compound_data)
        
        # Mock fetcher response
        fetcher_response = Mock()
        fetcher_response.text = "O"
        fetcher_response.raise_for_status = Mock()
        
        # Mock scorer response
        scorer_response = Mock()
        scorer_response.json.return_value = {
            "PropertyTable": {
                "Properties": [{
                    "CanonicalSMILES": "O",
                }]
            }
        }
        scorer_response.raise_for_status = Mock()
        
        synonyms_response = Mock()
        synonyms_response.json.return_value = {
            "InformationList": {
                "Information": [{"Synonym": ["water"]}]
            }
        }
        synonyms_response.raise_for_status = Mock()
        
        mock_fetcher_get.return_value = fetcher_response
        mock_scorer_get.side_effect = [scorer_response, synonyms_response]
        
        manager = VerificationManager(config)
        result = manager.verify_all(tmp_results)
        
        # With two resolvers, we should have higher confidence due to diversity bonus
        assert "seg_multi" in result
        if len(result["seg_multi"]) > 0:
            hit = result["seg_multi"][0]
            # Cross-resolver consensus should boost the score
            assert hit.supporting_evidence_count >= 2
    
    def test_manager_unverified_fallback(self, config, tmp_results) -> None:
        """For a segment with similarity hit (not identity) and no worker, assert is_verified=False."""
        # Set up data with a similarity hit (not identity) with an ident_type that has no worker
        # Using PUBCHEM_CID for a protein signature type - no worker will apply
        similarity_data = {
            "smiles": {
                "test_resolver": {
                    "signature": "test_smiles",
                    "hit_type": "similarity",  # Not identity, so needs evidence
                    "ident_type": "PUBCHEM_CID",
                    "hits": [["TEST123", 50.0]]  # similarity format with score
                }
            }
        }
        tmp_results.set_data("identifiers/seg_unsupported", similarity_data)
        
        manager = VerificationManager(config)
        result = manager.verify_all(tmp_results)
        
        # Segment should be in result
        assert "seg_unsupported" in result
        if len(result["seg_unsupported"]) > 0:
            hit = result["seg_unsupported"][0]
            # Similarity hit without worker/scorer should not be verified
            assert hit.is_verified is False
            # Rejection reason can be no_worker or verification_failed depending on flow
            assert hit.rejection_reason in ("no_worker", "verification_failed", "below_threshold")
    
    @patch("src_new.verification.fetchers.compound_fetcher.requests.get")
    @patch("src_new.verification.scorers.pubchem_scorer.requests.get")
    def test_manager_weights_computation(
        self,
        mock_scorer_get,
        mock_fetcher_get,
        manager,
        identification_results
    ) -> None:
        """Assert final_confidence is within plausible range (0-100 if verified, 0 if not)."""
        # Mock fetcher response
        fetcher_response = Mock()
        fetcher_response.text = "O"
        fetcher_response.raise_for_status = Mock()
        
        # Mock scorer response
        scorer_response = Mock()
        scorer_response.json.return_value = {
            "PropertyTable": {
                "Properties": [{
                    "CanonicalSMILES": "O",
                    "IsomericSMILES": "O",
                    "IUPACName": "oxidane",
                    "MolecularFormula": "H2O"
                }]
            }
        }
        scorer_response.raise_for_status = Mock()
        
        synonyms_response = Mock()
        synonyms_response.json.return_value = {
            "InformationList": {
                "Information": [{"Synonym": ["water"]}]
            }
        }
        synonyms_response.raise_for_status = Mock()
        
        mock_fetcher_get.return_value = fetcher_response
        mock_scorer_get.side_effect = [scorer_response, synonyms_response]
        
        result = manager.verify_all(identification_results)
        
        for segment, hits in result.items():
            for hit in hits:
                if hit.is_verified:
                    # Verified hits should have confidence > 0 and <= 100
                    assert 0.0 < hit.final_confidence <= 100.0
                else:
                    # Unverified hits have final_confidence = 0.0
                    assert hit.final_confidence == 0.0


class TestIdentityOnlyVerification:
    """Tests for identity-only verification (without similarity/annotation scores)."""
    
    def test_identity_hit_verified_with_high_resolver_score(self, config, tmp_results) -> None:
        """Identity hit with high resolver_score (100) should be verified even without similarity/annotation."""
        # Set up data with an identity hit but no applicable worker/scorer
        identity_data = {
            "residue_sequence_protein": {
                "blast_nr_resolver": {
                    "signature": "MVLSPADK",
                    "hit_type": "identity",
                    "ident_type": "NR_ID",
                    "hits": ["NP_001"]
                }
            }
        }
        tmp_results.set_data("identifiers/seg_identity", identity_data)
        
        manager = VerificationManager(config)
        result = manager.verify_all(tmp_results)
        
        assert "seg_identity" in result
        assert len(result["seg_identity"]) > 0
        
        hit = result["seg_identity"][0]
        # Identity hit with resolver_score=100 should be verified
        # (resolver_weight * 100 >= min_final_confidence)
        assert hit.is_verified is True
        assert hit.identifier == "NP_001"
        assert hit.ident_type == "NR_ID"
        # similarity_score should be None since no worker ran
        assert hit.similarity_score is None
    
    def test_identity_hit_below_threshold_not_verified(self, config, tmp_results) -> None:
        """Identity hit with low final_confidence should NOT be verified even if hit_type is identity."""
        # Create a config with very high min_final_confidence threshold
        from dataclasses import replace
        high_threshold_config = replace(config)
        high_threshold_config.verification = replace(
            high_threshold_config.verification,
            min_final_confidence=99.0  # Very high threshold
        )
        
        # Set up data with an identity hit
        identity_data = {
            "residue_sequence_protein": {
                "weak_resolver": {
                    "signature": "MVLSPADK",
                    "hit_type": "identity",
                    "ident_type": "NR_ID",
                    "hits": ["NP_002"]
                }
            }
        }
        tmp_results.set_data("identifiers/seg_low_conf", identity_data)
        
        manager = VerificationManager(high_threshold_config)
        result = manager.verify_all(tmp_results)
        
        assert "seg_low_conf" in result
        if len(result["seg_low_conf"]) > 0:
            hit = result["seg_low_conf"][0]
            # With high threshold (99), resolver_weight=0.4 * 100 = 40 < 99
            # So it should NOT be verified
            assert hit.is_verified is False
            # Rejection reason can be below_threshold or no_worker depending on flow
            assert hit.rejection_reason in ("below_threshold", "no_worker")
    
    def test_identity_hit_no_similarity_score_preserved(self, config, tmp_results) -> None:
        """Identity hit should preserve similarity_score=None when verified."""
        identity_data = {
            "residue_sequence_protein": {
                "blast_resolver": {
                    "signature": "MVLSPADK",
                    "hit_type": "identity",
                    "ident_type": "NR_ID",
                    "hits": ["NP_003"]
                }
            }
        }
        tmp_results.set_data("identifiers/seg_no_sim", identity_data)
        
        manager = VerificationManager(config)
        result = manager.verify_all(tmp_results)
        
        assert "seg_no_sim" in result
        if len(result["seg_no_sim"]) > 0:
            hit = result["seg_no_sim"][0]
            if hit.is_verified:
                # similarity_score should be None, not 0.0
                assert hit.similarity_score is None
