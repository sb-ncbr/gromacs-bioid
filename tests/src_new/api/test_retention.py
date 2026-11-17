"""Run retention (src_new/api/retention.py): what may and may not be deleted."""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from src_new.api import retention as ret

NOW = datetime(2027, 3, 1, tzinfo=timezone.utc)
OLD = (NOW - timedelta(days=60)).isoformat()


def mk(runs: Path, rid: str, status="success", finished=OLD, retention=None, age_s=7200, **pipe):
    d = runs / rid
    d.mkdir(parents=True)
    p = {"status": status, "finished_at": finished, **pipe}
    if retention is not None:
        p["retention"] = retention
    (d / "results.json").write_text(json.dumps({"created_at": finished, "pipeline": p}))
    t = time.time() - age_s
    os.utime(d / "results.json", (t, t))
    return d


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.delenv("BAT3_EXAMPLE_RUNS", raising=False)
    monkeypatch.setattr("src_new.api.routes.runs.served_example_ids", lambda d: set())
    d = tmp_path / "runs"
    d.mkdir()
    return d


def ids(runs, now=NOW):
    return {c["run_id"] for c in ret.candidates(runs, now)}


def test_parse_retention():
    assert ret.parse_retention(None) == {"policy": "default"}
    assert ret.parse_retention("preserve") == {"policy": "preserve"}
    assert ret.parse_retention("14") == {"policy": "days", "days": 14}
    for bad in ("0", "400", "forever", "-3"):
        with pytest.raises(ret.RetentionError):
            ret.parse_retention(bad)


def test_policies(runs):
    mk(runs, "default-old", retention={"policy": "default"})
    mk(runs, "custom-long", retention={"policy": "days", "days": 90})
    mk(runs, "custom-short", retention={"policy": "days", "days": 7})
    mk(runs, "kept", retention={"policy": "preserve"})
    mk(runs, "recent", finished=(NOW - timedelta(days=3)).isoformat(), retention={"policy": "default"})
    assert ids(runs) == {"default-old", "custom-short"}


def test_runs_from_before_the_policy_get_30_days_from_its_start(runs):
    mk(runs, "legacy", finished="2026-09-01T00:00:00+00:00")
    assert ids(runs, datetime(2026, 12, 9, tzinfo=timezone.utc)) == set()
    assert ids(runs, datetime(2026, 12, 11, tzinfo=timezone.utc)) == {"legacy"}


def test_never_touched(runs, monkeypatch):
    mk(runs, "running", status="running")
    mk(runs, "queued", status="queued")
    mk(runs, "fresh-write", age_s=60)
    mk(runs, "example-env")
    mk(runs, "example-served")
    monkeypatch.setenv("BAT3_EXAMPLE_RUNS", '["example-env"]')
    monkeypatch.setattr("src_new.api.routes.runs.served_example_ids", lambda d: {"example-served"})
    (runs / "_adhoc").mkdir()
    (runs / "no-results").mkdir()
    (runs / "broken").mkdir()
    (runs / "broken" / "results.json").write_text("{not json")
    (runs / "linked").symlink_to(mk(runs.parent, "elsewhere"))
    (runs / "resolver_cache.sqlite3").write_text("x")
    mk(runs, "normal")
    assert ids(runs) == {"normal"}


def test_examples_lookup_failure_skips_the_sweep(runs, monkeypatch):
    def boom(d):
        raise RuntimeError("examples unavailable")
    monkeypatch.setattr("src_new.api.routes.runs.served_example_ids", boom)
    mk(runs, "normal")
    with pytest.raises(RuntimeError):
        ret.sweep(runs, NOW, enforce=True)
    assert (runs / "normal").is_dir()


def test_report_only_by_default(runs, monkeypatch):
    monkeypatch.delenv("BAT3_RETENTION_ENFORCE", raising=False)
    for i in range(3):
        mk(runs, f"keep-{i}", retention={"policy": "preserve"})
    mk(runs, "due")
    summary = ret.sweep(runs, NOW)
    assert summary["enforce"] is False and summary["due"] == 1 and summary["moved"] == []
    assert (runs / "due").is_dir()


def test_enforce_moves_to_trash_then_purges_after_grace(runs):
    for i in range(3):
        mk(runs, f"keep-{i}", retention={"policy": "preserve"})
    mk(runs, "due")
    summary = ret.sweep(runs, NOW, enforce=True)
    assert summary["moved"] == ["due"]
    assert not (runs / "due").exists() and (runs / "_expired" / "due" / "results.json").is_file()
    assert ret.sweep(runs, NOW + timedelta(days=6), enforce=True)["purged"] == []
    assert ret.sweep(runs, NOW + timedelta(days=8), enforce=True)["purged"] == ["due"]
    assert not (runs / "_expired" / "due").exists()


