"""Every MCP tool against a mocked BioID API, through an MCP client session."""
from __future__ import annotations

import base64
import json

import httpx
import pytest

from .conftest import MOLECULES, OPTIONS, PUBLIC, RUN, SIGNATURES_A, STATUS, SUMMARY, VERIFICATION

pytestmark = pytest.mark.anyio


async def test_tool_list(call):
    tools = await call.session.list_tools()
    names = {t.name for t in tools.tools}
    assert names == {"list_presets", "submit_structure", "submit_files", "get_run_status",
                     "get_results", "get_molecule_details", "list_examples", "cancel_run",
                     "prepare_upload", "get_results_json"}
    by_name = {t.name: t for t in tools.tools}
    assert by_name["get_results"].annotations.readOnlyHint is True
    assert by_name["cancel_run"].annotations.destructiveHint is True
    # no admin surface
    assert not names & {"delete_run", "rerun_all", "list_runs"}


# -- list_presets --------------------------------------------------------

async def test_list_presets(call, api):
    api.get("https://api.test/api/v1/runs/config/options").respond(json=OPTIONS)
    err, out = await call("list_presets")
    assert not err
    ids = [p["id"] for p in out["presets"]]
    assert ids == ["balanced", "quick", "exact", "deep"]
    quick = out["presets"][1]
    assert "searches disabled: blast_nt, blast_nt_similarity" in quick["changes"]
    assert "verification.verify_top_n = 30 (default 50)" in quick["changes"]
    assert out["presets"][0]["changes"] == ["none (server defaults)"]


async def test_list_presets_old_server(call, api):
    api.get("https://api.test/api/v1/runs/config/options").respond(404, json={"detail": "Not Found"})
    err, out = await call("list_presets")
    assert not err
    assert out["presets"] == [] and "does not offer presets" in out["note"]


# -- submit_files --------------------------------------------------------

def _created(request: httpx.Request):
    return httpx.Response(200, json={"run_id": "new-run-1", "status": "queued",
                                     "message": "ok", "results_url": "/runs/new-run-1/status",
                                     "owner_token": "tok-1"})


async def test_submit_files_text_and_base64(call, api):
    api.get("https://api.test/api/v1/runs/config/options").respond(json=OPTIONS)
    route = api.post("https://api.test/api/v1/runs").mock(side_effect=_created)
    err, out = await call("submit_files", {
        "files": [{"name": "topol.top", "text": "[ system ]\n"},
                  {"name": "dir/conf.gro", "content_base64": base64.b64encode(b"GRO").decode()}],
        "preset": "quick", "run_name": "my run"})
    assert not err, out
    assert out["run_id"] == "new-run-1"
    assert out["owner_token"] == "tok-1" and "cancel_run" in out["owner_token_note"]
    assert out["preset"] == "quick"
    assert out["results_page"] == f"{PUBLIC}/runs/new-run-1"
    assert "2-8 minutes" in out["next"]
    assert out["files"] == [{"name": "topol.top", "bytes": 11}, {"name": "conf.gro", "bytes": 3}]
    body = route.calls.last.request.content
    assert b'name="preset"\r\n\r\nquick' in body
    assert b'name="run_name"\r\n\r\nmy run' in body
    assert b'filename="topol.top"' in body and b'filename="conf.gro"' in body
    assert b"run_id" not in route.calls.last.request.url.query  # never choose the id


async def test_submit_files_without_preset_sends_none(call, api):
    route = api.post("https://api.test/api/v1/runs").mock(side_effect=_created)
    err, out = await call("submit_files", {"files": [{"name": "x.pdb", "text": "ATOM"}]})
    assert not err
    assert out["preset"] == "balanced"
    assert b'name="preset"' not in route.calls.last.request.content


