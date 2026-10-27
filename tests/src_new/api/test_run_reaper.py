"""Zombie-run reaper tests (OQ-16 deadlock fix). Pure filesystem + mocks."""

from __future__ import annotations

import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src_new.api.run_reaper import (
    MISSES_TO_FAIL,
    collect_live_task_ids,
    read_run_status,
    sweep,
)


def _mk_run(runs_dir, run_id, status):
    d = runs_dir / run_id
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "pipeline": {"name": "BAT3", "run_id": run_id, "status": status},
        "tasks": {}, "artifacts": {}, "warnings": [],
        "critical_errors": [], "events": [], "data": {},
    }
    (d / "results.json").write_text(json.dumps(payload))
    return d


# --- read_run_status ---------------------------------------------------------

def test_read_run_status_ok_and_unreadable(tmp_path):
    _mk_run(tmp_path, "r1", "running")
    assert read_run_status(tmp_path / "r1" / "results.json") == "running"
    bad = tmp_path / "bad" / "results.json"
    bad.parent.mkdir()
    bad.write_text("{not json")
    assert read_run_status(bad) is None
    assert read_run_status(tmp_path / "missing" / "results.json") is None


# --- sweep semantics ----------------------------------------------------------

def test_sweep_fails_zombie_only_after_two_misses(tmp_path):
    _mk_run(tmp_path, "dead1", "running")
    misses = {}

    out1 = sweep(tmp_path, live_task_ids=set(), misses=misses)
    assert out1["zombies_failed"] == []                 # first miss: warn only
    assert read_run_status(tmp_path / "dead1" / "results.json") == "running"

    out2 = sweep(tmp_path, live_task_ids=set(), misses=misses)
    assert out2["zombies_failed"] == ["dead1"]          # second miss: failed

    payload = json.loads((tmp_path / "dead1" / "results.json").read_text())
    assert payload["pipeline"]["status"] == "failed"
    assert any(e["code"] == "worker_lost" for e in payload["critical_errors"])
    assert any(e["kind"] == "worker_lost" for e in payload["events"])


def test_sweep_leaves_live_and_terminal_runs_alone(tmp_path):
    live = _mk_run(tmp_path, "alive1", "running")
    _mk_run(tmp_path, "done1", "success")
    _mk_run(tmp_path, "gone1", "cancelled")
    out = sweep(tmp_path, live_task_ids={"alive1"}, misses={})
    assert out["zombies_failed"] == []
    assert read_run_status(live / "results.json") == "running"
    assert read_run_status(tmp_path / "done1" / "results.json") == "success"
    assert read_run_status(tmp_path / "gone1" / "results.json") == "cancelled"


def test_sweep_queued_run_never_failed(tmp_path):
    """bughunt BH-005 (inverts the old :72 expectation): a queued run is
    invisible to celery inspect by construction (broker-held message), so
    empty inspect data must NEVER fail it."""
    _mk_run(tmp_path, "stuckq", "queued")
    misses = {}
    for _ in range(3):
        out = sweep(tmp_path, set(), misses)
        assert out["zombies_failed"] == []
    assert read_run_status(tmp_path / "stuckq" / "results.json") == "queued"
    assert "stuckq" not in misses


def _mk_heartbeat(run_dir, age_s):
    hb = run_dir / "heartbeat"
    hb.touch()
    import os as _os
    import time as _time
    _os.utime(hb, (_time.time() - age_s,) * 2)


def test_sweep_fresh_heartbeat_kept_even_with_empty_inspect(tmp_path):
    """running + fresh heartbeat + empty live set -> kept (inspect lies)."""
    run_dir = _mk_run(tmp_path, "beating", "running")
    _mk_heartbeat(run_dir, age_s=10)
    misses = {}
    for _ in range(3):
        out = sweep(tmp_path, set(), misses)
        assert out["zombies_failed"] == []
    assert read_run_status(run_dir / "results.json") == "running"


def test_sweep_stale_heartbeat_failed_in_one_sweep(tmp_path):
    """running + heartbeat older than 15 min -> failed immediately."""
    run_dir = _mk_run(tmp_path, "flatline", "running")
    _mk_heartbeat(run_dir, age_s=3600)
    out = sweep(tmp_path, live_task_ids=set(), misses={})
    assert out["zombies_failed"] == ["flatline"]
    payload = json.loads((run_dir / "results.json").read_text())
    assert payload["pipeline"]["status"] == "failed"
    assert any(e["code"] == "worker_lost" for e in payload["critical_errors"])
    ev = [e for e in payload["events"] if e["kind"] == "worker_lost"][0]
    assert "stale" in ev["detail"]


