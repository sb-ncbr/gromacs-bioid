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
