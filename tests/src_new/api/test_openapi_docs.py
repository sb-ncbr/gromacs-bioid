"""The published API reference and the fixes it brought (2026-11-19)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from src_new.api import models, openapi_docs
from src_new.api.main import app

client = TestClient(app)


def test_every_published_route_is_documented():
    published = {(m, r.path) for r in app.routes if isinstance(r, APIRoute) and r.include_in_schema
                 for m in r.methods}
    assert published == set(openapi_docs.ENDPOINTS)
    for (method, path), ep in openapi_docs.ENDPOINTS.items():
        assert len(ep.description) >= 30, (method, path)
        assert ep.example is not None, (method, path)


def test_schema_carries_examples_errors_and_parameters():
    schema = client.get("/openapi.json").json()
    for path, ops in schema["paths"].items():
        for method, op in ops.items():
            for p in op.get("parameters", []):
                assert p.get("description"), (method, path, p["name"])
            if path.startswith("/files/"):
                continue
            ok = next(v for k, v in op["responses"].items() if k.startswith("2"))
            assert any("example" in c or "examples" in c for c in ok["content"].values()), (method, path)
            if "{run_id}" in path:
                assert "404" in op["responses"], (method, path)
                run = next(p for p in op["parameters"] if p["name"] == "run_id")
                assert run["example"] == openapi_docs.EXAMPLE_RUN
    assert [t["name"] for t in schema["tags"]] == ["Runs", "Settings", "Results", "Files", "Managing runs",
                                                   "Service"]
    assert set(schema["paths"]) <= set(openapi_docs.PATH_ORDER)  # every path has its place
    assert list(schema["paths"]) == [p for p in openapi_docs.PATH_ORDER if p in schema["paths"]]
    by_tag: dict[str, list[str]] = {}
    for path, ops in schema["paths"].items():
        for method, op in ops.items():
            by_tag.setdefault(op["tags"][0], []).append(op["summary"])
    assert by_tag["Runs"] == ["Submit a run", "Run status and progress", "Queue position", "Run summary"]
    assert by_tag["Managing runs"][-1] == "Delete a run"


@pytest.mark.parametrize("key,model", [
    ("status", models.RunStatusResponse), ("summary", models.RunSummaryResponse),
    ("queue", models.RunQueueResponse), ("molecules", models.MoleculeSummaryResponse),
    ("molecule_info", models.MoleculeInfoResponse), ("verification", models.VerificationResponse),
    ("verification_segment", models.VerificationResponse), ("identifiers", models.IdentifiersResponse),
    ("signatures", models.SignaturesResponse), ("files", models.RunFilesResponse),
    ("loading", models.LoadingInfoResponse), ("render", models.RenderPathsResponse),
    ("examples", models.ExamplesResponse), ("capabilities", models.CapabilitiesResponse),
])
def test_captured_examples_still_match_the_response_models(key, model):
    model.model_validate(openapi_docs.examples()[key])


def test_partial_run_example_is_documented():
    # 2026-11-21 (mdval audit item 7)
    models.RunSummaryResponse.model_validate(openapi_docs.PARTIAL_SUMMARY)
    schema = client.get("/openapi.json").json()
    ok = schema["paths"]["/api/v1/runs/{run_id}"]["get"]["responses"]["200"]["content"]["application/json"]
    assert ok["examples"]["partial"]["value"]["completeness"] == "partial"
    assert ok["examples"]["run"]["value"]["completeness"] == "complete"
    for name in ("PipelineStatusResponse", "RunSummaryResponse", "RunListItem"):
        props = schema["components"]["schemas"][name]["properties"]
        assert {"completeness", "partial_stages"} <= set(props), name


def _run(tmp_path: Path, run_id: str, pipeline: dict, data: dict | None = None, **top) -> Path:
    d = tmp_path / run_id
    d.mkdir()
    (d / "results.json").write_text(json.dumps({"pipeline": pipeline, "data": data or {}, **top}))
    return d


def test_files_lists_real_runs_only(tmp_path, monkeypatch):
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    (tmp_path / "_settings").mkdir()
    (tmp_path / "_settings" / "queue_tokens.json").write_text("{}")
    assert client.get("/api/v1/runs/_settings/files").status_code in (404, 422)
    run = _run(tmp_path, "r1", {"status": "success"})
    (run / ".hidden").mkdir()
    (run / ".hidden" / "x").write_text("x")
    (run / "input").mkdir()
    (run / "input" / "a.pdb").write_text("x")
    assert client.get("/api/v1/runs/r1/files").json()["files"] == ["input/a.pdb", "results.json"]


def test_since_without_a_zone_is_utc(tmp_path, monkeypatch):
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    d = _run(tmp_path, "r1", {"status": "running"})
    body = json.loads((d / "results.json").read_text())
    body["warnings"] = [{"code": "a", "message": "old", "recorded_at": "2026-11-08T10:00:00+00:00"},
                        {"code": "b", "message": "new", "recorded_at": "2026-11-08T12:00:00+00:00"}]
    (d / "results.json").write_text(json.dumps(body))
    for since in ("2026-11-08T11:00:00", "2026-11-08T11:00:00Z", "2026-11-08T12:00:00+01:00"):
        r = client.get("/api/v1/runs/r1/status", params={"since": since})
        assert r.status_code == 200 and [w["code"] for w in r.json()["warnings"]] == ["b"], since
    assert len(client.get("/api/v1/runs/r1/status?since=2026-11-08").json()["warnings"]) == 2


def test_molecule_info_matches_the_results_page(tmp_path, monkeypatch):
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    hit = {"identifier": "2332", "database": "pubchem", "final_confidence": 80.0}
    _run(tmp_path, "r1", {"status": "success"}, {
        "fragments": {"segments": [{"segment": "A__v1", "type": "small_molecule", "atoms_per_copy": 9,
                                    "resname": "BEN"}]},
        "verification": {"A__v1": {"verified_hits": [
            {**hit, "is_verified": True},
            {**hit, "identifier": "1", "final_confidence": 95.0, "is_verified": False}]}}})
    info = client.get("/api/v1/runs/r1/molecules/A__v1/info").json()
    assert info["confidence"] == 80.0  # the rejected 95 does not count


def test_runs_are_listed_newest_first_and_results_url_is_the_api(tmp_path, monkeypatch):
    from src_new.api.security import ip_hash
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    for rid, at in (("a-new", "2026-11-09T00:00:00+00:00"), ("z-old", "2026-11-01T00:00:00+00:00"),
                    ("m-mid", "2026-11-05T00:00:00+00:00")):
        _run(tmp_path, rid, {"status": "success", "creator_ip_hash": ip_hash("testclient")}, created_at=at)
    runs = client.get("/api/v1/runs").json()["runs"]
    assert [r["run_id"] for r in runs] == ["a-new", "m-mid", "z-old"]
    assert openapi_docs.ENDPOINTS[("POST", "/api/v1/runs")].example["results_url"].startswith("/api/v1/runs/")


def test_cors_exposes_retry_after():
    r = client.get("/api/v1/health", headers={"Origin": "https://example.org"})
    assert "Retry-After" in r.headers.get("access-control-expose-headers", "")


def test_molecule_counts_come_from_the_stored_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    _run(tmp_path, "r1", {"status": "success"}, {"fragments": {
        "total_fragment_count": 65, "type_counts": {"protein": 1},
        "unique": {"k": {"segment_ids": ["A"], "segment_names": ["A"], "molecule_type": "protein",
                         "atom_count": 1629, "residue_indices": list(range(223))}},
        "segments": [{"segment": "A", "type": "protein"}]}})
    m = client.get("/api/v1/runs/r1/molecules").json()
    assert m["total_fragment_count"] == 65
    assert m["unique_molecules"]["k"]["residue_count"] == 223


def test_config_json_has_priority_over_the_preset():
    from src_new.config.loader import RunConfig
    from src_new.config.presets import checked_overrides, resolve_run_config
    base = RunConfig.from_default_ini()
    assert base.identifiers.blast_uniref50 is True
    assert resolve_run_config("quick", None).identifiers.blast_uniref50 is False
    back_on = checked_overrides({"identifiers": {"blast_uniref50": True}}, base, keep_defaults=True)
    assert resolve_run_config("quick", back_on).identifiers.blast_uniref50 is True
    # a non-changeable field equal to the server's value is still accepted and dropped
    path = base.blast.nr_aa_db
    assert checked_overrides({"blast": {"nr_aa_db": path}}, base, keep_defaults=True) == {}
