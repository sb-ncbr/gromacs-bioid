"""bughunt BH-004: process isolation for pipeline tasks.

The threads-pool worker could not kill a C-level compute spin per task:
the bond-order ladder hung R01/P24/M13/F13 worker slots forever (the
in-thread guard misses capped/coordinate-polymer fragments). The
pipeline now runs in a forked CHILD process joined with a wall-clock
limit (BAT3_PIPELINE_TIMEOUT_S): on expiry the child is terminated, the
run is marked failed with code "timeout", and the message is ACKED (no
redelivery loop).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

fastapi_testclient = pytest.importorskip("fastapi.testclient")

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src_new.api.tasks import run_pipeline_task


def _mk_run(runs_dir: Path, run_id: str, status: str = "queued") -> Path:
    d = runs_dir / run_id
    (d / "input").mkdir(parents=True, exist_ok=True)
    (d / "results.json").write_text(json.dumps({
        "pipeline": {"name": "BAT3", "run_id": run_id, "status": status},
        "tasks": {}, "artifacts": {}, "warnings": [],
        "critical_errors": [], "events": [], "data": {},
    }))
    return d


class TestChildIsolation:
    def test_timeout_kills_child_and_marks_failed(self, tmp_path, monkeypatch):
        run_dir = _mk_run(tmp_path, "hang1")
        (run_dir / "input" / "structure.pdb").write_text(
            "ATOM      1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\n"
            "END\n")
        monkeypatch.setenv("BAT3_PIPELINE_TIMEOUT_S", "0.2")
        out = run_pipeline_task(
            run_id="hang1",
            input_dir=str(run_dir / "input"),
            results_path=str(run_dir / "results.json"),
        )
        assert out["status"] == "failed"
        assert out["error"] == "timeout"
        payload = json.loads((run_dir / "results.json").read_text())
        assert payload["pipeline"]["status"] == "failed"
        codes = [e["code"] for e in payload["critical_errors"]]
        assert "timeout" in codes
        kinds = [e["kind"] for e in payload["events"]]
        assert "task_timeout" in kinds

    def test_child_failure_reported_through_pipe(self, tmp_path):
        # empty input dir: the child's pipeline fails gracefully at
        # discovery and reports ("failed", message) through the pipe
        run_dir = _mk_run(tmp_path, "empty1")
        out = run_pipeline_task(
            run_id="empty1",
            input_dir=str(run_dir / "input"),
            results_path=str(run_dir / "results.json"),
        )
        assert out["status"] == "failed"
        assert out["error"]  # the child's message, not a parent-side guess
        payload = json.loads((run_dir / "results.json").read_text())
        assert payload["pipeline"]["status"] == "failed"
