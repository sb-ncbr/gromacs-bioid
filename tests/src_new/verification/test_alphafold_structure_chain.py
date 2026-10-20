"""AlphaFind structure-verification chain tests (v3.138 taxonomy fix).

Covers the three broken links that sent every AlphaFind hit to no_worker:
  1. structure worker accepts ALPHAFOLD_ID x ca_only_pdb (was ALPHAFIND_ID
     x pdb_protein/pdb_nucleic only);
  2. structure fetcher resolves ALPHAFOLD_ID to the AFDB model file with
     dynamic version fallback v6->v5->v4 (v4 URLs already 404 in the wild);
  3. end-to-end OFFLINE tm-score path with real fixtures (crambin crystal
     CA-only signature vs the AFDB P01542 model), where tmtools is present.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src_new.verification.fetchers.structure_fetcher import (
    StructureSignatureFetcher,
    _alphafold_accession,
)
from src_new.verification.workers.structure_worker import StructureVerificationWorker

FIXTURES = Path(__file__).parent / "fixtures"


class TestAccessionNormalization:
    def test_bare_accession_passes(self):
        assert _alphafold_accession("P01542") == "P01542"

    def test_wrapped_af_id_unwrapped(self):
        assert _alphafold_accession("AF-P01542-F1-model_v6") == "P01542"

    def test_case_normalized(self):
        assert _alphafold_accession("af-p01542-f1-model_v4") == "P01542"


class TestStructureFetcherAlphafold:
    def test_supports_alphafold_and_legacy_alphafind(self):
        fetcher = StructureSignatureFetcher()
        assert fetcher.supports("ALPHAFOLD_ID")
        assert fetcher.supports("ALPHAFIND_ID")

    @patch("src_new.verification.fetchers.structure_fetcher.rcsb_cache.get_cached")
    def test_version_fallback_walks_down(self, mock_get):
        not_found = Mock(status_code=404, text="")
        ok = Mock(status_code=200, text="HEADER AF\nATOM      1  N   GLY A   1\nEND\n")
        mock_get.side_effect = [not_found, not_found, ok]

        fetcher = StructureSignatureFetcher()
        result = fetcher.fetch("P01542", "ALPHAFOLD_ID")

        assert result == ok.text
        urls = [c.args[0] for c in mock_get.call_args_list]
        assert urls[0].endswith("AF-P01542-F1-model_v6.pdb")
        assert urls[2].endswith("AF-P01542-F1-model_v4.pdb")

    @patch("src_new.verification.fetchers.structure_fetcher.rcsb_cache.get_cached")
    def test_all_versions_missing_returns_none(self, mock_get):
        mock_get.return_value = Mock(status_code=404, text="")
        fetcher = StructureSignatureFetcher()
        assert fetcher.fetch("ZZZZZZ", "ALPHAFOLD_ID") is None
        assert mock_get.call_count == 3

    @patch("src_new.verification.fetchers.structure_fetcher.rcsb_cache.get_cached")
    def test_wrapped_identifier_fetches_by_accession(self, mock_get):
        ok = Mock(status_code=200, text="HEADER AF\nATOM      1  N   GLY A   1\nEND\n")
        mock_get.return_value = ok
        fetcher = StructureSignatureFetcher()
        assert fetcher.fetch("AF-P01542-F1-model_v6", "ALPHAFOLD_ID") == ok.text
        assert mock_get.call_args_list[0].args[0].endswith("AF-P01542-F1-model_v6.pdb")


class TestStructureWorkerTypes:
    def test_alphafold_id_with_ca_only_pdb_now_applicable(self):
        worker = StructureVerificationWorker()
        assert worker.is_applicable("ca_only_pdb", "ALPHAFOLD_ID") is True

    def test_existing_matrix_unchanged(self):
        worker = StructureVerificationWorker()
        assert worker.is_applicable("pdb_protein", "PDB_ID") is True
        assert worker.is_applicable("pdb_nucleic", "ALPHAFIND_ID") is True
        assert worker.is_applicable("smiles", "PDB_ID") is False
        assert worker.is_applicable("pdb_protein", "UNIPROT_ID") is False


class TestTmScoreOfflineIntegration:
    """Real structure verification of the AlphaFind hit path.

    Fixtures: 1crn_ca_only.pdb (46 CA atoms, mirrors the ca_only_pdb
    signature shape) + AF-P01542-F1-model_v6.pdb (real AFDB model; the
    live AlphaFind probe reported tm_score_target 0.9589 for this pair).
    """

    @pytest.fixture
    def fixtures(self):
        tmtools = pytest.importorskip("tmtools")
        query = (FIXTURES / "1crn_ca_only.pdb").read_text()
        canonical = (FIXTURES / "AF-P01542-F1-model_v6.pdb").read_text()
        return query, canonical

    def test_tm_score_matches_alphafind_probe(self, fixtures):
        query, canonical = fixtures
        worker = StructureVerificationWorker()
        score = worker._verify_with_tmscore(query, canonical)
        assert score is not None
        assert score.metric_name == "tm_score"
        # server-computed reference: 0.9589 for 1CRN-vs-AF-P01542; allow slack
        assert 0.85 < score.raw_score <= 1.0
        assert score.normalized_score > 0.0

    def test_verify_entrypoint_uses_tmscore_not_proxy(self, fixtures):
        query, canonical = fixtures
        worker = StructureVerificationWorker()
        score = worker.verify(query, "P01542", "ALPHAFOLD_ID", canonical)
        assert score is not None
        assert score.metric_name == "tm_score"
