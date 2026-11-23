"""Worker restarts re-queue runs under the same run id (2026-11-23).

A worker shutting down (SIGTERM: redeploy, scale-down, eviction) stops its
pipelines and puts their runs back in the queue at once, without counting an
attempt; a worker killed outright is found by the reaper (stale heartbeat)
and retried at once as an attempt. Stale messages of a re-queued run end
skipped_superseded (pipeline.dispatch).
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest
from celery.exceptions import Reject
from celery.signals import worker_shutting_down

from src_new import cancellation, retries
from src_new.api import run_reaper
from src_new.api import tasks as wtasks


class FakeLock:
    """The per-run execution lock (tasks._run_lock_client)."""

    def __init__(self):
        self.store: dict[str, str] = {}

    def set(self, key, value, nx=False, ex=None, **_kw):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    def get(self, key):
        return self.store.get(key)

    def eval(self, script, numkeys, key, token, ttl=0):
        if self.store.get(key) != token:
            return 0
        if script is wtasks._RELEASE_LOCK_LUA:
            del self.store[key]
        return 1


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A runs dir, no broker Redis, a fake lock, a recording enqueue."""
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.setattr(cancellation, "CACHE_S", 0.05)
    lock = FakeLock()
    monkeypatch.setattr(wtasks, "_run_lock_client", lambda: lock)
    sent = []

    def enqueue(*a):
        # the new message must find the run lock free (else skipped_running)
        sent.append({"args": a, "lock_free": not lock.store})
    monkeypatch.setattr(retries, "_enqueue", enqueue)
    wtasks._WORKER_STOPPING.clear()
    yield type("Env", (), {"runs": tmp_path, "lock": lock, "sent": sent})
    wtasks._WORKER_STOPPING.clear()


def _run(runs: Path, run_id: str = "r1", status: str = "queued", **pipeline) -> Path:
    run_dir = runs / run_id
    (run_dir / "input").mkdir(parents=True)
    (run_dir / "results.json").write_text(json.dumps({
        "created_at": "2026-11-23T10:00:00+00:00",
        "pipeline": {"name": "BAT3", "status": status, "run_id": run_id, "queue": "repository",
                     "owner_token_sha256": "abc", "retention": {"policy": "default"}, **pipeline}}))
    return run_dir


def _kwargs(run_dir: Path, **extra) -> dict:
    return dict(run_id=run_dir.name, input_dir=str(run_dir / "input"),
                results_path=str(run_dir / "results.json"), config_path=None, **extra)


def _pipeline(run_dir: Path) -> dict:
    return json.loads((run_dir / "results.json").read_text())["pipeline"]


def _busy_child(run_id, input_dir, results_path, config_path, conn):
    """A pipeline in the middle of its work: running, with a BLAST-like
    grandchild, and deaf to everything but signals."""
    import subprocess as sp
    from src_new.results.results_manager import ResultsManager
    ResultsManager(results_path).start_run(step_definitions=[{"step_id": "identify_molecules"}])
    Path(results_path).with_name("results.log").write_text("interrupted execution\n")
    p = sp.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    Path(results_path).with_name("grandchild.pid").write_text(str(p.pid))
    time.sleep(120)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    try:  # a zombie (exited, not reaped yet) counts as gone
        with open(f"/proc/{pid}/stat") as f:
            return f.read().split(")")[-1].split()[0] != "Z"
    except OSError:
        return True


def _start_busy_task(run_dir: Path, monkeypatch, **kwargs) -> tuple[threading.Thread, dict]:
    monkeypatch.setattr(wtasks, "_run_pipeline_child", _busy_child)
    out: dict = {}

    def go():
        res = wtasks.run_pipeline_task.apply(kwargs=_kwargs(run_dir, **kwargs))
        out["state"], out["result"] = res.state, res.result
    t = threading.Thread(target=go)
    t.start()
    for _ in range(200):
        if (run_dir / "grandchild.pid").exists():
            break
        time.sleep(0.05)
    assert (run_dir / "grandchild.pid").exists(), out
    return t, out


def _shut_down() -> None:
    """What Celery's warm-shutdown handler sends in the worker's main process."""
    worker_shutting_down.send(sender="celery@test", sig="SIGTERM", how="Warm", exitcode=0)


