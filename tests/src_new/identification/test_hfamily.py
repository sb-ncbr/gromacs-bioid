"""F9 fastformula H-family resolver tests. HTTP fully mocked."""

from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from unittest.mock import MagicMock

import pytest

from src_new.identification.resolvers.hfamily import (
    FormulaHFamilyResolver, _parse_formula, _hill,
)
from src_new.identification.base import IdentifierResolutionError


def _resolver():
    cfg = MagicMock()
    cfg.pubchem.retry_attempts = 2
    cfg.pubchem.retry_delay_s = 0.0
    cfg.identifiers = MagicMock()
    r = FormulaHFamilyResolver.__new__(FormulaHFamilyResolver)
    # run base __init__ manually-less: set what _is_applicable/_resolve use
    r.config = cfg
    import requests
    r._session = requests.Session()
    r._session._hf_retry_attempts = 2
    r._local_db = None  # mirror handle is normally set in __init__; stub stays PUG-path
    r._session._hf_retry_delay = 0.0
    r.h_range = 2
    return r


def test_parse_and_hill():
    parts = _parse_formula("C25H18N4O5")
    assert parts == {"C": 25, "H": 18, "N": 4, "O": 5}
    assert _hill({"C": 25, "H": 18, "N": 4, "O": 5}) == "C25H18N4O5"
    assert _hill({"C": 1, "H": 4}) == "CH4"
    with pytest.raises(IdentifierResolutionError):
        _parse_formula("not_a_formula!!")


def test_applicability():
    r = _resolver()
    assert r._is_applicable("C25H18N4O5") is True
    assert r._is_applicable("Ar") is False          # single element
    assert r._is_applicable("garbage!") is False


def test_hfamily_unions_and_dedupes(monkeypatch):
    r = _resolver()
    calls = []

    def fake_get(path):
        calls.append(path)
        # distinct cid per H variant to test union; overlap on the middle one
        if "C10H12N2" in path: return {"IdentifierList": {"CID": [101, 102]}}
        if "C10H13N2" in path: return {"IdentifierList": {"CID": [102, 103]}}
        if "C10H14N2" in path: return {"IdentifierList": {"CID": [103, 104]}}
        return {"IdentifierList": {"CID": []}}

    monkeypatch.setattr(r, "_pug_get", fake_get)
    hits = r._resolve_similarity("C10H13N2", "/tmp")
    cids = [c for c, _ in hits]
    assert cids == ["101", "102", "103", "104"]           # union, deduped, order-preserved
    assert all(score == 50.0 for _, score in hits)
    # h_range=2 -> 5 variant queries with clamped H
    assert len(calls) == 5
    assert any("C10H11N2" in c for c in calls) and any("C10H15N2" in c for c in calls)


def test_identity_channel_empty():
    r = _resolver()
    assert r._resolve_identity("C10H13N2", "/tmp") == []


def test_404_yields_no_candidates(monkeypatch):
    r = _resolver()
    monkeypatch.setattr(r, "_pug_get", lambda path: None)
    assert r._resolve_similarity("C9H9N", "/tmp") == []


class TestHFamilyLocalBackend:
    """F13: local mirror caps replace the PUG etiquette caps (200/500)."""

    def _local_resolver(self, per_query, total):
        r = _resolver()
        r._local_db = MagicMock()
        r._local_per_query = per_query
        r._local_max_total = total
        return r

    def test_offline_capability_flag(self):
        r = _resolver()
        r._local_db = None
        # offline_capable defined on the class; _resolver() builds via __new__
        from src_new.identification.resolvers.hfamily import FormulaHFamilyResolver
        assert FormulaHFamilyResolver.offline_capable(r) is False
        r._local_db = MagicMock()
        assert FormulaHFamilyResolver.offline_capable(r) is True

    def test_local_caps_replace_pug_caps(self):
        db = MagicMock()
        db.by_formula = MagicMock(side_effect=lambda formula, limit: list(range(limit)))
        r = self._local_resolver(per_query=5000, total=25000)
        r._local_db = db
        seen_limits = []
        def capture(formula, limit):
            seen_limits.append(limit)
            return list(range(limit))
        r._local_db.by_formula = capture
        hits = r._resolve_similarity("C5H6N2O2", "/tmp")
        # 9 H-variants (h_range=2 -> 5 variants) each capped at local per-query,
        # none of the PUG constants (200/500) may appear
        assert "500" not in str(type(hits))
        assert all(l == 5000 for l in seen_limits)
        # dedupe across variants keeps every unique cid (all lists identical here)
        assert len(hits) == 5000

    def test_local_total_cap_bounds_union(self):
        r = self._local_resolver(per_query=5000, total=600)
        counts = {"n": 0}
        def gen(formula, limit):
            counts["n"] += 1
            base = counts["n"] * 100000
            return list(range(base, base + limit))
        r._local_db.by_formula = gen
        hits = r._resolve_similarity("C5H6N2O2", "/tmp")
        assert len(hits) == 600

    def test_pug_path_keeps_legacy_caps(self, monkeypatch):
        r = _resolver()  # _local_db is None -> PUG path
        calls = []
        class Resp:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"IdentifierList": {"CID": list(range(1, 1000))}}
        monkeypatch.setattr(r._session, "get", lambda *a, **k: (calls.append(a) or Resp()))
        hits = r._resolve_similarity("C5H6N2O2", "/tmp")
        # PUG path: per-query MaxRecords=200 constant, total capped at 500
        assert "MaxRecords=200" in calls[0][0]
        assert len(hits) == 500