@pytest.mark.parametrize("files, message", [
    ([], "No files given"),
    ([{"name": "notes.txt", "text": "hi"}], "not a format BioID reads"),
    ([{"name": "a.pdb", "text": "x"}, {"name": "a.pdb", "text": "y"}], "Duplicate file name"),
    ([{"name": "a.pdb"}], "exactly one of 'text' or 'content_base64'"),
    ([{"name": "a.pdb", "text": "x", "content_base64": "eA=="}], "exactly one"),
    ([{"name": "a.pdb", "text": ""}], "is empty"),
    ([{"name": "a.tpr", "content_base64": "!!!notbase64"}], "base64"),
    ([{"name": "a.pdb", "text": "x" * 2000}], "prepare_upload"),
    ([{"name": "..", "text": "x"}], "Invalid file name"),
])
async def test_submit_files_rejects(call, api, files, message):
    route = api.post("https://api.test/api/v1/runs").mock(side_effect=_created)
    err, text = await call("submit_files", {"files": files})
    assert err and message in text, text
    assert not route.called


async def test_submit_unknown_preset(call, api):
    api.get("https://api.test/api/v1/runs/config/options").respond(json=OPTIONS)
    route = api.post("https://api.test/api/v1/runs").mock(side_effect=_created)
    err, text = await call("submit_files", {"files": [{"name": "a.pdb", "text": "x"}], "preset": "turbo"})
    assert err and "Unknown preset 'turbo'" in text and "quick" in text
    assert not route.called


async def test_submit_preset_on_old_server(call, api):
    api.get("https://api.test/api/v1/runs/config/options").respond(404)
    route = api.post("https://api.test/api/v1/runs").mock(side_effect=_created)
    err, text = await call("submit_files", {"files": [{"name": "a.pdb", "text": "x"}], "preset": "quick"})
    assert err and "does not support presets" in text
    # 'balanced' is the default anyway: allowed, and not sent
    err, out = await call("submit_files", {"files": [{"name": "a.pdb", "text": "x"}], "preset": "balanced"})
    assert not err and b'name="preset"' not in route.calls.last.request.content


async def test_submit_api_errors(call, api):
    api.post("https://api.test/api/v1/runs").respond(422, json={"detail": "Unknown config section: foo"})
    err, text = await call("submit_files", {"files": [{"name": "a.pdb", "text": "x"}]})
    assert err and "HTTP 422" in text and "Unknown config section" in text


async def test_submit_api_timeout(call, api):
    api.post("https://api.test/api/v1/runs").mock(side_effect=httpx.ReadTimeout("slow"))
    err, text = await call("submit_files", {"files": [{"name": "a.pdb", "text": "x"}]})
    assert err and "did not answer in time" in text


async def test_submit_api_unreachable(call, api):
    api.post("https://api.test/api/v1/runs").mock(side_effect=httpx.ConnectError("refused"))
    err, text = await call("submit_files", {"files": [{"name": "a.pdb", "text": "x"}]})
    assert err and "Could not reach the BioID API" in text


async def test_submit_api_500(call, api):
    api.post("https://api.test/api/v1/runs").respond(500, text="boom")
    err, text = await call("submit_files", {"files": [{"name": "a.pdb", "text": "x"}]})
    assert err and "HTTP 500" in text and "boom" in text


# -- submit_structure ------------------------------------------------------

async def test_submit_structure_pdb_id(call, api):
    rcsb = api.get("https://files.rcsb.org/download/3PTB.pdb").respond(text="HEADER 3PTB\nATOM\n")
    route = api.post("https://api.test/api/v1/runs").mock(side_effect=_created)
    err, out = await call("submit_structure", {"pdb_id": "3ptb"})
    assert not err, out
    assert rcsb.called
    assert out["files"] == [{"name": "3PTB.pdb", "bytes": 17}]
    body = route.calls.last.request.content
    assert b'filename="3PTB.pdb"' in body
    assert b"PDB 3PTB>Fetched from RCSB" in body


async def test_submit_structure_falls_back_to_mmcif(call, api):
    api.get("https://files.rcsb.org/download/8GLV.pdb").respond(404)
    api.get("https://files.rcsb.org/download/8GLV.cif").respond(text="data_8GLV\n")
    route = api.post("https://api.test/api/v1/runs").mock(side_effect=_created)
    err, out = await call("submit_structure", {"pdb_id": "8GLV", "run_name": "ribosome"})
    assert not err, out
    assert out["files"][0]["name"] == "8GLV.cif"
    assert b'name="run_name"\r\n\r\nribosome' in route.calls.last.request.content