def test_task_skips_terminal_run_on_redelivery(tmp_path):
    """bughunt BH-005 (sticky terminal): an acks_late redelivered message
    must not flip a reaped/completed run back to running."""
    from src_new.api.tasks import run_pipeline_task
    run_dir = _mk_run(tmp_path, "donez", "failed")
    input_dir = run_dir / "input"
    input_dir.mkdir(exist_ok=True)
    out = run_pipeline_task(
        run_id="donez",
        input_dir=str(input_dir),
        results_path=str(run_dir / "results.json"),
    )
    assert out["status"] == "skipped_terminal"
    assert read_run_status(run_dir / "results.json") == "failed"


def test_sweep_recovery_resets_miss_counter(tmp_path):
    """A run re-appearing in the fleet between sweeps must NOT be failed."""
    _mk_run(tmp_path, "flaky", "running")
    misses = {}
    sweep(tmp_path, set(), misses)                                  # miss 1
    out = sweep(tmp_path, {"flaky"}, misses)                        # re-joined
    assert out["zombies_failed"] == []
    out = sweep(tmp_path, set(), misses)                            # miss 1 again
    assert out["zombies_failed"] == []                              # counter reset ✓
    assert read_run_status(tmp_path / "flaky" / "results.json") == "running"


def test_sweep_skips_unreadable_and_cleans_stale_misses(tmp_path):
    _mk_run(tmp_path, "ok1", "running")
    bad_dir = tmp_path / "corrupt"
    bad_dir.mkdir()
    (bad_dir / "results.json").write_text("{nope")
    misses = {"ghost": 1}
    out = sweep(tmp_path, {"ok1"}, misses)
    assert out["errors"] == 1
    assert "ghost" not in misses                                    # stale forgotten


def test_sweep_counts_idempotent_after_failure(tmp_path):
    """A failed run is terminal; later sweeps must not touch it again."""
    _mk_run(tmp_path, "once", "running")
    misses = {}
    for _ in range(MISSES_TO_FAIL + 1):
        sweep(tmp_path, set(), misses)
    out = sweep(tmp_path, set(), misses)
    assert out["zombies_failed"] == []
    assert json.loads((tmp_path / "once" / "results.json").read_text())["pipeline"]["status"] == "failed"


# --- collect_live_task_ids ----------------------------------------------------

class _Bucket:
    def __init__(self, value=None, exc=None):
        self._v, self._e = value, exc

    def __call__(self):
        if self._e:
            raise self._e
        return self._v


class _FakeInspect:
    def __init__(self, active=None, reserved=None, scheduled=None):
        self.active = active or _Bucket({})
        self.reserved = reserved or _Bucket({})
        self.scheduled = scheduled or _Bucket({})


class _FakeControl:
    def __init__(self, inspector):
        self._i = inspector

    def inspect(self, timeout=None):
        return self._i


class _FakeApp:
    def __init__(self, inspector):
        self.control = _FakeControl(inspector)


def test_collect_live_task_ids_merges_all_buckets():
    app = _FakeApp(_FakeInspect(
        active=_Bucket({"w1": [{"id": "a1"}]}),
        reserved=_Bucket({"w2": [{"id": "r1"}]}),
        scheduled=_Bucket({"w3": [{"id": "s1"}]}),
    ))
    assert collect_live_task_ids(app) == {"a1", "r1", "s1"}


def test_collect_live_task_ids_survives_bucket_failure():
    app = _FakeApp(_FakeInspect(
        active=_Bucket(exc=ConnectionError("broker down")),
        reserved=_Bucket({"w1": [{"id": "r1"}]}),
    ))
    assert collect_live_task_ids(app) == {"r1"}   # partial truth, no crash


# --- celery conf mentions -----------------------------------------------------

def test_pipeline_celery_app_has_late_acks_and_reject_on_lost():
    from src_new.celery_app import celery as pipeline_celery
    assert pipeline_celery.conf["task_acks_late"] is True
    assert pipeline_celery.conf["task_reject_on_worker_lost"] is True
    # pre-existing hardening must not have been disturbed
    assert pipeline_celery.conf["worker_prefetch_multiplier"] == 1
