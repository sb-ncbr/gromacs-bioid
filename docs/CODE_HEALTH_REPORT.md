# BioID v2 Code Health Report

> **⚠️ SUPERSEDED — 2026-08-12 prototype-era audit (Wave G banner, 2026-10-06).**
> This early health report is **superseded in scope** by the 2026-10 final audit:
> 28 findings (F-01..F-28 + N1 + OQ register) tracked in `.tmp/final_findings.md`
> and resolved/ruled through `docs/CHEMISTRY_FIX_TODO.md` (§A–§F9), with empirical
> verification and fleet deployment to v3.131. Several risks listed below are already
> fixed (resume, canonical signatures, dispatch bookkeeping, resolver contracts);
> others remain as documented deferred lanes (F-26 dispatch unification: see
> `.tmp/F26_DESIGN.md`; OQ-4/OQ-5/OQ-8). Keep this file as historical record only.

This report audits the current BioID v2 repository against the intended workflow:

```text
load files -> repair/infer missing data -> extract simulated objects -> generate representations -> search databases -> validate/filter candidates -> output standardized annotations
```

The report is based on inspected code in `main.py`, `api_endpoint.py`, `config.ini`, `requirements.txt`, `src/`, `tests/`, and existing `docs/`. No source code was changed for this audit.

## Summary

The repository has a workable prototype pipeline around MDAnalysis loading, segment-level signature generation, identifier resolvers, summary output, and task orchestration. The largest risks for BioID v2 readiness are:

- No packaging/test configuration and no declared pytest dependency.
- Current tests are likely out of sync with current `Task` and `Simulation` constructors.
- No formal atomic map, entity model, candidate schema, warning schema, or versioned annotation output.
- Entity extraction is currently segment/first-fragment centered.
- Database failures and no-hit cases are not cleanly separated.
- Several scientific inference paths mutate MDAnalysis objects without structured provenance.
- Large MD systems may be loaded fully into memory.
- CLI/API surfaces are prototype-oriented and not yet product-stable.

## Findings

### 1. No Packaging Metadata

- Severity: high
- Location: repository root
- Description: No `pyproject.toml`, `setup.py`, `setup.cfg`, package metadata, or install configuration was found.
- Why it matters: Contributors and users do not have a standard install path, test dependency group, console script, package version, or build metadata.
- Suggested fix: Add `pyproject.toml` with package metadata, runtime dependencies, dev/test dependencies, console scripts, and Python version constraints.
- Blocks readiness: publication yes; API yes; CLI yes; web partially.

### 2. Test Runner Is Not Declared

- Severity: high
- Location: `requirements.txt`, `tests/`
- Description: Tests are pytest-style, but `pytest` is not listed in `requirements.txt`, and no pytest configuration was found. In the inspected environment, `python -m pytest --version` failed with `No module named pytest`.
- Why it matters: Contributors and agents cannot reliably run the test suite from repository instructions alone.
- Suggested fix: Add pytest to dev dependencies and define an official test command.
- Blocks readiness: publication yes; API no; CLI no; web no.

### 3. Current Tests Appear Incompatible With Current Constructors

- Severity: high
- Location: `tests/executor/test_tasks.py`, `tests/executor/test_executor.py`, `tests/loader/test_simulation.py`, `src/executor/task.py`, `src/loader/simulation.py`
- Description: `Task.__init__` asserts `task_progress_info is not None`, but multiple tests instantiate `Task(...)` without `task_progress_info`. `Simulation.__init__` requires `log_handler` and `log_path`, but tests instantiate `Simulation(simulation_directory, results_path)` with two arguments.
- Why it matters: The existing suite likely fails before validating behavior. This undermines trust in all future changes.
- Suggested fix: Either update tests to pass required arguments or make constructor defaults explicit and supported.
- Blocks readiness: publication yes; API yes; CLI partially; web yes.

### 4. Runtime Dependencies Are Pinned but Not Separated

- Severity: medium
- Location: `requirements.txt`
- Description: Runtime, service, chemistry, visualization, and development-like dependencies are pinned in one flat file. There is no separation for test/dev/network/optional dependencies.
- Why it matters: Installing the project may pull heavyweight packages that are not always needed, while missing test tooling. Reproducibility and deployment profiles are unclear.
- Suggested fix: Move to dependency groups such as runtime, dev, test, web, chemistry, and optional database adapters.
- Blocks readiness: publication yes; API partially; CLI partially; web partially.

