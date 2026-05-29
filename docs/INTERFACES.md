# BioID v2 Product Interface Specification

This document specifies how BioID v2 should be exposed through command-line, Python API, and web/API service interfaces. It separates current behavior from proposed behavior. No interface changes are implemented by this document.

## Current Interface Baseline

### Current CLI

The current command-line entry point is `main.py`.

Current options:

- `-r`, `--run`: execute workflow once.
- `-i`, `--input`: directory containing simulation folders.
- `-t`, `--task`: task to execute; can be repeated. Current task names come from `TaskType`: `ALL`, `INPUT`, `CREATE`, `LOAD`, `GENERATE_SIGNATURES`, `RESOLVE_IDENTIFIERS`, `SUMMARIZE`, `METADATA`, `UNLOAD`.
- `-s`, `--stats`: stats aggregation mode; can be repeated.
- `-v`, `--verbose`: emit non-critical failure messages.
- `-vv`, `--very_verbose`: emit debug messages.

Current behavior:

- `main.py` initializes loggers, calls database sync according to `config.ini`, discovers simulation folders inside `--input`, creates task chains, and runs `ExecutorCore`.
- Each simulation directory can receive `all_files.txt`, `used_files.txt`, `tasks.log`, `results.log`, `errors.log`, `results.json`, and generated representation files.
- Network database sync is controlled by `config.ini` under `[databases] sync_enabled`, not by a CLI flag.
- Signature and resolver enable/disable behavior is controlled by `config.ini`, not by CLI flags.

Current gaps:

- No explicit CLI command named `identify`, `validate`, or `export`.
- No direct CLI switch for output format.
- No direct CLI switch for strict/lenient mode.
- No direct CLI switch for network database search on/off.
- No direct CLI switch for saving intermediate representations beyond current task behavior.
- No explicit structured input validation command.

### Current Python API

The current API-facing file is `api_endpoint.py`.

Current public function:

```python
def run_analyze(directory: str, task_uuid: str) -> str | None:
    ...
```

Current behavior:

- Runs the full `ALL` task chain for one simulation directory.
- Blocks until the executor finishes.
- Sets `TMP/CURR_UUID` in runtime configuration.
- Returns the absolute path to `results.json`, or `None` if the job failed.

Current gaps:

- No typed Python API for input bundles, entities, candidates, warnings, or final annotations.
- No public API for running individual stages outside the task system.
- No public API for exporting selected output formats.
- No public API for inspecting warnings or provenance as structured objects.

### Current Web/API Service

There is no full web service package in this repository. Current service-oriented behavior appears in:

- `api_endpoint.py`, which can be called by an external service.
- `tasks.log`, created through task progress metadata in `src/executor/task_creator.py`.
- `results.json`, `results.log`, and `errors.log` output files in simulation directories.

Current gaps:

- No visible upload endpoint implementation.
- No job registry or job-status API in this repository.
- No result download endpoint in this repository.
- No structured progress schema.

## Interface Goals

BioID interfaces should let users:

- Identify biomolecules in a simulation.
- Validate inputs before running expensive work.
- Run local deterministic analysis with or without external database search.
- Export annotations in machine-readable and human-readable formats.
- Choose strict or lenient behavior.
- Inspect uncertain, ambiguous, repaired, and failed parts of the analysis.
- See the evidence and databases behind each annotation.
- Preserve reproducibility metadata.

## 1. CLI Interface

### Proposed Command Shape

Proposed top-level command name:

```text
bioid
```

Proposed subcommands:

```text
bioid identify
bioid validate-inputs
bioid export
bioid inspect
bioid stats
```

The existing `main.py --run --task ...` behavior can be preserved during transition, but future documentation should prefer clear subcommands.

### Identify a Simulation

Proposed:

```bash
bioid identify --input /path/to/simulation --output /path/to/output
bioid identify --input /path/to/batch --batch --output /path/to/output
```

Required behavior:

- Accept one simulation directory or a batch directory.
- Write output to an explicit output directory.
- Create `results.json` or a versioned annotation file.
- Return non-zero exit code for fatal input or pipeline failure.
- Continue to report partial annotations when non-fatal uncertainty is present.

Current equivalent:

```bash
python main.py --run --input /path/to/batch --task ALL
```

Current limitation:

- `--input` currently expects a directory containing simulation folders, not necessarily a single simulation folder.

