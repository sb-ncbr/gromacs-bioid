# BioID v2 Implementation Roadmap

This roadmap turns the current repository state into a practical polishing plan for BioID v2. It is intended for Codex agents, Claude Code agents, and human contributors. Tasks are written so they can be copied into future implementation prompts.

Current repository facts:

- Source code lives under `src/`.
- Main CLI entry point is `main.py`.
- A service-facing file exists at `api_endpoint.py`.
- Configuration currently lives in `config.ini`.
- Dependencies are listed in `requirements.txt`; no packaging file such as `pyproject.toml` is currently present.
- Tests live under `tests/`.
- Core implementation areas are `src/loader`, `src/signatures`, `src/identifiers`, `src/verifier`, `src/executor`, `src/stats`, and `src/utils`.
- The current persisted output path is the JSON-oriented `ResultsFile` abstraction in `src/loader/results_file.py`.

Use this roadmap with the project specification documents in `docs/`. Preserve existing public behavior unless a task explicitly calls out a bug fix or schema versioning step.

## Phase 1: Stabilize Repository and Tests

### Goal

Make the repository importable, testable, and predictable before deeper scientific changes.

### Concrete Tasks

- Add or confirm project packaging metadata. If adding packaging, define package discovery for the current `src` layout and keep `main.py` usable.
- Decide whether the package import name remains `src` or moves to a BioID-specific package name. Do not rename modules until a migration plan exists.
- Turn `requirements.txt` into a documented dependency source, or add a packaging file that captures runtime and test dependencies.
- Add pytest configuration for markers such as `network`, `slow`, `integration`, and optional MDAnalysis/RDKit-heavy tests.
- Ensure `main.py --help` works without importing optional heavy dependencies.
- Make a small smoke test set that avoids network calls and large binary fixtures.
- Keep default tests offline. Move real database tests behind an explicit marker.
- Add CI configuration after test commands are stable.

### Likely Files/Modules

- `requirements.txt`
- `main.py`
- `config.ini`
- `tests/`
- Proposed packaging file: `pyproject.toml` or equivalent
- Proposed CI config under `.github/workflows/` if GitHub Actions is chosen

### Validation/Tests

- `uv run pytest` should discover tests.
- A fast command such as `uv run pytest tests/output tests/utils tests/error_handling` should pass without network.
- CLI help should be checked with `uv run python main.py --help`.
- Import smoke tests should cover the intended public package/module import path.

### Blockers

- No repository-level packaging metadata is currently present.
- Local `python -m pytest` may fail when pytest is not installed outside the managed environment.
- Several modules import heavy scientific dependencies at import time.

### Definition of Done

- A new contributor can install or run the project using documented commands.
- CLI help and package imports are covered by smoke tests.
- Default tests are offline and can be run in CI.
- Optional network and expensive tests are clearly marked.

## Phase 2: Formalize Data Model and Annotation Schema

### Goal

Define stable objects that move through the BioID pipeline and produce versioned, machine-readable annotations.

### Concrete Tasks

- Implement the concepts in `docs/DATA_MODEL.md`: `InputBundle`, `AtomicMap`, `RepairRecord`, `SimulatedObject` or `Entity`, `MolecularRepresentation`, `DatabaseCandidate`, `ValidationResult`, and `FinalAnnotation`.
- Decide whether these objects are implemented with dataclasses, Pydantic, TypedDict, or another typed model. Keep dependency impact explicit.
- Add schema versioning to final annotation output.
- Add software/version metadata to outputs.
- Add a warnings/provenance channel that can be carried from loading through final annotation.
- Keep `ResultsFile` compatibility while introducing a stable export layer.
- Write JSON schema or equivalent validation for final annotations.

### Likely Files/Modules

- `src/loader/results_file.py`
- `src/loader/simulation.py`
- `src/loader/repair_fragment.py`
- `src/signatures/signature_manager.py`
- `src/identifiers/identifier_manager.py`
- `src/verifier/verification_workers/verification_core.py`
- `src/verifier/summarizer.py`
- Proposed new model/schema module under `src/`, with name chosen during implementation
- `tests/output/`

