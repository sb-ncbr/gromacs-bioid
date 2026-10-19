"""API tests for v3.137 Phase C: render-path extension + examples endpoint.

Fixtures build fake run dirs (results.json + render/system.png) directly under
a tmp runs root, monkeypatching get_runs_dir where the handlers read it.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import src_new.api.routes.runs as runs_mod
from src_new.api.routes.runs import (
    _example_candidates,
    get_example_runs,
    parse_run_title,
    router as runs_router,
)


# ---------------------------------------------------------------------------
# pure helpers
# ---------------------------------------------------------------------------

def test_parse_run_title_convention():
    title, desc = parse_run_title("MD-A0017A DNA example>NaCl box equilibrated 100 ns", "abc12345-x")
    assert title == "MD-A0017A DNA example"
    assert desc == "NaCl box equilibrated 100 ns"


def test_parse_run_title_no_separator():
    title, desc = parse_run_title("Plain run name", "abc12345-x")
    assert title == "Plain run name"
    assert desc is None


def test_parse_run_title_missing_name_falls_back_to_id():
    title, desc = parse_run_title(None, "abc12345-x")
    assert title == "abc12345"
    assert desc is None


def _mk_fake_run(runs_dir, run_id, status="success", run_name="T>d", created="2026-10-19T12:00:00",
                 has_png=True):
    d = runs_dir / run_id
    (d / "render").mkdir(parents=True, exist_ok=True)
    if has_png:
        (d / "render" / "system.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    payload = {
        "pipeline": {"status": status, "run_name": run_name},
        "created_at": created,
        "tasks": {}, "artifacts": {}, "warnings": [],
        "critical_errors": [], "events": [],
        "data": {"simulation": {"n_atoms": 12345},
                 "render": {"system_png": str(d / "render" / "system.png"),
                            "segments": {"seg_1_A": {"png": str(d / "render" / "segments" / "seg_1_A.png"),
                                                     "mmcif": str(d / "seg_1_A.mmcif")}}}},
    }
    (d / "results.json").write_text(json.dumps(payload))
    return d


def test_example_candidates_filters_and_orders(tmp_path):
    _mk_fake_run(tmp_path, "r_old", created="2026-10-01")
    _mk_fake_run(tmp_path, "r_new", created="2026-10-19")
    _mk_fake_run(tmp_path, "r_failed", status="failed", created="2026-10-20")
    _mk_fake_run(tmp_path, "r_nopng", has_png=False, created="2026-10-21")
    cand = _example_candidates(tmp_path)
    assert [c["run_id"] for c in cand] == ["r_new", "r_old"]


def test_get_example_runs_explicit_ordering(tmp_path):
    for rid, c in (("a", "2026-10-19"), ("b", "2026-10-10"), ("c", "2026-01-01")):
        _mk_fake_run(tmp_path, rid, created=c)
    picks = get_example_runs(tmp_path, 2, explicit_ids=["c", "b"])
    assert [p["run_id"] for p in picks] == ["c", "b"]


def test_get_example_runs_explicit_then_autofill(tmp_path):
    for rid, c in (("a", "2026-10-19"), ("b", "2026-10-10"), ("z", "2026-11-01")):
        _mk_fake_run(tmp_path, rid, created=c)
    picks = get_example_runs(tmp_path, 2, explicit_ids=["b"])
    assert [p["run_id"] for p in picks] == ["b", "z"]


# ---------------------------------------------------------------------------
# HTTP surface
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("BAT3_EXAMPLE_RUNS", raising=False)


def _client(tmp_path):
    app = FastAPI()
    app.include_router(runs_router, prefix="/api/v1/runs", tags=["runs"])
    os.environ["BAT3_RUNS_DIR"] = str(tmp_path)
    return TestClient(app)


def test_examples_endpoint_shape(tmp_path):
    _mk_fake_run(tmp_path, "r1", run_name="Alpha box>Example sim with ions")
    _mk_fake_run(tmp_path, "r2", run_name="No description", created="2026-10-01")
    _mk_fake_run(tmp_path, "r3", status="failed")
    client = _client(tmp_path)
    resp = client.get("/api/v1/runs/examples?limit=3")
    assert resp.status_code == 200
    ex = resp.json()["examples"]
    assert [e["run_id"] for e in ex] == ["r1", "r2"]
    assert ex[0]["title"] == "Alpha box"
    assert ex[0]["description"] == "Example sim with ions"
    assert ex[1]["description"] is None
    assert ex[0]["image_url"].endswith("/files/r1/render/system.png")


def test_examples_respects_env_override(tmp_path, monkeypatch):
    _mk_fake_run(tmp_path, "newest", created="2026-10-19")
    _mk_fake_run(tmp_path, "chosen", created="2026-01-01", run_name="Curated>Pin me")
    monkeypatch.setenv("BAT3_EXAMPLE_RUNS", '["chosen"]')
    client = _client(tmp_path)
    resp = client.get("/api/v1/runs/examples?limit=3")
    ex = resp.json()["examples"]
    assert ex[0]["run_id"] == "chosen"
    assert ex[1]["run_id"] == "newest"


def test_render_endpoint_reports_pngs_and_atom_count(tmp_path):
    _mk_fake_run(tmp_path, "r1")
    client = _client(tmp_path)
    resp = client.get("/api/v1/runs/r1/render")
    assert resp.status_code == 200
    body = resp.json()
    os_sep = os.sep
    assert body["system_png"].endswith(f"render{os_sep}system.png")
    assert body["segment_pngs"]["seg_1_A"].endswith(f"segments{os_sep}seg_1_A.png")
    assert body["total_atom_count"] == 12345


def test_render_endpoint_tolerates_missing_render_block(tmp_path):
    d = _mk_fake_run(tmp_path, "bare", has_png=False)
    payload = json.loads((d / "results.json").read_text())
    payload["data"] = {}
    (d / "results.json").write_text(json.dumps(payload))
    client = _client(tmp_path)
    resp = client.get("/api/v1/runs/bare/render")
    assert resp.status_code == 200
    body = resp.json()
    assert body["system_png"] is None
    assert body["segment_pngs"] == {}
    assert body["total_atom_count"] is None