### Validate Inputs

Proposed:

```bash
bioid validate-inputs --input /path/to/simulation
bioid validate-inputs --input /path/to/batch --batch
```

Required behavior:

- List detected files and inferred roles.
- Report supported, unsupported, missing, duplicate, and ambiguous files.
- Report likely load strategy without running full identification.
- Optionally emit a machine-readable validation report.

Current status:

- Proposed. Current loader strategy selection is only exercised during load.

### Export Annotations

Proposed:

```bash
bioid export --results /path/to/results.json --format json --output annotation.json
bioid export --results /path/to/results.json --format table --output summary.tsv
bioid export --results /path/to/results.json --format jsonld --output annotation.jsonld
```

Required behavior:

- Convert current or versioned results into requested output format.
- Validate schema before export.
- Support stable, reproducible output.

Current status:

- Proposed. Current output is direct `ResultsFile` JSON plus generated files in the simulation directory.

### Run With or Without Network Database Search

Proposed:

```bash
bioid identify --input sim --database-search off
bioid identify --input sim --database-search local
bioid identify --input sim --database-search network
bioid identify --input sim --database-search all
```

Modes:

- `off`: run loading, repair, entity extraction, representation generation, and local annotation only.
- `local`: allow local databases and local executables such as BLAST.
- `network`: allow remote database services.
- `all`: allow local and remote resolvers.

Current status:

- Resolver and sync behavior are configured through `config.ini`.
- No direct CLI flag controls database search mode.

### Choose Output Format

Proposed:

```bash
bioid identify --input sim --output-format json
bioid identify --input sim --output-format jsonld
bioid identify --input sim --output-format table
bioid identify --input sim --output-format all
```

Output formats are specified later in this document.

Current status:

- Current primary output is `results.json`.
- mmCIF files can be generated during summarization.

### Choose Strict or Lenient Mode

Proposed:

```bash
bioid identify --input sim --mode strict
bioid identify --input sim --mode lenient
```

Expected behavior:

- `strict`: fail or withhold annotations when required evidence is missing, ambiguous, inferred with low confidence, or chemically invalid.
- `lenient`: produce partial annotations with warnings and reduced confidence.

Current status:

- Some strictness-like behavior exists in configuration for FASTA generation, such as `fasta_map_determine_sequence_strict_mode`.
- No global strict/lenient CLI mode exists.

### Enable Verbose Logging

Current:

```bash
python main.py --run --input batch --task ALL --verbose
python main.py --run --input batch --task ALL --very_verbose
```

Proposed:

```bash
bioid identify --input sim --verbose
bioid identify --input sim --debug
bioid identify --input sim --log-file bioid.log
```

Expected behavior:

- `--verbose`: include non-critical failure messages.
- `--debug`: include full stage-level diagnostic logs.
- Logs should identify simulation, file, entity, stage, resolver, and warning/error code where possible.

### Save Intermediate Representations

Proposed:

```bash
bioid identify --input sim --save-intermediates
bioid identify --input sim --save-representations pdb,mmcif,fasta,smiles
```

Expected behavior:

- Save generated representations in a predictable output directory.
- Include paths in annotation output.
- Do not save very large intermediate data unless explicitly requested.

Current status:

- Some representations are stored in `results.json`.
- `ResultsSummarizer` can export `simulation.mmcif` and per-segment mmCIF files.
- There is no general CLI switch controlling intermediate files.

## 2. Python API

The Python API should expose BioID as a library, not only as a task runner.

### Proposed API Sketch

```python
from bioid import BioIDPipeline, PipelineOptions

options = PipelineOptions(
    database_search="local",
    mode="lenient",
    output_format="json",
    save_intermediates=True,
)

pipeline = BioIDPipeline(options)
result = pipeline.run("/path/to/simulation")

annotations = result.annotations
warnings = result.warnings
entities = result.entities
candidates = result.candidates
```

Current status:

- Proposed. Current import paths are under `src`, and the current API helper is `api_endpoint.run_analyze`.

### Load Input Bundle

Proposed:

```python
bundle = pipeline.load_input_bundle("/path/to/simulation")
```

Expected return:

- Input file list.
- File types and roles.
- Topology/trajectory/structure relationships.
- Loader metadata.
- Input validation warnings.

Current status:

- Proposed. Current file discovery and archive unpacking happen inside `create_tasks_for_simulations`.

