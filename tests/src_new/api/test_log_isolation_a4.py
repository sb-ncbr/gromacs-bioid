"""W3 A4 (BH-007): worker log isolation.

Production evidence (g0a2091-1028, 127 logs): every log has consecutive
duplicate lines (24,682 pairs), sibling-run lines appear in another run's
log (77/127), third-party celery lines in 117/127, and 33 logs were written
to after the run had finished. Causes: (a) the Celery PARENT attaches run
file handlers to the ROOT logger pre-fork; (b) the forked child inherits
them (cross-talk between pool slots) and adds its own (duplicates); (c)
child teardown removes only its own handler; (d) SIGTERM arrives while the
child still joins the logger tree, and celery's SIGTERM swallow forces a
SIGKILL +30 s.

Fix contract pinned by these tests:
- the parent task attaches NO handlers (parent diagnostics go through the
  module logger -> celery worker log only);
- the child strips ALL inherited ROOT handlers with removeHandler only
  (never close/flush: the descriptors belong to the parent) and resets
  SIGTERM to SIG_DFL so `terminate()` needs no SIGKILL escalation;
- setup/teardown symmetry: after teardown, nothing lands in the run log.
"""

from __future__ import annotations

import logging
import multiprocessing as mp
import os
import signal
import time
from pathlib import Path

import pytest

from src_new.api import tasks as wtasks
from src_new.utils.logging_utils import setup_run_log_handlers, teardown_run_log_handlers


def _invoke(run_id: str, run_dir: Path, results_path: Path) -> dict:
    return wtasks.run_pipeline_task.apply(kwargs=dict(
        run_id=run_id, input_dir=str(run_dir / "input"),
        results_path=str(results_path), config_path=None,
    )).get()


def _read(p: Path) -> str:
    return p.read_text() if p.exists() else ""


def _child_body(run_dir: str, n_lines: int, marker: str) -> None:
    """What the pipeline child does at startup (A4 contract)."""
    handlers = wtasks._child_log_setup(run_dir)
    log = logging.getLogger()  # child logs through root, as the pipeline does
    for i in range(n_lines):
        log.info(f"{marker}-{i}")
    teardown_run_log_handlers(handlers)
    # late write after teardown: must go nowhere
    logging.getLogger().info(f"{marker}-LATE-AFTER-TEARDOWN")


class TestChildLoggingIsolation:
    def test_concurrent_runs_logs_isolated(self, tmp_path):
        """Defense-in-depth: the fork parent carries (a) a celery-worker
        stdout-style handler and (b) a STALE handler for an unrelated
        run-C results.log. Two forked children (A, B) must each produce
        a clean own log: no duplicates, no cross-run lines, no parent-
        emitted celery lines; the parent's handler objects must survive
        (children strip with removeHandler only, never close).
        """
        run_a = tmp_path / "runA"
        run_b = tmp_path / "runB"
        run_c = tmp_path / "runC"
        for d in (run_a, run_b, run_c):
            d.mkdir()

        # parent-side sinks that must NOT leak into child run logs
        worker_log = tmp_path / "parent_worker.log"
        wh = logging.FileHandler(worker_log, encoding="utf-8")
        wh.setFormatter(logging.Formatter("%(name)s: %(message)s"))
        logging.getLogger().addHandler(wh)
        stale_c = setup_run_log_handlers(str(run_c))  # legacy-leak simulation
        try:
            ctx = mp.get_context("fork")
            procs = [
                ctx.Process(target=_child_body, args=(str(run_a), 5, "AAA")),
                ctx.Process(target=_child_body, args=(str(run_b), 5, "BBB")),
            ]
            for p in procs:
                p.start()
            # parent keeps logging like a celery worker does
            logging.getLogger("celery.worker.control").info(
                "WORKER_LINE_FROM_PARENT")
            for p in procs:
                p.join(timeout=30)
            assert all(p.exitcode == 0 for p in procs)
        finally:
            pass

        log_a = _read(run_a / "results.log")
        log_b = _read(run_b / "results.log")
        log_c = _read(run_c / "results.log")

        a_lines = [l for l in log_a.splitlines() if "AAA-" in l]
        assert len(a_lines) == 5, f"expected 5 unique AAA lines, got {len(a_lines)}: {a_lines}"
        assert "BBB-" not in log_a, "cross-talk: B lines in A's log"
        assert "WORKER_LINE_FROM_PARENT" not in log_a, "parent line in A's log"
        assert "LATE-AFTER-TEARDOWN" not in log_a
        # no consecutive duplicates (the b9/b10 production signature)
        a_all = log_a.splitlines()
        assert all(a_all[i] != a_all[i + 1] for i in range(len(a_all) - 1))

        b_lines = [l for l in log_b.splitlines() if "BBB-" in l]
        assert len(b_lines) == 5, f"expected 5 unique BBB lines: {b_lines}"
        assert "AAA-" not in log_b, "cross-talk: A lines in B's log"
        assert "WORKER_LINE_FROM_PARENT" not in log_b

        # the stale foreign-run handler received nothing from the children
        assert "AAA-" not in log_c and "BBB-" not in log_c

        # parent's own handler still usable -> children must not close
        # inherited handlers (only removeHandler)
        still_ok = True
        try:
            logging.getLogger().info("parent-line-after-children")
        except Exception:
            still_ok = False
        assert still_ok
        logging.getLogger().removeHandler(wh)
        teardown_run_log_handlers(stale_c)
        assert "WORKER_LINE_FROM_PARENT" in _read(worker_log)
        assert "parent-line-after-children" in _read(worker_log)

    def test_child_resets_sigterm_to_default(self, tmp_path):
        """celery installs its own SIGTERM handler (warm shutdown) in the
        pool worker; the forked child inherits it, which would swallow
        terminate() and force the +30 s SIGKILL path. _child_log_setup must
        reset SIGTERM to SIG_DFL."""
        ctx = mp.get_context("fork")

        def probe(conn, run_dir):
            wtasks._child_log_setup(run_dir)
            conn.send(signal.getsignal(signal.SIGTERM) == signal.SIG_DFL)
            conn.close()

        (tmp_path / "probe").mkdir()
        parent, child = ctx.Pipe()
        p = ctx.Process(target=probe, args=(child, str(tmp_path / "probe")))
        p.start()
        p.join(timeout=15)
        assert p.exitcode == 0
        assert parent.recv() is True, "SIGTERM not reset to SIG_DFL in child"


