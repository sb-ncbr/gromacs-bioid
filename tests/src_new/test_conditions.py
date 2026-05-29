from __future__ import annotations

import json
import logging
from pathlib import Path

from src_new.executor.conditions import (
    ConditionResult,
    ConditionSeverity,
    directory_exists,
    file_exists,
    non_empty_file,
    python_predicate,
)
from src_new.executor.task import StepContext, StepResult
from src_new.results.results_manager import ResultsManager


def _make_context(tmp_path: Path) -> StepContext:
    manager = ResultsManager(tmp_path / "results.json")
    logger = logging.getLogger("tests.src_new.conditions")
    return StepContext(
        results=manager,
        state={},
        working_directory=tmp_path,
        output_directory=tmp_path,
        logger=logger,
    )


def test_existing_file_condition_passes(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    file_path = tmp_path / "file.txt"
    file_path.write_text("hello\n", encoding="utf-8")

    result = file_exists(lambda context, step_result: file_path)(context, None)

    assert isinstance(result, ConditionResult)
    assert result.passed is True


def test_missing_file_condition_fails(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    file_path = tmp_path / "missing.txt"

    result = file_exists(lambda context, step_result: file_path)(context, None)

    assert result.passed is False
    assert result.code == "file_missing"


def test_existing_directory_condition_passes(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    directory = tmp_path / "data"
    directory.mkdir()

    result = directory_exists(lambda context, step_result: directory)(context, None)

    assert result.passed is True


def test_missing_directory_condition_fails(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    directory = tmp_path / "missing_dir"

    result = directory_exists(lambda context, step_result: directory)(context, None)

    assert result.passed is False
    assert result.code == "directory_missing"


def test_non_empty_file_condition_works(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    empty_file = tmp_path / "empty.txt"
    empty_file.write_text("", encoding="utf-8")
    full_file = tmp_path / "full.txt"
    full_file.write_text("x\n", encoding="utf-8")

    empty_result = non_empty_file(lambda context, step_result: empty_file)(context, None)
    full_result = non_empty_file(lambda context, step_result: full_file)(context, None)

    assert empty_result.passed is False
    assert full_result.passed is True


def test_custom_predicate_condition_works(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    result = python_predicate(
        lambda context, step_result: context.output_directory == tmp_path,
        "Output directory matched.",
    )(context, StepResult())

    assert result.passed is True
    assert result.message == "Output directory matched."


def test_failed_conditions_preserve_severity(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    result = python_predicate(
        lambda context, step_result: False,
        "Optional condition failed.",
        severity=ConditionSeverity.WARNING,
        code="optional_condition_failed",
    )(context, None)

    assert result.passed is False
    assert result.severity == ConditionSeverity.WARNING
    assert result.code == "optional_condition_failed"


def test_condition_result_details_are_json_serializable(tmp_path: Path) -> None:
    context = _make_context(tmp_path)
    file_path = tmp_path / "missing.txt"

    result = file_exists(lambda context, step_result: file_path)(context, None)

    assert json.loads(json.dumps(result.details)) == {"path": str(file_path)}
