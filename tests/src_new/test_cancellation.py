"""Cancelling a running run (2026-11-23, src_new/cancellation.py).

The threads pool cannot terminate a task: cancel and delete record the
request, and the pipeline (executor, resolvers, BLAST service calls, local
BLAST runs) and the Celery task stop on their own.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from src_new import cancellation, retries


class FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}
        self.ttl: dict[str, int] = {}

    def set(self, key, value, ex=None, **_kw):
        self.store[key] = value
        self.ttl[key] = ex
        return True

    def exists(self, key):
        return int(key in self.store)


class DownRedis:
    def set(self, *a, **k):
        import redis
        raise redis.ConnectionError("down")

    exists = set


@pytest.fixture
def fake_redis(monkeypatch):
    r = FakeRedis()
    monkeypatch.setattr(cancellation, "_client", lambda: r)
    return r


@pytest.fixture
def fast(monkeypatch):
    """Poll and cache in fractions of a second."""
    monkeypatch.setattr(cancellation, "POLL_S", 0.1)
    monkeypatch.setattr(cancellation, "CACHE_S", 0.05)


def _run(tmp_path: Path, run_id: str = "r1", status: str = "running", indent=None) -> Path:
    run_dir = tmp_path / run_id
    (run_dir / "input").mkdir(parents=True)
    (run_dir / "results.json").write_text(json.dumps(
        {"created_at": "x", "pipeline": {"name": "BAT3", "status": status, "run_id": run_id}},
        indent=indent))
    return run_dir


# -- request_cancel / is_cancelled ---------------------------------------------

def test_request_cancel_sets_the_key_and_the_marker(tmp_path, fake_redis):
    run_dir = _run(tmp_path)
    assert not cancellation.is_cancelled("r1", run_dir)
    assert cancellation.request_cancel("r1", run_dir)
    assert fake_redis.store.keys() == {"bioid:cancel:r1"}
    assert fake_redis.ttl["bioid:cancel:r1"] == 2 * 24 * 3600
    assert (run_dir / cancellation.MARKER).exists()
    cancellation.forget("r1")
    assert cancellation.is_cancelled("r1", run_dir)


def test_the_redis_key_alone_cancels(tmp_path, fake_redis):
    run_dir = _run(tmp_path)
    fake_redis.store["bioid:cancel:r1"] = "1"
    assert cancellation.is_cancelled("r1", run_dir)
    assert cancellation.is_cancelled("r1")  # no directory known


@pytest.mark.parametrize("indent", [None, 2])
def test_file_fallbacks_without_redis(tmp_path, monkeypatch, indent):
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    run_dir = _run(tmp_path, indent=indent)
    assert not cancellation.is_cancelled("r1", run_dir)
    # results.json says cancelled
    run_dir2 = _run(tmp_path, "r2", status="cancelled", indent=indent)
    assert cancellation.is_cancelled("r2", run_dir2)
    # results.json gone / directory gone
    (run_dir / "results.json").unlink()
    assert cancellation.is_cancelled("r1", run_dir, fresh=True)
    assert cancellation.is_cancelled("r3", tmp_path / "r3")
    # marker file
    run_dir4 = _run(tmp_path, "r4")
    (run_dir4 / cancellation.MARKER).write_text("1")
    assert cancellation.is_cancelled("r4", run_dir4)
    assert not cancellation.is_cancelled(None, run_dir4)


def test_redis_down_breaks_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(cancellation, "_client", lambda: DownRedis())
    run_dir = _run(tmp_path)
    assert not cancellation.is_cancelled("r1", run_dir)
    assert cancellation.request_cancel("r1", run_dir)  # the marker file still works
    cancellation.forget("r1")
    assert cancellation.is_cancelled("r1", run_dir)
    assert not cancellation.request_cancel("r9")  # nothing could be recorded, no raise


def test_answers_are_cached_briefly_and_true_for_good(tmp_path, fake_redis, monkeypatch):
    run_dir = _run(tmp_path)
    assert not cancellation.is_cancelled("r1", run_dir)
    fake_redis.store["bioid:cancel:r1"] = "1"
    assert not cancellation.is_cancelled("r1", run_dir)  # cached
    assert cancellation.is_cancelled("r1", run_dir, fresh=True)
    fake_redis.store.clear()
    assert cancellation.is_cancelled("r1", run_dir)  # sticky


def test_bind_check_and_thread_pool_propagation(tmp_path, fake_redis):
    from src_new.executor.parallel import run_with_thread_pool
    run_dir = _run(tmp_path)
    assert cancellation.current() is None
    cancellation.check()  # no run: nothing to do
    with cancellation.bind("r1", run_dir):
        seen = run_with_thread_pool(4, lambda _i: cancellation.current(), list(range(6)))
        assert seen == [("r1", run_dir)] * 6
        cancellation.request_cancel("r1")
        with pytest.raises(cancellation.RunCancelled):
            run_with_thread_pool(2, lambda _i: cancellation.check(), [1, 2, 3])
    assert cancellation.current() is None


def test_run_subprocess_kills_on_cancel(tmp_path, fake_redis, fast):
    run_dir = _run(tmp_path)
    cmd = [sys.executable, "-c", "import sys, time; sys.stdin.read(); time.sleep(60)"]
    with cancellation.bind("r1", run_dir):
        threading.Timer(0.3, cancellation.request_cancel, args=("r1",)).start()
        t0 = time.monotonic()
        with pytest.raises(cancellation.RunCancelled):
            cancellation.run_subprocess(cmd, input="MKV", text=True, timeout=60)
        assert time.monotonic() - t0 < 5
        # timeouts and normal runs behave like subprocess.run
        cancellation.forget("r1")
        fake_redis.store.clear()
        with pytest.raises(subprocess.TimeoutExpired):
            cancellation.run_subprocess(cmd, input="MKV", text=True, timeout=0.3)
        ok = cancellation.run_subprocess([sys.executable, "-c", "print(input()[::-1])"],
                                         input="abc\n", text=True, timeout=30)
        assert (ok.returncode, ok.stdout.strip()) == (0, "cba")


# -- BLAST service call ----------------------------------------------------------

@pytest.fixture
def slow_service():
    """/search answers only after 60 s; records when a client hangs up."""
    hung_up = threading.Event()

    def _hung_up(conn) -> bool:
        """The client closed its end (an EOF is readable)."""
        import select
        import socket
        try:
            if not select.select([conn], [], [], 0)[0]:
                return False
            return conn.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT) == b""
        except OSError:
            return True

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length") or 0))
            for _ in range(600):
                if _hung_up(self.connection):
                    hung_up.set()
                    return
                time.sleep(0.1)

        def log_message(self, *a):
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", hung_up
    httpd.shutdown()


def test_blast_service_search_stops_within_seconds_of_a_cancel(tmp_path, fake_redis, fast, slow_service):
    from src_new.identification.resolvers import blast_service_client as svc
    url, hung_up = slow_service
    run_dir = _run(tmp_path)
    with cancellation.bind("r1", run_dir):
        threading.Timer(0.5, cancellation.request_cancel, args=("r1",)).start()
        t0 = time.monotonic()
        with pytest.raises(cancellation.RunCancelled):
            svc.search(url, release="nr-1", query="MKV", task=None, max_target_seqs=5, timeout_s=3600)
        assert time.monotonic() - t0 < 5
    assert hung_up.wait(5), "the service did not see the client go away"


def test_blast_service_errors_keep_their_meaning(slow_service):
    from src_new.identification.resolvers import blast_service_client as svc
    with pytest.raises(svc.ServiceUnavailable):  # nothing listens
        svc.search("http://127.0.0.1:9", release="r", query="M", task=None, max_target_seqs=1, timeout_s=1)
    url, _ = slow_service
    with pytest.raises(svc.ServiceTimeout):  # no answer in time
        svc.search(url, release="r", query="M", task=None, max_target_seqs=1, timeout_s=-59.5)


# -- executor --------------------------------------------------------------------

def _steps(log, first=None):
    from src_new.executor.task import PipelineStep, StepResult

    def step(name, action=None):
        def handler(context):
            log.append(name)
            if action:
                action()
            return StepResult(summary={})
        return PipelineStep(step_id=name, name=name, handler=handler)
    return [step("load", first), step("identify"), step("export")]


def test_executor_stops_between_steps(tmp_path, fake_redis):
    from src_new.executor.executor import PipelineExecutor
    from src_new.results.results_manager import ResultsManager
    run_dir = _run(tmp_path)
    log: list[str] = []
    executor = PipelineExecutor(steps=_steps(log, lambda: cancellation.request_cancel("r1", run_dir)),
                                results_manager=ResultsManager(run_dir / "results.json"))
    with pytest.raises(cancellation.RunCancelled):
        executor.run(output_directory=run_dir, working_directory=run_dir / "input", run_id="r1")
    assert log == ["load"]
    payload = json.loads((run_dir / "results.json").read_text())
    assert payload["pipeline"]["status"] == "cancelled"
    assert {k: v["status"] for k, v in payload["tasks"].items()} == {
        "load": "success", "identify": "skipped", "export": "skipped"}
    assert any(e["kind"] == "run_cancelled" for e in payload["events"])


def test_executor_writes_nothing_into_a_deleted_run(tmp_path, monkeypatch):
    import shutil
    from src_new.executor.executor import PipelineExecutor
    from src_new.results.results_manager import ResultsManager
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    run_dir = _run(tmp_path)
    log: list[str] = []
    executor = PipelineExecutor(steps=_steps(log, lambda: shutil.rmtree(run_dir)),
                                results_manager=ResultsManager(run_dir / "results.json"))
    with pytest.raises(cancellation.RunCancelled):
        executor.run(output_directory=tmp_path / "out", working_directory=tmp_path / "out", run_id="r1")
    assert log == ["load"]
    assert not run_dir.exists()


def test_a_run_cancelled_during_its_last_step_is_cancelled_not_success(tmp_path, fake_redis):
    from src_new.executor.executor import PipelineExecutor
    from src_new.executor.task import PipelineStep
    from src_new.results.results_manager import ResultsManager
    run_dir = _run(tmp_path)
    step = PipelineStep(step_id="export", name="export",
                        handler=lambda c: cancellation.request_cancel("r1", run_dir))
    with pytest.raises(cancellation.RunCancelled):
        PipelineExecutor(steps=[step], results_manager=ResultsManager(run_dir / "results.json")).run(
            output_directory=run_dir, run_id="r1")
    assert json.loads((run_dir / "results.json").read_text())["pipeline"]["status"] == "cancelled"


def test_resolvers_stop_before_the_next_search(tmp_path, fake_redis):
    from src_new.config.loader import RunConfig
    from src_new.identification.resolution_manager import IdentifierResolutionManager
    from src_new.results.results_manager import ResultsManager
    run_dir = _run(tmp_path)
    calls: list[str] = []

    class Resolver:
        identifier_type = "PDB_ID"

        def __init__(self, name):
            self.name = name

        def is_applicable(self, *_a, **_kw):
            return True

        def resolve(self, **_kw):
            calls.append(self.name)
            cancellation.request_cancel("r1")
            return []

    class Registry:
        def get_applicable_resolvers(self, _signature_type, as_similarity=False):
            return [] if as_similarity else [Resolver("a"), Resolver("b")]

    manager = IdentifierResolutionManager(Registry(), RunConfig(), signature_type_map={"fasta_map": "fasta"})
    with cancellation.bind("r1", run_dir), pytest.raises(cancellation.RunCancelled):
        manager.resolve(results=ResultsManager(run_dir / "results.json"), segment="A",
                        signature_generator_name="fasta_map", signature="MKV", errors=[])
    assert len(calls) <= 1


# -- no retry --------------------------------------------------------------------

def test_a_cancelled_run_is_never_retried(tmp_path, monkeypatch, fake_redis):
    from src_new.api.run_reaper import mark_worker_lost
    from src_new.executor.executor import PipelineExecutor
    from src_new.results.results_manager import ResultsManager
    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    retries.set_policy("repository", {"enabled": True, "worker_lost": True})
    payload = {"pipeline": {"run_id": "r1", "status": "running", "queue": "repository"}, "warnings": []}
    assert retries.plan(payload, "worker_lost") is not None
    assert retries.plan({"pipeline": {**payload["pipeline"], "status": "cancelled"}}, "worker_lost") is None
    fake_redis.store["bioid:cancel:r1"] = "1"
    cancellation.forget("r1")
    assert retries.plan(payload, "worker_lost") is None

    # the reaper finds the cancelled run's worker gone: cancelled, not failed/retried
    run_dir = _run(tmp_path, "r2")
    (run_dir / cancellation.MARKER).write_text("1")
    assert mark_worker_lost(run_dir / "results.json", sweep_count=3)
    assert json.loads((run_dir / "results.json").read_text())["pipeline"]["status"] == "cancelled"

    # an attempt scheduled for a retry just before the cancel is not re-queued
    run_dir = _run(tmp_path, "r3")
    data = json.loads((run_dir / "results.json").read_text())
    data["pipeline"].update(status="retry_scheduled", retry={"attempt": 1, "at": 0})
    (run_dir / "results.json").write_text(json.dumps(data))
    (run_dir / cancellation.MARKER).write_text("1")
    sent = []
    assert not retries.requeue(run_dir, enqueue=lambda *a: sent.append(a))
    assert not sent
    assert json.loads((run_dir / "results.json").read_text())["pipeline"]["status"] == "cancelled"

    # the executor does not schedule a retry for a cancelled incomplete run
    run_dir = _run(tmp_path, "r4")
    data = json.loads((run_dir / "results.json").read_text())
    data["pipeline"]["queue"] = "repository"
    (run_dir / "results.json").write_text(json.dumps(data))

    def incomplete(context):
        context.add_warning("identifier_resolver_failed", "chembl: HTTP Error 500",
                            details={"segment": "L", "service": "chembl_struct@sim"})
        cancellation.request_cancel("r4", run_dir)
    from src_new.executor.task import PipelineStep
    with pytest.raises(cancellation.RunCancelled):
        PipelineExecutor(steps=[PipelineStep(step_id="identify", handler=incomplete)],
                         results_manager=ResultsManager(run_dir / "results.json")).run(
            output_directory=run_dir, run_id="r4")
    assert json.loads((run_dir / "results.json").read_text())["pipeline"]["status"] == "cancelled"


# -- Celery task -----------------------------------------------------------------

def _child_ignoring_the_cancel(run_id, input_dir, results_path, config_path, conn):
    """A pipeline stuck where it does not look at the cancel (C-level compute):
    it also started a BLAST-like grandchild."""
    import subprocess as sp
    import time as t
    p = sp.Popen([sys.executable, "-c", "import time; time.sleep(120)"])
    Path(results_path).with_name("grandchild.pid").write_text(str(p.pid))
    t.sleep(120)


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


def test_the_task_stops_a_pipeline_that_ignores_the_cancel(tmp_path, monkeypatch, fake_redis):
    from src_new.api import tasks as wtasks
    monkeypatch.setattr(wtasks, "_CANCEL_GRACE_S", 0.5)
    monkeypatch.setattr(cancellation, "CACHE_S", 0.05)
    monkeypatch.setattr(wtasks, "_run_pipeline_child", _child_ignoring_the_cancel)
    run_dir = _run(tmp_path)
    results_path = run_dir / "results.json"
    out = {}
    t = threading.Thread(target=lambda: out.update(wtasks._spawn_pipeline_child(
        "r1", str(run_dir / "input"), results_path, None)))
    t.start()
    for _ in range(100):
        if (run_dir / "grandchild.pid").exists():
            break
        time.sleep(0.05)
    grandchild = int((run_dir / "grandchild.pid").read_text())
    t0 = time.monotonic()
    cancellation.request_cancel("r1", run_dir)
    t.join(30)
    assert out == {"status": "cancelled", "run_id": "r1"}
    assert time.monotonic() - t0 < 10
    assert json.loads(results_path.read_text())["pipeline"]["status"] == "cancelled"
    for _ in range(50):
        if not _alive(grandchild):
            break
        time.sleep(0.1)
    assert not _alive(grandchild), "the pipeline's BLAST-like child survived"


def test_the_task_removes_what_a_deleted_run_left(tmp_path, monkeypatch):
    from src_new.api import tasks as wtasks
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.setattr(wtasks, "_CANCEL_GRACE_S", 0.2)
    monkeypatch.setattr(cancellation, "CACHE_S", 0.05)

    def child(run_id, input_dir, results_path, config_path, conn):
        import shutil
        import time as t
        shutil.rmtree(Path(results_path).parent)  # the API deletes the run ...
        (Path(input_dir) / "tmp").mkdir(parents=True)  # ... and a stage writes on
        t.sleep(120)
    monkeypatch.setattr(wtasks, "_run_pipeline_child", child)
    run_dir = _run(tmp_path)
    out = wtasks._spawn_pipeline_child("r1", str(run_dir / "input"), run_dir / "results.json", None)
    assert out["status"] == "cancelled"
    assert not run_dir.exists()


def test_a_cancelled_or_deleted_queued_run_is_not_started(tmp_path, monkeypatch):
    from src_new.api import tasks as wtasks
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)

    class Lock:
        def set(self, *a, **k):
            raise AssertionError("must not take the lock")
    monkeypatch.setattr(wtasks, "_run_lock_client", lambda: Lock())
    run_dir = _run(tmp_path, status="queued")
    (run_dir / cancellation.MARKER).write_text("1")
    res = wtasks.run_pipeline_task.apply(kwargs=dict(
        run_id="r1", input_dir=str(run_dir / "input"),
        results_path=str(run_dir / "results.json"), config_path=None)).get()
    assert res["status"] == "skipped_cancelled"
    res = wtasks.run_pipeline_task.apply(kwargs=dict(
        run_id="gone", input_dir=str(tmp_path / "gone" / "input"),
        results_path=str(tmp_path / "gone" / "results.json"), config_path=None)).get()
    assert res["status"] == "skipped_cancelled"
    assert not (tmp_path / "gone").exists()


# -- API -------------------------------------------------------------------------

@pytest.fixture
def api(tmp_path, monkeypatch, fake_redis):
    from fastapi.testclient import TestClient
    from src_new.api.main import app
    from src_new.api.security import new_owner_token

    revoked = []

    class Result:
        status = "STARTED"

        def __init__(self, task_id):
            self.id = task_id

        def revoke(self, terminate=False):
            revoked.append(self.id)

    monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
    monkeypatch.setattr("src_new.celery_app.celery.AsyncResult", Result)
    token, sha = new_owner_token()
    with TestClient(app) as client:
        yield client, {"X-Owner-Token": token}, sha, revoked


def _owned(tmp_path, run_id, sha, status="running"):
    run_dir = _run(tmp_path, run_id, status=status)
    data = json.loads((run_dir / "results.json").read_text())
    data["pipeline"]["owner_token_sha256"] = sha
    (run_dir / "results.json").write_text(json.dumps(data))
    return run_dir


def test_cancel_and_delete_tell_the_worker(tmp_path, api, fake_redis):
    client, owner, sha, revoked = api
    run_dir = _owned(tmp_path, "run-a", sha)
    # running and not cancelled: delete still refuses
    assert client.delete("/runs/run-a", headers=owner).status_code == 409
    assert run_dir.exists() and not fake_redis.store
    r = client.post("/runs/run-a/cancel", headers=owner)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert "bioid:cancel:run-a" in fake_redis.store and revoked == ["run-a"]
    assert (run_dir / cancellation.MARKER).exists()
    # the worker's last write said "running" again before it stopped
    data = json.loads((run_dir / "results.json").read_text())
    data["pipeline"]["status"] = "running"
    (run_dir / "results.json").write_text(json.dumps(data))
    assert client.delete("/runs/run-a", headers=owner).status_code == 200
    assert not run_dir.exists()

    # deleting a finished run also records the cancel (a worker may still be on it)
    _owned(tmp_path, "run-b", sha, status="cancelled")
    assert client.delete("/runs/run-b", headers=owner).status_code == 200
    assert "bioid:cancel:run-b" in fake_redis.store


def test_admin_cancel_tells_the_worker(tmp_path, api, fake_redis, monkeypatch):
    client, _owner, sha, revoked = api
    from src_new.api import admin
    monkeypatch.setattr(admin, "_drop_cache", lambda *_a: None)
    from src_new.api.main import app
    app.dependency_overrides[admin.require_admin] = lambda: None
    try:
        run_dir = _owned(tmp_path, "run-c", sha)
        r = client.post("/api/v1/admin/runs/run-c/cancel")
        assert r.status_code == 200, r.text
    finally:
        app.dependency_overrides.pop(admin.require_admin, None)
    assert "bioid:cancel:run-c" in fake_redis.store and revoked == ["run-c"]
    assert (run_dir / cancellation.MARKER).exists()
    assert json.loads((run_dir / "results.json").read_text())["pipeline"]["status"] == "cancelled"
