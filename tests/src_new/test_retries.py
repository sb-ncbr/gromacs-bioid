"""Incomplete runs, queues and automatic retries (2026-11-18)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src_new import completeness, retries
from src_new.api import queue_tokens

W500 = {"code": "identifier_resolver_failed", "step_id": "identify_molecules",
        "message": "chembl_struct@sim (smiles): [Identifier] CHEMBL searching failed: HTTP Error 500: Internal",
        "details": {"segment": "LIG", "service": "chembl_struct@sim"}}
W_NA = {"code": "identifier_resolver_failed",
        "message": "mmcif_struct@sim (mmcif): no_polymer_payload",
        "details": {"segment": "LIG", "service": "mmcif_struct@sim"}}
W_BLAST = {"code": "identifier_resolver_failed",
           "message": "blast_nr_protein (fasta_map_protein): BLAST timed out after 43200s.",
           "details": {"segment": "P", "service": "blast_nr_protein"}}
W_BUDGET = {"code": "stage_time_budget", "step_id": "verify_results", "message": "verify_results hit its time limit"}


def test_gaps_count_only_retryable_failures():
    data = {"warnings": [W500, dict(W500, details={"segment": "LIG2", "service": "chembl_struct@sim"}),
                         W_NA, W_BLAST, W_BUDGET, {"code": "pbc_unwrap_applied", "message": "x"}]}
    gaps = completeness.gaps(data)
    assert [(g["service"], g["reason"], g["count"]) for g in gaps] == [
        ("chembl_struct@sim", "server_error", 2), ("time limit (verify_results)", "budget", 1)]
    assert gaps[0]["segments"] == ["LIG", "LIG2"]
    assert not completeness.is_incomplete({"warnings": [W_NA, W_BLAST]})


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    return tmp_path


def _payload(lane="repository", attempts=0, warnings=(W500,)):
    return {"created_at": "2026-11-18T10:00:00+00:00",
            "pipeline": {"name": "BAT3", "run_id": "r1", "status": "running", "queue": lane,
                         "owner_token_sha256": "abc", "retention": {"policy": "default"},
                         "started_at": "2026-11-18T10:00:05+00:00",
                         "attempts": [{"attempt": i + 1} for i in range(attempts)]},
            "warnings": list(warnings), "data": {"identifiers": {"x": 1}}}


def test_policy_off_by_default_and_validated(runs_dir):
    assert retries.plan(_payload(), "incomplete") is None
    with pytest.raises(ValueError):
        retries.set_policy("repository", {"max_attempts": 0})
    with pytest.raises(ValueError):
        retries.set_policy("repository", {"bogus": 1})
    with pytest.raises(ValueError):
        retries.set_policy("nope", {"enabled": True})
    assert retries.set_policy("repository", {"enabled": True, "max_attempts": 3, "delay_minutes": 30})["enabled"]
    assert retries.policy("web")["enabled"] is False


def test_plan_respects_lane_reason_and_attempts(runs_dir):
    retries.set_policy("repository", {"enabled": True, "max_attempts": 3, "delay_minutes": 30})
    plan = retries.plan(_payload(), "incomplete", now=1000.0)
    assert plan["attempt"] == 1 and plan["at"] == 1000.0 + 1800
    assert plan["gaps"] == [{"service": "chembl_struct@sim", "reason": "server_error", "count": 1}]
    assert retries.plan(_payload(lane="web"), "incomplete") is None           # web: off
    assert retries.plan(_payload(warnings=[W_BLAST]), "incomplete") is None   # nothing retryable
    assert retries.plan(_payload(attempts=2), "incomplete") is None           # 3rd attempt is the last
    assert retries.plan(_payload(warnings=[]), "worker_lost")["reason"] == "worker_lost"
    retries.set_policy("repository", {"worker_lost": False})
    assert retries.plan(_payload(warnings=[]), "worker_lost") is None


def test_schedule_then_requeue_keeps_the_run_id(runs_dir):
    retries.set_policy("repository", {"enabled": True, "max_attempts": 3, "delay_minutes": 1})
    run = runs_dir / "r1"
    (run / "input").mkdir(parents=True)
    (run / "config.ini").write_text("[identifiers]\n")
    (run / "results.log").write_text("attempt 1 log\n")
    payload = _payload()
    plan = retries.plan(payload, "incomplete", now=0.0)
    retries.schedule(payload, plan)
    (run / "results.json").write_text(json.dumps(payload))
    assert retries.client_status(payload["pipeline"]) == "queued"
    assert retries.due(payload["pipeline"], now=61.0) and not retries.due(payload["pipeline"], now=10.0)

    sent = []
    assert retries.requeue(run, enqueue=lambda *a: sent.append(a))
    fresh = json.loads((run / "results.json").read_text())
    p = fresh["pipeline"]
    # 2026-11-23: the task carries the run's new dispatch
    assert sent == [("r1", str(run / "input"), str(run / "results.json"), str(run / "config.ini"),
                     "validation.repo.celery", p["dispatch"])]
    assert p["status"] == "queued" and p["run_id"] == "r1" and p["owner_token_sha256"] == "abc"
    assert p["queue"] == "repository" and "retry" not in p and "started_at" not in p
    assert [a["attempt"] for a in p["attempts"]] == [1]
    assert "warnings" not in fresh and "data" not in fresh
    archived = json.loads((run / "attempts/1/results.json").read_text())
    assert archived["warnings"] == [W500]
    assert (run / "attempts/1/results.log").read_text() == "attempt 1 log\n"
    assert not (run / "results.log").exists()
    # the next attempt is the 2nd of 3
    assert retries.plan(dict(fresh, warnings=[W500]), "incomplete")["attempt"] == 2


def test_requeue_failure_puts_the_run_back(runs_dir):
    retries.set_policy("repository", {"enabled": True})
    run = runs_dir / "r1"
    (run / "input").mkdir(parents=True)
    payload = _payload()
    retries.schedule(payload, retries.plan(payload, "incomplete", now=0.0))
    (run / "results.json").write_text(json.dumps(payload))

    def broken(*a):
        raise ConnectionError("broker down")

    with pytest.raises(ConnectionError):
        retries.requeue(run, enqueue=broken)
    back = json.loads((run / "results.json").read_text())["pipeline"]
    assert back["status"] == "retry_scheduled" and back["retry"]["at"] > 0


def test_reaper_requeues_due_runs_and_retries_lost_workers(runs_dir, monkeypatch):
    from src_new.api import run_reaper
    retries.set_policy("repository", {"enabled": True, "delay_minutes": 1})
    run = runs_dir / "r1"
    (run / "input").mkdir(parents=True)
    payload = _payload(warnings=[])
    payload["pipeline"]["status"] = "running"
    (run / "results.json").write_text(json.dumps(payload))
    assert run_reaper.mark_worker_lost(run / "results.json", sweep_count=1, cause="test")
    p = json.loads((run / "results.json").read_text())["pipeline"]
    assert p["status"] == "retry_scheduled" and p["retry"]["reason"] == "worker_lost"

    sent = []
    monkeypatch.setattr(retries, "_enqueue", lambda *a: sent.append(a[0]))
    p["retry"]["at"] = 0
    data = json.loads((run / "results.json").read_text())
    data["pipeline"] = p
    (run / "results.json").write_text(json.dumps(data))
    summary = {"errors": 0}
    run_reaper._requeue_if_due(run, summary)
    assert sent == ["r1"] and summary["requeued"] == ["r1"]


def test_web_lane_lost_worker_still_fails(runs_dir):
    from src_new.api import run_reaper
    run = runs_dir / "r1"
    run.mkdir()
    payload = _payload(lane="web", warnings=[])
    (run / "results.json").write_text(json.dumps(payload))
    run_reaper.mark_worker_lost(run / "results.json", sweep_count=1, cause="test")
    assert json.loads((run / "results.json").read_text())["pipeline"]["status"] == "failed"


def test_queue_tokens(runs_dir):
    assert not queue_tokens.check(runs_dir, "repository", "x")
    token = queue_tokens.create(runs_dir, "repository")
    assert queue_tokens.check(runs_dir, "repository", token)
    assert not queue_tokens.check(runs_dir, "repository", token + "x")
    assert token not in (runs_dir / queue_tokens.FILE).read_text()
    assert queue_tokens.info(runs_dir, "repository")["hint"] == token[-4:]
    assert queue_tokens.revoke(runs_dir, "repository")
    assert not queue_tokens.check(runs_dir, "repository", token)


# -- API -----------------------------------------------------------------------

PDB = b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n"


@pytest.fixture
def client(runs_dir, monkeypatch):
    sent = []
    monkeypatch.setattr("src_new.api.routes.runs.run_pipeline_task.apply_async",
                        lambda *a, **k: sent.append(k))
    from src_new.api.main import app
    c = TestClient(app)
    c.sent = sent
    return c


def _submit(client, headers=None, **form):
    return client.post("/api/v1/runs", files=[("files", ("system.pdb", PDB, "chemical/x-pdb"))],
                       data=form, headers=headers or {})


def test_repository_queue_needs_a_token(client, runs_dir):
    assert _submit(client, queue="repository").status_code == 403
    assert _submit(client, queue="elsewhere").status_code == 422
    assert not any(p.is_dir() and not p.name.startswith("_") for p in runs_dir.iterdir())
    token = queue_tokens.create(runs_dir, "repository")
    r = _submit(client, headers={"X-Queue-Token": token}, queue="repository")
    assert r.status_code == 200, r.text
    run_id = r.json()["run_id"]
    assert client.sent[-1]["queue"] == "validation.repo.celery"
    status = client.get(f"/api/v1/runs/{run_id}/status").json()
    assert status["queue"] == "repository" and status["pipeline"]["status"] == "queued"
    web = _submit(client)
    assert web.status_code == 200
    assert client.get(f"/api/v1/runs/{web.json()['run_id']}").json()["queue"] == "web"


def test_waiting_retry_reads_as_queued(client, runs_dir):
    run = runs_dir / "r1"
    (run / "input").mkdir(parents=True)
    payload = _payload()
    payload["pipeline"].update(status="retry_scheduled",
                               retry={"attempt": 1, "max_attempts": 3, "reason": "incomplete", "at": 5.0})
    (run / "results.json").write_text(json.dumps(payload))
    status = client.get("/api/v1/runs/r1/status").json()
    assert status["pipeline"]["status"] == "queued"
    assert status["retry"]["attempt"] == 1
    assert status["incomplete"][0]["service"] == "chembl_struct@sim"
    summary = client.get("/api/v1/runs/r1").json()
    assert summary["status"] == "queued" and summary["incomplete_count"] == 1
    assert client.get("/api/v1/runs/r1/queue").json()["state"] == "queued"


def test_owner_rerun_supersedes_and_drops_old_ncbi_defaults(client, runs_dir):
    from src_new.config.loader import RunConfig
    r = _submit(client)
    old_id, owner = r.json()["run_id"], r.json()["owner_token"]
    old = runs_dir / old_id
    cfg = RunConfig.from_default_ini()
    cfg.identifiers.blast_nr_protein = True  # what an older run's config.ini carries
    cfg.to_ini_path(old / "config.ini")
    data = json.loads((old / "results.json").read_text())
    data["pipeline"]["status"] = "success"
    (old / "results.json").write_text(json.dumps(data))

    stranger = client.post(f"/api/v1/runs/{old_id}/rerun")
    assert stranger.status_code == 200
    assert "superseded_by" not in json.loads((old / "results.json").read_text())["pipeline"]

    mine = client.post(f"/api/v1/runs/{old_id}/rerun", headers={"X-Owner-Token": owner})
    new_id = mine.json()["run_id"]
    assert json.loads((old / "results.json").read_text())["pipeline"]["superseded_by"] == new_id
    new_status = client.get(f"/api/v1/runs/{new_id}/status").json()
    assert new_status["rerun_of"] == old_id
    assert RunConfig.from_ini_path(runs_dir / new_id / "config.ini").identifiers.blast_nr_protein is False


@pytest.mark.parametrize("lane, expected", [("repository", "retry_scheduled"), ("web", "success")])
def test_executor_schedules_a_retry_for_an_incomplete_run(runs_dir, lane, expected):
    from src_new.executor.executor import PipelineExecutor
    from src_new.executor.task import PipelineStep, StepResult
    from src_new.results.results_manager import ResultsManager
    retries.set_policy("repository", {"enabled": True})
    results_path = runs_dir / "r1" / "results.json"
    results_path.parent.mkdir()
    results_path.write_text(json.dumps({"pipeline": {"name": "BAT3", "status": "queued", "queue": lane}}))
    manager = ResultsManager(results_path)

    def lookups(context):
        context.add_warning(W500["code"], W500["message"], details=W500["details"])
        return StepResult(summary={})

    PipelineExecutor(steps=[PipelineStep(step_id="identify", name="Identify", handler=lookups)],
                     results_manager=manager).run()
    pipeline = json.loads(results_path.read_text())["pipeline"]
    assert pipeline["status"] == expected
    assert ("retry" in pipeline) == (lane == "repository")


def test_only_the_owner_reruns_on_the_repository_queue(client, runs_dir):
    token = queue_tokens.create(runs_dir, "repository")
    r = _submit(client, headers={"X-Queue-Token": token}, queue="repository")
    run_id, owner = r.json()["run_id"], r.json()["owner_token"]
    data = json.loads((runs_dir / run_id / "results.json").read_text())
    data["pipeline"]["status"] = "success"
    (runs_dir / run_id / "results.json").write_text(json.dumps(data))
    stranger = client.post(f"/api/v1/runs/{run_id}/rerun").json()["run_id"]
    assert client.get(f"/api/v1/runs/{stranger}").json()["queue"] == "web"
    assert client.sent[-1].get("queue") != "validation.repo.celery"
    mine = client.post(f"/api/v1/runs/{run_id}/rerun", headers={"X-Owner-Token": owner}).json()["run_id"]
    assert client.get(f"/api/v1/runs/{mine}").json()["queue"] == "repository"
    assert client.sent[-1]["queue"] == "validation.repo.celery"


def test_cancel_a_waiting_retry_keeps_results(client, runs_dir):
    r = _submit(client)
    run_id, owner = r.json()["run_id"], r.json()["owner_token"]
    path = runs_dir / run_id / "results.json"
    data = json.loads(path.read_text())
    data["pipeline"].update(status="retry_scheduled", retry={"attempt": 1, "max_attempts": 3,
                                                             "reason": "incomplete", "at": 9e9})
    path.write_text(json.dumps(data))
    assert client.post(f"/api/v1/runs/{run_id}/cancel").status_code == 403
    res = client.post(f"/api/v1/runs/{run_id}/cancel", headers={"X-Owner-Token": owner})
    assert res.json()["status"] == "success"
    p = json.loads(path.read_text())["pipeline"]
    assert p["status"] == "success" and p["retry"]["cancelled"] is True


# 2026-11-21 (mdval audit item 7): partial runs and their retries

W_ID_BUDGET = {"code": "stage_time_budget", "step_id": "identify_molecules",
               "message": "identify_molecules exceeded its time budget; proceeding with partial identifications"}


def test_completeness_tells_partial_from_incomplete():
    ok = {"pipeline": {"status": "success"}, "warnings": [W_NA, W_BLAST]}
    assert completeness.state(ok) == {"completeness": "complete", "partial_stages": []}
    remote = {"pipeline": {"status": "success"}, "warnings": [W500]}
    assert completeness.state(remote) == {"completeness": "incomplete", "partial_stages": []}
    cut = {"pipeline": {"status": "success"}, "warnings": [W500, W_BUDGET, W_ID_BUDGET],
           "tasks": {"generate_signatures": {"summary": {"partial": False}},
                     "identify_molecules": {"summary": {"partial": True}},
                     "verify_results": {"summary": {}}}}
    assert completeness.state(cut) == {"completeness": "partial",
                                       "partial_stages": ["identify_molecules", "verify_results"]}
    # a summary flag alone counts; unfinished runs have no verdict yet
    flag = {"pipeline": {"status": "running"}, "tasks": {"generate_signatures": {"summary": {"partial": True}}}}
    assert completeness.state(flag) == {"completeness": None, "partial_stages": ["generate_signatures"]}
    assert completeness.state({"pipeline": {"status": "failed"}})["completeness"] is None


def test_time_limits_alone_are_not_retried(runs_dir):
    retries.set_policy("repository", {"enabled": True, "max_attempts": 3})
    assert retries.plan(_payload(warnings=[W_ID_BUDGET]), "incomplete") is None
    assert retries.plan(_payload(warnings=[W_BUDGET, W_ID_BUDGET]), "incomplete") is None
    plan = retries.plan(_payload(warnings=[W500, W_ID_BUDGET]), "incomplete")
    assert plan["gaps"] == [{"service": "chembl_struct@sim", "reason": "server_error", "count": 1}]


def test_a_partial_run_ends_success_with_completeness(runs_dir):
    from src_new.executor.executor import PipelineExecutor
    from src_new.executor.task import PipelineStep, StepResult
    from src_new.results.results_manager import ResultsManager
    retries.set_policy("repository", {"enabled": True})
    results_path = runs_dir / "r1" / "results.json"
    results_path.parent.mkdir()
    results_path.write_text(json.dumps({"pipeline": {"name": "BAT3", "status": "queued", "queue": "repository"}}))

    def identify(context):
        context.add_warning(W_ID_BUDGET["code"], W_ID_BUDGET["message"])
        return StepResult(summary={"identified": True, "partial": True})

    PipelineExecutor(steps=[PipelineStep(step_id="identify_molecules", name="Identify", handler=identify)],
                     results_manager=ResultsManager(results_path)).run()
    pipeline = json.loads(results_path.read_text())["pipeline"]
    assert pipeline["status"] == "success" and "retry" not in pipeline  # not retried: same budget
    assert pipeline["completeness"] == "partial"
    assert pipeline["partial_stages"] == ["identify_molecules"]


def test_api_reports_completeness_next_to_status(client, runs_dir):
    from src_new.api.security import ip_hash
    run = runs_dir / "r1"
    run.mkdir()
    payload = _payload(warnings=[W500, W_ID_BUDGET])
    payload["pipeline"].update(status="success", creator_ip_hash=ip_hash("testclient"))
    payload["tasks"] = {"identify_molecules": {"name": "Identify", "status": "warning",
                                               "summary": {"partial": True}}}
    (run / "results.json").write_text(json.dumps(payload))
    status = client.get("/api/v1/runs/r1/status").json()
    assert status["pipeline"]["status"] == "success"
    assert status["pipeline"]["completeness"] == "partial"
    assert status["pipeline"]["partial_stages"] == ["identify_molecules"]
    summary = client.get("/api/v1/runs/r1").json()
    assert (summary["status"], summary["completeness"], summary["partial_stages"]) == (
        "success", "partial", ["identify_molecules"])
    listed = client.get("/api/v1/runs").json()["runs"]
    assert [(r["run_id"], r["completeness"], r["partial_stages"]) for r in listed] == [
        ("r1", "partial", ["identify_molecules"])]