### 5. CLI Is Prototype-Oriented and Not Product-Stable

- Severity: medium
- Location: `main.py`
- Description: The CLI exposes `--run`, `--input`, repeated `--task`, stats mode, and verbosity flags. It does not expose product-level commands for input validation, output format selection, strict/lenient mode, database search policy, or export.
- Why it matters: BioID users need stable commands for identifying simulations and exporting annotations without knowing internal task names.
- Suggested fix: Add a stable CLI command structure, while preserving current task mode for debugging.
- Blocks readiness: publication partially; API no; CLI yes; web no.

### 6. API Surface Is a Blocking Helper, Not a Typed API

- Severity: medium
- Location: `api_endpoint.py`
- Description: The API exposes only `run_analyze(directory, task_uuid) -> str | None`, which runs the full task chain and returns a `results.json` path.
- Why it matters: API/web integrations need job state, progress, structured errors, warnings, entities, candidates, and typed annotations.
- Suggested fix: Add typed Python API objects and stage methods, or a service layer that wraps the executor with job state and structured results.
- Blocks readiness: publication no; API yes; CLI no; web yes.

### 7. Global Configuration Is Loaded at Import Time

- Severity: medium
- Location: `src/__init__.py`, `config.ini`
- Description: `core_config` is a global `ConfigParser` loaded from `config.ini` at import time and mutated by `api_endpoint.run_analyze`.
- Why it matters: Global mutable config complicates tests, concurrent API jobs, reproducibility, and per-run options.
- Suggested fix: Introduce immutable per-run configuration objects passed into pipeline stages; keep global config only as defaults.
- Blocks readiness: publication partially; API yes; CLI partially; web yes.

### 8. Deployment-Specific Configuration Is Committed

- Severity: high
- Location: `config.ini`
- Description: PDB upload/delete commands include specific SSH/SCP targets and public URLs. BLAST paths and cache paths are machine/deployment-specific.
- Why it matters: This is fragile outside the original deployment and can fail or expose unintended operational assumptions.
- Suggested fix: Move deployment-specific values to environment-specific config templates or secrets, and validate required settings at runtime.
- Blocks readiness: publication yes; API partially; CLI partially; web yes.

### 9. Pipeline Lacks Formal Atomic Map Model

- Severity: high
- Location: `src/loader/simulation.py`, `src/loader/universe_loader.py`
- Description: The atomic system is represented directly by MDAnalysis `Universe`/`AtomGroup`; selected counts and flags are written to `ResultsFile`. There is no `AtomicMap` object or schema.
- Why it matters: Later stages cannot reliably preserve atom/residue/source provenance or validate transformations independently of MDAnalysis.
- Suggested fix: Add a normalized atomic map data contract and adapter from MDAnalysis.
- Blocks readiness: publication partially; API yes; CLI partially; web yes.

### 10. Loader Strategy Selection Is Narrow and Implicitly Ordered

- Severity: medium
- Location: `src/loader/universe_loader.py`
- Description: `load()` iterates `LoadStrategy` enum values and returns the first strategy that succeeds. Strategies generally require exactly one file of each expected type.
- Why it matters: Multiple plausible file combinations, multi-trajectory datasets, and mixed input directories can produce brittle or surprising behavior.
- Suggested fix: Add explicit file discovery, validation, strategy precedence rules, and structured diagnostics for rejected strategies.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 11. XTC Loading Strategy Is Scientifically Suspect

- Severity: high
- Location: `src/loader/universe_loader.py`, `_load_xtc`
- Description: `_load_xtc` attempts `Universe(xtc_files[0], in_memory=True, infer_system=True)` with only an `.xtc` file.
- Why it matters: XTC trajectory files normally require topology information. Treating trajectory-only loading as valid can produce failures or incomplete systems.
- Suggested fix: Require compatible topology for trajectory formats, or mark trajectory-only input as unsupported/degraded with explicit warnings.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 12. PDB Loader Mutates Connectivity Without Provenance

- Severity: high
- Location: `src/loader/universe_loader.py`, `fix_pdb`, `_load_pdb`
- Description: PDB loading writes temporary PDB files, uppercases element fields, removes `CONECT` lines, and uses RDKit `DetermineConnectivity` before loading.
- Why it matters: Connectivity inference changes scientific evidence and should be recorded. Current output only records `LoadStrategy.PDB` and used file.
- Suggested fix: Emit structured `RepairRecord`/warning entries for element normalization, removed bonds, and inferred connectivity.
- Blocks readiness: publication partially; API yes; CLI partially; web yes.

