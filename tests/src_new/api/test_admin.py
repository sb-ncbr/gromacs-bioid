"""Admin API (src_new/api/admin.py)."""
from __future__ import annotations

import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from src_new.api import admin, security
from src_new.api.main import app


class FakeRedis:
    def __init__(self):
        self.kv, self.lists, self.sets = {}, {"validation.ui.celery": 3}, {}

    def get(self, k):
        return self.kv.get(k)

    def incr(self, k):
        self.kv[k] = int(self.kv.get(k, 0)) + 1
        return self.kv[k]

    def expire(self, k, s):
        pass

    def llen(self, k):
        return self.lists.get(k, 0)

    def delete(self, k):
        self.lists.pop(k, None)

    def lrange(self, k, a, b):
        n = self.lists.get(k, 0)
        return [json.dumps({"headers": {"id": rid}}).encode() for rid in (["busy", "done", "gone"] + ["x"] * n)[:n]]

    def sadd(self, k, v):
        self.sets.setdefault(k, set()).add(v)

    def srem(self, k, v):
        self.sets.get(k, set()).discard(v)

    def smembers(self, k):
        return {x.encode() for x in self.sets.get(k, set())}


@pytest.fixture
def env(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setenv("BAT3_RUNS_DIR", str(runs))
    monkeypatch.setenv("BAT3_ADMIN_PASSWORD", "correct horse")
    monkeypatch.setenv("BAT3_EXAMPLE_RUNS", '["example"]')
    r = FakeRedis()
    monkeypatch.setattr(security, "_redis", r)
    admin._cache.clear()
    for rid, status in (("example", "success"), ("done", "success"), ("busy", "running")):
        (runs / rid).mkdir()
        (runs / rid / "results.json").write_text(json.dumps(
            {"created_at": "2026-11-10T10:00:00+00:00",
             "pipeline": {"status": status, "finished_at": "2026-11-10T10:05:00+00:00"}}))
    (runs / "example" / "render").mkdir()
    (runs / "example" / "render" / "system.png").write_bytes(b"png")
    return SimpleNamespace(runs=runs, redis=r)


@pytest.fixture
def client():
    return TestClient(app)


def token(client):
    r = client.post("/api/v1/admin/login", json={"password": "correct horse"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_login(env, client, monkeypatch):
    assert client.post("/api/v1/admin/login", json={"password": "nope"}).status_code == 401
    assert client.get("/api/v1/admin/overview").status_code == 401
    assert client.get("/api/v1/admin/overview", headers={"Authorization": "Bearer x.y"}).status_code == 401
    h = token(client)
    monkeypatch.setattr(admin, "_k8s", lambda: (_ for _ in ()).throw(RuntimeError("no cluster")))
    monkeypatch.setattr(admin, "_workers", lambda: {"workers": []})
    body = client.get("/api/v1/admin/overview", headers=h).json()
    assert body["queues"]["queues"][0] == {"name": "validation.ui.celery", "waiting": 3}
    assert body["runs"]["total"] == 3 and body["runs"]["by_status"]["running"] == 1
    assert "error" in body["deployments"]  # one failing section does not break the page


def test_admin_disabled_without_password(env, client, monkeypatch):
    monkeypatch.delenv("BAT3_ADMIN_PASSWORD")
    assert client.post("/api/v1/admin/login", json={"password": ""}).status_code == 503


def test_failed_logins_are_throttled(env, client):
    for _ in range(10):
        client.post("/api/v1/admin/login", json={"password": "nope"})
    r = client.post("/api/v1/admin/login", json={"password": "correct horse"})
    assert r.status_code == 429


def test_password_change_invalidates_sessions(env, client, monkeypatch):
    h = token(client)
    monkeypatch.setenv("BAT3_ADMIN_PASSWORD", "new")
    assert client.post("/api/v1/admin/runs/done/retention", json={"retention": "preserve"},
                       headers=h).status_code == 401


def test_run_actions(env, client):
    h = token(client)
    r = client.post("/api/v1/admin/runs/example/delete", headers=h)
    assert r.status_code == 403
    assert client.post("/api/v1/admin/runs/busy/delete", headers=h).status_code == 400
    r = client.post("/api/v1/admin/runs/done/retention", json={"retention": "preserve"}, headers=h)
    assert r.json()["retention"] == {"policy": "preserve"}
    assert client.post("/api/v1/admin/runs/done/delete", headers=h).status_code == 200
    assert (env.runs / "_expired" / "done" / "results.json").is_file()
    assert client.post("/api/v1/admin/expired/done/restore", headers=h).status_code == 200
    assert (env.runs / "done" / "results.json").is_file()
    assert client.post("/api/v1/admin/runs/%2e%2e/delete", headers=h).status_code in (404, 422)


def test_kubernetes_actions_are_limited(env, client, monkeypatch):
    calls = []
    apps = SimpleNamespace(
        patch_namespaced_deployment_scale=lambda n, ns, body: calls.append(("scale", n, body)),
        patch_namespaced_deployment=lambda n, ns, body: calls.append(("restart", n)))
    core = SimpleNamespace(delete_namespaced_pod=lambda n, ns: calls.append(("pod", n)))
    monkeypatch.setattr(admin, "_k8s", lambda: (apps, core))
    h = token(client)
    assert client.post("/api/v1/admin/deployments/bat3-ui-worker/scale", json={"replicas": 4}, headers=h).status_code == 200
    assert client.post("/api/v1/admin/deployments/bat3-ui-worker/scale", json={"replicas": 99}, headers=h).status_code == 422
    assert client.post("/api/v1/admin/deployments/bat3-ceitec-bat3-api/scale", json={"replicas": 2}, headers=h).status_code == 400
    for other in ("validation-api", "mdpc-dashboard", "pdbcharges-toolkit-2"):
        assert client.post(f"/api/v1/admin/deployments/{other}/restart", headers=h).status_code == 404
        assert client.post(f"/api/v1/admin/pods/{other}-abc/delete", headers=h).status_code == 404
    assert client.post("/api/v1/admin/deployments/bat3-redis/restart", headers=h).status_code == 400
    assert client.post("/api/v1/admin/pods/bat3-redis-x-y/delete", headers=h).status_code == 400
    assert client.post("/api/v1/admin/deployments/bioid-mcp/restart", headers=h).status_code == 200
    assert client.post("/api/v1/admin/pods/bat3-ui-worker-abc-123/delete", headers=h).status_code == 200
    assert calls == [("scale", "bat3-ui-worker", {"spec": {"replicas": 4}}), ("restart", "bioid-mcp"),
                     ("pod", "bat3-ui-worker-abc-123")]


def test_queue_actions(env, client, monkeypatch):
    sent = []
    fake_control = SimpleNamespace(cancel_consumer=lambda q: sent.append(("pause", q)),
                                   add_consumer=lambda q: sent.append(("resume", q)))
    monkeypatch.setattr("src_new.celery_app.celery.control", fake_control, raising=False)
    h = token(client)
    monkeypatch.setattr("src_new.results.results_manager.ResultsManager.finish_run",
                        lambda self, status: sent.append(("finish", self.path.parent.name, status)),
                        raising=False)
    env.redis.lists["validation.ui.celery"] = 3
    (env.runs / "busy" / "results.json").write_text(json.dumps({"pipeline": {"status": "queued"}}))
    out = client.post("/api/v1/admin/queues/validation.ui.celery/purge", headers=h).json()
    assert out["removed"] == 3 and out["cancelled"] == ["busy"]  # done: finished; gone: no run
    assert client.post("/api/v1/admin/queues/celery/pause", headers=h).status_code == 200
    assert client.post("/api/v1/admin/queues/celery/resume", headers=h).status_code == 200
    assert client.post("/api/v1/admin/queues/other/purge", headers=h).status_code == 404
    assert sent == [("finish", "busy", "cancelled"), ("pause", "celery"), ("resume", "celery")]


def test_admin_routes_not_published(client):
    assert not [p for p in client.get("/openapi.json").json()["paths"] if "admin" in p]
