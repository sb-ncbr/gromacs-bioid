"""The published OpenAPI schema is the public /api/v1 surface only."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src_new.api.main import app

client = TestClient(app)


def test_schema_lists_only_public_v1_routes():
    paths = client.get("/openapi.json").json()["paths"]
    assert all(p.startswith("/api/v1/") for p in paths)
    for internal in ("/api/v1/runs/rerun-all", "/api/v1/runs/config/default",
                     "/api/v1/runs/config/parallel-default", "/api/v1/runs/{run_id}/render"):
        assert internal not in paths
    assert "/api/v1/runs/{run_id}/download/results.json" in paths
    assert paths["/api/v1/runs"]["post"]["summary"] == "Submit a run"


def test_internal_routes_still_served():
    # hidden from the schema, not removed
    assert client.get("/runs/config/default").status_code == 200


def test_download_results_json(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    run = tmp_path / "abc-123"
    run.mkdir()
    (run / "results.json").write_text(json.dumps({"pipeline": {"status": "success", "creator_ip": "1.2.3.4"}}))
    r = client.get("/api/v1/runs/abc-123/download/results.json")
    assert r.status_code == 200
    assert r.json()["pipeline"] == {"status": "success"}
    assert "attachment" in r.headers["content-disposition"]
    assert client.get("/api/v1/runs/nope/download/results.json").status_code == 404
    assert client.get("/api/v1/runs/..%2E/download/results.json").status_code == 404