### 13. Large Systems Are Loaded Into Memory

- Severity: high
- Location: `src/loader/universe_loader.py`
- Description: Multiple loader strategies pass `in_memory=True` to MDAnalysis.
- Why it matters: Long trajectories and large systems can exhaust memory, especially for web/API jobs.
- Suggested fix: Make memory mode configurable, default to lazy trajectory loading where possible, and add performance tests.
- Blocks readiness: publication partially; API partially; CLI partially; web yes.

### 14. Repair/Inference Mutates Data Without Structured Records

- Severity: high
- Location: `src/loader/repair_fragment.py`, `Simulation.fix_missing_elements`
- Description: Element inference functions assign `fragment.atoms.elements = new_elements`, but no structured record says which atoms were inferred, method used, confidence, or failure details.
- Why it matters: Final annotations cannot explain uncertainty or distinguish original evidence from inferred fields.
- Suggested fix: Add `RepairRecord` output and avoid silent mutation where an annotation-only repair is safer.
- Blocks readiness: publication partially; API yes; CLI partially; web yes.

### 15. Element Guessing Heuristics Are Risky

- Severity: medium
- Location: `src/loader/repair_fragment.py`, `guess_element`, `estimate_elements_from_names`
- Description: Element guessing uses mass proximity and atom type/name prefixes with broad rules such as `"NA" in t -> "N"` and `"CL" in t -> "CL"`.
- Why it matters: Ambiguous atom names/types can be misclassified, especially for ions, coarse-grained beads, and force-field-specific types.
- Suggested fix: Add force-field-aware rules, confidence scores, ambiguity detection, and tests with negative cases.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 16. Atom Name Repair Is Non-Scientific

- Severity: high
- Location: `src/loader/repair_fragment.py`, `fix_names`
- Description: `fix_names` generates two-character arbitrary names from letters/digits for all atoms in a fragment.
- Why it matters: Arbitrary atom names may make exporters pass while losing chemically meaningful names. This must not be treated as scientific repair.
- Suggested fix: Mark this as export-only synthetic naming, record provenance, and avoid using synthetic names as molecular evidence.
- Blocks readiness: publication partially; API yes; CLI partially; web yes.

### 17. Entity Extraction Is Segment-Centered and Uses Only First Fragment

- Severity: high
- Location: `src/loader/simulation.py`, `get_segments`, `get_fragment`
- Description: `get_fragment(segment_name)` selects atoms by `segid` and returns `fragments[0]`. Segment statistics record molecule counts, but later signature generation iterates segment names and often operates on one representative fragment.
- Why it matters: Repeated molecules, mixed segments, solvent, membrane lipids, and duplicated species may not be represented as first-class entities.
- Suggested fix: Add an entity extraction layer that represents each entity/copy or deduplicated species explicitly.
- Blocks readiness: publication yes; API yes; CLI partially; web yes.

### 18. Entity Classification Is Crude and Contains a Logic Bug

- Severity: high
- Location: `src/verifier/summarizer.py`, `ResultsSummarizer._classify_segment_type`
- Description: Lipid/carbohydrate classification uses carbon/oxygen counts and a condition `1 > (atom_c_cnt / atom_o_cnt) > 3`, which can never be true. As written, that branch cannot classify carbohydrate.
- Why it matters: Entity classes are scientifically important output. A dead condition makes carbohydrate classification impossible through that path.
- Suggested fix: Replace crude heuristics with tested classification rules and add unit tests for lipids, carbohydrates, ligands, ions, solvent, proteins, and nucleic acids.
- Blocks readiness: publication partially; API yes; CLI partially; web yes.

### 19. Nucleic-Acid Applicability Looks Inverted for Multi-Atom Residues

- Severity: high
- Location: `src/signatures/signature_generators/fasta.py`, `MapFastaGenerator._is_applicable`, `ResnameFastaGenerator._is_applicable`; `src/signatures/signature_generators/pdb.py`, `PDBGenerator._is_applicable`
- Description: For nucleic acids, applicability requires `not SegmentSupports.MULTI_ATOM_RESIDUES`. Real nucleic acid residues are typically multi-atom.
- Why it matters: Nucleic acid sequence and PDB representations may be skipped for normal nucleic acid inputs.
- Suggested fix: Revisit the meaning of `MULTI_ATOM_RESIDUES` and add nucleic acid fixtures/tests.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 20. PDB Generation May Use Wrong Atom IDs