async def test_submit_structure_unknown_entry(call, api):
    api.get("https://files.rcsb.org/download/9ZZZ.pdb").respond(404)
    api.get("https://files.rcsb.org/download/9ZZZ.cif").respond(404)
    err, text = await call("submit_structure", {"pdb_id": "9ZZZ"})
    assert err and "not found at RCSB" in text


@pytest.mark.parametrize("args, message", [
    ({}, "exactly one of 'pdb_id' or 'url'"),
    ({"pdb_id": "3PTB", "url": "https://x.org/a.pdb"}, "exactly one"),
    ({"pdb_id": "hello world"}, "is not a PDB id"),
    ({"url": "http://example.org/a.pdb"}, "Only https://"),
    ({"url": "https://127.0.0.1/a.pdb"}, "non-public address"),
    ({"url": "https://10.43.193.47/a.pdb"}, "non-public address"),
    ({"url": "https://169.254.169.254/latest/meta-data"}, "non-public address"),
    ({"url": "https://[::1]/a.pdb"}, "non-public address"),
    ({"url": "https://user:pw@example.org/a.pdb"}, "credentials"),
    ({"url": "https://example.org:8443/a.pdb"}, "default https port"),
])
async def test_submit_structure_rejects(call, api, args, message):
    route = api.post("https://api.test/api/v1/runs").mock(side_effect=_created)
    err, text = await call("submit_structure", args)
    assert err and message in text, text
    assert not route.called


async def test_submit_structure_url(call, api, monkeypatch):
    import mcp_server.fetch as fetch

    async def resolve(host):
        assert host == "zenodo.example"
        return "93.184.216.34"
    monkeypatch.setattr(fetch, "resolve_public", resolve)
    dl = api.get("https://93.184.216.34/records/1/files/sim.tpr").respond(content=b"TPRDATA")
    route = api.post("https://api.test/api/v1/runs").mock(side_effect=_created)
    err, out = await call("submit_structure", {"url": "https://zenodo.example/records/1/files/sim.tpr"})
    assert not err, out
    req = dl.calls.last.request
    assert req.headers["host"] == "zenodo.example"
    assert req.extensions["sni_hostname"] == "zenodo.example"
    assert out["files"] == [{"name": "sim.tpr", "bytes": 7}]
    assert b'filename="sim.tpr"' in route.calls.last.request.content


async def test_submit_structure_url_needs_known_extension(call, api, monkeypatch):
    import mcp_server.fetch as fetch

    async def resolve(host):
        return "93.184.216.34"
    monkeypatch.setattr(fetch, "resolve_public", resolve)
    api.get("https://93.184.216.34/download").respond(content=b"x")
    route = api.post("https://api.test/api/v1/runs").mock(side_effect=_created)
    err, text = await call("submit_structure", {"url": "https://host.example/download"})
    assert err and "Pass 'filename'" in text
    err, out = await call("submit_structure", {"url": "https://host.example/download",
                                               "filename": "bundle.zip"})
    assert not err and out["files"][0]["name"] == "bundle.zip"
    assert route.call_count == 1


# -- get_run_status ------------------------------------------------------

async def test_get_run_status_finished(call, api):
    api.get(f"https://api.test/api/v1/runs/{RUN}/status").respond(json=STATUS)
    api.get(f"https://api.test/api/v1/runs/{RUN}").respond(json=SUMMARY)
    err, out = await call("get_run_status", {"run_id": RUN})
    assert not err, out
    assert out["status"] == "success"
    assert out["title"] == "Trypsin with benzamidine"
    assert out["elapsed_minutes"] == 7.8
    assert out["stages_done"] == "3/3"
    assert out["molecules_searched"] == "5/5"
    assert out["failed_searches"][0] == "blast_nr_protein [A]: BLAST timed out after 300s"
    assert "/app/databases" not in json.dumps(out)
    assert out["warnings"] == {"pbc_unwrap_applied": 1}
    assert out["next"] == "Finished. Call get_results."
    assert out["results_page"] == f"{PUBLIC}/runs/{RUN}"


