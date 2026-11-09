"""A rerun records the requester's IP (user request 2026-11-09).

New submissions stored pipeline.creator_ip, reruns did not, so a rerun
never showed under "Your annotations" (GET /runs?mine=1).
"""
from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from src_new.api.main import app
from src_new.api.routes.runs import _rerun_name


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr("src_new.api.routes.runs.run_pipeline_task.apply_async",
                        lambda **kwargs: None)
    old = tmp_path / "old-run"
    (old / "input").mkdir(parents=True)
    (old / "input" / "3PTB.pdb").write_text("ATOM\n")
    (old / "results.json").write_text(json.dumps(
        {"pipeline": {"status": "success", "run_name": "Trypsin>Crystal structure"}}))
    return tmp_path


def test_rerun_records_requester_ip_and_shows_as_mine(runs_dir):
    client = TestClient(app)
    hdr = {"X-Forwarded-For": "203.0.113.7, 10.0.0.1"}
    r = client.post("/api/v1/runs/old-run/rerun", headers=hdr)
    assert r.status_code == 200
    new_id = r.json()["run_id"]
    data = json.loads((runs_dir / new_id / "results.json").read_text())
    assert data["pipeline"]["creator_ip"] == "203.0.113.7"
    assert data["pipeline"]["run_name"] == "Trypsin (re-run)>Crystal structure"
    mine = client.get("/api/v1/runs?mine=1", headers=hdr).json()["runs"]
    assert new_id in {x["run_id"] for x in mine}


def test_rerun_name_keeps_the_description():
    assert _rerun_name("MDR00042100") == "MDR00042100 (re-run)"
    assert _rerun_name("Title > Desc") == "Title (re-run)> Desc"