### Validation/Tests

- Add golden JSON tests for final annotations.
- Add schema validation tests for required fields and stable ordering.
- Test that warnings and repair records survive serialization.

### Blockers

- Current output is a free-form nested JSON structure.
- Candidate hits, validation, and summary output are not represented by one typed schema.
- Existing confidence fields mix original database scores and observed validation scores.

### Definition of Done

- Final annotations have a documented schema version.
- Every final annotation can reference candidates, evidence, warnings, and provenance.
- Output comparison tests can detect accidental schema drift.

## Phase 3: Harden Input Loading

### Goal

Make file loading reliable for supported MD and structure inputs, with clear metadata and error behavior.

### Concrete Tasks

- Inventory the current `LoadStrategy` values in `src/loader/universe_loader.py` and document which formats are actually supported.
- Validate topology/coordinate/trajectory combinations before constructing an MDAnalysis universe.
- Make unsupported or missing files fail with actionable messages.
- Preserve loader metadata: selected strategy, original paths, topology path, coordinate path, trajectory path, and MDAnalysis load details where available.
- Add explicit handling for single structure files such as PDB.
- Add or propose explicit mmCIF and AMBER support only after confirming MDAnalysis behavior and fixtures.
- Review `_load_xtc`; trajectory-only loading should require or report the missing topology requirement clearly.
- Keep generated temporary files deterministic and isolated.

### Likely Files/Modules

- `src/loader/universe_loader.py`
- `src/loader/simulation.py`
- `src/loader/results_file.py`
- `src/utils/file_utils.py`
- `tests/loader/test_universe_loader.py`
- `tests/loader/test_simulation.py`

### Validation/Tests

- Add tiny PDB fixture tests for atom count, residue names, segment or chain identifiers, and coordinates.
- Add tests for missing topology plus trajectory combinations.
- Add tests for unsupported extensions.
- Add tests that loader metadata is persisted.
- Avoid large binary fixtures; use tiny synthetic files or fixture generation code.

### Blockers

- Current implementation lists GROMACS-oriented strategies and PDB but does not clearly expose AMBER or mmCIF support.
- Some strategies rely on optional dependencies and external tools.
- Loader metadata is written in fragments rather than through a typed `InputBundle`.

### Definition of Done

- Supported formats are documented from implementation and covered by tests.
- Missing or invalid input combinations produce clear errors.
- Loader output records enough metadata for reproducibility.

## Phase 4: Harden Repair and Inference

### Goal

Allow safe deterministic repair while making uncertainty visible and avoiding scientifically unsafe guesses.

### Concrete Tasks

- Convert repair operations in `src/loader/repair_fragment.py` into recorded `RepairRecord` entries.
- Preserve original values when names, elements, masses, or bonds are changed or inferred.
- Add confidence or certainty levels to each inference.
- Distinguish loaded, inferred, repaired, and unknown fields.
- Review element inference from mass, atom name, and atom type for ambiguous cases.
- Make missing masses and missing bonds explicit instead of silently masking uncertainty.
- Add warnings for unknown residues and conflicting topology/coordinate information.
- Fix representation code paths that call repair functions for the wrong reason.

### Likely Files/Modules

- `src/loader/repair_fragment.py`
- `src/loader/simulation.py`
- `src/signatures/signature_generators/pdb.py`
- `src/signatures/signature_generators/smiles.py`
- `src/signatures/signature_manager.py`
- `tests/loader/test_repair_fragment.py`

### Validation/Tests

- Test missing element inferred from atom name.
- Test missing element inferred from mass.
- Test ambiguous atom names produce warnings or unknown values.
- Test original values are retained after repair.
- Test unsafe repair is rejected or marked unsupported.

### Blockers

- Current repair logic mutates MDAnalysis fragments directly.
- There is no central provenance ledger for repairs.
- Current warnings are mainly logger messages, not annotation data.

### Definition of Done

- Every repair or inference can be traced from output back to method and source field.
- Ambiguous inference is visible in final annotations.
- Unsafe or impossible repair is not silently accepted.

## Phase 5: Harden Entity Extraction