- Severity: high
- Location: `src/signatures/signature_generators/pdb.py`, `fragment_to_pdb_biopython`
- Description: In the non-backbone branch, each atom is created with `atom_ids_to_indices[atoms.ids[0]]` rather than `atoms.ids[i]`, so atoms in a residue may receive the same serial/index value.
- Why it matters: Generated PDB signatures feed structural database search. Invalid atom numbering can harm matching and validation.
- Suggested fix: Use the current atom ID/index for each atom and add PDB export validation tests.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 21. PDB Applicability Calls Element Repair When Names Are Not Unique

- Severity: medium
- Location: `src/signatures/signature_generators/pdb.py`, `PDBGenerator._is_applicable`
- Description: If atom names are not unique, the code calls `simulation.fix_missing_elements(fragment_name)` instead of name repair.
- Why it matters: Non-unique names are not fixed by element inference. PDB output can remain invalid.
- Suggested fix: Call a name-specific repair method, or mark PDB generation inapplicable with a warning.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 22. Direct PDB CONECT Writer Cannot Handle More Than Four Bonds

- Severity: medium
- Location: `src/signatures/signature_generators/pdb.py`, `_pdb_bonds_line`
- Description: `_pdb_bonds_line` chooses a format from four templates based on `len(other_atoms) - 1`; atoms with more than four bonded neighbors will index out of range.
- Why it matters: Some structures or inferred connectivity can break PDB export unexpectedly.
- Suggested fix: Split CONECT records into chunks according to PDB format limits.
- Blocks readiness: publication no; API partially; CLI partially; web partially.

### 23. SMILES Generation Depends on Inferred Single Bonds and Retried Bond Order Guessing

- Severity: medium
- Location: `src/signatures/signature_generators/smiles.py`
- Description: All fragment bonds are initially added as single bonds, then RDKit `DetermineBondOrders` is called with a guessed charge that is changed by parsing exception text.
- Why it matters: Incorrect bond orders or charge inference can produce wrong SMILES, especially for ions, lipids, charged ligands, and non-standard chemistry.
- Suggested fix: Record limitations, validate chemistry strictly, and add fixture tests for charged/ambiguous molecules.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 24. Signature Generation Has No Structured Applicability or Failure Output

- Severity: medium
- Location: `src/signatures/signature_manager.py`, `SignatureGenerator.generate_signature`
- Description: Attempted/generated signatures are recorded, but reasons for inapplicability or failure are only logs.
- Why it matters: Users cannot understand why a representation was not produced.
- Suggested fix: Add structured representation status with reason, warning, and provenance.
- Blocks readiness: publication partially; API yes; CLI partially; web yes.

### 25. Database Adapter Failures Are Collapsed

- Severity: high
- Location: `src/identifiers/identifier_resolvers/identifier_resolver.py`, resolver subclasses
- Description: `resolve_signature()` catches `IdentifierResolutionError` and generic exceptions, logs them, and returns `None`. Several subclass methods catch exceptions and return empty lists.
- Why it matters: Database unavailable, no hits, parse failure, disabled resolver, and invalid query can become indistinguishable.
- Suggested fix: Return structured adapter status and warnings; keep no-hit separate from failure.
- Blocks readiness: publication partially; API yes; CLI partially; web yes.

### 26. Candidate Score Semantics Are Inconsistent

- Severity: high
- Location: `src/identifiers/identifier_manager.py`, `add_identifiers`; resolver modules
- Description: Exact hits are stored as `100.0`; some similarity scores are fractions converted to percentages, some are already percentages or thresholds, and BLAST has richer e-value/coverage/identity data that is reduced to one score.
- Why it matters: Candidate ranking and final confidence can be scientifically misleading.
- Suggested fix: Store resolver score, score type, raw metrics, thresholds, and normalized confidence separately.
- Blocks readiness: publication partially; API yes; CLI partially; web yes.

### 27. PubChem Similarity Scores May Be Thresholds, Not Per-Hit Scores

- Severity: medium
- Location: `src/identifiers/identifier_resolvers/pubchem.py`, `pubchem_fetch_similarity_match`
- Description: Similarity results return `[(cid, threshold), ...]`, not per-hit similarity values.
- Why it matters: Downstream ranking may treat all PubChem similarity hits as equally scored at the requested threshold.
- Suggested fix: If PubChem does not provide per-hit score in this path, mark score type as adapter threshold and avoid ranking within that result set by score.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 28. Metadata Downloading Is Mostly Disabled

