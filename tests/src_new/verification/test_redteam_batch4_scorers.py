"""Red-team batch-4 (5.3) — D-07 annotation scorer schema bugs + position effects.

Ground truth recorded live 2026-10-23 into fixtures/d07/:
  - UniProt P00698 (?fields= trimmed): proteinExistence is the STRING
    '1: Evidence at protein level', never the integer 1 — the scorer's
    `== 1` check never fired, capping every entry at 80.
  - ChEBI 15377: default_structure carries 'standard_inchi_key', not
    'inchi_key' — the scorer capped at 80.
  - PubChem PUG CID 702: even a legacy-name property request now returns
    'SMILES' and 'ConnectivitySMILES' — reading 'CanonicalSMILES' /
    'IsomericSMILES' scores 65.
  - PubChem live-budget consumed in window order made IDENTICAL records
    score differently by position (100x12, 85, 70...). Fixed by a per-CID
    result cache: a record scores once and repeats verbatim.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src_new.verification.scorers.uniprot_scorer import UniProtAnnotationScorer
from src_new.verification.scorers.chebi_scorer import ChebiAnnotationScorer
from src_new.verification.scorers.pubchem_scorer import PubChemAnnotationScorer

FIX = Path(__file__).parent / "fixtures" / "d07"


def _fixture(name: str) -> dict:
    return json.loads((FIX / name).read_text())


class TestD07UniProtSchema:
    def test_protein_existence_string_reaches_full_score(self):
        entry = _fixture("uniprot_P00698_fields.json")
        with patch("src_new.verification.scorers.uniprot_scorer.requests.get") as g:
            g.return_value = Mock(status_code=200,
                                  json=lambda: entry,
                                  raise_for_status=lambda: None)
            q = UniProtAnnotationScorer().score("P00698", "UNIPROT_ID")
        assert q is not None
        # 10 base + 30 reviewed + 5*4 annotation + 20 protein-existence
        # + 10 genes + 10 GO = 100 (bug form capped at 80)
        assert q.score == 100.0, (q.score, q.signals)
        assert "protein_existence" in q.signals

    def test_fetch_is_fields_trimmed(self):
        entry = _fixture("uniprot_P00698_fields.json")
        with patch("src_new.verification.scorers.uniprot_scorer.requests.get") as g:
            g.return_value = Mock(status_code=200,
                                  json=lambda: entry,
                                  raise_for_status=lambda: None)
            UniProtAnnotationScorer().score("P00698", "UNIPROT_ID")
        url = g.call_args.args[0]
        assert "fields=" in url, url
        assert "protein_existence" in url and "annotation_score" in url

    def test_failure_returns_none(self):
        """W3.3 item 2: fetch failure -> annotation UNKNOWN (None, blend
        re-weights), never a real 0.0 (supersedes D-07's "still zero")."""
        with patch("src_new.verification.scorers.uniprot_scorer.requests.get",
                   side_effect=Exception("network down")):
            q = UniProtAnnotationScorer().score("P00698", "UNIPROT_ID")
        assert q is None


class TestD07ChebiSchema:
    def test_standard_inchi_key_reaches_full_score(self):
        entry = _fixture("chebi_15377.json")
        with patch("src_new.verification.scorers.chebi_scorer.requests.get") as g:
            g.return_value = Mock(status_code=200,
                                  json=lambda: entry,
                                  raise_for_status=lambda: None)
            q = ChebiAnnotationScorer().score("CHEBI:15377", "CHEBI_ID")
        assert q is not None
        # 20 base + 20 definition + 20 smiles + 20 inchi_key + 20 stars
        assert q.score == 100.0, (q.score, q.signals)
        assert "inchi_key" in q.signals


class TestD07PugPathSchema:
    def _props_and_synonyms(self):
        props = _fixture("pug_702_props.json")
        synonyms = {"InformationList": {"Information": [{"Synonym": ["ethanol"]}]}}
        return [props, synonyms]

    def test_pug_new_property_keys_scored(self):
        scorer = PubChemAnnotationScorer()
        scorer.configure(live_fetch=True, timeout_s=3.0)
        scorer.begin_segment(10)
        with patch("src_new.verification.scorers.pubchem_scorer._local_db",
                   return_value=None):
            with patch.object(scorer, "_live_get_json",
                              side_effect=self._props_and_synonyms()):
                q = scorer.score("702", "PUBCHEM_CID")
        assert q is not None
        assert "canonical_smiles" in q.signals, q.signals
        assert "isomeric_smiles" in q.signals, q.signals
        # 20 base + 20 canonical + 15 isomeric + 15 iupac + 15 formula
        # + 15 synonyms = 100 (bug form capped at 65)
        assert q.score == 100.0, (q.score, q.signals)


class TestD07PositionIndependence:
    @staticmethod
    def _fake_requests_get(used: dict):
        def fake_get(url, timeout=None, **kw):
            used["n"] += 1
            if "property" in url:
                payload = _fixture("pug_702_props.json")
            else:
                payload = {"InformationList": {"Information": [{"Synonym": ["e"]}]}}
            return Mock(status_code=200, json=lambda: payload,
                        raise_for_status=lambda: None)
        return fake_get

    def test_identical_cid_scores_identically_after_budget_exhaustion(self):
        """Window-position independence: the same record always yields the
        same A, even after the live-call budget is gone."""
        scorer = PubChemAnnotationScorer()
        scorer.configure(live_fetch=True, timeout_s=3.0)
        scorer.begin_segment(2)  # exactly enough for one full CID
        used = {"n": 0}

        with patch("src_new.verification.scorers.pubchem_scorer._local_db",
                   return_value=None), \
             patch("src_new.verification.scorers.pubchem_scorer.requests.get",
                   side_effect=self._fake_requests_get(used)):
            first = scorer.score("702", "PUBCHEM_CID")
            scorer.begin_segment(0)  # new segment, no budget
            second = scorer.score("702", "PUBCHEM_CID")

        assert first is not None and second is not None
        assert first.score == second.score, (first.score, second.score)
        assert set(first.signals) == set(second.signals)

    def test_repeat_lookup_does_not_consume_budget(self):
        scorer = PubChemAnnotationScorer()
        scorer.configure(live_fetch=True, timeout_s=3.0)
        scorer.begin_segment(4)
        used = {"n": 0}

        with patch("src_new.verification.scorers.pubchem_scorer._local_db",
                   return_value=None), \
             patch("src_new.verification.scorers.pubchem_scorer.requests.get",
                   side_effect=self._fake_requests_get(used)):
            first = scorer.score("702", "PUBCHEM_CID")
            repeat = scorer.score("702", "PUBCHEM_CID")  # cached: no calls
            assert used["n"] == 2, used  # old code would re-fetch (4)
            assert repeat is not None and repeat.score == first.score
            q962 = scorer.score("962", "PUBCHEM_CID")  # different CID fetched
            assert used["n"] == 4, used  # 2 calls for 702 + 2 for 962
        assert q962 is not None