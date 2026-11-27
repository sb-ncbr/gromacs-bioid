"""Repository-queue campaign runs read a campaign input directory in place
(g2 rerun): token-gated, confined to BAT3_CAMPAIGN_INPUT_ROOT, linked into
the run's own input directory."""
import os

import pytest
from fastapi.testclient import TestClient

from src_new.api import queue_tokens

INGRESS_PEER = ("10.42.0.10", 50000)
PDB = b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n"


@pytest.fixture
def env(tmp_path, monkeypatch):
    runs, campaign = tmp_path / "runs", tmp_path / "validation"
    runs.mkdir()
    (campaign / "1234" / "input").mkdir(parents=True)
    (campaign / "1234" / "input" / "structure.pdb").write_bytes(PDB)
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "x.pdb").write_bytes(PDB)
    monkeypatch.setenv("BAT3_RUNS_DIR", str(runs))
    monkeypatch.setenv("BAT3_CAMPAIGN_INPUT_ROOT", str(campaign))
    sent = []
    monkeypatch.setattr("src_new.api.routes.runs.run_pipeline_task.apply_async",
                        lambda *a, **k: sent.append(k))
    from src_new.api.main import app
    c = TestClient(app, client=INGRESS_PEER)
    c.sent = sent
    return c, runs, campaign, queue_tokens.create(runs, "repository")


def test_campaign_input_links_files_and_queues_repository(env):
    c, runs, campaign, token = env
    r = c.post("/api/v1/runs?run_id=g2-1234", data={"queue": "repository", "campaign_input": "1234/input"},
               headers={"X-Queue-Token": token})
    assert r.status_code == 200, r.text
    linked = runs / "g2-1234" / "input" / "structure.pdb"
    assert linked.is_symlink() and linked.resolve() == (campaign / "1234/input/structure.pdb").resolve()
    assert c.sent[-1]["queue"] == "validation.repo.celery"
    assert c.sent[-1]["kwargs"]["input_dir"] == str(runs / "g2-1234" / "input")


@pytest.mark.parametrize("rel", ["../outside", "/etc", "1234/../../outside", "9999/input", ""])
def test_campaign_input_is_confined(env, rel):
    c, runs, _campaign, token = env
    r = c.post("/api/v1/runs", data={"queue": "repository", "campaign_input": rel},
               headers={"X-Queue-Token": token})
    assert r.status_code == 422, r.text
    assert not [p for p in runs.iterdir() if p.is_dir() and not p.name.startswith("_")]


def test_campaign_input_needs_the_repository_queue_and_token(env):
    c, _runs, _campaign, token = env
    assert c.post("/api/v1/runs", data={"campaign_input": "1234/input"}).status_code == 403
    assert c.post("/api/v1/runs", data={"queue": "repository", "campaign_input": "1234/input"},
                  headers={"X-Queue-Token": "wrong"}).status_code == 403


def test_campaign_input_symlink_escape_rejected(env, tmp_path):
    c, _runs, campaign, token = env
    os.symlink(tmp_path / "outside", campaign / "evil")
    r = c.post("/api/v1/runs", data={"queue": "repository", "campaign_input": "evil"},
               headers={"X-Queue-Token": token})
    assert r.status_code == 422


def test_plain_upload_still_works_and_empty_is_rejected(env):
    c, _runs, _campaign, _token = env
    ok = c.post("/api/v1/runs", files=[("files", ("system.pdb", PDB, "chemical/x-pdb"))])
    assert ok.status_code == 200, ok.text
    assert c.post("/api/v1/runs", data={}).status_code == 422
