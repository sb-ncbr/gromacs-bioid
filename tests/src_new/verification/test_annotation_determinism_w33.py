"""W3.3 item 2: annotation-score determinism.

Production evidence (re-eval corrections, 2026-11-01): the SAME identifier
scored differently across twin runs — CID 137895 at 85 in T02a but 100 in
T02b, the InChIKey row 100 vs 85 — silently swapping top-1. Root cause:
an incomplete remote fetch (network failure / rate limit / per-segment
live budget gone) produced a silently LOWER real score (85, or 0.0 for
the REST scorers) instead of an honest UNKNOWN, and the confidence blend
treats a real low score as measured. b12 fleet gate erosion (UniProt
validated@1 0.6093 vs 0.770; ligand non-ion exact@1 0.4530 vs 0.547) is
the same class at campaign scale (cold pod-local caches -> remote storm).

Rule (user directive): fetch failure -> None (annotation UNKNOWN → the
blend re-weights over the measured terms), never a lower score. A signal
is only legitimately absent when the fetch SUCCEEDED and the record
genuinely lacks it. Live-fetch disabled keeps the documented deterministic
store floor. Successful scores stay per-identifier cached (D-07); Nones
are never cached, so a transient failure re-attempts on the next segment.

Tests mock requests — no live network.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

requests = pytest.importorskip("requests")

from src_new.molecules.pubchem_db import CompoundRow
from src_new.verification.scorers import pubchem_scorer as pubmod
from src_new.verification.scorers.chebi_scorer import ChebiAnnotationScorer
from src_new.verification.scorers.chembl_scorer import ChemblAnnotationScorer
from src_new.verification.scorers.pubchem_scorer import PubChemAnnotationScorer
from src_new.verification.scorers.uniprot_scorer import UniProtAnnotationScorer


def _ok(payload: dict) -> Mock:
    return Mock(status_code=200, json=lambda: payload,
                raise_for_status=lambda: None)


_UNIPROT_ENTRY = {
    "entryType": "UniProtKB reviewed (Swiss-Prot)",
    "annotationScore": 5,
    "proteinExistence": "1: Evidence at protein level",
    "genes": [{"gene": {"locusName": "X"}}],
    "uniProtKBCrossReferences": [{"database": "GO", "id": "GO:1"}],
}

_MIRROR_ROW = CompoundRow(cid=962, smiles="O", inchikey="X" * 27,
                          formula_hill="H2O", exact_mass=18.0106)

_PROPS_FULL = {
    "PropertyTable": {"Properties": [{
        "ConnectivitySMILES": "O", "SMILES": "O",
        "IUPACName": "oxidane", "MolecularFormula": "H2O",
    }]}
}
_SYNONYMS = {"InformationList": {"Information": [{"Synonym": ["water"]}]}}
_SYNONYMS_EMPTY = {"InformationList": {"Information": [{"Synonym": []}]}}


class TestFailureReturnsNone:
    def test_uniprot_fetch_failure_is_none(self):
        with patch("src_new.verification.scorers.uniprot_scorer.requests.get",
                   side_effect=Exception("rate limited")):
            q = UniProtAnnotationScorer().score("P00698", "UNIPROT_ID")
        assert q is None

    def test_chembl_fetch_failure_is_none(self):
        with patch("src_new.verification.scorers.chembl_scorer.requests.get",
                   side_effect=Exception("timeout")):
            q = ChemblAnnotationScorer().score("CHEMBL25", "CHEMBL_ID")
        assert q is None

    def test_chebi_fetch_failure_is_none(self):
        with patch("src_new.verification.scorers.chebi_scorer.requests.get",
                   side_effect=Exception("conn reset")):
            q = ChebiAnnotationScorer().score("CHEBI:15377", "CHEBI_ID")
        assert q is None


class TestUniProtSuccessCache:
    def test_identical_identifier_fetched_once(self):
        calls = {"n": 0}

        def fake_get(url, timeout=None, **kw):
            calls["n"] += 1
            return _ok(_UNIPROT_ENTRY)

        scorer = UniProtAnnotationScorer()
        with patch("src_new.verification.scorers.uniprot_scorer.requests.get",
                   side_effect=fake_get):
            first = scorer.score("P00698", "UNIPROT_ID")
            repeat = scorer.score("P00698", "UNIPROT_ID")
            via_alphafold = scorer.score("AF-P00698-F1-model_v4", "ALPHAFOLD_ID")
        assert calls["n"] == 1, calls
        assert first is not None and repeat is not None
        assert repeat.score == first.score
        assert via_alphafold is not None
        assert via_alphafold.score == first.score


class TestPubChemLiveFillDeterminism:
    def _scorer(self, *, live: bool, budget: int = 25) -> PubChemAnnotationScorer:
        scorer = PubChemAnnotationScorer()
        scorer.configure(live_fetch=live, timeout_s=3.0)
        scorer.begin_segment(budget)
        return scorer

    def test_mirror_hit_synonyms_fetch_fails_is_none(self, monkeypatch):
        """T02 regression: mirror floor 70 + live iupac 15 = 85 silently when
        the synonyms call failed; the same identifier hits 100 when it
        succeeds. Failure must be UNKNOWN (None), not the 85."""
        monkeypatch.setattr(pubmod, "_local_db", lambda: _stub_db(_MIRROR_ROW))

        def fake_get(url, timeout=None, **kw):
            if "property" in url:
                return _ok(_PROPS_FULL)
            raise Exception("synonyms 429")

        scorer = self._scorer(live=True)
        with patch.object(pubmod.requests, "get", side_effect=fake_get):
            q = scorer.score("962", "PUBCHEM_CID")
        assert q is None

    def test_mirror_hit_budget_exhausted_is_none(self, monkeypatch):
        """Budget-skipped fill proves nothing about the missing signals —
        a floor here would re-create cross-run position dependence."""
        monkeypatch.setattr(pubmod, "_local_db", lambda: _stub_db(_MIRROR_ROW))
        scorer = self._scorer(live=True, budget=0)
        with patch.object(pubmod.requests, "get") as mock_get:
            q = scorer.score("962", "PUBCHEM_CID")
        mock_get.assert_not_called()
        assert q is None

    def test_mirror_hit_live_disabled_keeps_floor(self, monkeypatch):
        """live_fetch=False: the mirror floor is the deterministic policy
        answer (documented store floor), not a fetch failure."""
        monkeypatch.setattr(pubmod, "_local_db", lambda: _stub_db(_MIRROR_ROW))
        scorer = self._scorer(live=False)
        with patch.object(pubmod.requests, "get") as mock_get:
            q = scorer.score("962", "PUBCHEM_CID")
        mock_get.assert_not_called()
        assert q is not None
        assert q.score == 70.0

    def test_mirror_hit_legitimately_missing_synonyms_stays_85(self, monkeypatch):
        """Fetch SUCCEEDED, record genuinely has no synonyms → 85 is the real
        measured score, not a failure."""
        monkeypatch.setattr(pubmod, "_local_db", lambda: _stub_db(_MIRROR_ROW))

        def fake_get(url, timeout=None, **kw):
            return _ok(_PROPS_FULL if "property" in url else _SYNONYMS_EMPTY)

        scorer = self._scorer(live=True)
        with patch.object(pubmod.requests, "get", side_effect=fake_get):
            q = scorer.score("962", "PUBCHEM_CID")
        assert q is not None
        assert q.score == 85.0

    def test_full_pug_synonyms_fetch_fails_is_none(self, monkeypatch):
        monkeypatch.setattr(pubmod, "_local_db", lambda: None)

        def fake_get(url, timeout=None, **kw):
            if "property" in url:
                return _ok(_PROPS_FULL)
            raise Exception("synonyms down")

        scorer = self._scorer(live=True)
        with patch.object(pubmod.requests, "get", side_effect=fake_get):
            q = scorer.score("962", "PUBCHEM_CID")
        assert q is None

    def test_none_is_not_cached_and_recovers(self, monkeypatch):
        """A transient failure must NOT be cached: the next segment's retry
        converges to the deterministic cached success (cross-run parity)."""
        monkeypatch.setattr(pubmod, "_local_db", lambda: _stub_db(_MIRROR_ROW))
        state = {"fail": True}

        def fake_get(url, timeout=None, **kw):
            if state["fail"]:
                raise Exception("transient")
            return _ok(_PROPS_FULL if "property" in url else _SYNONYMS)

        scorer = self._scorer(live=True)
        with patch.object(pubmod.requests, "get", side_effect=fake_get):
            first = scorer.score("962", "PUBCHEM_CID")
            scorer.begin_segment(25)
            state["fail"] = False
            second = scorer.score("962", "PUBCHEM_CID")
        assert first is None
        assert second is not None
        assert second.score == 100.0


class TestManagerBlendUnchanged:
    def test_none_annotation_reweights(self):
        from src_new.verification.manager import _compose_confidence
        with_none = _compose_confidence(0.4, 0.3, 0.3, 80.0, 60.0, None)
        with_zero = _compose_confidence(0.4, 0.3, 0.3, 80.0, 60.0, 0.0)
        assert with_none > with_zero  # UNKNOWN must not act as a real zero


def _stub_db(row):
    db = Mock()
    db.by_cid.return_value = row
    db.by_inchikey.return_value = row
    return db
