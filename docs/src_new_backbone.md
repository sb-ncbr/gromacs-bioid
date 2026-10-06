# `src_new` Pipeline Backbone

> **⚠️ ERA NOTE — content 2026-08-12, pre-final-audit (Wave G banner, 2026-10-06).**
> Structural description of `src_new/` remains broadly accurate, but behavior details
> changed during the 2026-10 audit waves: `ResultsManager.start_run` preserves persisted
> step statuses (F-03 resume works), `results_manager`/`executor` are exercised by the
> campaign fleet (v3.131), dispatch machinery lives in `queue_processor.py` +
> `src_new/api/tasks.py:run_pipeline_task` (see `.tmp/F26_DESIGN.md` for dispatch
> unification state), and resolver-layer fixes (OQ-1..OQ-11) added local mirrors +
> contract repairs. Consult `docs/CHEMISTRY_FIX_TODO.md` (§F ledger) before relying on
> any behavioral claim below.

`src_new/` is the new generic execution backbone for BioID v2. It is intentionally independent from the legacy `src/` runtime so future GROMACS, AMBER, PDB, and mmCIF stages can be added without inheriting the old executor/task coupling.

## Main pieces

- `src_new/results/results_manager.py`
  - Owns the central `results.json`.
  - Loads existing state, repairs optional sections, writes atomically, records metadata, tasks, warnings, critical errors, events, artifacts, and nested pipeline data.
- `src_new/executor/task.py`
  - Defines `Task`, `TaskContext`, `TaskResult`, and compatibility aliases (`PipelineStep`, `StepContext`, `StepResult`).
  - Each step is a normal Python callable operating on a shared context.
- `src_new/executor/conditions.py`
  - Defines reusable checks such as `file_exists`, `directory_exists`, `non_empty_file`, `context_key_exists`, and `python_predicate`.
  - Conditions return structured `ConditionResult` values with a severity of `warning` or `critical`.
- `src_new/executor/executor.py`
  - Validates prerequisites.
  - Runs steps sequentially.
  - Records task lifecycle and failures into `results.json`.
  - Stops on critical failures and continues after warnings.

## Minimal workflow

Typical usage looks like this:

1. Create a work directory.
2. Create a `ResultsManager` pointing at `results.json`.
3. Define one or more `Task` objects.
4. Run `PipelineExecutor.run(...)` with:
   - `initial_state`
   - `run_metadata`
   - `input_kind`
   - `input_files`
   - `working_directory`
   - `output_directory`
5. Inspect `results.json` for pipeline status, task status, artifacts, warnings, critical errors, and events.

## Demo

A runnable developer example lives in [examples/src_new_backbone_demo.py](/home/tomsko/tmp/BAT2/examples/src_new_backbone_demo.py:1).

Run it from the repository root:

```bash
python3 examples/src_new_backbone_demo.py
```

Or choose a custom work directory and input kind:

```bash
python3 examples/src_new_backbone_demo.py --workdir /tmp/bioid-demo --input-kind gromacs
```

The demo shows:

- creating a work directory
- creating/loading `results.json`
- setting pipeline metadata
- registering `input_kind` and `input_files`
- defining three dummy tasks
- running the executor
- printing final task statuses

## How future biomolecule steps should map onto this backbone

The example tasks are placeholders for the real BioID stages:

- `check_input`
  - future role: validate a GROMACS/AMBER/PDB/mmCIF input bundle before loading
- `write_intermediate`
  - future role: build an atomic map, normalize structures, or export an intermediate representation
- `validate_output`
  - future role: validate a generated representation, annotation candidate set, or final filtered output

## Recommended conventions for new steps

- Use `initial_state` for already-known inputs such as discovered file paths.
- Use `context.record_data(...)` for structured pipeline state that should live in `results.json`.
- Use `context_updates` in `TaskResult` for transient in-memory state between tasks.
- Use `output_paths` on `Task` to declare produced files that should be recorded as artifacts.
- Use `skip_if_output_exists=True` when a step can safely reuse declared outputs.
- Use `context.add_warning(...)` for recoverable issues.
- Use `context.fail(...)` for critical failures that must stop the pipeline.
- Prefer explicit preconditions/postconditions over ad hoc checks inside unrelated steps.

## `results.json` schema

The current schema version is `0.1.0`. The top-level structure is:

```json
{
  "schema_version": "0.1.0",
  "created_at": "...",
  "updated_at": "...",
  "pipeline": {
    "name": null,
    "status": "created",
    "input_kind": null,
    "input_files": {},
    "metadata": {},
    "failure_message": null
  },
  "tasks": {},
  "artifacts": {},
  "warnings": [],
  "critical_errors": [],
  "events": [],
  "data": {}
}
```

Notes:

- `tasks` stores per-task lifecycle state, summaries, task-local warnings, task-local critical errors, recorded artifact ids, and task-local events.
- `artifacts` stores produced or reused outputs keyed by artifact id.
- `events` stores the global execution event stream, including logs.
- `data` is the structured state area for pipeline-specific information shared across tasks.
- `schema_version` is intentionally explicit so future migrations can branch through `src_new/results/schema.py::normalize_results_document`.

## Current scope

This backbone is generic execution infrastructure only. It does not yet implement:

- GROMACS/AMBER/PDB/mmCIF loading
- MDAnalysis integration
- atomic mapping
- molecule typing
- representation export
- resolver/database search
- scientific validation logic

Those stages should be added as new steps on top of this executor/results foundation, not by extending the legacy `src/executor` code.