### Run Full Pipeline

Current:

```python
from api_endpoint import run_analyze

results_path = run_analyze("/path/to/simulation", task_uuid="job-id")
```

Proposed:

```python
result = pipeline.run("/path/to/simulation")
```

Expected behavior:

- Return a typed result object.
- Preserve `results.json` path and generated file paths.
- Include structured warnings, entities, candidates, validation results, and final annotations.

### Run Individual Stages

Proposed:

```python
bundle = pipeline.load_input_bundle(path)
atomic_map = pipeline.load(bundle)
repaired_map = pipeline.repair(atomic_map)
entities = pipeline.extract_entities(repaired_map)
representations = pipeline.generate_representations(entities)
candidates = pipeline.search_databases(representations)
validated = pipeline.validate_candidates(candidates)
annotations = pipeline.annotate(validated)
```

Current status:

- Current task stages are available through `TaskType`, but not exposed as typed Python API stage methods.

### Inspect Warnings

Proposed:

```python
for warning in result.warnings:
    print(warning.code, warning.stage, warning.message)
```

Expected behavior:

- Warnings are structured and linked to files, atoms, residues, entities, candidates, or annotations.

Current status:

- Proposed. Current warnings/errors are mostly logs, exceptions, result paths, and `errors.log`.

### Access Entities

Proposed:

```python
for entity in result.entities:
    print(entity.entity_id, entity.entity_type, entity.atom_count)
```

Current status:

- Proposed. Current code exposes segments and fragments through `Simulation.get_segments()` and `Simulation.get_fragment()`.

### Access Candidates

Proposed:

```python
candidates = result.candidates_for_entity("entity_000001")
```

Expected behavior:

- Return database, identifier, score, method, provenance, and validation state.

Current status:

- Current candidates are stored under `identifiers/<segment>/<signature_generator>/<resolver>/hits`.

### Export Annotations

Proposed:

```python
result.export("annotation.json", format="json")
result.export("annotation.jsonld", format="jsonld")
result.export("summary.tsv", format="table")
```

Current status:

- Proposed. Current code writes `ResultsFile` JSON during processing.

## 3. Web/API Service

The web/API service should be asynchronous and job-oriented.

### Upload or Submit Inputs

Proposed endpoints:

```text
POST /jobs
POST /jobs/{job_id}/files
POST /jobs/{job_id}/start
```

Expected behavior:

- Accept compressed or multi-file simulation inputs.
- Validate files before starting expensive processing.
- Store original filenames and checksums.
- Return a job ID.

Current status:

- No upload endpoints are visible in this repository.
- `task_uuid` is accepted by `run_analyze`, likely for external job tracking.

### Asynchronous Jobs

Proposed endpoints:

```text
GET /jobs/{job_id}
POST /jobs/{job_id}/cancel
```

Job states:

- `created`
- `validating`
- `queued`
- `running`
- `completed`
- `completed_with_warnings`
- `failed`
- `cancelled`

Current status:

- `api_endpoint.run_analyze()` is blocking.
- `ExecutorCore` supports task execution, but no service-level job API is present here.

### Progress Reporting

Proposed endpoint:

```text
GET /jobs/{job_id}/progress
```

Progress fields:

- current stage
- completed stages
- total stages
- stage status
- elapsed time
- warnings count
- database search status
- output files produced so far

Current status:

- `tasks.log` is written via task progress metadata.
- No structured progress response schema is present.

### Result Download

Proposed endpoints:

```text
GET /jobs/{job_id}/results
GET /jobs/{job_id}/results/annotation.json
GET /jobs/{job_id}/results/summary.tsv
GET /jobs/{job_id}/results/files/{filename}
```

Expected behavior:

- Download final annotations.
- Download generated representation files.
- Download logs and reports.
- Return clear 404/409 responses for missing or incomplete results.

Current status:

- `run_analyze()` returns a local `results.json` path.

### Warnings and Errors

Proposed endpoints:

```text
GET /jobs/{job_id}/warnings
GET /jobs/{job_id}/errors
```

Expected behavior:

- Expose structured warnings and errors.
- Separate fatal errors from scientific uncertainty.
- Link warnings/errors to stages, files, entities, and annotations.

Current status:

- `errors.log` is produced from task logs during `UNLOAD`.
- No structured warning/error API is present.

### Database Search Status

Proposed fields:

