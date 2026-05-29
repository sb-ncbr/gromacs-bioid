from __future__ import annotations

from pathlib import Path

from src_new import (
    ConditionSeverity,
    PipelineExecutor,
    ResultsManager,
    Task,
    TaskContext,
    TaskResult,
    TaskStatus,
    file_exists,
)


def test_root_package_exports_core_backbone_api(tmp_path: Path) -> None:
    results_path = tmp_path / "results.json"
    input_file = tmp_path / "input.txt"
    input_file.write_text("demo\n", encoding="utf-8")

    def check_input(context: TaskContext) -> TaskResult:
        return TaskResult(summary={"checked": True})

    task = Task(
        task_id="check_input",
        name="Check Input",
        handler=check_input,
        preconditions=(file_exists(lambda context, result: input_file),),
    )

    manager = ResultsManager(results_path, pipeline_name="public_api_test")
    executor = PipelineExecutor(steps=[task], results_manager=manager, pipeline_name="public_api_test")
    context = executor.run(input_kind="pdb_mmcif", input_files={"structure": input_file})

    assert isinstance(context, TaskContext)
    assert manager.get_task_status("check_input") == TaskStatus.SUCCESS
    assert ConditionSeverity.WARNING.value == "warning"


def test_results_manager_task_oriented_methods_work(tmp_path: Path) -> None:
    manager = ResultsManager(tmp_path / "results.json")
    manager.start_run(task_definitions=[{"task_id": "prepare", "name": "Prepare"}], input_kind="gromacs")
    manager.start_task("prepare")
    manager.finish_task(task_id="prepare", status=TaskStatus.SUCCESS, summary={"ok": True})

    payload = manager.as_dict()
    assert payload["pipeline"]["input_kind"] == "gromacs"
    assert payload["tasks"]["prepare"]["status"] == "success"
