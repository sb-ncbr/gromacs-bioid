from __future__ import annotations

import json
from pathlib import Path

import pytest

from src_new.results.results_manager import ResultsManager
from src_new.results.schema import StepStatus
from src_new.utils import file_utils


def test_results_manager_creates_valid_file_and_parent_directories(tmp_path: Path) -> None:
    results_path = tmp_path / "nested" / "run" / "results.json"

    manager = ResultsManager(results_path, pipeline_name="bioid_test")
    payload = manager.as_dict()

    assert results_path.exists()
    assert payload["schema_version"] == "0.1.0"
    assert payload["pipeline"]["name"] == "bioid_test"
    assert payload["pipeline"]["status"] == "created"
    assert payload["tasks"] == {}
    assert payload["artifacts"] == {}
    assert payload["warnings"] == []
    assert payload["critical_errors"] == []
    assert payload["events"] == []
    assert payload["data"] == {}


def test_results_manager_loads_existing_content_and_preserves_unknown_keys(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    existing_payload = {
        "schema_version": "0.1.0",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "pipeline": {
            "name": "existing_pipeline",
            "status": "created",
            "input_kind": "pdb",
            "input_files": {"structure": "input.pdb"},
            "metadata": {"seed": 7},
        },
        "tasks": {},
        "artifacts": {},
        "warnings": [],
        "critical_errors": [],
        "events": [],
        "data": {"previous": {"value": 1}},
        "custom_block": {"preserve_me": True},
    }
    results_path.write_text(json.dumps(existing_payload), encoding="utf-8")

    manager = ResultsManager(results_path)
    manager.set_data("new/value", 2)

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["pipeline"]["name"] == "existing_pipeline"
    assert payload["data"]["previous"]["value"] == 1
    assert payload["data"]["new"]["value"] == 2
    assert payload["custom_block"]["preserve_me"] is True


def test_results_manager_rejects_non_object_root(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    results_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match="root must be a JSON object"):
        ResultsManager(results_path)


def test_results_manager_rejects_invalid_json_syntax(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    results_path.write_text("{invalid json", encoding="utf-8")

    with pytest.raises(ValueError, match="not valid JSON"):
        ResultsManager(results_path)


def test_results_manager_repairs_missing_optional_sections(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    partial_payload = {
        "schema_version": "0.1.0",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "pipeline": {"name": "partial", "status": "created", "metadata": {}},
    }
    results_path.write_text(json.dumps(partial_payload), encoding="utf-8")

    manager = ResultsManager(results_path)
    payload = manager.as_dict()

    assert payload["tasks"] == {}
    assert payload["artifacts"] == {}
    assert payload["warnings"] == []
    assert payload["critical_errors"] == []
    assert payload["events"] == []
    assert payload["data"] == {}


def test_results_manager_writes_atomically(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)
    real_replace = file_utils.os.replace
    captured: dict[str, str] = {}

    def tracking_replace(src: str, dst: str) -> None:
        captured["src"] = src
        captured["dst"] = dst
        real_replace(src, dst)

    monkeypatch.setattr(file_utils.os, "replace", tracking_replace)
    manager.set_data("demo/value", 1)

    assert str(captured["dst"]) == str(results_path)
    assert str(captured["src"]) != str(results_path)
    assert Path(captured["src"]).parent == results_path.parent
    assert Path(captured["src"]).suffix == ".tmp"


def test_results_manager_stores_paths_as_strings_and_records_task_outputs(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    output_path = tmp_path / "out.txt"
    output_path.write_text("done\n", encoding="utf-8")
    manager = ResultsManager(results_path)
    manager.start_run(step_definitions=[{"step_id": "export", "name": "Export"}])
    artifact_id = manager.add_artifact(step_id="export", path=output_path, description="Output file")

    payload = manager.as_dict()
    assert payload["artifacts"][artifact_id]["path"] == str(output_path)
    assert payload["tasks"]["export"]["artifacts"] == [artifact_id]


def test_results_manager_records_pipeline_metadata_and_input_files(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path, pipeline_name="bioid_test")
    manager.start_run(
        step_definitions=[{"step_id": "prepare", "name": "Prepare"}],
        metadata={"mode": "test"},
        input_kind="pdb",
        input_files={"structure": tmp_path / "input.pdb"},
        working_directory=str(tmp_path),
        output_directory=str(tmp_path / "outputs"),
    )

    payload = manager.as_dict()
    assert payload["pipeline"]["name"] == "bioid_test"
    assert payload["pipeline"]["metadata"]["mode"] == "test"
    assert payload["pipeline"]["metadata"]["working_directory"] == str(tmp_path)
    assert payload["pipeline"]["metadata"]["output_directory"] == str(tmp_path / "outputs")
    assert payload["pipeline"]["input_kind"] == "pdb"
    assert payload["pipeline"]["input_files"]["structure"] == str(tmp_path / "input.pdb")


def test_results_manager_records_task_start_finish_warnings_and_critical_errors(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)
    manager.start_run(step_definitions=[{"step_id": "prepare", "name": "Prepare"}])
    manager.start_step("prepare")
    manager.record_warning(code="demo_warning", message="soft issue", step_id="prepare", details={"count": 1})
    manager.record_error(
        code="demo_error",
        message="hard issue",
        step_id="prepare",
        details={"reason": "failure"},
        critical=True,
        exception_type="RuntimeError",
    )
    manager.finish_step(step_id="prepare", status=StepStatus.FAILED, summary={"ok": False}, context_keys=["bundle"])

    payload = manager.as_dict()
    task = payload["tasks"]["prepare"]
    assert task["started_at"] is not None
    assert task["finished_at"] is not None
    assert task["status"] == "failed"
    assert task["summary"] == {"ok": False}
    assert task["context_keys"] == ["bundle"]
    assert payload["warnings"][0]["code"] == "demo_warning"
    assert payload["critical_errors"][0]["code"] == "demo_error"
    assert manager.has_critical_errors() is True


def test_results_manager_saved_data_is_json_serializable(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)
    manager.start_run(
        step_definitions=[{"step_id": "prepare", "name": "Prepare"}],
        metadata={"path": tmp_path / "demo"},
        input_files={"structure": tmp_path / "input.pdb"},
    )
    manager.set_data("paths/output", tmp_path / "output.dat")

    payload = manager.as_dict()
    json.dumps(payload)
    json.loads(results_path.read_text(encoding="utf-8"))


def test_results_manager_migrates_legacy_shape_on_load(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    legacy_payload = {
        "schema_version": "1.0",
        "run": {
            "pipeline_name": "legacy_pipeline",
            "status": "running",
            "started_at": "2026-01-01T00:00:00+00:00",
            "metadata": {"legacy": True},
        },
        "steps": {
            "prepare": {
                "name": "Prepare",
                "status": "success",
                "requires_steps": [],
                "warnings": [],
                "errors": [],
                "artifacts": [],
                "context_keys": [],
            }
        },
        "logs": [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "level": "INFO",
                "logger": "demo",
                "message": "legacy log",
                "step_id": "prepare",
                "details": {},
            }
        ],
        "errors": [
            {
                "code": "legacy_error",
                "message": "legacy failure",
                "step_id": "prepare",
                "details": {},
                "exception_type": "RuntimeError",
            }
        ],
        "artifacts": [
            {
                "step_id": "prepare",
                "path": "/tmp/file.txt",
                "kind": "file",
                "description": "legacy artifact",
                "metadata": {},
            }
        ],
        "data": {},
    }
    results_path.write_text(json.dumps(legacy_payload), encoding="utf-8")

    manager = ResultsManager(results_path)
    payload = manager.as_dict()

    assert payload["pipeline"]["name"] == "legacy_pipeline"
    assert payload["tasks"]["prepare"]["status"] == "success"
    assert payload["critical_errors"][0]["code"] == "legacy_error"
    assert payload["events"][0]["kind"] == "log"
    assert next(iter(payload["artifacts"].values()))["path"] == "/tmp/file.txt"


# ---------------------------------------------------------------------------
# OQ-2 (ruling 2026-10-05): critical_errors lifecycle semantics
#   requeue(resume) = errors KEPT ; delete+requeue(clean re-run) = errors CLEARED
# ---------------------------------------------------------------------------


def test_oq2_resume_reopen_keeps_critical_errors(tmp_path: Path) -> None:
    """Resume semantic: re-instantiating the manager on an existing
    results.json preserves prior critical_errors (the 'keep them' side)."""
    results_path = tmp_path / "run" / "results.json"
    manager = ResultsManager(results_path, pipeline_name="oq2")
    manager.record_error(code="demo_error", message="first epoch", critical=True)
    manager.finish_run("completed")

    reopened = ResultsManager(results_path, pipeline_name="oq2")
    errors = reopened.as_dict()["critical_errors"]
    assert len(errors) == 1 and errors[0]["code"] == "demo_error"


def test_oq2_clean_rerun_resets_critical_errors(tmp_path: Path) -> None:
    """Clean-re-run semantic: deleting results.json (snapshotted by the
    operator) before requeue yields a fresh payload with empty
    critical_errors (the 'can clear' side)."""
    results_path = tmp_path / "run" / "results.json"
    manager = ResultsManager(results_path, pipeline_name="oq2")
    manager.record_error(code="demo_error", message="first epoch", critical=True)
    manager.finish_run("completed")

    results_path.unlink()  # operator clean-re-run step (after snapshot)
    fresh = ResultsManager(results_path, pipeline_name="oq2")
    payload = fresh.as_dict()
    assert payload["critical_errors"] == []
    assert payload["warnings"] == []
    assert payload["tasks"] == {}