- database search mode
- resolver enabled/disabled state
- attempted databases
- skipped databases and reasons
- cache hit/miss counts
- network failures
- rate limits or retries

Current status:

- Attempted resolvers are stored under `identifiers/<segment>/<signature_generator>/attempted`.
- Database sync status is printed by `sync()`, not exposed as structured service state.

### Reproducibility Metadata

Proposed fields:

- BioID version
- schema version
- configuration digest
- input file checksums
- selected load strategy
- used files
- database versions or cache state
- resolver versions
- command/options used
- creation timestamp

Current status:

- Some information exists in `results.json`, `used_files.txt`, `all_files.txt`, and logs.
- No unified reproducibility metadata block exists.

## 4. Output Formats

### JSON

Expected:

- Primary machine-readable output.
- Versioned schema.
- Includes entities, candidates, validation results, final annotations, warnings, and provenance.

Current:

- `results.json` is written by `ResultsFile`.
- It is flexible but not versioned or schema-validated.

### JSON-LD or FAIR-Oriented Metadata

Expected:

- Optional export for repository interoperability and semantic search.
- Should map stable identifiers, provenance, dataset relationships, and entity annotations into linked-data terms where appropriate.

Current:

- Proposed. No JSON-LD exporter is visible.

### Tabular Summary

Expected:

- Human-readable summary for spreadsheets or quick inspection.
- One row per entity or annotation.
- Include entity type, best identifier, confidence, warnings count, source segment, and key evidence.

Current:

- Proposed. Stats aggregation exists under `src/stats/`, but no annotation table exporter is visible.

### Representation Files

Expected:

- PDB/mmCIF files for simulation or entity structures.
- FASTA files for sequence entities.
- SMILES/InChI text files for valid chemical entities.
- Fingerprint files if useful for downstream workflows.

Current:

- mmCIF export exists in `ResultsSummarizer`.
- Some signatures are stored inline in `results.json`.

### Logs and Reports

Expected:

- `results.log`: diagnostic log.
- `errors.log`: fatal and non-fatal error summary.
- `warnings.json`: structured scientific warnings.
- `report.html` or `report.md`: optional human-readable report.

Current:

- `results.log`, `errors.log`, and `tasks.log` exist through task execution.
- Structured warning reports are proposed.

## 5. UX Expectations

### Identified Content

Users should see:

- Each detected entity.
- Entity type.
- Best identifier where available.
- Confidence.
- Source segment/chain/residue range.
- Copy number where known.

Current:

- Summary fields are written under `summary/segments/<segment>/...`.

### Uncertain or Ambiguous Results

Users should see:

- Unknown and ambiguous entities.
- Low-confidence annotations.
- Candidate alternatives.
- Reasons why certainty is limited.

Current:

- Some uncertainty can be inferred from `confidence`, `verification`, missing identifiers, logs, and `UNKNOWN` classification.
- Structured ambiguity explanations are proposed.

### Evidence for Each Annotation

Users should see:

- Input files used.
- Load strategy.
- Generated representations.
- Resolver hits.
- Validation results.
- Repair/inference records.

Current:

- Pieces of evidence exist across `simulation`, `signatures`, `identifiers`, and `summary` result paths.
- A unified evidence view is proposed.

### Databases Searched

Users should see:

- Which resolvers/databases were enabled.
- Which were attempted.
- Which were skipped and why.
- Which failed.
- Which returned no hits.

Current:

- Attempted resolvers are stored per segment/signature.
- Skipped and failed reasons are mostly logs or implicit behavior.

### Repairs and Inferences

Users should see:

- What data was missing or inconsistent.
- What BioID inferred.
- Which method was used.
- Confidence and impact on final annotation.
- Whether the original data was mutated or only annotated.

Current:

- Repair methods exist, especially around element inference, but structured repair records are proposed.

## Compatibility and Migration

Short-term:

- Keep `main.py --run --input --task` working.
- Keep `api_endpoint.run_analyze()` working for external callers.
- Add exporters and adapters around current `ResultsFile` output before replacing it.

Medium-term:

- Add a stable CLI command structure.
- Add typed Python API objects.
- Add structured warnings/provenance and schema validation.
- Add service-level job and progress schemas.

Long-term:

- Make CLI, Python API, and web/API service share the same pipeline core and output schema.
- Keep interface-specific code focused on orchestration, validation, progress, and formatting.
