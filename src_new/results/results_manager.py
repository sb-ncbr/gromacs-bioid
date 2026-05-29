from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Union

from .schema import StepStatus, TaskStatus
from ..utils.file_utils import atomic_write_json


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _convert_paths_to_strings(obj):
    """Recursively convert Path objects to strings in a data structure."""
    if isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: _convert_paths_to_strings(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_convert_paths_to_strings(item) for item in obj]
    return obj


class ResultsManager:
    def __init__(self, path: Union[Path, str], pipeline_name: str = ""):
        self.path = Path(path)
        self._payload = None
        
        if not self.path.exists():
            # Create new file with default payload
            self._payload = {
                "schema_version": "0.1.0",
                "created_at": _now_iso(),
                "updated_at": _now_iso(),
                "pipeline": {
                    "name": pipeline_name,
                    "status": "created",
                    "metadata": {}
                },
                "tasks": {},
                "artifacts": {},
                "warnings": [],
                "critical_errors": [],
                "events": [],
                "data": {}
            }
            self._save()
        else:
            # Load existing file
            try:
                content = self.path.read_text(encoding="utf-8")
                self._payload = json.loads(content)
            except json.JSONDecodeError:
                raise ValueError("not valid JSON")
            
            # Check if root is a list
            if isinstance(self._payload, list):
                raise ValueError("root must be a JSON object")
            
            # Run legacy migration if needed
            self._migrate_legacy()
            
            # Ensure all required keys exist
            self._ensure_required_keys()
            
            # Save after migration
            self._save()
    
    def _migrate_legacy(self) -> None:
        """Migrate legacy format to new format."""
        payload = self._payload
        
        # If the payload contains a "run" key (old format)
        if "run" in payload:
            run_data = payload.pop("run")
            
            # Move run content into pipeline
            pipeline = payload.get("pipeline", {})
            pipeline["name"] = run_data.get("pipeline_name") or run_data.get("name", "")
            pipeline["status"] = run_data.get("status", "created")
            if "started_at" in run_data:
                pipeline["started_at"] = run_data["started_at"]
            if "metadata" in run_data:
                pipeline["metadata"] = run_data.get("metadata", {})
            payload["pipeline"] = pipeline
            
            # Rename steps -> tasks
            if "steps" in payload:
                steps = payload.pop("steps")
                tasks = {}
                for step_id, step_data in steps.items():
                    # Keep name, status, started_at, finished_at
                    # Remove warnings, errors, artifacts, requires_steps
                    task_data = {
                        "name": step_data.get("name", ""),
                        "status": step_data.get("status", "pending"),
                    }
                    if "started_at" in step_data:
                        task_data["started_at"] = step_data["started_at"]
                    if "finished_at" in step_data:
                        task_data["finished_at"] = step_data["finished_at"]
                    if "summary" in step_data:
                        task_data["summary"] = step_data["summary"]
                    if "context_keys" in step_data:
                        task_data["context_keys"] = step_data["context_keys"]
                    task_data["artifacts"] = []
                    tasks[step_id] = task_data
                payload["tasks"] = tasks
            
            # Convert logs -> events with kind: "log"
            if "logs" in payload:
                logs = payload.pop("logs")
                events = []
                for log in logs:
                    event = dict(log)
                    event["kind"] = "log"
                    events.append(event)
                payload["events"] = events
            
            # Convert errors -> critical_errors
            if "errors" in payload:
                errors = payload.pop("errors")
                payload["critical_errors"] = errors
            
            # Convert old artifacts list to new dict format
            if "artifacts" in payload and isinstance(payload["artifacts"], list):
                old_artifacts = payload.pop("artifacts")
                new_artifacts = {}
                artifact_keys_by_step = {}
                
                for artifact in old_artifacts:
                    key = str(uuid.uuid4())
                    step_id = artifact.get("step_id", "")
                    new_artifacts[key] = {
                        "step_id": step_id,
                        "path": artifact.get("path", ""),
                        "description": artifact.get("description", ""),
                        "kind": artifact.get("kind", "file")
                    }
                    if step_id not in artifact_keys_by_step:
                        artifact_keys_by_step[step_id] = []
                    artifact_keys_by_step[step_id].append(key)
                
                payload["artifacts"] = new_artifacts
                
                # Update task artifacts lists
                for step_id, keys in artifact_keys_by_step.items():
                    if step_id in payload.get("tasks", {}):
                        payload["tasks"][step_id]["artifacts"] = keys
        
        self._payload = payload
    
    def _ensure_required_keys(self) -> None:
        """Ensure all required top-level keys exist."""
        required_keys = ["tasks", "artifacts", "warnings", "critical_errors", "events", "data"]
        for key in required_keys:
            if key not in self._payload:
                if key in ["tasks", "artifacts", "data"]:
                    self._payload[key] = {}
                else:
                    self._payload[key] = []
    
    def _save(self) -> None:
        """Save the payload atomically."""
        self._payload["updated_at"] = _now_iso()
        # Convert any Path objects to strings before saving
        clean_payload = _convert_paths_to_strings(copy.deepcopy(self._payload))
        atomic_write_json(self.path, clean_payload)
    
    def start_run(self, step_definitions=None, task_definitions=None, metadata=None,
                  input_kind=None, input_files=None, working_directory=None, 
                  output_directory=None) -> None:
        """Start a new run with the given step/task definitions."""
        # Normalize task_definitions to step_definitions
        definitions = step_definitions or task_definitions or []
        
        # Set pipeline status to running
        self._payload["pipeline"]["status"] = "running"
        self._payload["pipeline"]["started_at"] = _now_iso()
        
        # Store metadata
        meta = self._payload["pipeline"].get("metadata", {})
        if metadata:
            meta.update(_convert_paths_to_strings(metadata))
        if input_kind is not None:
            self._payload["pipeline"]["input_kind"] = input_kind
        if input_files is not None:
            # Convert Path values to strings
            converted_files = {}
            for k, v in input_files.items():
                if isinstance(v, Path):
                    converted_files[k] = str(v)
                else:
                    converted_files[k] = v
            self._payload["pipeline"]["input_files"] = converted_files
        if working_directory is not None:
            meta["working_directory"] = str(working_directory)
        if output_directory is not None:
            meta["output_directory"] = str(output_directory)
        self._payload["pipeline"]["metadata"] = meta
        
        # Initialize tasks from definitions
        for definition in definitions:
            step_id = definition.get("step_id") or definition.get("task_id")
            if step_id:
                self._payload["tasks"][step_id] = {
                    "name": definition.get("name", ""),
                    "status": "pending",
                    "artifacts": [],
                    "context_keys": []
                }
        
        self._save()
    
    def start_step(self, step_id: str) -> None:
        """Mark a step as running."""
        if step_id in self._payload["tasks"]:
            self._payload["tasks"][step_id]["status"] = "running"
            self._payload["tasks"][step_id]["started_at"] = _now_iso()
        self._save()
    
    def start_task(self, task_id: str) -> None:
        """Alias for start_step."""
        self.start_step(task_id)
    
    def finish_step(self, step_id: str, status: StepStatus, summary: dict = None, 
                    context_keys: list = None) -> None:
        """Finish a step with the given status."""
        if step_id in self._payload["tasks"]:
            task = self._payload["tasks"][step_id]
            task["status"] = status.value if isinstance(status, StepStatus) else status
            task["finished_at"] = _now_iso()
            if summary is not None:
                task["summary"] = summary
            if context_keys is not None:
                task["context_keys"] = context_keys
        self._save()
    
    def finish_task(self, task_id: str, status: TaskStatus, summary: dict = None,
                    context_keys: list = None) -> None:
        """Alias for finish_step but with TaskStatus."""
        self.finish_step(task_id, status, summary, context_keys)
    
    def record_warning(self, code: str, message: str, step_id: str = None, 
                       details: dict = None) -> None:
        """Record a warning."""
        warning = {
            "code": code,
            "message": message,
            "details": details or {}
        }
        if step_id:
            warning["step_id"] = step_id
        self._payload["warnings"].append(warning)
        self._save()
    
    def record_error(self, code: str, message: str, step_id: str = None,
                     details: dict = None, critical: bool = False,
                     exception_type: str = None) -> None:
        """Record an error."""
        error = {
            "code": code,
            "message": message,
            "details": details or {}
        }
        if step_id:
            error["step_id"] = step_id
        if critical:
            error["critical"] = True
        if exception_type:
            error["exception_type"] = exception_type
        self._payload["critical_errors"].append(error)
        self._save()
    
    def add_event(self, kind: str, **kwargs) -> None:
        """Add a structured event to the events list."""
        event = {"kind": kind, "timestamp": _now_iso()}
        event.update(kwargs)
        self._payload["events"].append(event)
        self._save()
    
    def record_progress(self, step_id: str, label: str, value: Any) -> None:
        """Record intermediate progress for a running step."""
        if step_id not in self._payload["tasks"]:
            return
        if "progress" not in self._payload["tasks"][step_id]:
            self._payload["tasks"][step_id]["progress"] = {}
        self._payload["tasks"][step_id]["progress"][label] = value
        self._save()
    
    def add_artifact(self, step_id: str, path: Path, description: str = "", 
                     kind: str = "file") -> str:
        """Add an artifact and return its UUID key."""
        key = str(uuid.uuid4())
        path_str = str(path) if isinstance(path, Path) else path
        
        self._payload["artifacts"][key] = {
            "step_id": step_id,
            "path": path_str,
            "description": description,
            "kind": kind
        }
        
        if step_id in self._payload["tasks"]:
            if "artifacts" not in self._payload["tasks"][step_id]:
                self._payload["tasks"][step_id]["artifacts"] = []
            self._payload["tasks"][step_id]["artifacts"].append(key)
        
        self._save()
        return key
    
    def set_data(self, path: str, value) -> None:
        """Set nested data using slash-separated path."""
        segments = path.split("/")
        current = self._payload["data"]
        
        for i, segment in enumerate(segments[:-1]):
            if segment not in current:
                current[segment] = {}
            current = current[segment]
        
        # Convert Path to string if needed
        final_value = str(value) if isinstance(value, Path) else value
        current[segments[-1]] = final_value
        
        self._save()
    
    def get_data(self, path: str, default=None):
        """Get nested data using slash-separated path."""
        segments = path.split("/")
        current = self._payload["data"]
        
        for segment in segments:
            if not isinstance(current, dict) or segment not in current:
                return default
            current = current[segment]
        
        return current
    
    def data_exists(self, path: str) -> bool:
        """Check if data exists at the given path."""
        segments = path.split("/")
        current = self._payload["data"]
        
        for segment in segments:
            if not isinstance(current, dict) or segment not in current:
                return False
            current = current[segment]
        
        return True
    
    def has_critical_errors(self) -> bool:
        """Check if there are any critical errors."""
        return len(self._payload.get("critical_errors", [])) > 0
    
    def get_task_status(self, step_id: str) -> str:
        """Get the status of a task."""
        if step_id in self._payload["tasks"]:
            return self._payload["tasks"][step_id]["status"]
        return "unknown"
    
    def as_dict(self) -> dict:
        """Return a deep copy of the in-memory payload."""
        return copy.deepcopy(self._payload)

    def set_pipeline_field(self, key: str, value) -> None:
        """Set a field in the pipeline section."""
        self._payload["pipeline"][key] = value
        self._save()


    def finish_run(self, status: str) -> None:
        """Set pipeline final status and finished_at timestamp."""
        self._payload["pipeline"]["status"] = status
        self._payload["pipeline"]["finished_at"] = _now_iso()
        self._save()