# -- graceful shutdown -----------------------------------------------------------

def test_shutdown_requeues_a_running_run_under_the_same_id(env, monkeypatch):
    retries.set_policy("repository", {"enabled": True, "max_attempts": 3})
    run_dir = _run(env.runs, dispatch="d0")
    t, out = _start_busy_task(run_dir, monkeypatch, dispatch="d0")
    assert _pipeline(run_dir)["status"] == "running"
    grandchild = int((run_dir / "grandchild.pid").read_text())

    t0 = time.monotonic()
    _shut_down()
    t.join(30)
    assert time.monotonic() - t0 < 8, "must finish well within the grace period"
    # the message is acked: the task returned normally
    assert out["state"] == "SUCCESS", out
    assert out["result"]["status"] == "requeued_worker_restart"
    # the pipeline and its BLAST-like child are gone
    for _ in range(50):
        if not _alive(grandchild):
            break
        time.sleep(0.1)
    assert not _alive(grandchild)

    p = _pipeline(run_dir)
    assert p["status"] == "queued" and p["run_id"] == "r1"
    assert p["owner_token_sha256"] == "abc" and p["queue"] == "repository"
    assert p["dispatch"] not in (None, "d0") and out["result"]["dispatch"] == p["dispatch"]
    # not an attempt: the retry policy's count is untouched
    assert "attempts" not in p
    assert retries.plan({"pipeline": p, "warnings": []}, "worker_lost")["attempt"] == 1
    assert [(r["restart"], r["reason"]) for r in p["restarts"]] == [(1, "worker_restart")]
    assert p["restarts"][0]["started_at"] and p["restarts"][0]["results"] == "restarts/1/results.json"
    events = json.loads((run_dir / "results.json").read_text())["events"]
    assert [e["kind"] for e in events] == ["worker_restart"]
    assert "same run id" in events[0]["message"]
    # what the interrupted execution wrote is kept aside
    assert json.loads((run_dir / "restarts/1/results.json").read_text())["pipeline"]["status"] == "running"
    assert (run_dir / "restarts/1/results.log").read_text() == "interrupted execution\n"
    assert (run_dir / "input").is_dir()
    # re-sent at once to the run's queue, with the new dispatch, lock released first
    assert len(env.sent) == 1
    args = env.sent[0]["args"]
    assert args[0] == "r1" and args[1] == str(run_dir / "input")
    assert args[4] == "validation.repo.celery" and args[5] == p["dispatch"]
    assert env.sent[0]["lock_free"] and not env.lock.store

    # the new message runs the run; the old one, redelivered, does not
    monkeypatch.setattr(wtasks, "_spawn_pipeline_child", lambda *a, **k: {"status": "completed"})
    wtasks._WORKER_STOPPING.clear()  # the next worker
    stale = wtasks.run_pipeline_task.apply(kwargs=_kwargs(run_dir, dispatch="d0")).get()
    assert stale["status"] == "skipped_superseded"
    fresh = wtasks.run_pipeline_task.apply(kwargs=_kwargs(run_dir, dispatch=p["dispatch"])).get()
    assert fresh["status"] == "completed"


def test_shutdown_does_not_requeue_a_cancelled_run(env, monkeypatch):
    run_dir = _run(env.runs)
    t, out = _start_busy_task(run_dir, monkeypatch)
    monkeypatch.setattr(wtasks, "_CANCEL_GRACE_S", 60.0)  # the shutdown cuts the grace short
    cancellation.request_cancel("r1", run_dir)
    time.sleep(0.5)  # the task has seen the cancel
    t0 = time.monotonic()
    _shut_down()
    t.join(30)
    assert time.monotonic() - t0 < 8
    assert out["result"] == {"status": "cancelled", "run_id": "r1"}
    assert _pipeline(run_dir)["status"] == "cancelled"
    assert not env.sent and not (run_dir / "restarts").exists()


def test_a_cancel_arriving_with_the_shutdown_wins(env, monkeypatch):
    run_dir = _run(env.runs)
    t, out = _start_busy_task(run_dir, monkeypatch)
    (run_dir / cancellation.MARKER).write_text("1")  # not seen by the task yet
    _shut_down()
    t.join(30)
    assert out["result"]["status"] == "cancelled"
    assert _pipeline(run_dir)["status"] == "cancelled" and not env.sent