class TestParentNoHandlers:
    def test_skip_paths_do_not_leak_root_handlers(self, tmp_path, monkeypatch):
        """Parent attaches nothing on ANY path: measure root handler delta
        across (a) sticky-terminal skip and (b) A1 lock-held skip."""
        import json as _json

        run_dir = tmp_path / "runA"
        (run_dir / "input").mkdir(parents=True)
        results_path = run_dir / "results.json"
        results_path.write_text(_json.dumps(
            {"pipeline": {"status": "failed"}}))  # terminal -> BH-005 skip path

        monkeypatch.setenv("CELERY_BROKER_URL", "redis://fake:6379/0")

        class _FakeRedis:
            def set(self, *a, **k):
                return None  # lock held -> A1 skip path

        monkeypatch.setattr(wtasks, "_run_lock_client", lambda: _FakeRedis())

        before_handlers = list(logging.getLogger().handlers)
        r1 = _invoke("runA", run_dir, results_path)
        assert r1["status"] == "skipped_terminal"
        # now non-terminal -> hits the lock path
        results_path.write_text(_json.dumps({"pipeline": {"status": "running"}}))
        r2 = _invoke("runA", run_dir, results_path)
        assert r2["status"] == "skipped_running"
        assert list(logging.getLogger().handlers) == before_handlers, (
            "parent task leaked root handlers")
        assert logging.getLogger("pipeline_runA").handlers == [], (
            "run logger must not keep file handlers in the parent")

    def test_timeout_terminates_without_kill(self, tmp_path, monkeypatch):
        """Child still running at the wall-clock limit: terminate() must
        reap it well under the 30 s SIGKILL-escalation window."""
        import json as _json

        run_dir = tmp_path / "runT"
        (run_dir / "input").mkdir(parents=True)
        results_path = run_dir / "results.json"
        results_path.write_text(_json.dumps({"pipeline": {"status": "running"}}))

        monkeypatch.setenv("BAT3_PIPELINE_TIMEOUT_S", "1")
        monkeypatch.setenv("CELERY_BROKER_URL", "redis://fake:6379/0")

        class _FakeRedis:
            def __init__(self):
                self.store = {}

            def set(self, key, value, nx=False, ex=None, xx=False):
                if nx and key in self.store:
                    return None
                self.store[key] = value
                return True

            def eval(self, script, numkeys, key, token, ttl=0):
                if self.store.get(key) != token:
                    return 0
                if script is wtasks._RELEASE_LOCK_LUA:
                    self.store.pop(key, None)
                return 1

        monkeypatch.setattr(wtasks, "_run_lock_client", lambda: _FakeRedis())

        def sleepy(*a, **k):
            import time as _t
            _t.sleep(60)

        monkeypatch.setattr(wtasks, "_run_pipeline_child", sleepy)

        t0 = time.monotonic()
        result = _invoke("runT", run_dir, results_path)
        elapsed = time.monotonic() - t0
        assert result["status"] == "failed"
        assert result.get("error_code") == "timeout" or "timeout" in str(result)
        assert elapsed < 20, (
            f"terminate() did not reap the child promptly ({elapsed:.1f}s); "
            "the SIGKILL fallback path takes ~30s+")
