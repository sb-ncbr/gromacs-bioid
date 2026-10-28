"""W3 A1 (BH-039): duplicate concurrent execution guard.

Production evidence (g0a2091-1028): the broker Redis `timeout 60` closes
the idle consumer connection while both pool slots are busy; Celery
restores the unacked message and a second pod executes the SAME run
concurrently into the same run directory (32/125 tasks received 2-3x;
M13 x3, F14 x2). The BH-005 sticky-terminal guard caught 0 of them —
every redelivery was of a RUNNING run.

Fix contract pinned by these tests:
- per-run atomic Redis lock (SET NX EX) refreshed by the heartbeat loop;
  lock held -> ack + skipped_running, no fork, run dir untouched
  (heartbeat file must NOT even be touched before the lock decision);
- Redis down -> heartbeat fallback (status running + heartbeat < 90 s);
- lock released in finally, also on child crash/timeout;
- results.json writes stay atomic (temp + os.replace) — the temp file
  pattern existed but is now load-bearing for the lock-free edge cases.
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


def _invoke(run_id: str, run_dir: Path, results_path: Path) -> dict:
    return wtasks.run_pipeline_task.apply(kwargs=dict(
        run_id=run_id, input_dir=str(run_dir / "input"),
        results_path=str(results_path), config_path=None,
    )).get()


def _write_status(results_path: Path, status: str) -> None:
    results_path.write_text(json.dumps({"pipeline": {"status": status}}))


class FakeRedis:
    """Minimal dict-backed stand-in for redis.Redis (lock ops only)."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.expires: dict[str, int] = {}
        self.fail = False  # simulate broker being unreachable

    def set(self, key, value, nx=False, ex=None, xx=False):
        if self.fail:
            raise ConnectionError("broker down")
        if nx and key in self.store:
            return None
        if xx and key not in self.store:
            return None
        self.store[key] = value
        if ex:
            self.expires[key] = ex
        return True

    def get(self, key):
        if self.fail:
            raise ConnectionError("broker down")
        return self.store.get(key)

    def eval(self, script, numkeys, key, token, ttl=0):
        """Emulate the compare-token + expire/delete Lua scripts."""
        if self.fail:
            raise ConnectionError("broker down")
        if self.store.get(key) != token:
            return 0
        if script is wtasks._RELEASE_LOCK_LUA:
            del self.store[key]
            self.expires.pop(key, None)
            return 1
        self.expires[key] = ttl
        return 1


def _seed_run(tmp_path: Path, status: str = "running",
              heartbeat_age_s: float | None = None) -> tuple[Path, Path]:
    run_dir = tmp_path / "runA"
    (run_dir / "input").mkdir(parents=True)
    results_path = run_dir / "results.json"
    _write_status(results_path, status)
    if heartbeat_age_s is not None:
        hb = run_dir / "heartbeat"
        hb.touch()
        old = time.time() - heartbeat_age_s
        os.utime(hb, (old, old))
    return run_dir, results_path


@pytest.fixture
def redis_env(monkeypatch):
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://fake:6379/0")


