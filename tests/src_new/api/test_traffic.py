"""Traffic statistics (src_new/api/traffic.py)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src_new.api import security, traffic
from src_new.api.main import app

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)
GEO = {"198.51.100.1": {"country": "CZ", "country_name": "Czechia", "city": "Brno", "lat": 49.2, "lon": 16.6},
       "198.51.100.2": {"country": "DE", "country_name": "Germany", "city": "Berlin", "lat": 52.5, "lon": 13.4}}


@pytest.fixture
def runs(tmp_path, monkeypatch):
    runs = tmp_path / "runs"
    runs.mkdir()
    monkeypatch.setenv("BAT3_RUNS_DIR", str(runs))
    monkeypatch.setenv("BAT3_TRAFFIC", "1")
    monkeypatch.setattr(traffic, "locate", lambda ip: dict(GEO.get(ip or "", {})))
    monkeypatch.setattr(security, "_redis", None)
    traffic._buffer.clear()
    return runs


def rec(kind="request", ip="198.51.100.1", route="/api/v1/runs/{run_id}/verification", status=200,
        method="GET", minutes_ago=10, **kw):
    traffic.record(kind, ip=ip, route=route, status=status, method=method,
                   now=NOW - timedelta(minutes=minutes_ago), **kw)


def test_record_flush_summarize(runs):
    rec("pageview", route="/", referrer="https://www.google.com/search?q=bioid", user_agent="Mozilla Firefox/120")
    rec("pageview", ip="198.51.100.2", route="/runs/:id")
    rec(method="POST", route="/api/v1/runs", client="web")
    rec(method="POST", route="/api/v1/runs", ip="198.51.100.2", client="mcp")
    rec(status=429, method="POST", route="/api/v1/runs")
    rec(status=500)
    rec(minutes_ago=60 * 30)  # outside 24h
    rec("pageview", ip="203.0.113.9", route="/", user_agent="Googlebot/2.1")
    assert traffic.flush() == 8
    s = traffic.summarize("24h", now=NOW)
    t = s["totals"]
    assert (t["visitors"], t["pageviews"], t["runs"], t["rate_limited"], t["errors"]) == (2, 3, 2, 1, 1)
    assert s["runs_by_client"] == {"web": 1, "mcp": 1}
    assert {c["code"]: c["visitors"] for c in s["countries"]} == {"CZ": 1, "DE": 1}
    assert {(p["city"], p["visitors"]) for p in s["places"]} == {("Brno", 1), ("Berlin", 1)}
    assert s["referrers"] == [{"name": "www.google.com", "count": 1}]
    assert s["clients"]["bot"] == 1 and s["bucket"] == "hour"
    assert traffic.summarize("7d", now=NOW)["totals"]["requests"] == 5
    # the address is never written, only its keyed hash
    raw = "".join(p.read_text() for p in (runs / "_traffic").rglob("*.jsonl"))
    assert "198.51.100.1" not in raw and security.ip_hash("198.51.100.1") in raw


def test_prune_keeps_90_days(runs):
    rec(minutes_ago=60 * 24 * 100)
    rec(minutes_ago=5)
    traffic.flush()
    assert traffic.prune(now=NOW) == [(NOW - timedelta(days=100)).strftime("%Y-%m-%d")]
    assert traffic.summarize("all", now=NOW)["totals"]["requests"] == 1


def test_page_routes():
    assert traffic.page_route("/runs/1c2a4d4b-94cb?x=1") == "/runs/:id"
    assert traffic.page_route("/admin") is None
    assert traffic.page_route("/documentation/rest-api/") == "/documentation/rest-api/"
    assert traffic.page_route("/whatever") == "(other)"


def test_polling_is_not_recorded():
    assert not traffic.worth_recording("GET", "/api/v1/runs/{run_id}/status", 200, "web")
    assert traffic.worth_recording("GET", "/api/v1/runs/{run_id}/status", 404, "web")
    assert traffic.worth_recording("GET", "/api/v1/runs/{run_id}/status", 200, "mcp")
    assert traffic.worth_recording("POST", "/api/v1/runs", 200, "web")
    assert not traffic.worth_recording("GET", "/api/v1/admin/overview", 200, "web")


def test_middleware_and_beacon(runs, monkeypatch):
    monkeypatch.setattr("src_new.api.routes.runs.run_pipeline_task.apply_async", lambda *a, **k: None)
    c = TestClient(app)
    h = {"X-Forwarded-For": "198.51.100.1", "X-BioID-Client": "web"}
    c.get("/api/v1/runs/nope/verification", headers=h)
    c.get("/api/v1/runs/nope/status", headers=h)  # 404: recorded
    c.post("/api/v1/events/pageview", json={"path": "/runs/abc", "referrer": "https://x.org/a"}, headers=h)
    c.post("/api/v1/events/pageview", json={"path": "/"}, headers={**h, "DNT": "1"})
    c.post("/api/v1/events/pageview", json={"path": "/admin"}, headers=h)
    traffic.flush()
    events = [json.loads(l) for p in (runs / "_traffic").rglob("*.jsonl") for l in p.read_text().splitlines()]
    assert sorted((e["kind"], e["route"], e.get("status")) for e in events) == [
        ("pageview", "/runs/:id", 200),
        ("request", "/api/v1/runs/{run_id}/status", 404),
        ("request", "/api/v1/runs/{run_id}/verification", 404),
    ]
    assert all(e["client"] == "web" and e["country"] == "CZ" for e in events)


def test_geoip_refresh_never_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("BAT3_GEOIP_REFRESH", "1")
    monkeypatch.setenv("BAT3_GEOIP_DB", "/proc/forbidden/geoip/x.mmdb")
    monkeypatch.setattr(security, "_redis", None)
    assert traffic.refresh_geoip() is None


def test_admin_traffic_endpoint(runs, monkeypatch):
    from src_new.api import admin
    monkeypatch.setenv("BAT3_ADMIN_PASSWORD", "pw")
    admin._cache.clear()
    c = TestClient(app)
    tok = c.post("/api/v1/admin/login", json={"password": "pw"}).json()["token"]
    rec("pageview", route="/", minutes_ago=1)
    traffic.flush()
    r = c.get("/api/v1/admin/traffic?window=1h", headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200 and r.json()["window"] == "1h"
    assert c.get("/api/v1/admin/traffic?window=5y", headers={"Authorization": f"Bearer {tok}"}).status_code == 422
    assert c.get("/api/v1/admin/traffic").status_code == 401


def test_locate_with_a_real_database(monkeypatch):
    db = Path("/home/tomsko/.claude/jobs/ece11c6f/tmp/geo/city.mmdb")
    if not db.is_file():
        pytest.skip("no local DB-IP database")
    monkeypatch.setenv("BAT3_GEOIP_DB", str(db))
    loc = traffic.locate("147.251.6.218")
    assert loc["country"] == "CZ" and round(loc["lat"]) == 49
    assert traffic.locate("10.0.0.1") == {"country": "internal"}
    assert traffic.locate("not an ip") == {}