async def test_get_run_status_queued(call, api):
    status = {**STATUS, "pipeline": {**STATUS["pipeline"], "status": "queued", "started_at": None,
                                     "finished_at": None},
              "tasks": [], "warnings": [], "progress": None}
    api.get(f"https://api.test/api/v1/runs/{RUN}/status").respond(json=status)
    api.get(f"https://api.test/api/v1/runs/{RUN}").respond(json={**SUMMARY, "status": "queued", "run_name": None})
    api.get(f"https://api.test/api/v1/runs/{RUN}/queue").respond(json={"state": "queued", "position": 3, "ahead": 2})
    err, out = await call("get_run_status", {"run_id": RUN})
    assert not err, out
    assert out["status"] == "queued" and out["queue_position"] == 3 and out["runs_ahead"] == 2
    assert "check again" in out["next"]


async def test_get_run_status_running(call, api):
    status = {**STATUS, "pipeline": {**STATUS["pipeline"], "status": "running", "finished_at": None},
              "tasks": [{"task_id": "load_simulation", "name": "Load Simulation", "status": "success"},
                        {"task_id": "identify_molecules", "name": "Identify Molecules", "status": "running"},
                        {"task_id": "verify_results", "name": "Verify Results", "status": "pending"}],
              "progress": {"molecules_done": 1, "molecules_total": 4, "per_segment": {}}}
    api.get(f"https://api.test/api/v1/runs/{RUN}/status").respond(json=status)
    api.get(f"https://api.test/api/v1/runs/{RUN}").respond(json=SUMMARY)
    err, out = await call("get_run_status", {"run_id": RUN})
    assert out["current_stage"] == "Identify Molecules"
    assert out["stages_done"] == "1/3" and out["molecules_searched"] == "1/4"
    assert "elapsed_minutes" in out


async def test_get_run_status_failed(call, api):
    status = {**STATUS, "pipeline": {**STATUS["pipeline"], "status": "failed"},
              "critical_errors": [{"code": "load_failed", "message": "No topology found"}]}
    api.get(f"https://api.test/api/v1/runs/{RUN}/status").respond(json=status)
    api.get(f"https://api.test/api/v1/runs/{RUN}").respond(json=SUMMARY)
    api.get(f"https://api.test/api/v1/runs/{RUN}/loading").respond(
        json={"run_id": RUN, "failure_summary": {"reason": "missing_topology", "message": "add a .top"}})
    err, out = await call("get_run_status", {"run_id": RUN})
    assert out["errors"] == ["No topology found"]
    assert out["load_failure"]["reason"] == "missing_topology"
    assert "failed" in out["next"]


async def test_get_run_status_not_found(call, api):
    api.get("https://api.test/api/v1/runs/missing-run/status").respond(404, json={"detail": "Run 'missing-run' not found"})
    err, text = await call("get_run_status", {"run_id": "missing-run"})
    assert err and "was not found on BioID" in text


@pytest.mark.parametrize("bad", ["../etc/passwd", "a/b", "", "x" * 200, "a..b"])
async def test_run_id_validation(call, api, bad):
    err, text = await call("get_run_status", {"run_id": bad})
    assert err and "not a valid BioID run id" in text
    assert not api.calls  # nothing reached the API


# -- get_results -----------------------------------------------------------

def _mock_results(api, status="success", verification=VERIFICATION):
    api.get(f"https://api.test/api/v1/runs/{RUN}").respond(json={**SUMMARY, "status": status})
    api.get(f"https://api.test/api/v1/runs/{RUN}/molecules").respond(json=MOLECULES)
    api.get(f"https://api.test/api/v1/runs/{RUN}/verification").respond(json=verification)