class TestRunLock:
    def test_redelivery_of_running_run_is_noop(self, tmp_path, monkeypatch, redis_env):
        """Lock held by another worker -> skipped_running, NO fork, and the
        run directory is not touched (no heartbeat file appearing)."""
        run_dir, results_path = _seed_run(tmp_path)
        fake = FakeRedis()
        # another worker already holds the lock
        fake.set(wtasks._LOCK_PREFIX + "runA", "other-worker:123:runA")
        monkeypatch.setattr(wtasks, "_run_lock_client", lambda: fake)

        forks = []
        monkeypatch.setattr(wtasks, "_spawn_pipeline_child",
                            lambda *a, **k: forks.append(1))

        before = results_path.read_text()
        result = _invoke("runA", run_dir, results_path)
        assert result["status"] == "skipped_running"
        assert result["run_id"] == "runA"
        assert forks == [], "skipped redelivery must not fork a child"
        assert not (run_dir / "heartbeat").exists(), (
            "the lock decision happens BEFORE any heartbeat touch")
        assert results_path.read_text() == before, "run results untouched"

    def test_lock_acquired_normal_path_and_released(self, tmp_path, monkeypatch, redis_env):
        run_dir, results_path = _seed_run(tmp_path)
        fake = FakeRedis()
        monkeypatch.setattr(wtasks, "_run_lock_client", lambda: fake)
        monkeypatch.setattr(wtasks, "_spawn_pipeline_child",
                            lambda *a, **k: {"status": "completed", "run_id": "runA"})

        result = _invoke("runA", run_dir, results_path)
        assert result["status"] == "completed"
        assert (wtasks._LOCK_PREFIX + "runA") not in fake.store, (
            "lock released in finally")

    def test_lock_released_on_child_crash_and_timeout(self, tmp_path, monkeypatch, redis_env):
        run_dir, results_path = _seed_run(tmp_path)
        fake = FakeRedis()
        monkeypatch.setattr(wtasks, "_run_lock_client", lambda: fake)

        def boom(*a, **k):
            raise RuntimeError("child crashed")
        monkeypatch.setattr(wtasks, "_spawn_pipeline_child", boom)

        with pytest.raises(RuntimeError):
            _invoke("runA", run_dir, results_path)
        assert (wtasks._LOCK_PREFIX + "runA") not in fake.store

    def test_redis_down_heartbeat_fallback(self, tmp_path, monkeypatch, redis_env):
        """Broker unreachable: running run with a FRESH heartbeat -> skip;
        stale heartbeat (> 90 s) -> proceed (another worker died)."""
        run_dir, results_path = _seed_run(tmp_path, heartbeat_age_s=5)
        fake = FakeRedis()
        fake.fail = True
        monkeypatch.setattr(wtasks, "_run_lock_client", lambda: fake)
        monkeypatch.setattr(wtasks, "_spawn_pipeline_child",
                            lambda *a, **k: {"status": "completed", "run_id": "runA"})

        result = _invoke("runA", run_dir, results_path)
        assert result["status"] == "skipped_running"

        # stale heartbeat: proceed
        old = time.time() - 200
        os.utime(run_dir / "heartbeat", (old, old))
        result = _invoke("runA", run_dir, results_path)
        assert result["status"] == "completed"

    def test_terminal_skip_precedes_lock(self, tmp_path, monkeypatch, redis_env):
        """BH-005 sticky-terminal check still dominates: a terminal run with
        NO lock contention returns skipped_terminal."""
        run_dir, results_path = _seed_run(tmp_path, status="failed")
        fake = FakeRedis()
        monkeypatch.setattr(wtasks, "_run_lock_client", lambda: fake)
        result = _invoke("runA", run_dir, results_path)
        assert result["status"] == "skipped_terminal"


class TestAtomicResultsWrites:
    def test_results_write_is_atomic(self, tmp_path):
        """Rapid saves never leave a torn or missing results.json, and
        readers always see complete JSON."""
        path = tmp_path / "r" / "results.json"
        rm = ResultsManager(str(path), pipeline_name="t")
        rm.start_run()
        errors = []
        stop = threading.Event()

        def writer():
            i = 0
            while not stop.is_set():
                rm.set_data(f"stress/k{i % 4}", list(range(i % 50)))
                i += 1

        def reader():
            while not stop.is_set():
                try:
                    content = path.read_text()
                    json.loads(content)
                except json.JSONDecodeError as exc:
                    errors.append(f"torn: {exc}")
                except FileNotFoundError:
                    errors.append("results.json vanished")

        threads = [threading.Thread(target=writer) for _ in range(2)] + \
                  [threading.Thread(target=reader) for _ in range(3)]
        for t in threads:
            t.start()
        time.sleep(1.5)
        stop.set()
        for t in threads:
            t.join(timeout=5)
        assert errors == [], errors[:3]
        # no leftover temp files from the atomic path
        assert list(path.parent.glob("*.tmp")) == []

    def test_failed_write_leaves_previous_content(self, tmp_path, monkeypatch):
        path = tmp_path / "r" / "results.json"
        rm = ResultsManager(str(path), pipeline_name="t")
        rm.start_run()
        good = path.read_text()

        import src_new.utils.file_utils as fu
        orig = fu.atomic_write_json

        def explode(p, data):
            # simulate disk-full mid-write after temp creation
            (tmp_path / "r" / "garbage.tmp").write_text("partial")
            raise OSError("No space left on device")
        monkeypatch.setattr("src_new.results.results_manager.atomic_write_json", explode)
        with pytest.raises(OSError):
            rm.set_data("boom", 1)
        assert path.read_text() == good, (
            "previous results.json must survive a failed write")
