"""Tests for the NFS-truth settlement helpers in queue_processor.

The janitor (settle_by_results_truth) must:
  - parse the stage map from a (potentially huge) results.json via tail-read,
  - settle completed only when EVERY stage is success/skipped,
  - skip everything else (fresh files, mid-run, torn writes, missing files,
    missing run links) without raising.
"""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import queue_processor as qp


def _results_payload(stage_statuses: dict) -> dict:
    tasks = {name: {"name": name, "status": st, "artifacts": []}
             for name, st in stage_statuses.items()}
    return {
        "artifacts": [], "created_at": "x", "critical_errors": [],
        "data": {"pad": "y" * 2048}, "events": [], "pipeline": {},
        "schema_version": 1, "tasks": tasks, "updated_at": "x", "warnings": [],
    }


def _write(tmp_path, payload: dict, name: str = "results.json") -> str:
    p = tmp_path / name
    p.write_text(json.dumps(payload))
    return str(p)


class TestTailParser:
    def test_all_success_parsed(self, tmp_path):
        path = _write(tmp_path, _results_payload(
            {"discover_input": "success", "load_simulation": "success",
             "generate_signatures": "success", "identify_molecules": "skipped",
             "verify_results": "success", "export_results": "success"}))
        stages = qp._read_results_stage_status(path)
        assert stages is not None
        assert set(stages.values()) == {"success", "skipped"}

    def test_running_stage_visible(self, tmp_path):
        path = _write(tmp_path, _results_payload(
            {"discover_input": "success", "generate_signatures": "running",
             "verify_results": "pending"}))
        stages = qp._read_results_stage_status(path)
        assert stages == {"discover_input": "success",
                          "generate_signatures": "running",
                          "verify_results": "pending"}

    def test_torn_tail_returns_none(self, tmp_path):
        path = tmp_path / "results.json"
        path.write_text('{"data": {"x": 1}, "tasks": {"a": {"status": "success"')
        assert qp._read_results_stage_status(str(path)) is None

    def test_no_tasks_returns_none(self, tmp_path):
        path = tmp_path / "results.json"
        path.write_text(json.dumps({"data": {"x": 1}}))
        assert qp._read_results_stage_status(str(path)) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert qp._read_results_stage_status(str(tmp_path / "nope.json")) is None


class TestSettleByResultsTruth:
    def _fake_item(self, entry_id: int, item_id: int = 1, started_at=None):
        item = MagicMock()
        item.id = item_id
        item.entry_id = entry_id
        item.status = "processing"
        item.batch_id = None
        item.started_at = started_at
        return item

    def _old_dt(self, seconds_ago: int):
        from datetime import datetime, timedelta, timezone
        return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=seconds_ago)

    def test_settles_all_success(self, tmp_path):
        (tmp_path / "42").mkdir()
        path = _write(tmp_path / "42", _results_payload(
            {"discover_input": "success", "load_simulation": "success",
             "repair_topology": "skipped", "generate_signatures": "success",
             "identify_molecules": "success", "verify_results": "success",
             "export_results": "success"}))
        started = self._old_dt(7200)
        recent = started.timestamp() + 3600  # file written during this attempt
        os.utime(path, (recent, recent))

        item = self._fake_item(42, started_at=started)
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = [item]

        run = MagicMock(); run.id = 7; run.celery_task_id = "x"
        with patch.object(qp, "RESULTS_MIN_AGE_S", 0), \
             patch.object(qp, "RESULTS_ROOT", str(tmp_path)), \
             patch.object(qp, "_resolve_run_for_queue_item", return_value=run), \
             patch.object(qp, "_settle_queue_item") as settle_mock, \
             patch.object(qp, "_update_batch_counters"), \
             patch.object(qp, "_log_activity_safe"):
            n = qp.settle_by_results_truth(db)
        assert n == 1
        assert settle_mock.call_count == 1
        assert settle_mock.call_args[0][3] is True

    def test_skips_fresh_file(self, tmp_path):
        (tmp_path / "43").mkdir()
        _write(tmp_path / "43", _results_payload(
            {"a": "success", "b": "success"}))  # mtime = now

        item = self._fake_item(43, started_at=self._old_dt(7200))
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = [item]

        run = MagicMock()
        with patch.object(qp, "RESULTS_MIN_AGE_S", 900), \
             patch.object(qp, "RESULTS_ROOT", str(tmp_path)), \
             patch.object(qp, "_resolve_run_for_queue_item", return_value=run), \
             patch.object(qp, "_settle_queue_item") as settle_mock:
            n = qp.settle_by_results_truth(db)
        assert n == 0
        assert settle_mock.call_count == 0

    def test_skips_stale_artifact(self, tmp_path):
        """Old all-success artifact predating the current attempt -> no settle."""
        (tmp_path / "44").mkdir()
        path = _write(tmp_path / "44", _results_payload(
            {"a": "success", "b": "success"}))
        started = self._old_dt(3600)
        ancient = started.timestamp() - 86400  # file from yesterday's cycle
        os.utime(path, (ancient, ancient))

        item = self._fake_item(44, started_at=started)
        db = MagicMock()
        db.query.return_value.filter.return_value.filter.return_value \
            .order_by.return_value.limit.return_value.all.return_value = [item]

        run = MagicMock()
        with patch.object(qp, "RESULTS_MIN_AGE_S", 0), \
             patch.object(qp, "RESULTS_ROOT", str(tmp_path)), \
             patch.object(qp, "_resolve_run_for_queue_item", return_value=run), \
             patch.object(qp, "_settle_queue_item") as settle_mock:
            n = qp.settle_by_results_truth(db)
        assert n == 0
        assert settle_mock.call_count == 0

    def test_disabled_flag_short_circuits(self):
        with patch.object(qp, "RESULTS_TRUTH_ENABLED", False):
            assert qp.settle_by_results_truth(MagicMock()) == 0