async def test_get_results(call, api):
    _mock_results(api)
    err, out = await call("get_results", {"run_id": RUN})
    assert not err, out
    assert out["status"] == "success"
    assert out["summary"] == {"molecules": 5, "identified": 2, "exact": 1, "lead": 1, "not_identified": 1}
    mols = {m["molecule"]: m for m in out["molecules"]}
    prot = mols["A"]
    # highest confidence verified hit wins (UniProt 84.1 over PDB 81.4)
    assert prot["best"]["database"] == "UniProt" and prot["best"]["id"] == "P00760"
    assert prot["best"]["confidence"] == 84.1 and prot["best"]["confidence_label"] == "high"
    assert prot["best"]["evidence"] == "100% sequence identity"
    assert prot["also_in"] == ["PDB:1AQ7"]
    assert prot["verified_hits"] == 3
    assert "display_name" not in prot  # 'A' == segment id
    lig = mols["A__v1"]
    assert lig["display_name"] == "BEN" and lig["state"] == "identified"
    assert lig["best"]["evidence"] == "similar skeleton (100%)"
    assert lig["rejected_hits"] == 1
    assert mols["A__v2"]["state"] == "exact"
    assert mols["A__v3"]["state"] == "lead" and mols["A__v3"]["copies"] == 62
    assert mols["A__v3"]["best"]["confidence_label"] == "low"
    assert mols["B"]["state"] == "not_identified" and mols["B"]["rejected_hits"] == 1
    assert out["results_csv"].endswith(f"/api/v1/runs/{RUN}/download/results.csv")
    assert "equivalence_class_id" not in json.dumps(out)


async def test_get_results_truncates(call, api):
    _mock_results(api)
    err, out = await call("get_results", {"run_id": RUN, "max_molecules": 2})
    assert len(out["molecules"]) == 2 and "3 more molecules" in out["truncated"]
    assert out["summary"]["molecules"] == 5


async def test_get_results_running(call, api):
    _mock_results(api, status="running", verification={"run_id": RUN, "segment": "unknown", "hits": []})
    err, out = await call("get_results", {"run_id": RUN})
    assert not err
    assert {m["state"] for m in out["molecules"]} == {"pending"}
    assert "still in progress" in out["note"]


async def test_get_results_failed(call, api):
    _mock_results(api, status="failed", verification={"run_id": RUN, "segment": "unknown", "hits": []})
    err, out = await call("get_results", {"run_id": RUN})
    assert {m["state"] for m in out["molecules"]} == {"not_searched"}
    assert "failed" in out["note"]


async def test_get_results_not_found(call, api):
    api.get("https://api.test/api/v1/runs/nope").respond(404, json={"detail": "Run 'nope' not found"})
    api.get("https://api.test/api/v1/runs/nope/molecules").respond(404)
    api.get("https://api.test/api/v1/runs/nope/verification").respond(404)
    err, text = await call("get_results", {"run_id": "nope"})
    assert err and "was not found" in text


# -- get_molecule_details --------------------------------------------------

def _mock_details(api, seg="A", verification=None):
    api.get(f"https://api.test/api/v1/runs/{RUN}/molecules").respond(json=MOLECULES)
    hits = [h for h in VERIFICATION["hits"] if h["segment"] == seg]
    api.get(f"https://api.test/api/v1/runs/{RUN}/verification", params={"segment": seg}).respond(
        json=verification or {"run_id": RUN, "segment": seg, "hits": hits})
    api.get(f"https://api.test/api/v1/runs/{RUN}/signatures", params={"segment": seg}).respond(
        json=SIGNATURES_A if seg == "A" else {"run_id": RUN, "signatures": [
            {"segment": seg, "generator": "smiles", "signature": "[N][C]"},
            {"segment": seg, "generator": "smiles_not_sanitized", "signature": "NC(N)C1CCCCC1"},
            {"segment": seg, "generator": "inchi_key", "signature": "OYOFUEDXAMRQBB-UHFFFAOYSA-N"},
            {"segment": seg, "generator": "resname", "signature": "BEN"}]})
    api.get(f"https://api.test/api/v1/runs/{RUN}/status").respond(json=STATUS)


async def test_get_molecule_details_protein(call, api):
    _mock_details(api, "A")
    err, out = await call("get_molecule_details", {"run_id": RUN, "molecule": "A", "max_hits": 2})
    assert not err, out
    assert out["molecule"] == "A" and out["kind"] == "protein" and out["state"] == "identified"
    assert out["descriptors"]["sequence"] == "IVGGYTCGANTVPY"
    assert out["descriptors"]["sequence_length"] == 14
    assert out["descriptors"]["formula_heavy_atoms"] == "C1012N279O324S14"
    assert "ATOM" not in json.dumps(out["descriptors"])  # no coordinate blobs
    assert [h["id"] for h in out["verified"]] == ["P00760", "1AQ7"]
    assert out["verified"][0]["organism"] == "Bos taurus"
    assert out["verified_more"] == 1
    assert out["verified_by_database"] == {"PDB": 2, "UniProt": 1}
    assert out["failed_searches"] == ["blast_nr_protein (fasta_map_protein): BLAST timed out after 300s"]


