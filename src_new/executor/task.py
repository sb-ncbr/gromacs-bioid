from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Any
import logging

from ..results.results_manager import ResultsManager
from ..config.loader import RunConfig
from .errors import CriticalStepError


@dataclass
class StepResult:
    payload: Any = None
    summary: dict = field(default_factory=dict)
    context_updates: dict = field(default_factory=dict)


@dataclass
class TaskResult:
    payload: Any = None
    summary: dict = field(default_factory=dict)
    context_updates: dict = field(default_factory=dict)


class StepContext:
    def __init__(self, results: ResultsManager, state: dict, working_directory: Path, 
                 output_directory: Path, logger: logging.Logger, config: RunConfig = None):
        self.results = results
        self.state = state
        self.working_directory = Path(working_directory)
        self.output_directory = Path(output_directory)
        self.logger = logger
        self._current_step_id = None
        self._step_warnings = []
        self._step_artifacts = []
        self.config = config or RunConfig()

    def record_data(self, path: str, value: Any) -> None:
        self.results.set_data(path, value)

    def get_value(self, key: str, default=None):
        return self.state.get(key, default)

    def set_value(self, key: str, value) -> None:
        """Store a value in the task state (v3.143, red-team E-01).

        set_stage_budget() has always written the stage deadline through this
        method, but it never existed on the real context (only on MagicMock),
        so per-stage time budgets silently never armed since 2026-09-19.
        """
        self.state[key] = value

    def require_value(self, key: str):
        if key not in self.state:
            raise KeyError(key)
        return self.state[key]

    def has_value(self, key: str) -> bool:
        return key in self.state

    # Codes that are informational by design (synced with the UI error-catalog
    # `kind: "info"` entries): molecule-scoped non-applicability notes must NOT
    # flip the owning task's status to orange ("warning") in the taskbar.
    INFO_WARNING_CODES = frozenset({
        # v3.143 (E-22): `signature_generator_failed` is NOT informational —
        # it fires on real failures (generator exception / returned None),
        # and demoting it hid dead channels behind green tasks. True
        # applicability no-ops use `signature_generator_not_applicable`.
        "signature_generator_not_applicable",
        "pbc_unwrap_applied",
        "coords_rescaled_nm_to_angstrom",
    })

    def add_warning(self, code: str, message: str, details: dict = None,
                    severity: str = None) -> None:
        details = details or {}
        sev = severity or ("info" if code in self.INFO_WARNING_CODES else "warning")
        self._step_warnings.append((code, message, details, sev))
        if self._current_step_id:
            self.results.record_warning(code, message, step_id=self._current_step_id,
                                        details=details, severity=sev)

    def add_artifact(self, path: Path, description: str = "", kind: str = "file") -> None:
        if self._current_step_id:
            self.results.add_artifact(self._current_step_id, path, description=description, kind=kind)

    def set_progress(self, label: str, value: Any) -> None:
        """Report intermediate progress for the current step."""
        if self._current_step_id:
            self.results.record_progress(self._current_step_id, label, value)

    def fail(self, code: str, message: str, details: dict = None) -> None:
        raise CriticalStepError(message, code=code, details=details or {})


class TaskContext(StepContext):
    pass


@dataclass
class PipelineStep:
    step_id: str
    name: str = ""
    handler: Callable = None
    preconditions: tuple = field(default_factory=tuple)
    postconditions: tuple = field(default_factory=tuple)
    requires_steps: tuple = field(default_factory=tuple)
    output_paths: tuple = field(default_factory=tuple)
    skip_if_output_exists: bool = False

    @property
    def id(self):
        return self.step_id


@dataclass
class Task:
    task_id: str = ""
    step_id: str = ""
    name: str = ""
    handler: Callable = None
    preconditions: tuple = field(default_factory=tuple)
    postconditions: tuple = field(default_factory=tuple)
    requires_tasks: tuple = field(default_factory=tuple)
    requires_steps: tuple = field(default_factory=tuple)
    output_paths: tuple = field(default_factory=tuple)
    skip_if_output_exists: bool = False

    @property
    def id(self):
        return self.task_id or self.step_id