def test_a_task_not_started_yet_does_not_start(env, monkeypatch):
    run_dir = _run(env.runs)
    forks = []
    monkeypatch.setattr(wtasks, "_spawn_pipeline_child", lambda *a, **k: forks.append(1))
    _shut_down()
    with pytest.raises(Reject) as exc:
        wtasks.run_pipeline_task.run(**_kwargs(run_dir))
    assert exc.value.requeue is True  # handed back to the broker as it is
    assert not forks and not env.lock.store and not env.sent
    assert not (run_dir / "heartbeat").exists()
    assert _pipeline(run_dir)["status"] == "queued"


def test_a_shutdown_that_cannot_send_hands_the_message_back(env, monkeypatch):
    run_dir = _run(env.runs, dispatch="d0")
    t, out = _start_busy_task(run_dir, monkeypatch, dispatch="d0")

    def broker_down(*a):
        raise ConnectionError("broker down")
    monkeypatch.setattr(retries, "_enqueue", broker_down)
    _shut_down()
    t.join(30)
    # rejected with requeue: the broker puts this message back
    assert out["state"] == "REJECTED", out
    assert isinstance(out["result"], Reject) and out["result"].requeue
    p = _pipeline(run_dir)
    # queued, and the message handed back is still the run's message
    assert p["status"] == "queued" and p["dispatch"] == "d0"
    assert not env.lock.store


def test_a_run_that_finished_as_the_worker_stopped_stays_finished(env, monkeypatch):
    run_dir = _run(env.runs, status="success")
    assert retries.restart(run_dir) is None
    run_dir = _run(env.runs, "r2", status="retry_scheduled")
    assert retries.restart(run_dir) is None
    run_dir = _run(env.runs, "r3", status="queued")  # stopped before the pipeline started
    assert retries.restart(run_dir)
    p = _pipeline(run_dir)
    assert p["status"] == "queued" and "results" not in p["restarts"][0]
    assert not (run_dir / "restarts").exists()


# -- duplicates -------------------------------------------------------------------

def test_stale_messages_never_run_a_requeued_run(env, monkeypatch):
    forks = []
    monkeypatch.setattr(wtasks, "_spawn_pipeline_child",
                        lambda *a, **k: forks.append(1) or {"status": "completed"})
    # re-queued (d1) and running elsewhere: the original message is superseded
    run_dir = _run(env.runs, status="running", dispatch="d1")
    for stale in (None, "d0"):
        res = wtasks.run_pipeline_task.apply(kwargs=_kwargs(run_dir, dispatch=stale)).get()
        assert res["status"] == "skipped_superseded"
    # a duplicate of the current message meets the execution lock
    env.lock.store[wtasks._LOCK_PREFIX + "r1"] = "other-worker"
    res = wtasks.run_pipeline_task.apply(kwargs=_kwargs(run_dir, dispatch="d1")).get()
    assert res["status"] == "skipped_running"
    # finished: whatever message arrives, nothing runs
    run_dir = _run(env.runs, "r2", status="success", dispatch="d1")
    for d in (None, "d1"):
        res = wtasks.run_pipeline_task.apply(kwargs=_kwargs(run_dir, dispatch=d)).get()
        assert res["status"] == "skipped_terminal"
    assert not forks
    assert not (env.runs / "r1" / "heartbeat").exists()
    # a run never re-queued (no dispatch recorded) runs from its first message
    run_dir = _run(env.runs, "r3")
    assert wtasks.run_pipeline_task.apply(kwargs=_kwargs(run_dir)).get()["status"] == "completed"
    assert forks == [1]


def test_the_task_touches_the_heartbeat_when_it_starts(env, monkeypatch):
    run_dir = _run(env.runs, status="queued")
    hb = run_dir / "heartbeat"
    hb.touch()
    old = time.time() - 3600  # left by the interrupted execution
    os.utime(hb, (old, old))
    seen = {}
    monkeypatch.setattr(wtasks, "_spawn_pipeline_child",
                        lambda *a, **k: seen.update(age=time.time() - hb.stat().st_mtime)
                        or {"status": "completed"})
    wtasks.run_pipeline_task.apply(kwargs=_kwargs(run_dir)).get()
    assert seen["age"] < 60