async def test_get_molecule_details_by_display_name(call, api):
    _mock_details(api, "A__v1")
    err, out = await call("get_molecule_details", {"run_id": RUN, "molecule": "ben"})
    assert not err, out
    assert out["molecule"] == "A__v1" and out["display_name"] == "BEN"
    assert out["descriptors"]["smiles"] == "NC(N)C1CCCCC1"
    assert out["descriptors"]["inchi_key"] == "OYOFUEDXAMRQBB-UHFFFAOYSA-N"
    assert out["rejected"] == [{"database": "PubChem", "id": "999", "name": "Something",
                                "reason": "chemical structure does not match",
                                "raw_reason": "fingerprint_mismatch"}]
    assert out["rejected_total"] == 1


async def test_get_molecule_details_unknown(call, api):
    api.get(f"https://api.test/api/v1/runs/{RUN}/molecules").respond(json=MOLECULES)
    err, text = await call("get_molecule_details", {"run_id": RUN, "molecule": "XYZ"})
    assert err and "has no molecule 'XYZ'" in text and "A__v1 (BEN)" in text


# -- list_examples / cancel ------------------------------------------------

async def test_list_examples(call, api):
    route = api.get("https://api.test/api/v1/runs/examples").respond(json={"examples": [
        {"run_id": RUN, "title": "Trypsin with benzamidine", "description": "PDB 3PTB",
         "image_url": f"/files/{RUN}/render/system.png", "created_at": "2026-11-08"}]})
    err, out = await call("list_examples", {"limit": 3})
    assert not err
    assert route.calls.last.request.url.params["limit"] == "3"
    ex = out["examples"][0]
    assert ex["run_id"] == RUN and ex["results_page"] == f"{PUBLIC}/runs/{RUN}"
    assert ex["image"] == f"{PUBLIC}/files/{RUN}/render/system.png"


async def test_list_examples_limit_validated(call, api):
    err, text = await call("list_examples", {"limit": 50})
    assert err


async def test_cancel_run(call, api):
    route = api.post(f"https://api.test/api/v1/runs/{RUN}/cancel").respond(json={"run_id": RUN, "status": "cancelled"})
    err, out = await call("cancel_run", {"run_id": RUN, "owner_token": "tok"})
    assert not err and out["status"] == "cancelled" and route.called
    assert route.calls.last.request.headers["X-Owner-Token"] == "tok"


async def test_cancel_needs_owner_token(call, api):
    err, text = await call("cancel_run", {"run_id": RUN, "owner_token": " "})
    assert err and "owner_token is required" in text
    api.post(f"https://api.test/api/v1/runs/{RUN}/cancel").respond(
        403, json={"detail": "Only the submitter of this run can have it cancelled."})
    err, text = await call("cancel_run", {"run_id": RUN, "owner_token": "wrong"})
    assert err and "Only the submitter" in text


async def test_cancel_finished_run(call, api):
    api.post(f"https://api.test/api/v1/runs/{RUN}/cancel").respond(
        400, json={"detail": "Run is already in terminal state: success"})
    err, text = await call("cancel_run", {"run_id": RUN, "owner_token": "tok"})
    assert err and "already finished (success)" in text


# -- resource / prompt -------------------------------------------------------

async def test_guide_resource_and_prompt(call):
    resources = await call.session.list_resources()
    assert [str(r.uri) for r in resources.resources] == ["bioid://guide", "bioid://results-json"]
    res = await call.session.read_resource("bioid://guide")
    assert "Only verified hits count" in res.contents[0].text
    prompt = await call.session.get_prompt("explain_run", {"run_id": RUN})
    assert RUN in prompt.messages[0].content.text
