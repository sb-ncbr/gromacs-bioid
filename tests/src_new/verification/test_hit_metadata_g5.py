"""BACKEND_GAPS G5: hit name/organism (macromolecular ident types).

The redesigned results page shows "identified name" (e.g. "Ubiquitin")
explaining each DB id. There is no name/organism anywhere in persisted
results.json today — the scorers now surface them from payloads they
already fetch:

  - UniProtAnnotationScorer: extends its existing fields list with
    protein_name,organism_name (zero extra requests).
  - PDBAnnotationScorer: reads struct.title from the entry payload it
    already fetched + cached (memoized); organism via one best-effort
    shared-cache polymer-entity fetch (failure -> None, never a crash).
  - Manager threads them onto VerifiedHit (additive name/organism);
    dataclasses.asdict flows them into results.json.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src_new.verification.registry import VerificationRegistry
from src_new.verification.models import AnnotationQuality
from src_new.verification.scorers.pdb_scorer import PDBAnnotationScorer
from src_new.verification.scorers.uniprot_scorer import UniProtAnnotationScorer


class TestUniProtScorerMetadata:
    @patch("src_new.verification.scorers.uniprot_scorer.requests.get")
    def test_name_and_organism_from_existing_payload(self, mock_get) -> None:
        mock_response = Mock()
        mock_response.json.return_value = {
            "entryType": "UniProtKB reviewed (Swiss-Prot)",
            "annotationScore": 5,
            "proteinExistence": "1: Evidence at protein level",
            "genes": [{"gene": {"locusName": "BPTI"}}],
            "uniProtKBCrossReferences": [{"database": "GO", "id": "GO:1"}],
            "proteinDescription": {
                "recommendedName": {"fullName": {"value":
                                                 "Pancreatic trypsin inhibitor"}},
            },
            "organism": {"scientificName": "Bos taurus"},
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        scorer = UniProtAnnotationScorer()
        quality = scorer.score("P00760", "UNIPROT_ID")

        assert quality is not None
        assert quality.name == "Pancreatic trypsin inhibitor"
        assert quality.organism == "Bos taurus"
        # the same single request carries the new fields — no extra fetch
        called_url = mock_get.call_args[0][0]
        assert "protein_name" in called_url
        assert "organism_name" in called_url
        assert mock_get.call_count == 1

    @patch("src_new.verification.scorers.uniprot_scorer.requests.get")
    def test_fetch_failure_yields_none_metadata(self, mock_get) -> None:
        mock_get.side_effect = RuntimeError("network down")

        scorer = UniProtAnnotationScorer()
        quality = scorer.score("P00760", "UNIPROT_ID")

        assert quality is not None          # behaviour unchanged: 0.0 score stub
        assert quality.score == 0.0
        assert quality.name is None
        assert quality.organism is None


class TestPDBScorerMetadata:
    @patch("src_new.verification.scorers.pdb_scorer.rcsb_cache.get_cached")
    def test_title_from_entry_and_organism_from_entity(self, mock_get_cached) -> None:
        entry_response = Mock()
        entry_response.json.return_value = {
            "struct": {"title": "UbiA PRENYLTRANSFERASE-LIKE PROTEIN"},
            "rcsb_entry_info": {"resolution_combined": [2.0],
                                "deposited_model_count": 1,
                                "polymer_entity_count": 1},
            "exptl": [{"method": "X-RAY DIFFRACTION"}],
        }
        entity_response = Mock()
        entity_response.json.return_value = {
            "rcsb_entity_source_organism": [{"scientific_name": "Yersinia pestis"}],
        }

        def _route(url, timeout=30):
            if "/polymer_entity/" in url:
                return entity_response
            return entry_response

        mock_get_cached.side_effect = _route

        scorer = PDBAnnotationScorer()
        quality = scorer.score("1UBQ", "PDB_ID")

        assert quality is not None
        assert quality.name == "UbiA PRENYLTRANSFERASE-LIKE PROTEIN"
        assert quality.organism == "Yersinia pestis"
        # entry payload fetched exactly once (memoized); entity once
        urls = [c.args[0] for c in mock_get_cached.call_args_list]
        assert urls.count("https://data.rcsb.org/rest/v1/core/entry/1UBQ") == 1

    @patch("src_new.verification.scorers.pdb_scorer.rcsb_cache.get_cached")
    def test_missing_struct_and_entity_yield_none(self, mock_get_cached) -> None:
        entry_response = Mock()
        entry_response.json.return_value = {"rcsb_entry_info": {}}
        mock_get_cached.return_value = entry_response  # every URL: no struct/organism

        scorer = PDBAnnotationScorer()
        quality = scorer.score("1ABC", "PDB_ID")

        assert quality is not None
        assert quality.name is None
        assert quality.organism is None


class _HitGroupMgr:
    """Small manager harness for the threading assertion."""

    def __init__(self, scorer):
        from src_new.config.loader import RunConfig
        from src_new.verification.manager import VerificationManager

        cfg = MagicMock(spec=RunConfig)
        vc = MagicMock()
        vc.verify_top_n = 25
        vc.resolver_weight = 0.4
        vc.similarity_weight = 0.4
        vc.annotation_weight = 0.2
        vc.min_final_confidence = 30.0
        vc.belief_source_normalize = False
        cfg.verification = vc
        cfg.enable_annotation_quality = True

        reg = MagicMock()
        reg.get_scorer.return_value = scorer
        reg.get_applicable_workers.return_value = []
        reg.get_fetcher.return_value = None
        self.mgr = VerificationManager(cfg, registry=reg)

    def verify(self, identifier: str, ident_type: str):
        from src_new.verification.models import VerificationScore

        results = MagicMock()

        def get_data(path, default=None):
            if path == "identifiers":
                return {"A": {}}
            if path == "fragments/segments":
                return [{"segment": "A", "type": "protein"}]
            return default

        results.get_data.side_effect = get_data
        results.data_exists.side_effect = lambda p: p == "identifiers/A"

        group = {
            "signature": "x", "signature_type": "sequence",
            "consensus_score": 100.0, "source_resolvers": ["seq"],
            "hit_type": "identity",
        }
        with patch("src_new.verification.manager.collect_hits",
                   return_value=[MagicMock()]), \
             patch("src_new.verification.manager.deduplicate_and_score",
                   return_value={(identifier, ident_type): group}):
            return self.mgr.verify_all(results)["A"]


class TestManagerThreadsMetadata:
    def test_hit_carries_name_and_organism(self) -> None:
        class _Scorer:
            def score(self, identifier, ident_type):
                return AnnotationQuality(
                    database="uniprot", score=95.0, signals=["reviewed"],
                    name="Ubiquitin", organism="Homo sapiens")

        hits = _HitGroupMgr(_Scorer()).verify("P0CG48", "UNIPROT_ID")
        assert hits[0].name == "Ubiquitin"
        assert hits[0].organism == "Homo sapiens"

    def test_scorer_without_metadata_yields_none(self) -> None:
        class _Scorer:
            def score(self, identifier, ident_type):
                return AnnotationQuality(database="pdb", score=40.0, signals=[])

        hits = _HitGroupMgr(_Scorer()).verify("1UBQ", "PDB_ID")
        assert hits[0].name is None
        assert hits[0].organism is None
        assert hits[0].is_verified is True  # metadata absence never gates
