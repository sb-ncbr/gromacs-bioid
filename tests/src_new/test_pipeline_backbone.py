from __future__ import annotations

import json
from pathlib import Path

import pytest

from src_new.executor.conditions import (
    ConditionSeverity,
    artifact_file_exists,
    context_key_exists,
    directory_exists,
    non_empty_file,
    python_predicate,
    result_is_not_none,
)
from src_new.executor.errors import CriticalStepError, PostconditionFailedError
from src_new.executor.executor import PipelineExecutor
from src_new.executor.task import PipelineStep, StepResult, Task
from src_new.results.results_manager import ResultsManager


def test_pipeline_runs_with_prerequisites_and_postconditions(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    output_path = tmp_path / "outputs"
    manager = ResultsManager(results_path)

    def prepare_inputs(context):
        context.record_data("inputs/source_kind", "pdb")
        return StepResult(
            payload={"source_kind": "pdb"},
            summary={"source_kind": "pdb"},
            context_updates={"input_bundle": {"source_kind": "pdb"}},
        )

    def export_report(context):
        report_path = context.output_directory / "report.txt"
        report_path.write_text("annotation-ready\n", encoding="utf-8")
        context.add_artifact(report_path, description="Step report")
        return StepResult(
            payload={"report_path": str(report_path)},
            summary={"report_created": True},
            context_updates={"report_path": str(report_path)},
        )

    steps = [
        PipelineStep(step_id="prepare", name="Prepare Inputs", handler=prepare_inputs),
        PipelineStep(
            step_id="report",
            name="Export Report",
            handler=export_report,
            requires_steps=("prepare",),
            preconditions=(context_key_exists("input_bundle"),),
            postconditions=(
                context_key_exists("report_path"),
                result_is_not_none(),
                artifact_file_exists(lambda context, result: context.require_value("report_path")),
            ),
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager, pipeline_name="bioid_test")
    context = executor.run(output_directory=output_path)

    assert context.get_value("input_bundle") == {"source_kind": "pdb"}
    assert (output_path / "report.txt").exists()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["pipeline"]["status"] == "success"
    assert payload["tasks"]["prepare"]["status"] == "success"
    assert payload["tasks"]["report"]["status"] == "success"
    assert payload["data"]["inputs"]["source_kind"] == "pdb"
    artifact = next(iter(payload["artifacts"].values()))
    assert artifact["path"].endswith("report.txt")


def test_warning_step_allows_pipeline_to_continue(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def warn_step(context):
        context.add_warning("missing_optional_metadata", "Optional metadata is unavailable.")
        return StepResult(summary={"warning_emitted": True})

    def downstream_step(context):
        context.record_data("pipeline/downstream_ran", True)
        return StepResult(summary={"downstream_ran": True})

    steps = [
        PipelineStep(step_id="warn", name="Warn", handler=warn_step),
        PipelineStep(step_id="downstream", name="Downstream", handler=downstream_step, requires_steps=("warn",)),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    executor.run()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["pipeline"]["status"] == "success"
    assert payload["tasks"]["warn"]["status"] == "warning"
    assert payload["tasks"]["downstream"]["status"] == "success"
    assert payload["warnings"][0]["code"] == "missing_optional_metadata"


def test_critical_error_stops_pipeline_and_skips_remaining_steps(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def fail_step(context):
        raise CriticalStepError("critical failure", details={"resolver": "demo"})

    def should_not_run(context):
        return StepResult(summary={"ran": True})

    steps = [
        PipelineStep(step_id="fail", name="Fail", handler=fail_step),
        PipelineStep(step_id="after", name="After", handler=should_not_run, requires_steps=("fail",)),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    with pytest.raises(CriticalStepError):
        executor.run()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["pipeline"]["status"] == "failed"
    assert payload["tasks"]["fail"]["status"] == "failed"
    assert payload["tasks"]["after"]["status"] == "skipped"
    assert payload["critical_errors"][0]["code"] == "critical_step_error"


def test_postcondition_failure_is_recorded_and_raised(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def broken_step(context):
        return StepResult(summary={"created": False})

    steps = [
        PipelineStep(
            step_id="broken",
            name="Broken",
            handler=broken_step,
            postconditions=(artifact_file_exists(lambda context, result: context.output_directory / "missing.txt"),),
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    with pytest.raises(PostconditionFailedError):
        executor.run(output_directory=tmp_path / "outputs")

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["pipeline"]["status"] == "failed"
    assert payload["tasks"]["broken"]["status"] == "failed"
    assert payload["critical_errors"][0]["code"] == "artifact_missing"


def test_results_manager_supports_explicit_none_default(tmp_path: Path) -> None:
    manager = ResultsManager(tmp_path / "results.json")
    manager.set_data("inputs/type", "mmcif")

    assert manager.get_data("inputs/type") == "mmcif"
    assert manager.get_data("inputs/missing", default=None) is None
    assert manager.data_exists("inputs/type") is True
    assert manager.data_exists("inputs/missing") is False


def test_structured_logs_are_written_to_results_json(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def log_step(context):
        context.logger.info("step started")
        return StepResult(summary={"logged": True})

    steps = [PipelineStep(step_id="log", name="Log", handler=log_step)]
    executor = PipelineExecutor(steps=steps, results_manager=manager)
    executor.run()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    log_events = [event for event in payload["events"] if event["kind"] == "log"]
    assert log_events[0]["message"] == "step started"
    assert log_events[0]["task_id"] == "log"


def test_warning_postcondition_allows_pipeline_to_continue(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def prepare(context):
        return StepResult(summary={"prepared": True})

    def export_optional(context):
        return StepResult(summary={"optional_export": "skipped"})

    def finalize(context):
        context.record_data("pipeline/finalized", True)
        return StepResult(summary={"finalized": True})

    steps = [
        PipelineStep(step_id="prepare", name="Prepare", handler=prepare),
        PipelineStep(
            step_id="optional",
            name="Optional Export",
            handler=export_optional,
            requires_steps=("prepare",),
            postconditions=(
                directory_exists(
                    lambda context, result: context.output_directory / "missing_optional_dir",
                    severity=ConditionSeverity.WARNING,
                    code="optional_directory_missing",
                ),
            ),
        ),
        PipelineStep(step_id="finalize", name="Finalize", handler=finalize, requires_steps=("optional",)),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    executor.run(output_directory=tmp_path / "outputs")

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["pipeline"]["status"] == "success"
    assert payload["tasks"]["optional"]["status"] == "warning"
    assert payload["tasks"]["finalize"]["status"] == "success"
    assert payload["warnings"][0]["code"] == "optional_directory_missing"


def test_non_empty_file_postcondition_and_task_alias(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def write_file(context):
        output_file = context.output_directory / "summary.txt"
        output_file.write_text("done\n", encoding="utf-8")
        context.add_artifact(output_file, description="Summary file")
        return StepResult(
            payload=str(output_file),
            summary={"file_written": True},
            context_updates={"summary_file": str(output_file)},
        )

    steps = [
        Task(
            step_id="write",
            name="Write",
            handler=write_file,
            postconditions=(non_empty_file(lambda context, result: context.require_value("summary_file")),),
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    executor.run(output_directory=tmp_path / "outputs")

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["tasks"]["write"]["status"] == "success"
    artifact = next(iter(payload["artifacts"].values()))
    assert artifact["path"].endswith("summary.txt")


def test_python_predicate_precondition_can_warn_and_continue(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def run_with_soft_precondition(context):
        context.record_data("pipeline/soft_check_ran", True)
        return StepResult(summary={"ran": True})

    steps = [
        PipelineStep(
            step_id="soft",
            name="Soft Check",
            handler=run_with_soft_precondition,
            preconditions=(
                python_predicate(
                    lambda context, result: False,
                    "Optional precondition did not pass.",
                    severity=ConditionSeverity.WARNING,
                    code="optional_precondition_failed",
                    details_factory=lambda context, result: {"source": "test"},
                ),
            ),
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    executor.run()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["pipeline"]["status"] == "success"
    assert payload["tasks"]["soft"]["status"] == "warning"
    assert payload["warnings"][0]["code"] == "optional_precondition_failed"
    assert payload["warnings"][0]["details"]["condition_stage"] == "precondition"


def test_custom_condition_result_code_is_recorded_for_critical_failure(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def broken_step(context):
        return StepResult(summary={"ran": True})

    steps = [
        PipelineStep(
            step_id="broken",
            name="Broken",
            handler=broken_step,
            postconditions=(
                python_predicate(
                    lambda context, result: False,
                    "Custom critical condition failed.",
                    code="custom_condition_failed",
                ),
            ),
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    with pytest.raises(PostconditionFailedError):
        executor.run()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["critical_errors"][0]["code"] == "custom_condition_failed"