### Goal

Extract biological and chemical entities from whole MD systems without collapsing distinct molecules or flooding output with duplicate solvent/ion annotations.

### Concrete Tasks

- Define the entity extraction contract for proteins, nucleic acids, lipids, ligands, ions, solvent, unknowns, and transformed simulation products.
- Review current segment/fragment logic in `src/loader/simulation.py`.
- Add stable entity IDs and atom selections for every extracted object.
- Track copy number and deduplication keys for repeated molecular species.
- Preserve parent system, segment, chain, residue range, and atom membership.
- Summarize high-copy solvent, ions, and lipids intentionally instead of emitting uncontrolled duplicate annotations.
- Add explicit unknown or ambiguous entity handling.
- Ensure entity boundaries remain biologically meaningful for repeated chains and ligands.

### Likely Files/Modules

- `src/loader/simulation.py`
- `src/loader/results_file.py`
- `src/signatures/signature_manager.py`
- `src/verifier/summarizer.py`
- `tests/loader/test_simulation.py`
- Proposed entity model module under `src/`, with name chosen during implementation

### Validation/Tests

- One protein chain.
- Protein plus ligand.
- Protein plus ions and water.
- Repeated protein chains.
- Unknown residue/entity.
- Proposed future tests for nucleic acids and membrane/lipid-heavy systems.

### Blockers

- Current extraction is segment- and fragment-centered rather than an explicit BioID entity model.
- Copy number and deduplication are not first-class output fields.
- Lipid-heavy systems may be inefficient if every copy is processed independently.

### Definition of Done

- Every emitted entity has a stable ID, atom membership, type, and provenance.
- Duplicate species are represented with copy counts where appropriate.
- Unknown entities remain visible instead of being discarded.

## Phase 6: Harden Representation Generation

### Goal

Generate deterministic, valid molecular representations only when the source data supports them.

### Concrete Tasks

- Map current `SignatureType` values in `src/signatures/signature_manager.py` to BioID representation types.
- Replace bare return values or `None` with a representation result that can express success, unsupported, ambiguous, and failed.
- Ensure FASTA generation is deterministic and residue-aware for proteins and nucleic acids.
- Ensure PDB and mmCIF fragments preserve atom order, residue identifiers, and chain or segment metadata where possible.
- Keep SMILES generation limited to chemically valid cases; do not emit fake chemical strings from incomplete topology.
- Decide whether InChI is in scope for the current implementation; if not, mark it proposed.
- Make method/provenance and limitations part of every representation output.
- Review nucleic-acid applicability checks so valid nucleotide residues are not incorrectly rejected.

### Likely Files/Modules

- `src/signatures/signature_manager.py`
- `src/signatures/signature_generators/fasta.py`
- `src/signatures/signature_generators/pdb.py`
- `src/signatures/signature_generators/smiles.py`
- `src/signatures/signature_generators/fingerprint.py`
- `src/signatures/signature_generators/atom.py`
- `src/signatures/signature_generators/name.py`
- `src/verifier/summarizer.py`
- `tests/signatures/test_signature_generators.py`

### Validation/Tests

- Protein to FASTA.
- Protein to PDB fragment.
- Nucleic acid to sequence.
- Ligand to SMILES only when chemically valid.
- Ion to identifier-like representation.
- Unknown entity to unsupported or ambiguous status.
- Deterministic output comparison for repeated runs.

### Blockers

- mmCIF output currently appears in summary behavior rather than as a general representation generator.
- InChI generation is not currently present.
- Some applicability checks encode scientific assumptions that need review.

### Definition of Done

- Representation generation is deterministic and provenance-rich.
- Invalid or unsupported representations are explicit.
- Tests cover each existing generator and common failure paths.

## Phase 7: Modularize Database Adapters

### Goal

Make external database search modular, offline-testable, and normalized into a common candidate model.

### Concrete Tasks