def test_restore_brings_a_run_back_preserved(runs):
    for i in range(3):
        mk(runs, f"keep-{i}", retention={"policy": "preserve"})
    mk(runs, "due")
    ret.sweep(runs, NOW, enforce=True)
    ret.restore(runs, "due")
    data = json.loads((runs / "due" / "results.json").read_text())
    assert data["pipeline"]["retention"] == {"policy": "preserve"}
    assert not (runs / "due" / ".expired_at").exists()


def test_circuit_breaker_guards_the_default_policy_only(runs):
    for i in range(4):
        mk(runs, f"due-{i}")  # legacy runs: default policy
    mk(runs, "keep", retention={"policy": "preserve"})
    summary = ret.sweep(runs, NOW, enforce=True)  # 4 of 5 on the default policy: misconfiguration
    assert summary["aborted"] and summary["moved"] == []
    assert all((runs / f"due-{i}").is_dir() for i in range(4))


def test_short_explicit_retention_expires_in_batches(runs, monkeypatch):
    """A campaign's 1-day runs coming due together are not a misconfiguration."""
    monkeypatch.setattr(ret, "MAX_PER_SWEEP", 3)
    for i in range(5):
        mk(runs, f"campaign-{i}", retention={"policy": "days", "days": 1},
           finished=(NOW - timedelta(days=2, minutes=i)).isoformat())
    mk(runs, "keep", retention={"policy": "preserve"})
    s1 = ret.sweep(runs, NOW, enforce=True)
    assert s1["aborted"] is None and len(s1["moved"]) == 3 and s1["waiting"] == 2
    assert s1["moved"] == ["campaign-4", "campaign-3", "campaign-2"]  # oldest due first
    s2 = ret.sweep(runs, NOW, enforce=True)
    assert len(s2["moved"]) == 2 and s2["waiting"] == 0


def test_expired_runs_are_not_served(runs, monkeypatch):
    from fastapi.testclient import TestClient
    from src_new.api.main import app
    monkeypatch.setattr("src_new.api.main.get_runs_dir", lambda: runs)
    c = TestClient(app)
    assert c.get("/files/_expired/x/results.json").status_code == 404
    assert c.get("/files/resolver_cache.sqlite3").status_code == 404
    assert c.get("/files/resolver_cache.sqlite3.corrupt-1/x").status_code == 404
    assert c.get("/files/_quarantine_cache/2026-10-06/resolver_cache.sqlite3").status_code == 404


def test_owner_keeps_a_run_longer_from_today(runs):
    d = mk(runs, "mine", retention={"policy": "default"})  # finished 60 days ago: due
    assert "mine" in ids(runs)
    info = ret.keep_for(d, 90, now=NOW)
    assert info["policy"] == "days" and info["expires_at"].startswith("2027-05-30")
    assert "mine" not in ids(runs)  # the sweep sees the new expiry
    with pytest.raises(ret.RetentionError, match="already kept until 2027-05-30"):
        ret.keep_for(d, 30, now=NOW)  # never shortens
    with pytest.raises(ret.RetentionError):
        ret.keep_for(d, 1000, now=NOW)


def test_owner_cannot_change_preserved_or_unfinished_runs(runs):
    kept = mk(runs, "kept", retention={"policy": "preserve"})
    running = mk(runs, "running", status="running")
    with pytest.raises(ret.RetentionError, match="permanently"):
        ret.keep_for(kept, 365, now=NOW)
    with pytest.raises(ret.RetentionError, match="once it has finished"):
        ret.keep_for(running, 365, now=NOW)


def test_retention_api(runs, monkeypatch):
    import hashlib
    from fastapi.testclient import TestClient
    from src_new.api.main import app
    c = TestClient(app).__enter__()  # before the env change: startup mounts /files
    monkeypatch.setenv("BAT3_RUNS_DIR", str(runs))
    monkeypatch.setattr(ret, "_examples_cache", (0.0, None))
    recent = datetime.now(timezone.utc).isoformat()
    mk(runs, "owned", finished=recent, owner_token_sha256=hashlib.sha256(b"tok").hexdigest())
    status = c.get("/api/v1/runs/owned/status").json()["retention"]
    assert status["policy"] == "default" and status["expires_at"] and status["owner_choices"] == [30, 90, 180, 365]
    assert c.post("/api/v1/runs/owned/retention", json={"days": 90}).status_code == 403
    r = c.post("/api/v1/runs/owned/retention", json={"days": 90}, headers={"X-Owner-Token": "tok"})
    assert r.status_code == 200 and r.json()["days"] == 90
    r = c.post("/api/v1/runs/owned/retention", json={"days": 30}, headers={"X-Owner-Token": "tok"})
    assert r.status_code == 409 and "already kept" in r.json()["detail"]
    assert c.get("/api/v1/runs/owned").json()["retention"]["days"] == 90
    c.__exit__(None, None, None)
