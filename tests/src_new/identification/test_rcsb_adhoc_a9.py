"""W3 A9 (BH-044): RCSB structure search must work for Celery-dispatched
runs (runs the API does not know).

Production evidence: the mmCIF resolver built the segment URL as
`/files/{run_uuid}/input/{name}` over the deployment host; Celery runs
are not registered with the API, so every query hit HTTP 404
(`MmCif structure resolution failed: 404` in ~100 runs, b9 + g0a2091) —
structure search was silently OFF for the whole corpus path.

RCSB's public structure-search API takes a URL only (the legacy
anonymous user-upload endpoint is gone), so per the task set's fallback:
the worker writes the segment mmCIF to a SHARED adhoc directory as
`/files/adhoc/<sha256>.cif` (run-independent, unauthenticated,
short-lived by ops policy) and points RCSB there. Failures must be
countable: `structure_search_unavailable` reaches the resolver
_last_error channel (stage error + warning) with the HTTP status.
Tests mock RCSB — no live network.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from unittest import mock

import pytest

pytest.importorskip("MDAnalysis")
requests = pytest.importorskip("requests")

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.mmcif import MmCifResolver


def _config(tmp: Path, **pdb_kw) -> RunConfig:
    cfg = RunConfig()
    cfg.pdb.use_deployment_file_access = True
    cfg.pdb.deployment_file_url = "https://bioid.example"
    cfg.pdb.curr_uuid = "celery-run-not-in-api"
    for k, v in pdb_kw.items():
        setattr(cfg.pdb, k, v)
    return cfg


def _fake_rcsb_hit(post_mock, ident="4HHB", score=0.98):
    resp = mock.Mock()
    resp.status_code = 200
    resp.json.return_value = {
        "result_set": [{"identifier": ident, "score": score}]}
    resp.raise_for_status = lambda: None
    post_mock.return_value = resp


SIG = "data_seg\n_audit.creation_date 2026-10-28\n#\n"


class TestAdhocUrl:
    def test_resolver_uses_run_independent_adhoc_url(self, tmp_path):
        """The RCSB request must carry /files/adhoc/<sha256>.cif — never
        /files/{run_uuid}/... — and the worker must have written that
        file to the shared adhoc directory."""
        adhoc = tmp_path / "adhoc"
        resolver = MmCifResolver(_config(tmp_path, adhoc_files_dir=str(adhoc)))
        with mock.patch(
                "src_new.identification.resolvers._rcsb_search.requests.post"
        ) as post:
            _fake_rcsb_hit(post)
            out = resolver.resolve(SIG, str(tmp_path))
        assert out, "resolver must return the fake hit"
        req = post.call_args.kwargs["json"]
        url = req["query"]["nodes"][0]["parameters"]["value"]["url"]
        sha = hashlib.sha256(SIG.encode()).hexdigest()
        assert url == f"https://bioid.example/files/adhoc/{sha}.cif", url
        assert (adhoc / f"{sha}.cif").read_text() == SIG
        assert "celery-run-not-in-api" not in url

    def test_legacy_uuid_url_when_adhoc_unconfigured(self, tmp_path):
        """Guard: with adhoc_files_dir empty the pre-A9 deployment-URL
        path keeps working unchanged."""
        resolver = MmCifResolver(_config(tmp_path))
        with mock.patch(
                "src_new.identification.resolvers._rcsb_search.requests.post"
        ) as post:
            _fake_rcsb_hit(post)
            out = resolver.resolve(SIG, str(tmp_path))
        assert out
        url = post.call_args.kwargs["json"]["query"]["nodes"][0][
            "parameters"]["value"]["url"]
        assert "/files/celery-run-not-in-api/input/" in url

    def test_http_failure_records_structure_search_unavailable(self, tmp_path):
        """A failing RCSB request surfaces as a countable
        structure_search_unavailable error carrying the HTTP status —
        never a silent empty result (BH-044's ~100 silent 404s)."""
        resolver = MmCifResolver(_config(tmp_path,
                                         adhoc_files_dir=str(tmp_path)))
        resp = mock.Mock()
        resp.status_code = 404
        err = requests.exceptions.HTTPError(response=resp)
        resp.raise_for_status.side_effect = err
        resp.json.side_effect = err
        with mock.patch(
                "src_new.identification.resolvers._rcsb_search.requests.post",
                return_value=resp):
            out = resolver.resolve(SIG, str(tmp_path))
        assert out is None or out == []
        last = resolver.get_last_error() or ""
        assert "structure_search_unavailable" in last, last
        assert "404" in last


class TestAdhocServing:
    def test_api_serves_adhoc_files(self, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_ADHOC_DIR", str(tmp_path))
        from src_new.api.main import app
        from fastapi.testclient import TestClient
        sha = hashlib.sha256(b"hello").hexdigest()
        good = tmp_path / f"{sha}.cif"
        good.write_text("data_hello\n#")
        with TestClient(app) as client:
            r = client.get(f"/files/adhoc/{sha}.cif")
            assert r.status_code == 200, r.text
            assert r.text.startswith("data_hello")
            r2 = client.get("/files/adhoc/does-not-exist.cif")
            assert r2.status_code == 404
            r3 = client.get("/files/adhoc/..%2F..%2Fetc%2Fpasswd")
            assert r3.status_code == 404
