"""W3.1 item 5 (A1): lock re-acquisition after a Redis outage, abort on
duplicate takeover, and the /data/validation reaper extension.

Audit §3 item 5 acceptance: "a fault-injection test (Redis down for 150 s
mid-run) ends with exactly one execution and a terminal status."

The 150 s outage exceeds the lock TTL (120 s), so Redis comes back
WITHOUT the key (restart without persistence / eviction). Contract:

- refresh finds the key missing and NO duplicate holds it -> RE-TAKE
  the lock (SET NX, own token) and continue: one execution, unchanged;
- a redelivered duplicate re-took the key first -> the ORIGINAL aborts:
  its child is terminated, an execution_lock_lost event is recorded,
  the task acks with aborted_lock_lost; the duplicate (the current
  holder) finishes the run -> exactly one execution, terminal status;
- the execution token includes the thread id: the fleet runs Celery
  with --pool=threads --concurrency=2, where hostname:pid alone is
  IDENTICAL for two duplicate executions in one worker process (the
  token check could not tell them apart);
- the reaper sweeps /data/validation runs too (stale-heartbeat zombies
  there were never reaped — the reaper only scanned /app/runs).
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

import pytest

from src_new.api import tasks as wtasks
from src_new.results.results_manager import ResultsManager

KEY = wtasks._LOCK_PREFIX + "runA"


def _invoke(run_id: str, run_dir: Path, results_path: Path) -> dict:
    return wtasks.run_pipeline_task.apply(kwargs=dict(
        run_id=run_id, input_dir=str(run_dir / "input"),
        results_path=str(results_path), config_path=None,
    )).get()


def _seed_run(tmp_path: Path, status: str = "running") -> tuple[Path, Path]:
    run_dir = tmp_path / "runA"
    (run_dir / "input").mkdir(parents=True)
    results_path = run_dir / "results.json"
    results_path.write_text(json.dumps({"pipeline": {"status": status}}))
    return run_dir, results_path


class RestartFakeRedis:
    """Dict-backed lock backend that can lose its state (Redis restart).

    Implements exactly the operations run_pipeline_task uses: SET NX EX,
    GET, and the two token-checked Lua scripts. ``wipe()`` simulates a
    restart without persistence (the > TTL outage). ``gate`` optionally
    parks the FIRST eval call until the test releases it — used to
    sequence "duplicate re-took the lock" deterministically before the
    original's next refresh.
    """

    def __init__(self):
        self.store: dict[str, str] = {}
        self.set_calls: list[str] = []  # tokens of successful NX sets
        self.gate: threading.Event | None = None

    def wipe(self):
        self.store.clear()

    def set(self, key, value, nx=False, ex=None, xx=False):
        if nx and key in self.store:
            return None
        self.store[key] = value
        self.set_calls.append(value)
        return True

    def get(self, key):
        return self.store.get(key)

    def eval(self, script, numkeys, key, token, ttl=0):
        gate = self.gate
        if gate is not None:
            self.gate = None
            assert gate.wait(15), "test sequencing gate never released"
        if self.store.get(key) != token:
            return 0
        if script is wtasks._RELEASE_LOCK_LUA:
            del self.store[key]
            return 1
        return 1  # refresh


@pytest.fixture(autouse=True)
def _redis_env(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://fake:6379/0")


class TestLockReacquireAfterOutage:
    def test_outage_without_duplicate_retakes_lock_and_completes(
            self, tmp_path, monkeypatch):
        """Fault: key lost mid-run, nobody re-took it. The original must
        RE-TAKE the lock (SET NX, own token) and finish exactly once."""
        run_dir, results_path = _seed_run(tmp_path)
        fake = RestartFakeRedis()
        monkeypatch.setattr(wtasks, "_run_lock_client", lambda: fake)
        monkeypatch.setattr(wtasks, "_LOCK_HEARTBEAT_S", 0.05)

        spawns = []

        def _long_spawn(*a, **k):
            spawns.append(1)
            time.sleep(1.0)  # span the fault window below
            return {"status": "completed", "run_id": "runA"}

        monkeypatch.setattr(wtasks, "_spawn_pipeline_child", _long_spawn)

        result_holder = {}

        def _run():
            result_holder["res"] = _invoke("runA", run_dir, results_path)

        t = threading.Thread(target=_run)
        t.start()
        # wait for the lock + a couple of refresh beats
        for _ in range(200):
            if fake.set_calls:
                break
            time.sleep(0.02)
        assert fake.set_calls, "original never acquired the lock"
        time.sleep(0.2)
        # FAULT: Redis restarts without persistence (the >120 s outage)
        fake.wipe()
        t.join(30)
        assert result_holder["res"]["status"] == "completed"
        assert len(spawns) == 1, "exactly one execution"
        # RED at HEAD: the refresh failure was silent — the key was never
        # re-taken, so a duplicate could have started at any moment
        a_token = fake.set_calls[0]
        retakes = [c for c in fake.set_calls[1:] if c == a_token]
        assert retakes, (
            "original must RE-TAKE the lock after the key vanished "
            f"(set_calls={fake.set_calls})")

    def test_duplicate_takeover_original_aborts_exactly_one_execution(
            self, tmp_path, monkeypatch):
        """Fault: key lost mid-run AND a redelivered duplicate re-took it.
        The ORIGINAL aborts (child terminated, event recorded, ack with
        aborted_lock_lost); the duplicate completes the run."""
        run_dir, results_path = _seed_run(tmp_path)
        fake = RestartFakeRedis()
        monkeypatch.setattr(wtasks, "_run_lock_client", lambda: fake)
        monkeypatch.setattr(wtasks, "_LOCK_HEARTBEAT_S", 0.05)

        # REAL _spawn_pipeline_child with a controlled-but-real child
        # process: both children sleep long; the original's is TERMINATED
        # by the abort, only the duplicate's runs to completion. The
        # completion marker is a FILE (forked children cannot mutate
        # parent-side lists).
        completions_file = run_dir / "child_completions.txt"

        def _fake_child(run_id, input_dir, results_path, config_path, conn):
            import time as _t
            _t.sleep(8)
            with open(completions_file, "a") as fh:
                fh.write(run_id + "\n")
            try:
                conn.send(("ok", "child done"))
            except Exception:
                pass

        monkeypatch.setattr(wtasks, "_run_pipeline_child", _fake_child)

        res = {}

        def _run_original():
            res["a"] = _invoke("runA", run_dir, results_path)

        a = threading.Thread(target=_run_original)
        a.start()
        # original: lock taken, child sleeping, beats refreshing
        for _ in range(200):
            if fake.set_calls:
                break
            time.sleep(0.02)
        assert fake.set_calls
        a_token = fake.set_calls[0]
        time.sleep(0.15)

        # park the original's next refresh so the duplicate deterministically
        # re-takes the key FIRST (the real-world interleaving)
        gate = threading.Event()
        fake.gate = gate
        # FAULT part 1: Redis restarts without persistence
        fake.wipe()

        def _run_duplicate():
            res["b"] = _invoke("runA", run_dir, results_path)

        b = threading.Thread(target=_run_duplicate)
        b.start()
        # duplicate acquires the now-missing key (its own token)
        for _ in range(300):
            if len(fake.set_calls) >= 2 and fake.set_calls[1] != a_token:
                break
            time.sleep(0.02)
        assert len(fake.set_calls) >= 2, "duplicate never re-took the lock"
        b_token = fake.set_calls[1]
        assert b_token != a_token, (
            "execution tokens must differ per execution (thread id in "
            "token: threads-pool workers share hostname:pid)")

        # FAULT part 2: the outage ends; the original's refresh now sees
        # the DUPLICATE's key
        gate.set()

        a.join(30)
        b.join(60)
        assert res["a"]["status"] == "aborted_lock_lost", res["a"]
        assert res["b"]["status"] == "completed", res["b"]
        # exactly one execution ran to completion: the original's child
        # was TERMINATED before finishing (only the duplicate's child
        # reached the completion marker)
        done = (completions_file.read_text().splitlines()
                if completions_file.exists() else [])
        assert done == ["runA"], (
            f"exactly one execution must complete: {done}")
        # the abort is recorded on the run
        payload = json.loads(results_path.read_text())
        events = [e.get("kind") or e.get("event")
                  for e in payload.get("events", [])]
        assert "execution_lock_lost" in events, events
        # the duplicate's lock was never released by the original
        # (token-checked release is a no-op for foreign tokens)


class TestExecutionTokenIncludesThread:
    def test_token_has_thread_id(self):
        # RED at HEAD: hostname:pid only — identical for two threads of
        # one threads-pool worker (--pool=threads --concurrency=2)
        token = wtasks._execution_token()
        parts = token.split(":")
        assert len(parts) >= 3, (
            f"token must include a thread discriminator: {token}")
        # same process, different concurrently-live thread -> different token
        tokens = set()
        barrier = threading.Barrier(4)

        def _grab():
            barrier.wait(5)  # all threads concurrently live
            tokens.add(wtasks._execution_token())

        ts = [threading.Thread(target=_grab) for _ in range(4)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert len(tokens) == 4, (
            "tokens must be unique per concurrently-live thread")


class TestReaperValidationDirs:
    def test_reaper_run_dirs_includes_validation_by_default(self, tmp_path):
        from src_new.api.run_reaper import reaper_run_dirs
        dirs = reaper_run_dirs(tmp_path / "runs")
        assert Path("/data/validation") in dirs
        assert (tmp_path / "runs") in dirs

    def test_reaper_run_dirs_env_override(self, tmp_path, monkeypatch):
        from src_new.api.run_reaper import reaper_run_dirs
        monkeypatch.setenv("BAT3_REAPER_EXTRA_RUN_DIRS",
                           str(tmp_path / "extra1"))
        dirs = reaper_run_dirs(tmp_path / "runs")
        assert tmp_path / "extra1" in dirs
        assert Path("/data/validation") not in dirs

    def test_sweep_all_dirs_reaps_validation_zombies(self, tmp_path):
        """A stale-heartbeat running run under /data/validation gets
        failed by the extended sweep (was: invisible forever)."""
        from src_new.api.run_reaper import sweep_all_dirs
        runs = tmp_path / "runs"
        runs.mkdir()
        validation = tmp_path / "validation"
        validation.mkdir()

        def _mk(root: Path, name: str, status: str, hb_age: float):
            rd = root / name
            rd.mkdir()
            (rd / "results.json").write_text(json.dumps(
                {"pipeline": {"status": status}}))
            hb = rd / "heartbeat"
            hb.touch()
            old = time.time() - hb_age
            os.utime(hb, (old, old))

        _mk(runs, "run-ok", "running", 10)      # fresh: untouched
        _mk(validation, "4653", "running", 5000)  # stale zombie: reaped
        _mk(validation, "1089", "running", 10)    # fresh: untouched

        summary = sweep_all_dirs(
            runs, live_task_ids=set(), misses={},
            extra_dirs=[validation])
        assert summary["zombies_failed"] == ["4653"], summary
        v = json.loads((validation / "4653" / "results.json").read_text())
        assert v["pipeline"]["status"] == "failed"
        ok1 = json.loads((validation / "1089" / "results.json").read_text())
        assert ok1["pipeline"]["status"] == "running"
        ok2 = json.loads((runs / "run-ok" / "results.json").read_text())
        assert ok2["pipeline"]["status"] == "running"
