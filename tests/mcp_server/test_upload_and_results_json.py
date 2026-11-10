"""prepare_upload (files go straight to the REST API) and results.json access."""
from __future__ import annotations

import shlex

import pytest

from .conftest import OPTIONS, PUBLIC, RUN, SUMMARY

pytestmark = pytest.mark.anyio

RESULTS = {
    "pipeline": {"run_id": RUN, "status": "success"},
    "warnings": [{"code": "insufficient_bonds"}],
    "data": {
        "fragments": {"segments": [{"segment": "A", "type": "protein", "copies": 1}]},
        "verification": {"A": {"verified_hits": [{"identifier": "P00760", "final_confidence": 84.1,
                                                  "is_verified": True, "blob": "x" * 5000}]}},
    },
}


async def test_prepare_upload_builds_a_curl_command(call, api):
    api.get("https://api.test/api/v1/runs/config/options").respond(json=OPTIONS)
    err, out = await call("prepare_upload", {"file_paths": ["md run/topol.tpr", "conf.gro"],
                                             "preset": "quick", "run_name": "my run"})
    assert not err, out
    argv = shlex.split(out["curl"])
    assert argv[0] == "curl" and argv[-1] == f"{PUBLIC}/api/v1/runs"
    assert "files=@md run/topol.tpr" in argv and "files=@conf.gro" in argv
    assert "preset=quick" in argv and "run_name=my run" in argv
    assert "requests.post" in out["python"] and "get_run_status" in out["next"]


async def test_prepare_upload_rejects_unknown_format(call, api):
    err, out = await call("prepare_upload", {"file_paths": ["notes.docx"]})
    assert err and "not a format BioID reads" in out


async def test_results_json_links_and_guide(call, api):
    api.get(f"https://api.test/api/v1/runs/{RUN}").respond(json=SUMMARY)
    err, out = await call("get_results_json", {"run_id": RUN})
    assert not err, out
    assert out["download_url"] == f"{PUBLIC}/api/v1/runs/{RUN}/download/results.json"
    assert out["documentation"] == f"{PUBLIC}/documentation/results-json/"
    assert "data.verification.<seg>.verified_hits" in out["structure"]


async def test_results_json_path(call, api):
    api.get(f"https://api.test/api/v1/runs/{RUN}/download/results.json").respond(json=RESULTS)
    err, out = await call("get_results_json", {"run_id": RUN, "path": "data/fragments/segments/0"})
    assert not err, out
    assert out["value"] == {"segment": "A", "type": "protein", "copies": 1}
    err, out = await call("get_results_json", {"run_id": RUN, "path": "data/verification", "max_kb": 1})
    assert "truncated" in out and out["keys"] == ["A"] and len(out["json_prefix"]) == 1024
    err, out = await call("get_results_json", {"run_id": RUN, "path": "data/nope"})
    assert err and "Available" in out and "fragments" in out


async def test_get_results_links_results_json(call, api):
    from .test_tools import _mock_results
    _mock_results(api)
    err, out = await call("get_results", {"run_id": RUN})
    assert out["results_json"].endswith(f"/runs/{RUN}/download/results.json")
    assert out["results_json_docs"].endswith("/documentation/results-json/")


async def test_results_json_resource(call):
    res = await call.session.read_resource("bioid://results-json")
    assert "documentation/results-json" in res.contents[0].text


async def test_retention_is_forwarded(call, api):
    import httpx
    api.get("https://api.test/api/v1/runs/config/options").respond(json=OPTIONS)
    route = api.post("https://api.test/api/v1/runs").mock(
        return_value=httpx.Response(200, json={"run_id": "r", "status": "queued", "owner_token": "t"}))
    err, out = await call("submit_files", {"files": [{"name": "a.pdb", "text": "ATOM\n"}],
                                           "retention": "preserve"})
    assert not err, out
    assert b'name="retention"\r\n\r\npreserve' in route.calls.last.request.content
    err, out = await call("prepare_upload", {"file_paths": ["a.pdb"], "retention": "90"})
    assert "retention=90" in out["curl"]
