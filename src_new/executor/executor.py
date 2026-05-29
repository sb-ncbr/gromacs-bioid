from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Union

from .task import StepContext, StepResult, TaskResult, PipelineStep, TaskContext
from .errors import CriticalStepError, PreconditionFailedError, PostconditionFailedError
from .conditions import ConditionSeverity
from ..results.schema import StepStatus
from ..config.loader import RunConfig


class PipelineExecutor:
    def __init__(self, steps, results_manager, pipeline_name=None):
        self.steps = steps
        self.results_manager = results_manager
        self.pipeline_name = pipeline_name
    
    def _step_id(self, step) -> str:
        """Get the step/task ID from a step object."""
        return getattr(step, 'id', None) or getattr(step, 'task_id', None) or getattr(step, 'step_id', None)
    
    def run(self, output_directory=None, working_directory=None, input_kind=None, 
            input_files=None, run_metadata=None, run_config: RunConfig = None):
        """Execute the pipeline."""
        # Set fallback directories
        if output_directory is None:
            output_directory = Path.cwd()
        else:
            output_directory = Path(output_directory)
        
        if working_directory is None:
            working_directory = Path.cwd()
        else:
            working_directory = Path(working_directory)
        
        # Create output directory if it doesn't exist
        output_directory.mkdir(parents=True, exist_ok=True)
        
        # Normalize input_files dict values to strings
        normalized_input_files = None
        if input_files is not None:
            normalized_input_files = {}
            for k, v in input_files.items():
                if isinstance(v, Path):
                    normalized_input_files[k] = str(v)
                else:
                    normalized_input_files[k] = v
        
        # Build step_definitions from self.steps
        step_definitions = []
        for step in self.steps:
            step_id = self._step_id(step)
            name = getattr(step, 'name', '')
            step_definitions.append({"step_id": step_id, "name": name})
        
        # Call start_run
        self.results_manager.start_run(
            step_definitions=step_definitions,
            metadata=run_metadata or {},
            input_kind=input_kind,
            input_files=normalized_input_files,
            working_directory=str(working_directory),
            output_directory=str(output_directory)
        )
        
        # Set pipeline name if provided
        if self.pipeline_name:
            self.results_manager._payload["pipeline"]["name"] = self.pipeline_name
            self.results_manager._save()
        
        # Record config into results_manager if provided
        if run_config is not None:
            self.results_manager.set_data("config", run_config.to_dict())
        
        # Create TaskContext (which is also a StepContext) with a logger that captures events
        logger = logging.getLogger("base")
        logger.setLevel(logging.DEBUG)  # Allow DEBUG messages to propagate to handlers
        context = TaskContext(
            results=self.results_manager,
            state={},
            working_directory=working_directory,
            output_directory=output_directory,
            logger=logger,
            config=run_config or RunConfig()
        )
        
        # Track critical failures
        failed_critical = False
        failed_at_index = -1
        
        # Set up logging handler to capture log events
        class LogCaptureHandler(logging.Handler):
            def __init__(self, executor_self, context):
                super().__init__()
                self.executor_self = executor_self
                self.context = context
            
            def emit(self, record):
                try:
                    msg = self.format(record)
                    self.executor_self.results_manager.add_event(
                        "log",
                        level=record.levelname,
                        logger=record.name,
                        message=msg,
                        task_id=self.context._current_step_id
                    )
                except Exception:
                    pass
        
        log_handler = LogCaptureHandler(self, context)
        log_handler.setLevel(logging.INFO)
        logger.addHandler(log_handler)
        
        try:
            # Iterate over steps in order
            for i, step in enumerate(self.steps):
                step_id = self._step_id(step)
                
                # If a previous step suffered a critical failure, mark this step as SKIPPED
                if failed_critical:
                    self.results_manager._payload["tasks"][step_id]["status"] = "skipped"
                    self.results_manager._save()
                    continue
                
                # Check skip_if_output_exists
                if getattr(step, 'skip_if_output_exists', False):
                    output_paths = getattr(step, 'output_paths', ())
                    all_exist = True
                    for output_path in output_paths:
                        full_path = output_directory / output_path
                        if not full_path.exists():
                            all_exist = False
                            break
                    
                    if all_exist:
                        # Register each as an artifact
                        for output_path in output_paths:
                            full_path = output_directory / output_path
                            self.results_manager.add_artifact(step_id, full_path, description="Cached output")
                        
                        # Mark step as SKIPPED
                        self.results_manager._payload["tasks"][step_id]["status"] = "skipped"
                        self.results_manager._save()
                        continue
                
                # Start the step
                self.results_manager.start_step(step_id)
                context._current_step_id = step_id
                
                # Record step start event
                self.results_manager.add_event("step_start", task_id=step_id, step_name=getattr(step, 'name', ''))
                
                # Reset step-level tracking
                context._step_warnings = []
                
                # Track warnings for this step
                step_has_warnings = False
                
                # Evaluate preconditions
                preconditions = getattr(step, 'preconditions', ())
                precondition_failed = False
                for cond in preconditions:
                    result = cond(context, None)
                    if not result.passed:
                        # Inject condition_stage into details
                        details_copy = dict(result.details) if result.details else {}
                        details_copy["condition_stage"] = "precondition"
                        
                        if result.severity == ConditionSeverity.CRITICAL:
                            # Record critical error
                            self.results_manager.record_error(
                                code=result.code,
                                message=result.message,
                                step_id=step_id,
                                details=details_copy,
                                critical=True
                            )
                            # Finish step as FAILED
                            self.results_manager.finish_step(
                                step_id=step_id,
                                status=StepStatus.FAILED,
                                summary={},
                                context_keys=list(context.state.keys())
                            )
                            failed_critical = True
                            failed_at_index = i
                            precondition_failed = True
                            raise PreconditionFailedError(result.message)
                        else:
                            # WARNING - record warning and continue
                            self.results_manager.record_warning(
                                code=result.code,
                                message=result.message,
                                step_id=step_id,
                                details=details_copy
                            )
                            step_has_warnings = True
                
                if precondition_failed:
                    continue
                
                # Run handler
                step_result = None
                try:
                    handler = getattr(step, 'handler', None)
                    if handler:
                        step_result = handler(context)
                        if step_result is None:
                            step_result = StepResult()
                except CriticalStepError as e:
                    # Record critical error using e.code and e.details
                    self.results_manager.record_error(
                        code=e.code,
                        message=str(e),
                        step_id=step_id,
                        details=e.details,
                        critical=True
                    )
                    # Finish step as FAILED
                    self.results_manager.finish_step(
                        step_id=step_id,
                        status=StepStatus.FAILED,
                        summary={},
                        context_keys=list(context.state.keys())
                    )
                    failed_critical = True
                    failed_at_index = i
                    raise
                
                except Exception as e:
                    # Record critical error with code "unhandled_exception"
                    self.results_manager.record_error(
                        code="unhandled_exception",
                        message=str(e),
                        step_id=step_id,
                        details={},
                        critical=True,
                        exception_type=type(e).__name__
                    )
                    # Finish step as FAILED
                    self.results_manager.finish_step(
                        step_id=step_id,
                        status=StepStatus.FAILED,
                        summary={},
                        context_keys=list(context.state.keys())
                    )
                    failed_critical = True
                    failed_at_index = i
                    raise
                
                # Apply context_updates to context.state
                if step_result and hasattr(step_result, 'context_updates'):
                    for key, value in step_result.context_updates.items():
                        context.state[key] = value
                
                # Evaluate postconditions
                postconditions = getattr(step, 'postconditions', ())
                postcondition_failed = False
                for cond in postconditions:
                    result = cond(context, step_result)
                    if not result.passed:
                        # Inject condition_stage into details
                        details_copy = dict(result.details) if result.details else {}
                        details_copy["condition_stage"] = "postcondition"
                        
                        if result.severity == ConditionSeverity.CRITICAL:
                            # Record critical error
                            self.results_manager.record_error(
                                code=result.code,
                                message=result.message,
                                step_id=step_id,
                                details=details_copy,
                                critical=True
                            )
                            # Finish step as FAILED
                            self.results_manager.finish_step(
                                step_id=step_id,
                                status=StepStatus.FAILED,
                                summary=step_result.summary if step_result else {},
                                context_keys=list(context.state.keys())
                            )
                            failed_critical = True
                            failed_at_index = i
                            postcondition_failed = True
                            raise PostconditionFailedError(result.message)
                        else:
                            # WARNING - record warning and continue
                            self.results_manager.record_warning(
                                code=result.code,
                                message=result.message,
                                step_id=step_id,
                                details=details_copy
                            )
                            step_has_warnings = True
                
                if postcondition_failed:
                    continue
                
                # Determine final status
                final_status = StepStatus.SUCCESS
                if step_has_warnings or len(context._step_warnings) > 0:
                    final_status = StepStatus.WARNING
                
                # Auto-register artifacts for any existing files in step.output_paths
                output_paths = getattr(step, 'output_paths', ())
                for output_path in output_paths:
                    full_path = output_directory / output_path
                    if full_path.exists():
                        # Check if already registered
                        task_artifacts = self.results_manager._payload["tasks"].get(step_id, {}).get("artifacts", [])
                        already_registered = False
                        for artifact_key in task_artifacts:
                            artifact = self.results_manager._payload["artifacts"].get(artifact_key, {})
                            if artifact.get("path") == str(full_path):
                                already_registered = True
                                break
                        
                        if not already_registered:
                            self.results_manager.add_artifact(step_id, full_path, description="Output file")
                
                # Record step finish event
                self.results_manager.add_event("step_finish", task_id=step_id, status=final_status.value if isinstance(final_status, StepStatus) else final_status)
                
                # Finish the step
                self.results_manager.finish_step(
                    step_id=step_id,
                    status=final_status,
                    summary=step_result.summary if step_result else {},
                    context_keys=list(context.state.keys())
                )
        
        finally:
            logger.removeHandler(log_handler)
            
            # Mark remaining tasks as skipped if there was a critical failure
            if failed_critical and failed_at_index >= 0:
                for i in range(failed_at_index + 1, len(self.steps)):
                    step = self.steps[i]
                    step_id = self._step_id(step)
                    if step_id in self.results_manager._payload["tasks"]:
                        self.results_manager._payload["tasks"][step_id]["status"] = "skipped"
            
            # Set pipeline final status and timestamp
            self.results_manager.finish_run("failed" if failed_critical else "success")
        
        return context
