"""Red-team Batch 1.3 (broken channels) regression tests.

  C-05: InChIKey->CID IDSM SPARQL has a literal `}}` (plain-string close) ->
        HTTP 400 every call, fallback channel dead.
  C-04: AlphaFind treats a queued payload ({queue_position, results:[]}) as
        final -> returns empty; polling branch unreachable.
  C-07: _PUBCHEM_RESOLVERS breaker blocks idsm_pubchem (not a PUG client)
        and a phantom name "pubchem"; breaker skips are unrecorded.
  C-22: name resolver DB path is CWD-relative; no image/package fallback.
  C-23: IDSM similarity has no sachem:topn and no ranking -> candidate floods.
  B-17: morgan generator always raises (RingInfo uninitialized); type is
        unconsumed -> remove it.
  C-24: ccd_client.py is dead code (no importer).
"""
from __future__ import annotations

import importlib.util
import json
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

import pytest

from src_new.config.loader import RunConfig
from src_new.results.results_manager import ResultsManager


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, payload):
        self.urls = []
        self._payload = payload

    def get(self, url, timeout=None):
        self.urls.append(url)
        return _FakeResp(self._payload)


class TestC05SparqlBrace:
    def test_reverse_lookup_query_wellformed(self):
        from src_new.identification.resolvers.inchikey import _sparql_reverse_lookup

        payload = {"results": {"bindings": []}}
        sess = _FakeSession(payload)
        _sparql_reverse_lookup("AAAAAAAAAAAAAAAAAAAAAA-AA", sess)
        assert sess.urls, "no request issued"
        query = parse_qs(urlparse(sess.urls[0]).query)["query"][0]
        assert "}}" not in query, "literal double-brace ships to IDSM (C-05)"
        assert query.count("{") == query.count("}")


class TestC04AlphaFindQueued:
    def test_queued_payload_is_polled_not_returned(self, monkeypatch):
        import src_new.identification.resolvers.alphafind as af
        from src_new.identification.resolvers.alphafind import AlphaFindStructResolver

        r = AlphaFindStructResolver(RunConfig())
        queued = {"digest": "P0CG48", "queue_position": 0, "results": []}
        done = {"digest": "P0CG48", "search_time": 1,
                "results": [{"id": f"r{i}", "score": 0.9} for i in range(50)]}
        monkeypatch.setattr(r, "_alphafind_post", lambda p: queued)
        monkeypatch.setattr(r, "_alphafind_poll", lambda d: done)
        monkeypatch.setattr(af.time, "sleep", lambda s: None)

        out = r._alphafind_fetch_response("x.pdb")
        assert out is done or len(out.get("results", [])) == 50, (
            "queued payload (empty results) was returned as final (C-04)"
        )


class TestC07BreakerScope:
    def test_idsm_not_pug_gated(self):
        from src_new.identification.resolution_manager import (
            _PUBCHEM_RESOLVERS, _breaker_blocked)

        assert "idsm_pubchem" not in _PUBCHEM_RESOLVERS, (
            "IDSM does not call NCBI/PUG — it must not sit behind the PUG breaker"
        )
        assert "pubchem" not in _PUBCHEM_RESOLVERS  # phantom name matches nothing
        r = SimpleNamespace(name="idsm_pubchem", offline_capable=None)
        assert _breaker_blocked(r, pug_up=False) is False

    def test_breaker_skip_recorded_in_attempted(self, tmp_path, monkeypatch):
        import src_new.identification.resolution_manager as rm
        from src_new.identification.resolution_manager import IdentifierResolutionManager

        monkeypatch.setattr(rm, "_pubchem_healthy", lambda: False)

        calls = []
        blocked = SimpleNamespace(
            name="formula_pubchem",
            offline_capable=lambda: False,
            is_applicable=lambda *a, **k: calls.append("called") or True,
        )
        registry = SimpleNamespace(
            get_applicable_resolvers=lambda sig, as_similarity=False:
                [] if as_similarity else [blocked],
        )
        mgr = IdentifierResolutionManager(registry, RunConfig(),
                                          signature_type_map={"genA": "formula"})
        results = ResultsManager(tmp_path / "results.json")
        results.set_data("identifiers/SEG/genA", {})
        mgr.resolve(results, "SEG", "genA", "CH4")
        attempted = results.get_data("identifiers/SEG/genA/attempted") or []
        assert calls == [], "blocked resolver must not run"
        assert any("formula_pubchem" in a and "breaker" in a for a in attempted), (
            f"breaker skip unrecorded (C-07/C-10): attempted={attempted!r}"
        )


class TestC22NameDbFallback:
    def test_relative_db_path_resolves_from_package_root(self, tmp_path, monkeypatch):
        from src_new.identification.resolvers.name import NameDBSource, NameResolver

        monkeypatch.chdir(tmp_path)  # no ./databases/ccd.json here
        r = NameResolver(RunConfig(), NameDBSource.CCD)
        db = r._load_db(r.db_path)
        assert isinstance(db, dict) and len(db) > 0, (
            "CWD-relative ccd_db has no package/image fallback (C-22)"
        )


class TestC23IdsmTopN:
    def test_similarity_capped_and_ranked(self, monkeypatch):
        import src_new.identification.resolvers.idsm as idsm

        captured = {}

        class FakeWrapper:
            def __init__(self, endpoint):
                pass

            def setQuery(self, q):
                captured["query"] = q

            def setReturnFormat(self, fmt):
                pass

            def setTimeout(self, t):
                pass

            def query(self):
                binds = [
                    {"COMPOUND": {"value": f"http://rdf.ncbi.nlm.nih.gov/pubchem/compound/CID{1000+i}"},
                     "SCORE": {"value": str(0.80 + (i % 20) / 100)}}
                    for i in range(350)
                ]
                return SimpleNamespace(convert=lambda: {"results": {"bindings": binds}})

        monkeypatch.setattr(idsm, "SPARQLWrapper", FakeWrapper)
        out = idsm.idsm_fetch_similarity_match(
            "CC(=O)Oc1ccccc1C(=O)O", threshold=80,
            include_similarity=True, as_pubchem=True)
        assert "sachem:topn" in captured["query"], (
            "no server-side cap — floods like aspirin@0.8 -> 3430 rows (C-23)"
        )
        scores = [s for _, s in out]
        assert len(out) <= 200 and scores == sorted(scores, reverse=True)


class TestB17MorganRemoved:
    def test_morgan_generator_gone(self):
        from src_new.signatures.registry import get_default_generators

        names = [g.name for g in get_default_generators(RunConfig().signatures)]
        assert "morgan_fingerprint" not in names


class TestC24DeadCode:
    def test_ccd_client_deleted(self):
        assert importlib.util.find_spec("src_new.identification.ccd_client") is None, (
            "dead module still importable (C-24: wire normalize_resname or delete)"
        )