- Define an adapter interface around molecular representation input and `DatabaseCandidate` output.
- Normalize all resolver output fields: database, identifier, identifier type, name, synonyms, score, URL, method, raw response pointer, and provenance.
- Preserve raw response metadata by pointer or cached fixture, not by uncontrolled embedding.
- Keep live network calls out of default tests.
- Add explicit handling for empty results, malformed responses, rate limits, timeouts, and unavailable services.
- Review cache behavior in `src/identifiers/cache_manager.py`.
- Add optional live tests for selected adapters behind a network marker.

### Likely Files/Modules

- `src/identifiers/identifier_manager.py`
- `src/identifiers/cache_manager.py`
- `src/identifiers/identifier_resolvers/`
- `tests/identifiers/test_identifier_resolvers.py`
- `docs/DATABASE_ADAPTERS.md`

### Validation/Tests

- Mocked responses for each resolver family.
- Cached fixture tests for representative successful and failed responses.
- Schema validation for normalized candidates.
- Tests proving default test runs do not require internet access.

### Blockers

- Current resolver outputs are not normalized through one typed candidate object.
- Several resolvers assume network availability.
- Reliability concerns such as obsolete identifiers and redundant hits are not centrally handled.

### Definition of Done

- Every adapter returns the same candidate shape.
- Network failures are recoverable and visible.
- Offline tests cover parsing and normalization for each supported adapter family.

## Phase 8: Improve Scoring, Filtering, and Confidence

### Goal

Rank and explain database candidates without hiding ambiguity or mixing incompatible score types.

### Concrete Tasks

- Define a `ValidationResult` model for candidate checks.
- Separate original database score, BioID validation score, and final confidence.
- Record rejection reasons and conflicts.
- Preserve ambiguous candidate sets instead of over-filtering.
- Add entity type compatibility checks for protein, nucleic acid, compound, ion, solvent, lipid, and unknown entities.
- Review validation workers in `src/verifier/verification_workers/`.
- Fix compound/lipid/carbohydrate verification kind selection in summary logic.
- Make confidence classes or score ranges comparable across database families.
- Add warnings for conflicting identifiers and multiple equivalent best hits.

### Likely Files/Modules

- `src/verifier/verification_workers/verification_core.py`
- `src/verifier/verification_workers/protein_nucleic_worker.py`
- `src/verifier/verification_workers/compound_worker.py`
- `src/verifier/summarizer.py`
- `src/identifiers/identifier_manager.py`
- `tests/verifier/test_verification_core.py`

### Validation/Tests

- Single perfect candidate.
- Multiple equivalent candidates.
- Conflicting database identifiers.
- High sequence match with wrong entity type.
- Good structural match with poor metadata.
- No candidate.
- Candidate below threshold.

### Blockers

- Current summary confidence can differ from observed validation confidence.
- Candidate rejection reasons are not first-class data.
- Scores from sequence, structure, chemical, and name searches are not clearly normalized.

### Definition of Done

- Final annotations include best hit, candidate list, confidence, evidence, warnings, and conflicts.
- Ranking behavior is deterministic and covered by tests.
- Ambiguous results remain inspectable.

## Phase 9: Finalize CLI

### Goal

Expose BioID behavior through a stable command-line interface suitable for local users and batch workflows.

### Concrete Tasks

- Decide CLI command names and whether the current `main.py` remains the entry point.
- Align CLI naming with BioID v2 instead of legacy BAT wording where appropriate.
- Add or document commands for identifying a simulation, validating inputs, exporting annotations, and showing stats.
- Add options for network on/off, output format, strict/lenient mode, verbose logging, and saving intermediate representations.
- Ensure help and argument validation avoid heavy imports.
- Return useful exit codes for fatal errors, recoverable warnings, and validation failures.
- Make log file locations and result paths predictable.

### Likely Files/Modules

- `main.py`
- `src/executor/task_creator.py`
- `src/executor/core.py`
- `src/executor/task.py`
- `src/stats/stats_aggregator.py`
- `src/utils/logger_utils.py`
- `config.ini`
- CLI tests under `tests/`

### Validation/Tests

- CLI help test.
- CLI input validation test.
- Offline identify smoke test using a tiny fixture.
- Strict versus lenient mode behavior tests once modes exist.
- Snapshot or golden test for exported annotation output.

