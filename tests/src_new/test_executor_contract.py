from __future__ import annotations

import json
from pathlib import Path

import pytest

from src_new.executor.conditions import ConditionSeverity, context_key_exists, file_exists
from src_new.executor.errors import CriticalStepError, PostconditionFailedError, PreconditionFailedError
from src_new.executor.executor import PipelineExecutor
from src_new.executor.task import PipelineStep, StepResult
from src_new.results.results_manager import ResultsManager


def test_successful_task_runs_and_is_marked_success(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def write_output(context):
        output = context.output_directory / "done.txt"
        output.write_text("ok\n", encoding="utf-8")
        return StepResult(summary={"written": True})

    steps = [
        PipelineStep(
            step_id="write",
            name="Write",
            handler=write_output,
            output_paths=("done.txt",),
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    executor.run(output_directory=tmp_path / "outputs")

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["tasks"]["write"]["status"] == "success"
    assert next(iter(payload["artifacts"].values()))["path"].endswith("done.txt")


def test_task_with_missing_critical_precondition_does_not_run(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)
    ran = {"value": False}

    def should_not_run(context):
        ran["value"] = True
        return StepResult(summary={"ran": True})

    steps = [
        PipelineStep(
            step_id="guarded",
            name="Guarded",
            handler=should_not_run,
            preconditions=(context_key_exists("missing_input"),),
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    with pytest.raises(PreconditionFailedError):
        executor.run()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert ran["value"] is False
    assert payload["tasks"]["guarded"]["status"] == "failed"
    assert payload["critical_errors"][0]["code"] == "context_key_missing"


def test_task_with_warning_precondition_may_continue(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def run_anyway(context):
        context.record_data("pipeline/continued", True)
        return StepResult(summary={"continued": True})

    steps = [
        PipelineStep(
            step_id="soft_guarded",
            name="Soft Guarded",
            handler=run_anyway,
            preconditions=(
                context_key_exists(
                    "optional_input",
                    severity=ConditionSeverity.WARNING,
                    code="optional_input_missing",
                ),
            ),
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    executor.run()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["tasks"]["soft_guarded"]["status"] == "warning"
    assert payload["warnings"][0]["code"] == "optional_input_missing"


def test_task_exception_is_recorded_as_critical_and_stops_pipeline(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def explode(context):
        raise ValueError("boom")

    def after(context):
        return StepResult(summary={"ran": True})

    steps = [
        PipelineStep(step_id="explode", name="Explode", handler=explode),
        PipelineStep(step_id="after", name="After", handler=after, requires_steps=("explode",)),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    with pytest.raises(ValueError):
        executor.run()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["tasks"]["explode"]["status"] == "failed"
    assert payload["tasks"]["after"]["status"] == "skipped"
    assert payload["critical_errors"][0]["code"] == "unhandled_exception"


def test_warning_inside_task_does_not_stop_next_task(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def warn(context):
        context.add_warning("soft_issue", "warning emitted")
        return StepResult(summary={"warned": True})

    def after(context):
        return StepResult(summary={"ran": True})

    steps = [
        PipelineStep(step_id="warn", name="Warn", handler=warn),
        PipelineStep(step_id="after", name="After", handler=after, requires_steps=("warn",)),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    executor.run()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["tasks"]["warn"]["status"] == "warning"
    assert payload["tasks"]["after"]["status"] == "success"


def test_critical_error_inside_task_stops_following_tasks(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def fail_from_context(context):
        context.fail("inside_task_error", "task reported critical failure", {"source": "handler"})

    def after(context):
        return StepResult(summary={"ran": True})

    steps = [
        PipelineStep(step_id="fail", name="Fail", handler=fail_from_context),
        PipelineStep(step_id="after", name="After", handler=after, requires_steps=("fail",)),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    with pytest.raises(CriticalStepError):
        executor.run()

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["tasks"]["fail"]["status"] == "failed"
    assert payload["tasks"]["after"]["status"] == "skipped"
    assert payload["critical_errors"][0]["code"] == "inside_task_error"


def test_postcondition_failure_is_recorded(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    manager = ResultsManager(results_path)

    def no_output(context):
        return StepResult(summary={"ok": False})

    steps = [
        PipelineStep(
            step_id="validate",
            name="Validate",
            handler=no_output,
            postconditions=(file_exists(lambda context, result: context.output_directory / "missing.txt"),),
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    with pytest.raises(PostconditionFailedError):
        executor.run(output_directory=tmp_path / "outputs")

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["tasks"]["validate"]["status"] == "failed"
    assert payload["critical_errors"][0]["code"] == "file_missing"


def test_skip_if_outputs_exist_works(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    output_directory = tmp_path / "outputs"
    output_directory.mkdir()
    existing_output = output_directory / "ready.txt"
    existing_output.write_text("present\n", encoding="utf-8")
    manager = ResultsManager(results_path)
    ran = {"value": False}

    def should_be_skipped(context):
        ran["value"] = True
        return StepResult(summary={"ran": True})

    steps = [
        PipelineStep(
            step_id="cached",
            name="Cached",
            handler=should_be_skipped,
            output_paths=("ready.txt",),
            skip_if_output_exists=True,
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    executor.run(output_directory=output_directory)

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert ran["value"] is False
    assert payload["tasks"]["cached"]["status"] == "skipped"
    artifact = next(iter(payload["artifacts"].values()))
    assert artifact["path"] == str(existing_output)


def test_integration_mini_pipeline_records_outputs_and_events(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    output_directory = tmp_path / "outputs"
    manager = ResultsManager(results_path)
    declared_input = output_directory / "input.txt"

    def create_input(context):
        input_path = context.output_directory / "input.txt"
        input_path.write_text("alpha\n", encoding="utf-8")
        return StepResult(
            summary={"created": True},
            context_updates={"input_path": str(input_path)},
        )

    def process_input(context):
        source = Path(context.require_value("input_path"))
        output_path = context.output_directory / "output.txt"
        output_path.write_text(source.read_text(encoding="utf-8").upper(), encoding="utf-8")
        return StepResult(
            summary={"processed": True},
            context_updates={"output_path": str(output_path)},
        )

    def validate_output(context):
        output_path = Path(context.require_value("output_path"))
        assert output_path.exists()
        return StepResult(summary={"validated": True})

    steps = [
        PipelineStep(
            step_id="create_input",
            name="Create Input",
            handler=create_input,
            output_paths=("input.txt",),
        ),
        PipelineStep(
            step_id="process_input",
            name="Process Input",
            handler=process_input,
            requires_steps=("create_input",),
            output_paths=("output.txt",),
        ),
        PipelineStep(
            step_id="validate_output",
            name="Validate Output",
            handler=validate_output,
            requires_steps=("process_input",),
            postconditions=(file_exists(lambda context, result: Path(context.require_value("output_path"))),),
        ),
    ]

    executor = PipelineExecutor(steps=steps, results_manager=manager)
    executor.run(
        output_directory=output_directory,
        input_kind="pdb_mmcif",
        input_files={"structure": declared_input},
        run_metadata={"demo": True},
    )

    payload = json.loads(results_path.read_text(encoding="utf-8"))
    assert payload["tasks"]["create_input"]["status"] == "success"
    assert payload["tasks"]["process_input"]["status"] == "success"
    assert payload["tasks"]["validate_output"]["status"] == "success"
    assert payload["pipeline"]["input_kind"] == "pdb_mmcif"
    assert payload["pipeline"]["input_files"]["structure"] == str(declared_input)
    assert payload["pipeline"]["metadata"]["demo"] is True
    assert any(artifact["path"].endswith("input.txt") for artifact in payload["artifacts"].values())
    assert any(artifact["path"].endswith("output.txt") for artifact in payload["artifacts"].values())
    assert payload["critical_errors"] == []
    assert manager.has_critical_errors() is False
    assert payload["events"]
