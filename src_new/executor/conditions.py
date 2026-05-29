from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Any


class ConditionSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"


@dataclass
class ConditionResult:
    passed: bool
    message: str = ""
    severity: ConditionSeverity = ConditionSeverity.CRITICAL
    code: str = ""
    details: dict = field(default_factory=dict)


def _to_path(p) -> Path:
    """Convert to Path if needed."""
    if isinstance(p, Path):
        return p
    return Path(p)


def file_exists(path_factory: Callable[[Any, Any], Path]):
    """Returns a condition that checks if a file exists."""
    def condition(context, step_result) -> ConditionResult:
        path = _to_path(path_factory(context, step_result))
        if path.exists():
            return ConditionResult(passed=True)
        return ConditionResult(
            passed=False,
            message=f"File does not exist: {path}",
            code="file_missing",
            details={"path": str(path)}
        )
    return condition


def directory_exists(path_factory: Callable[[Any, Any], Path], 
                     severity: ConditionSeverity = ConditionSeverity.CRITICAL,
                     code: str = "directory_missing"):
    """Returns a condition that checks if a directory exists."""
    def condition(context, step_result) -> ConditionResult:
        path = _to_path(path_factory(context, step_result))
        if path.is_dir():
            return ConditionResult(passed=True)
        return ConditionResult(
            passed=False,
            message=f"Directory does not exist: {path}",
            severity=severity,
            code=code,
            details={"path": str(path)}
        )
    return condition


def non_empty_file(path_factory: Callable[[Any, Any], Path]):
    """Returns a condition that checks if a file exists and is non-empty."""
    def condition(context, step_result) -> ConditionResult:
        path = _to_path(path_factory(context, step_result))
        if not path.exists():
            return ConditionResult(
                passed=False,
                message=f"File does not exist: {path}",
                code="file_empty_or_missing",
                details={"path": str(path)}
            )
        if path.stat().st_size == 0:
            return ConditionResult(
                passed=False,
                message=f"File is empty: {path}",
                code="file_empty_or_missing",
                details={"path": str(path)}
            )
        return ConditionResult(passed=True)
    return condition


def artifact_file_exists(path_factory: Callable[[Any, Any], Path]):
    """Returns a condition that checks if an artifact file exists."""
    def condition(context, step_result) -> ConditionResult:
        path = _to_path(path_factory(context, step_result))
        if path.exists():
            return ConditionResult(passed=True)
        return ConditionResult(
            passed=False,
            message=f"Artifact file does not exist: {path}",
            code="artifact_missing",
            details={"path": str(path)}
        )
    return condition


def context_key_exists(key: str, severity: ConditionSeverity = ConditionSeverity.CRITICAL, code: str = None):
    """Returns a condition that checks if a context key exists."""
    if code is None:
        code = "context_key_missing"
    
    def condition(context, step_result) -> ConditionResult:
        if context.has_value(key):
            return ConditionResult(passed=True)
        return ConditionResult(
            passed=False,
            message=f"Context key does not exist: {key}",
            severity=severity,
            code=code,
            details={"key": key}
        )
    return condition


def python_predicate(predicate: Callable[[Any, Any], bool], 
                     message: str,
                     severity: ConditionSeverity = ConditionSeverity.CRITICAL,
                     code: str = None,
                     details_factory: Callable[[Any, Any], dict] = None):
    """Returns a condition that evaluates a Python predicate."""
    if code is None:
        code = "predicate_failed"
    
    def condition(context, step_result) -> ConditionResult:
        try:
            result = predicate(context, step_result)
        except Exception as e:
            return ConditionResult(
                passed=False,
                message=f"Predicate raised exception: {e}",
                severity=severity,
                code=code,
                details={"exception": str(e)}
            )
        
        if result:
            return ConditionResult(passed=True, message=message)
        
        details = details_factory(context, step_result) if details_factory else {}
        return ConditionResult(
            passed=False,
            message=message,
            severity=severity,
            code=code,
            details=details
        )
    return condition


def result_is_not_none():
    """Returns a condition that checks if the step result is not None."""
    def condition(context, step_result) -> ConditionResult:
        if step_result is not None:
            return ConditionResult(passed=True)
        return ConditionResult(
            passed=False,
            message="Step result is None",
            code="result_is_none",
            details={}
        )
    return condition
