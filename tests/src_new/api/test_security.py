"""Safety rails of the public runs API (src_new/api/security.py)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src_new.api import security
from src_new.api.main import app

PDB = b"ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nEND\n"
ALICE = {"X-Forwarded-For": "198.51.100.1"}
BOB = {"X-Forwarded-For": "198.51.100.2"}


class FakeRedis:
    def __init__(self, waiting: int = 0):
        self.waiting, self.counts = waiting, {}

    def llen(self, key):
        return self.waiting

    def incr(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key, seconds):
        pass


@pytest.fixture
def runs(tmp_path: Path, monkeypatch):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    monkeypatch.setenv("BAT3_RUNS_DIR", str(runs_dir))
    monkeypatch.setattr("src_new.api.routes.runs.run_pipeline_task.apply_async", lambda *a, **k: None)
    monkeypatch.setattr(security, "_redis", FakeRedis())
    return runs_dir


@pytest.fixture
def client():
    return TestClient(app)


def submit(client, headers=ALICE, **files):
    files = files or {"files": ("x.pdb", PDB)}
    return client.post("/api/v1/runs", files=files, headers=headers)


def test_dot_segment_run_ids_never_reach_the_filesystem(runs, client):
    (runs / "keep").mkdir()
    for rid in ("%2e", "%2e%2e", "..%2fx"):
        r = client.request("DELETE", f"/api/v1/runs/{rid}")
        assert r.status_code in (404, 405, 422), (rid, r.status_code)
    assert (runs / "keep").is_dir()


def test_owner_token_guards_delete_and_cancel(runs, client):
    r = submit(client)
    assert r.status_code == 200, r.text
    run_id, token = r.json()["run_id"], r.json()["owner_token"]
    assert token
    assert client.request("DELETE", f"/api/v1/runs/{run_id}").status_code == 403
    r = client.request("DELETE", f"/api/v1/runs/{run_id}", headers={"X-Owner-Token": "nope"})
    assert r.status_code == 403 and "Only the submitter" in r.json()["detail"]
    r = client.request("DELETE", f"/api/v1/runs/{run_id}", headers={"X-Owner-Token": token})
    assert r.status_code == 200 and not (runs / run_id).exists()


def test_runs_without_a_token_cannot_be_deleted(runs, client):
    (runs / "legacy").mkdir()
    (runs / "legacy" / "results.json").write_text(json.dumps({"pipeline": {"status": "success"}}))
    r = client.request("DELETE", "/api/v1/runs/legacy", headers={"X-Owner-Token": "x"})
    assert r.status_code == 403 and "no owner token" in r.json()["detail"]
    assert (runs / "legacy").is_dir()


def test_existing_run_id_is_not_overwritten(runs, client):
    run_id = submit(client).json()["run_id"]
    r = client.post("/api/v1/runs", params={"run_id": run_id}, files={"files": ("y.pdb", PDB)})
    assert r.status_code == 409


def test_run_list_shows_only_your_runs_without_addresses(runs, client):
    mine = submit(client, ALICE).json()["run_id"]
    theirs = submit(client, BOB).json()["run_id"]
    listed = client.get("/api/v1/runs", headers=ALICE).json()["runs"]
    assert [x["run_id"] for x in listed] == [mine]
    assert not listed[0].get("creator_ip")
    stored = json.loads((runs / theirs / "results.json").read_text())["pipeline"]
    assert "creator_ip" not in stored and stored["creator_ip_hash"] == security.ip_hash("198.51.100.2")


def test_upload_types_and_count(runs, client, monkeypatch):
    r = submit(client, files=("page.html", b"<script>alert(1)</script>"))
    assert r.status_code == 422 and "not a file type" in r.json()["detail"]
    monkeypatch.setattr("src_new.api.routes.runs.MAX_FILES", 2)
    r = client.post("/api/v1/runs", files=[("files", (f"{i}.pdb", PDB)) for i in range(3)])
    assert r.status_code == 413 and "Too many files" in r.json()["detail"]
    assert list(runs.iterdir()) == []


def test_upload_is_copied_with_the_bom_stripped(runs, client):
    run_id = submit(client, files=("x.pdb", b"\xef\xbb\xbf" + PDB)).json()["run_id"]
    assert (runs / run_id / "input" / "x.pdb").read_bytes() == PDB


def test_queue_cap_answers_429_with_retry_after(runs, client, monkeypatch):
    monkeypatch.setattr(security, "_redis", FakeRedis(waiting=security.QUEUE_CAP))
    r = submit(client)
    assert r.status_code == 429 and r.headers["Retry-After"] == "600"
    assert "busy" in r.json()["detail"]
    assert list(runs.iterdir()) == []


def test_hourly_limit_per_address(runs, client, monkeypatch):
    monkeypatch.setattr(security, "SUBMIT_LIMIT_PER_HOUR", 2)
    assert submit(client).status_code == 200
    assert submit(client).status_code == 200
    r = submit(client)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0
    assert "per hour" in r.json()["detail"]
    assert submit(client, BOB).status_code == 200  # another address is not affected


def test_limits_fail_open_without_redis(runs, client, monkeypatch):
    class Down:
        def llen(self, key):
            raise ConnectionError("redis down")
    monkeypatch.setattr(security, "_redis", Down())
    assert submit(client).status_code == 200


def test_rerun_all_is_not_public(runs, client, monkeypatch):
    assert client.post("/api/v1/runs/rerun-all").status_code == 404
    monkeypatch.setenv("BAT3_ADMIN_TOKEN", "s3cret")
    assert client.post("/api/v1/runs/rerun-all", headers={"X-Admin-Token": "wrong"}).status_code == 404
    assert client.post("/api/v1/runs/rerun-all", headers={"X-Admin-Token": "s3cret"}).status_code == 200


def test_rerun_rechecks_the_stored_config(runs, client):
    old = runs / "planted"
    (old / "input").mkdir(parents=True)
    (old / "input" / "x.pdb").write_bytes(PDB)
    (old / "results.json").write_text(json.dumps({"pipeline": {"status": "success"}}))
    (old / "config.ini").write_text("[blast]\nblastp_exec = /bin/sh\n")
    r = client.post("/api/v1/runs/planted/rerun")
    assert r.status_code == 422 and "cannot be re-run" in r.json()["detail"]
    (old / "config.ini").write_text("[identifiers]\nblast_nt = no\n")
    r = client.post("/api/v1/runs/planted/rerun")
    assert r.status_code == 200 and r.json()["owner_token"]


def test_files_are_served_sandboxed(client):
    # the /files mount is bound at import; the headers go on every /files response
    r = client.get("/files/some-run/input/page.html")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["Content-Security-Policy"].startswith("sandbox")


def test_creator_ip_migration(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "migrate_creator_ip", Path(__file__).resolve().parents[3] / "scripts" / "migrate_creator_ip.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for rid, status in (("done", "success"), ("busy", "running"), ("new", "success")):
        (tmp_path / rid).mkdir()
        pipe = {"status": status}
        if rid != "new":
            pipe["creator_ip"] = "192.0.2.9"
        (tmp_path / rid / "results.json").write_text(json.dumps({"pipeline": pipe}))
    assert mod.migrate(tmp_path, dry_run=False) == {
        "migrated": 1, "skipped_active": 1, "unchanged": 1, "unreadable": 0}
    done = json.loads((tmp_path / "done" / "results.json").read_text())["pipeline"]
    assert "creator_ip" not in done and done["creator_ip_hash"] == security.ip_hash("192.0.2.9")
    assert security.same_submitter(done, "192.0.2.9")
    assert mod.migrate(tmp_path, dry_run=False)["migrated"] == 0