### Blockers

- There is no packaging entry point yet.
- Current CLI behavior is tied to task execution and config conventions.
- Some imports still depend on optional scientific packages.

### Definition of Done

- CLI commands and options are documented.
- Help works in a minimal environment.
- Offline smoke workflow produces a schema-valid annotation file.

## Phase 10: Prepare API/Web Integration

### Goal

Separate reusable pipeline behavior from CLI concerns so API and web integrations can submit jobs, track progress, and retrieve reproducible results.

### Concrete Tasks

- Inspect and define the role of `api_endpoint.py`.
- Create a service-level contract for input submission, job creation, progress reporting, result retrieval, and error reporting.
- Keep pipeline execution independent from web framework details.
- Make warnings, repairs, database status, and reproducibility metadata available through the service layer.
- Define job states for queued, running, completed, completed with warnings, failed, and canceled if cancellation is supported.
- Ensure uploaded files are handled safely with size limits, extension checks, and isolated working directories.
- Keep database/network behavior configurable per job.

### Likely Files/Modules

- `api_endpoint.py`
- `src/executor/core.py`
- `src/executor/task.py`
- `src/executor/task_creator.py`
- `src/loader/results_file.py`
- `src/utils/logger_utils.py`
- Proposed service contract module under `src/`, with name chosen during implementation

### Validation/Tests

- Unit tests for job-state transitions.
- Tests for failed input validation.
- Tests for result download metadata.
- Tests with mocked pipeline execution.
- Optional web-framework tests only after the framework dependency is explicit.

### Blockers

- The stable final annotation schema must exist first.
- Pipeline progress and warnings are not currently centralized.
- API behavior is not yet documented as current versus proposed.

### Definition of Done

- CLI, Python API, and web/API service can call the same pipeline core.
- Jobs expose progress, warnings, errors, and reproducibility metadata.
- Service tests do not require live databases or large files.

## Phase 11: Prepare Publication-Quality Examples and Evaluation

### Goal

Provide small reproducible examples and evaluation evidence that BioID v2 works on realistic messy MD inputs.

### Concrete Tasks

- Create tiny fixture systems for protein, protein plus ligand, nucleic acid, ions plus solvent, unknown residue, duplicated species, and a degraded input.
- Add documented fixture-generation scripts when binary fixtures would be too large or unclear.
- Add golden annotation outputs with schema versions.
- Add evaluation cases for false positives, false negatives, ambiguous candidates, and redundant database hits.
- Add optional benchmark systems that are not part of the default test run.
- Add documentation showing CLI/API/web expected outputs for the same example.
- Define publication readiness criteria for CLI, API, and future web usage.

### Likely Files/Modules

- `tests/`
- Proposed fixture directory under `tests/`
- Proposed examples directory if publication examples are added
- `docs/SPECIFICATION.md`
- `docs/VALIDATION_PLAN.md`
- `docs/TESTING.md`
- `docs/INTERFACES.md`

### Validation/Tests

- Golden output comparison for stable JSON annotations.
- Tolerant score comparison where external algorithms produce small numeric differences.
- Performance smoke tests for duplicate-heavy systems.
- Optional live-network evaluation behind explicit markers.

### Blockers

- Schema versioning and deterministic output are prerequisites.
- Some target systems require file formats not yet proven in the current loader.
- Real database behavior must not make publication examples flaky.

### Definition of Done

- The repository contains small, documented examples that run offline.
- Evaluation outputs are reproducible and reviewable.
- Publication claims are backed by tests, fixtures, or clearly marked manual evaluation.

## Cross-Phase Rules for Future Agents

- Inspect the repository before changing code.
- Do not invent module paths or commands; discover them locally.
- Keep changes small and reviewable.
- Add tests when behavior changes.
- Keep scientific uncertainty visible in data, logs, and final annotations.
- Do not make default tests depend on live network services.
- Do not add large binary fixtures without a documented reason and alternative.
- Do not silently convert uncertain or invalid molecular information into confident identifiers.
- Prefer schema versioning over incompatible output changes.
- Preserve enough provenance to explain every final annotation.
