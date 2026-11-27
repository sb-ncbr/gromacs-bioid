"""campaign_rerun.py end to end against the real API app (Celery stubbed):
entries with the reference arm are submitted to the repository queue with
their input in place, followed to a terminal status and collected as
results-<arm>.json; a second pass resumes (409) instead of resubmitting."""
import importlib.util
import json
import os
import sys

import pytest
from fastapi.testclient import TestClient

SCRIPTS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
spec = importlib.util.spec_from_file_location("campaign_rerun", os.path.join(SCRIPTS, "campaign_rerun.py"))
cr = importlib.util.module_from_spec(spec)
sys.modules["campaign_rerun"] = cr
spec.loader.exec_module(cr)

PDB = b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n"


@pytest.fixture
def world(tmp_path, monkeypatch):
    runs, data = tmp_path / "runs", tmp_path / "validation"
    runs.mkdir()
    for eid in ("7", "12", "30"):
        (data / eid / "input").mkdir(parents=True)
        (data / eid / "input" / "structure.pdb").write_bytes(PDB)
        (data / eid / "results-g1.json").write_text("{}")
    (data / "99" / "input").mkdir(parents=True)  # no reference arm: not part of the campaign
    (data / "30" / "input" / "structure.pdb").unlink()  # empty input -> rejected
    monkeypatch.setenv("BAT3_RUNS_DIR", str(runs))
    monkeypatch.setenv("BAT3_CAMPAIGN_INPUT_ROOT", str(data))
    sent = []
    monkeypatch.setattr("src_new.api.routes.runs.run_pipeline_task.apply_async",
                        lambda *a, **k: sent.append(k["kwargs"]["run_id"]))
    from src_new.api import queue_tokens
    from src_new.api.main import app
    token = queue_tokens.create(runs, "repository")
    monkeypatch.setenv("BIOID_QUEUE_TOKEN", token)
    return runs, data, sent, TestClient(app, base_url="http://api", client=("10.42.0.9", 1))


def _finish(runs, run_id, status="success"):
    p = runs / run_id / "results.json"
    d = json.loads(p.read_text())
    d["pipeline"]["status"] = status
    d["tasks"] = {"verify_results": {"status": "success"}}
    p.write_text(json.dumps(d))


def _runner(world, *extra):
    runs, data, _sent, client = world
    args = ["--arm", "g2", "--api", "http://api", "--data-root", str(data),
            "--runs-dir", str(runs), "--poll-s", "0", "--report-s", "0", *extra]
    r = cr.Runner(_parse(args))
    r.session = client  # the API app instead of the network
    return r


def _parse(argv):
    """The argparse namespace main() builds (Runner swapped out)."""
    captured = {}

    class _R:
        def __init__(self, a):
            captured["a"] = a

        def run(self):
            pass
    orig = cr.Runner
    cr.Runner = _R
    try:
        cr.main(argv)
    finally:
        cr.Runner = orig
    return captured["a"]


def test_rerun_submits_in_place_collects_and_resumes(world):
    runs, data, sent, _client = world
    r = _runner(world)
    assert cr.campaign_entries(data, "results-g1.json") == ["7", "12", "30"]
    # first pass: submit, then the runs "finish" and a second loop collects
    r.args.max_in_flight = 10
    for entry in ("7", "12", "30"):
        r.submit(entry)
    assert sorted(sent) == ["g2-12", "g2-7"]
    assert r.state.entries["30"]["status"] == "rejected"
    assert (runs / "g2-7" / "input" / "structure.pdb").is_symlink()
    _finish(runs, "g2-7")
    _finish(runs, "g2-12", "failed")
    r.run()
    assert r.state.entries["7"]["status"] == "done:success"
    assert r.state.entries["12"]["status"] == "done:failed"
    assert json.loads((data / "7" / "results-g2.json").read_text())["pipeline"]["status"] == "success"
    # resume: a fresh runner with a lost state still finds the existing runs (409)
    r.state.path.unlink()
    r2 = _runner(world)
    r2.run()
    assert len(sent) == 2  # nothing resubmitted
    assert r2.state.entries["7"]["status"] == "done:success"


def test_dry_run_lists_entries(world, capsys):
    r = _runner(world, "--dry-run", "--limit", "2")
    r.run()
    out = json.loads(capsys.readouterr().out)
    assert out == {"entries": 2, "first": ["7", "12"], "example_run_id": "g2-7"}
