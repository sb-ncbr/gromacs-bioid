"""bughunt BH-006: /runs/{id}/queue reported failed runs as "queued".

A run with a TERMINAL pipeline.status but no started_at (reaped
worker_lost, load-failed before start) was reported "queued" and
counted in other runs' `ahead`. Terminal status now wins.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.src_new.api.test_api import client  # noqa: F401  (shared fixture)


def _write_results(run_dir: Path, status: str, started_at=None):
    import json
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "results.json").write_text(json.dumps({
        "pipeline": {"status": status, "started_at": started_at},
    }))


class TestQueueStateForFailedRuns:
    def test_failed_without_started_is_done(self, client: TestClient, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        _write_results(tmp_path / "r1", "failed", started_at=None)
        response = client.get("/runs/r1/queue")
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "done"
        assert body["position"] is None
        assert body["ahead"] is None

    def test_queued_run_reports_position_and_excludes_terminal(
            self, client: TestClient, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        # two genuinely queued runs (created order) + one failed-no-start
        import json
        for rid, created in (("q1", "2026-01-01T00:00:00Z"),
                             ("q2", "2026-01-02T00:00:00Z")):
            d = tmp_path / rid
            d.mkdir(parents=True)
            (d / "results.json").write_text(json.dumps({
                "pipeline": {"status": "queued", "started_at": None},
                "created_at": created,
            }))
        _write_results(tmp_path / "dead", "failed", started_at=None)

        body = client.get("/runs/q2/queue").json()
        assert body["state"] == "queued"
        assert body["position"] == 2
        assert body["ahead"] == 1  # only q1 ahead, NOT the dead run

    def test_running_still_running(self, client: TestClient, tmp_path, monkeypatch):
        monkeypatch.setenv("BAT3_RUNS_DIR", str(tmp_path))
        _write_results(tmp_path / "r2", "running",
                       started_at="2026-01-01T00:00:00Z")
        body = client.get("/runs/r2/queue").json()
        assert body["state"] == "running"