- Severity: medium
- Location: `src/verifier/metadata_downloader.py`
- Description: Most metadata fetch logic is commented out; `fetch_metadata()` currently returns `sim` without populating per-segment metadata.
- Why it matters: Product output may lack names, accessions, images, and cross-links even when identifiers exist.
- Suggested fix: Decide whether metadata fetching is in scope for current release; re-enable through structured adapters or remove the task from default pipeline.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 29. Summary Verification Uses Wrong VerificationKind for Compounds

- Severity: high
- Location: `src/verifier/summarizer.py`, `ResultsSummarizer.summarize`
- Description: Lipid/carbohydrate segments instantiate `Verifier(..., VerificationKind.PROTEIN, CompoundVerificationWorker())` instead of `VerificationKind.COMPOUND`.
- Why it matters: `Verifier.get_signature()` chooses signature type based on `VerificationKind`; using `PROTEIN` prevents compound verification from selecting SMILES signatures.
- Suggested fix: Use `VerificationKind.COMPOUND` and add tests for compound verification.
- Blocks readiness: publication partially; API yes; CLI partially; web yes.

### 30. Water and Atom Verification Can Bypass Evidence

- Severity: medium
- Location: `src/verifier/verification_workers/verification_core.py`, `calculate_identifier_confidence`
- Description: Water returns PubChem CID `962` with `100.0` confidence; atom returns the first identifier with `100.0`. These shortcuts do not carry provenance or explain evidence.
- Why it matters: Special cases should still show why the result is certain.
- Suggested fix: Convert special cases into explicit validation rules with evidence and provenance.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 31. Annotation Output Is Flexible JSON, Not a Schema

- Severity: high
- Location: `src/loader/results_file.py`, `src/verifier/summarizer.py`
- Description: `ResultsFile` writes arbitrary nested JSON paths. There is no schema version, required fields, type validation, or migration path.
- Why it matters: API/web/repository integrations need stable machine-readable output.
- Suggested fix: Add a versioned annotation schema and adapters from current `ResultsFile`.
- Blocks readiness: publication yes; API yes; CLI partially; web yes.

### 32. `ResultsFile.get_item(default=None)` Cannot Return `None` as a Default

- Severity: medium
- Location: `src/loader/results_file.py`, `get_item`
- Description: `get_item` treats `default is None` as “no default provided,” so callers cannot request `None` as a valid default.
- Why it matters: Several output fields use `None`, and schema handling often needs `None` defaults.
- Suggested fix: Use a sentinel object for default absence.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

### 33. Task Progress and Logging Are File-Based and Unstructured

- Severity: medium
- Location: `src/executor/task.py`, `src/executor/task_creator.py`, `src/utils/logger_utils.py`
- Description: Progress is dumped to `tasks.log` as JSON, errors are extracted from log lines into `errors.log`, and warnings are not structured.
- Why it matters: Web/API consumers need reliable progress, warning, and error schemas.
- Suggested fix: Add structured progress/warning/error events and keep text logs as diagnostics.
- Blocks readiness: publication no; API yes; CLI partially; web yes.

### 34. Logger Cleanup Uses Wrong Logger Name

- Severity: medium
- Location: `src/utils/logger_utils.py`, `close_task_log_output`
- Description: The file handler is added to logger `"identifier"` but removed from logger `"identification"`.
- Why it matters: File handlers can leak across tasks, causing duplicated logs or open file descriptors.
- Suggested fix: Remove the handler from `"identifier"` and add a regression test.
- Blocks readiness: publication no; API partially; CLI partially; web yes.

### 35. Executor Singleton Can Leak State Across Tests or Runs

- Severity: medium
- Location: `src/executor/core.py`, `ExecutorCore(metaclass=Singleton)`
- Description: `ExecutorCore` is a singleton but is instantiated with per-run options such as `terminate_on_finished`, `block_until_finished`, and `force_single_thread`.
- Why it matters: Multiple API jobs or tests can unexpectedly share executor state/configuration.
- Suggested fix: Avoid singleton for per-run executors or make lifecycle explicit and testable.
- Blocks readiness: publication no; API yes; CLI partially; web yes.

### 36. `ExecutorCore.is_active()` Can Access `None`