# -- hard kills: the reaper ------------------------------------------------------

def _stale(run_dir: Path, age: float = 600) -> None:
    hb = run_dir / "heartbeat"
    hb.touch()
    os.utime(hb, (time.time() - age, time.time() - age))


@pytest.mark.parametrize("fast", [True, False])
def test_reaper_retries_a_lost_worker_at_once_and_counts_it(env, fast):
    retries.set_policy("repository", {"enabled": True, "max_attempts": 3, "delay_minutes": 60})
    run_dir = _run(env.runs, status="running", started_at="2026-11-23T10:00:05+00:00")

    def reap():
        if fast:
            return run_reaper.sweep_lost_workers(env.runs, {})
        return run_reaper.sweep(env.runs, set(), {})

    for attempt in (1, 2):
        _stale(run_dir)
        out = reap()
        assert out["zombies_failed"] == ["r1"]
        p = _pipeline(run_dir)
        # queued again in the same sweep despite the 60 min delay, as an attempt
        assert p["status"] == "queued" and len(p["attempts"]) == attempt
        assert p["attempts"][-1]["reason"] == "worker_lost"
        assert env.sent[-1]["args"][5] == p["dispatch"]
        data = json.loads((run_dir / "results.json").read_text())
        data["pipeline"]["status"] = "running"  # the next attempt starts ...
        (run_dir / "results.json").write_text(json.dumps(data))
    # ... and loses its worker too: the 3rd attempt is the last, it fails
    _stale(run_dir)
    assert reap()["zombies_failed"] == ["r1"]
    assert _pipeline(run_dir)["status"] == "failed"
    assert len(env.sent) == 2


def test_reaper_leaves_fresh_heartbeats_and_queued_runs_alone(env):
    retries.set_policy("repository", {"enabled": True})
    running = _run(env.runs, "r1", status="running")
    _stale(running, age=run_reaper.HEARTBEAT_STALE_S - 30)
    queued = _run(env.runs, "r2", status="queued")
    _stale(queued, age=99999)
    assert run_reaper.HEARTBEAT_STALE_S <= 180
    for out in (run_reaper.sweep_lost_workers(env.runs, {}), run_reaper.sweep(env.runs, set(), {})):
        assert out["zombies_failed"] == []
    assert _pipeline(running)["status"] == "running" and _pipeline(queued)["status"] == "queued"


def test_web_lane_without_retries_still_fails_a_lost_worker(env):
    run_dir = _run(env.runs, status="running", queue="web")
    _stale(run_dir)
    assert run_reaper.sweep_lost_workers(env.runs, {})["zombies_failed"] == ["r1"]
    assert _pipeline(run_dir)["status"] == "failed" and not env.sent


def test_the_leader_keeps_its_lock():
    class R:
        def __init__(self):
            self.store = {}

        def set(self, key, value, nx=False, px=None):
            if nx and key in self.store:
                return None
            self.store[key] = value.encode()
            return True

        def get(self, key):
            return self.store.get(key)

        def pexpire(self, key, px):
            return True
    r = R()
    assert run_reaper._lead(r, "api-1:7", 1000)
    assert run_reaper._lead(r, "api-1:7", 1000)  # its own key: still the leader
    assert not run_reaper._lead(r, "api-1:8", 1000)


# -- surfaces ---------------------------------------------------------------------

def test_status_api_shows_the_restart(env):
    from fastapi.testclient import TestClient
    from src_new.api.main import app
    run_dir = _run(env.runs, status="running")
    assert retries.restart(run_dir)
    status = TestClient(app).get("/api/v1/runs/r1/status").json()
    assert status["pipeline"]["status"] == "queued"
    assert [(r["restart"], r["reason"]) for r in status["restarts"]] == [(1, "worker_restart")]
    assert status["attempts"] == [] and status["retry"] is None
    assert [e["kind"] for e in status["events"]] == ["worker_restart"]
    assert "same run id" in status["events"][0]["message"]