- Severity: medium
- Location: `src/executor/core.py`, `is_active`
- Description: `is_active()` returns `... and self._worker_thread.is_alive()`, but `_worker_thread` can be `None` after blocking runs or in forced single-thread mode.
- Why it matters: Status polling can raise instead of reporting inactive state.
- Suggested fix: Guard `self._worker_thread is not None`.
- Blocks readiness: publication no; API partially; CLI partially; web yes.

### 37. Signal-Based Timeouts Are Process/Thread Fragile

- Severity: medium
- Location: `src/executor/task.py`, `Task.execute`, `TaskList.execute`
- Description: Tasks use `signal.alarm()` for timeouts. Signal alarms are process-global and only work reliably in the main thread on Unix-like systems.
- Why it matters: Timeout behavior may be unreliable in multiprocessing/threaded API or web contexts.
- Suggested fix: Use process-level timeout management from the executor or a cross-platform timeout strategy.
- Blocks readiness: publication no; API partially; CLI partially; web yes.

### 38. Temporary and Output File Writes Are Spread Across Stages

- Severity: medium
- Location: `src/loader/universe_loader.py`, `src/executor/task_creator.py`, `src/verifier/summarizer.py`, resolver modules
- Description: Stages write `used_files.txt`, `all_files.txt`, temporary PDB files, mmCIF files, images, logs, and results directly.
- Why it matters: File ownership, cleanup, and output schema are hard to reason about, especially for API/web deployments.
- Suggested fix: Centralize output directory management and temporary file cleanup.
- Blocks readiness: publication partially; API partially; CLI partially; web yes.

### 39. Stats Mode Is Interactive

- Severity: low
- Location: `src/stats/stats_aggregator.py`, `SignatureStatsAggregator.run`
- Description: Stats aggregation prompts with `input()` to export failed signatures.
- Why it matters: Interactive prompts are unsuitable for automation, CI, API, and web use.
- Suggested fix: Replace prompts with CLI flags or non-interactive options.
- Blocks readiness: publication no; API no; CLI partially; web partially.

### 40. Documentation Is Now Stronger Than Implementation Contracts

- Severity: medium
- Location: `docs/`
- Description: The repository now has useful specification, architecture, data model, validation, interfaces, database adapter, and testing documents, but many described objects are proposed and not implemented.
- Why it matters: Contributors may assume future contracts already exist.
- Suggested fix: Add status labels in implementation issues/roadmap and prioritize adapters from current output to proposed schemas.
- Blocks readiness: publication partially; API partially; CLI partially; web partially.

## Missing Test Coverage

Current tests cover some loader and executor basics, but the following high-value areas are missing or unclear:

- Direct tests for `src/loader/repair_fragment.py`.
- Tests for PDB/mmCIF/AMBER loading.
- Tests for trajectory plus topology loading.
- Tests for entity extraction beyond segments/fragments.
- Tests for `SignatureType` generators.
- Tests for BLAST parser/filtering.
- Mocked tests for PubChem, ChEMBL, IDSM, PDB/RCSB, AlphaFind, metadata fetchers, and cache behavior.
- Tests for candidate scoring and duplicate/conflict handling.
- Tests for verification workers and compound validation.
- Tests for versioned annotation schema.
- Tests for structured warnings/provenance.
- Performance tests for large systems and trajectories.

## BioID Workflow Divergences

- Atomic map construction is implicit, not a first-class stage.
- Repair/inference happens opportunistically inside simulation/signature methods, not as a structured stage.
- Object extraction is segment-centered and often representative-fragment centered.
- Representation generation lacks structured applicability/failure reporting.
- Database search returns resolver-specific lists rather than normalized candidates.
- Candidate validation is summary-time and not modeled as candidate-level records.
- Standardized annotation output is not versioned or schema-validated.

## Suggested Priority Fixes

1. Make the current test suite runnable and update stale tests.
2. Add packaging metadata and dev/test dependencies.
3. Fix high-risk correctness bugs in summary classification, compound verification, nucleic-acid applicability, and PDB atom numbering.
4. Add structured warning/provenance records for repair/inference and database failures.
5. Add a minimal atomic map/entity abstraction or adapter.
6. Add normalized candidate output with score semantics.
7. Add versioned annotation schema output.
8. Refactor database adapters for mockable failure-aware behavior.
9. Reduce memory risk in loader strategies.
10. Stabilize CLI/API contracts around the documented product interfaces.
