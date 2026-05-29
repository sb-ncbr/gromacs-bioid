# BioID v2 Tasks

This task list is derived from the current repository, `docs/ROADMAP.md`, `docs/CODE_HEALTH_REPORT.md`, `docs/VALIDATION_PLAN.md`, `docs/TESTING.md`, and existing tests. No task is marked complete unless it is explicitly verified in a future session.

## Phase 1 — Repository stabilization

- [ ] Add project packaging metadata
  - Goal: Define how BioID v2 is installed, imported, tested, and exposed as a CLI without changing scientific behavior.
  - Files: `requirements.txt`, `main.py`, proposed `pyproject.toml`, `tests/`
  - Validation: Run import smoke tests and `uv run pytest` discovery.
  - Definition of done: Package metadata declares runtime/test dependencies, Python version support, package discovery, and the current CLI entry point or an explicit placeholder for it.

- [ ] Declare and document the official test command
  - Goal: Make the test runner reproducible for contributors and agents.
  - Files: `requirements.txt`, proposed `pyproject.toml`, proposed pytest config, `docs/TESTING.md`, `tests/`
  - Validation: `uv run pytest` runs or fails only for known dependency/test issues documented in the task output.
  - Definition of done: Pytest is declared in dev/test dependencies, test markers are configured, and `docs/TESTING.md` names the current command.

- [ ] Repair stale constructor tests
  - Goal: Align tests with current `Task` and `Simulation` constructor signatures or make defaults explicit if they are intended public behavior.
  - Files: `tests/executor/test_tasks.py`, `tests/executor/test_executor.py`, `tests/loader/test_simulation.py`, `src/executor/task.py`, `src/loader/simulation.py`
  - Validation: Run the affected test files with `uv run pytest`.
  - Definition of done: Existing tests validate current behavior without bypassing required constructor arguments.

- [ ] Add offline smoke tests for imports and CLI help
  - Goal: Prove basic package import and `main.py --help` work without live databases or full MD dependencies where possible.
  - Files: `main.py`, `tests/`, proposed CLI smoke test file
  - Validation: `uv run pytest` on the smoke test file; `uv run python main.py --help`.
  - Definition of done: Smoke tests fail clearly if imports or CLI help regress.

- [ ] Separate deployment-specific configuration from defaults
  - Goal: Remove machine-specific assumptions from normal repository use while preserving current configurable behavior.
  - Files: `config.ini`, proposed config template, `src/__init__.py`, `src/utils/sync_databases.py`
  - Validation: Run config-loading tests and a no-network smoke test.
  - Definition of done: Host-specific upload/delete commands, BLAST paths, cache paths, and sync behavior are documented as environment-specific settings.

## Phase 2 — Data model/schema

- [ ] Define the minimal versioned annotation envelope
  - Goal: Introduce a stable top-level schema for outputs without replacing all internals at once.
  - Files: `src/loader/results_file.py`, `src/verifier/summarizer.py`, proposed schema/model module, `tests/output/test_annotation_output_schema.py`
  - Validation: Add schema validation tests for required top-level fields.
  - Definition of done: Output can include `schema_version`, run metadata, warnings, candidates, validation results, and final annotations.

- [ ] Add proposed core model objects
  - Goal: Implement initial typed objects for `InputBundle`, `AtomicMap`, `RepairRecord`, `Entity`, `MolecularRepresentation`, `DatabaseCandidate`, `ValidationResult`, and `FinalAnnotation`.
  - Files: proposed model module under `src/`, `docs/DATA_MODEL.md`, `tests/output/`
  - Validation: Unit tests instantiate, serialize, and validate each object.
  - Definition of done: The model objects exist, are typed, and do not require network or MDAnalysis to test.

- [ ] Build an adapter from current `ResultsFile` JSON to the proposed schema
  - Goal: Preserve current pipeline output while making it consumable by a versioned annotation schema.
  - Files: `src/loader/results_file.py`, `src/verifier/summarizer.py`, proposed output adapter, `tests/output/`
  - Validation: Golden-output test using a small synthetic `ResultsFile` payload.
  - Definition of done: Existing result paths can be adapted into a schema-valid annotation envelope.

- [ ] Add a structured warning/provenance record
  - Goal: Make warnings and provenance first-class data instead of log-only context.
  - Files: proposed model module, `src/loader/results_file.py`, `src/utils/logger_utils.py`, `tests/output/`
  - Validation: Tests assert warning/provenance records survive JSON serialization.
  - Definition of done: A pipeline stage can emit structured warnings with stage, severity, affected object, and confidence impact.

## Phase 3 — Input loading

- [ ] Document actual loader strategy support in code and tests
  - Goal: Confirm supported formats from `LoadStrategy`, not from project goals.
  - Files: `src/loader/universe_loader.py`, `docs/SPECIFICATION.md`, `docs/TESTING.md`, `tests/loader/test_universe_loader.py`
  - Validation: Tests assert discovered strategies and expected file combinations.
  - Definition of done: GROMACS/PDB/XTC support boundaries are explicit, and AMBER/mmCIF support is marked needs confirmation if not implemented.

- [ ] Validate topology and trajectory combinations before loading
  - Goal: Prevent trajectory-only or mismatched input from being treated as valid scientific input.
  - Files: `src/loader/universe_loader.py`, `tests/loader/test_universe_loader.py`
  - Validation: Tests for XTC without topology, topology without coordinates, and unsupported combinations.
  - Definition of done: Invalid combinations fail with actionable errors and structured loader diagnostics.

- [ ] Preserve loader metadata
  - Goal: Record selected strategy, attempted strategies, used files, ignored files, and input relationships.
  - Files: `src/loader/universe_loader.py`, `src/loader/results_file.py`, proposed `InputBundle` model, `tests/loader/`
  - Validation: Loader tests assert metadata is present in output.
  - Definition of done: Every successful load records enough metadata to reproduce file selection.

- [ ] Add tiny single-structure loading fixture tests
  - Goal: Validate PDB-style loading for atom count, residues, segments/chains, and coordinates.
  - Files: `tests/loader/`, `tests/data/`, `src/loader/universe_loader.py`
  - Validation: Run the new loader fixture tests.
  - Definition of done: A tiny fixture verifies that core structure fields are preserved after loading.

- [ ] Confirm AMBER and mmCIF loading support
  - Goal: Determine whether AMBER and mmCIF inputs are supported today or only proposed.
  - Files: `src/loader/universe_loader.py`, `docs/SPECIFICATION.md`, `docs/ARCHITECTURE.md`, `tests/loader/`
  - Validation: Add tests if support exists; otherwise update docs with explicit limitations.
  - Definition of done: The repository no longer implies unverified AMBER/mmCIF support. This task needs confirmation.

## Phase 4 — Atomic map and repair

- [ ] Introduce a minimal `AtomicMap` adapter from MDAnalysis
  - Goal: Capture atoms, residues, segments, coordinates, elements, masses, bonds, charges, and source status outside direct MDAnalysis access.
  - Files: `src/loader/simulation.py`, proposed model module, `tests/loader/`
  - Validation: Unit tests build an `AtomicMap` from a tiny loaded or synthetic system.
  - Definition of done: Required and optional atomic fields are explicit, and missing values remain visible.

- [ ] Record repair operations as `RepairRecord` data
  - Goal: Track what was missing, inferred, repaired, method used, confidence, and original values.
  - Files: `src/loader/repair_fragment.py`, `src/loader/simulation.py`, proposed model module, `tests/loader/test_repair_fragment.py`
  - Validation: Tests for element inference from mass/name/type assert repair records.
  - Definition of done: Repair operations no longer mutate scientific fields without structured provenance.

- [ ] Mark synthetic atom names as export-only repairs
  - Goal: Prevent arbitrary generated atom names from being treated as molecular evidence.
  - Files: `src/loader/repair_fragment.py`, `src/loader/simulation.py`, `src/signatures/signature_generators/pdb.py`, `tests/loader/`
  - Validation: Tests assert generated names carry low-confidence/export-only provenance.
  - Definition of done: Synthetic names are visible as synthetic and do not improve identity confidence.

- [ ] Add ambiguity tests for element inference
  - Goal: Catch risky atom-name/type heuristics before they create false certainty.
  - Files: `src/loader/repair_fragment.py`, `tests/loader/test_repair_fragment.py`, `src/constants.py`
  - Validation: Tests for ions, unusual residues, ambiguous names, and unknown atom types.
  - Definition of done: Ambiguous inference produces warnings or unknown values rather than confident false elements.

- [ ] Make PDB connectivity inference provenance-aware
  - Goal: Record element normalization, removed `CONECT` lines, and RDKit-inferred connectivity during PDB loading.
  - Files: `src/loader/universe_loader.py`, `src/loader/results_file.py`, proposed repair/provenance model, `tests/loader/`
  - Validation: PDB loader test asserts connectivity changes are recorded.
  - Definition of done: PDB repair/inference steps are visible in output.

## Phase 5 — Entity extraction

- [ ] Define an explicit entity extraction contract
  - Goal: Move beyond segment/first-fragment assumptions toward BioID entities with atom membership.
  - Files: `src/loader/simulation.py`, proposed entity model, `docs/DATA_MODEL.md`, `tests/loader/`
  - Validation: Unit tests create entities with IDs, type, atom selection, segment/chain, residue range, and parent system.
  - Definition of done: Entity extraction has a documented code contract and does not depend on summary output.

- [ ] Preserve duplicate species and copy number
  - Goal: Represent repeated chains, lipids, solvent, and ions without losing atom membership or flooding annotations.
  - Files: `src/loader/simulation.py`, `src/verifier/summarizer.py`, proposed entity model, `tests/loader/`
  - Validation: Tests for repeated protein chains and repeated small molecules.
  - Definition of done: Copy number and deduplication key are explicit fields.

- [ ] Replace crude segment classification with tested rules
  - Goal: Classify proteins, nucleic acids, compounds, lipids, carbohydrates, solvent, ions, and unknowns more reliably.
  - Files: `src/verifier/summarizer.py`, `src/loader/simulation.py`, `tests/verifier/`, `tests/loader/`
  - Validation: Unit tests for each supported entity class and unknown residues.
  - Definition of done: The dead carbohydrate condition is fixed, and classification uncertainty is reported.

- [ ] Add unknown and ambiguous entity tests
  - Goal: Ensure unknown residues/entities are preserved instead of discarded or over-classified.
  - Files: `src/loader/simulation.py`, `src/verifier/summarizer.py`, `tests/loader/`, `tests/verifier/`
  - Validation: Tests with unusual residue names and mixed segments.
  - Definition of done: Unknown entities appear in output with warnings and atom membership.

## Phase 6 — Representation generation

- [ ] Add structured representation result status
  - Goal: Replace bare signature values or `None` with success, unsupported, ambiguous, or failed statuses.
  - Files: `src/signatures/signature_manager.py`, `src/signatures/signature_generators/signature_generator.py`, `tests/signatures/`
  - Validation: Tests assert applicability and failure reasons are recorded.
  - Definition of done: Users can see why each representation was or was not generated.

- [ ] Fix PDB atom numbering and name-repair path
  - Goal: Correct high-risk PDB representation bugs found in the audit.
  - Files: `src/signatures/signature_generators/pdb.py`, `tests/signatures/test_signature_generators.py`
  - Validation: PDB export tests inspect atom serial/index stability and non-unique name handling.
  - Definition of done: Generated PDB fragments are deterministic and valid for representative small systems.

- [ ] Chunk PDB `CONECT` records safely
  - Goal: Avoid export failure when atoms have more bonded neighbors than one PDB `CONECT` line can hold.
  - Files: `src/signatures/signature_generators/pdb.py`, `tests/signatures/`
  - Validation: Unit test for an atom with more than four bonded neighbors.
  - Definition of done: PDB bond output respects PDB line limits.

- [ ] Review nucleic acid FASTA/PDB applicability
  - Goal: Confirm and fix the current multi-atom residue check for nucleic acid representations.
  - Files: `src/signatures/signature_generators/fasta.py`, `src/signatures/signature_generators/pdb.py`, `tests/signatures/`
  - Validation: Add a tiny nucleic-acid-like fixture or synthetic segment test.
  - Definition of done: Valid nucleic acid residues can generate intended sequence/structure representations. This task needs confirmation for fixture design.

- [ ] Make SMILES generation explicitly conservative
  - Goal: Avoid emitting invalid or over-confident SMILES from incomplete topology, guessed charges, or unsafe bond order inference.
  - Files: `src/signatures/signature_generators/smiles.py`, `tests/signatures/`
  - Validation: Tests for chemically valid ligand, ion, unknown entity, and failed bond order inference.
  - Definition of done: SMILES output includes method/provenance and invalid cases return explicit failure/unsupported status.

- [ ] Confirm InChI representation scope
  - Goal: Decide whether InChI generation is implemented, planned, or out of scope for the current milestone.
  - Files: `src/signatures/`, `src/verifier/metadata_fetchers/inchikey_fetcher.py`, `docs/SPECIFICATION.md`, `docs/DATA_MODEL.md`
  - Validation: Add tests only if generation is implemented.
  - Definition of done: Docs and task backlog clearly mark InChI as implemented or proposed. This task needs confirmation.

## Phase 7 — Database adapters

- [ ] Define a common database adapter result model
  - Goal: Normalize resolver outputs into `DatabaseCandidate` with database, identifier, score, method, URL, raw response pointer, and provenance.
  - Files: `src/identifiers/identifier_manager.py`, `src/identifiers/identifier_resolvers/`, proposed model module, `tests/identifiers/`
  - Validation: Unit tests normalize mocked responses from each resolver family.
  - Definition of done: Resolvers can return a shared candidate shape without losing raw metrics.

- [ ] Separate no-hit, failure, disabled, and malformed-response states
  - Goal: Prevent database outages and parse errors from looking like valid empty result sets.
  - Files: `src/identifiers/identifier_resolvers/identifier_resolver.py`, resolver modules, `tests/identifiers/`
  - Validation: Mocked tests for network failure, empty result, malformed response, and disabled resolver.
  - Definition of done: Adapter status is explicit and warnings are emitted for failures.

- [ ] Add offline mocked tests for PDB/RCSB and BLAST parsing
  - Goal: Cover high-value sequence/structure database parsing without live services.
  - Files: `src/identifiers/identifier_resolvers/blast.py`, `src/identifiers/identifier_resolvers/pdb_struct.py`, `tests/identifiers/`
  - Validation: Run identifier tests with no network access.
  - Definition of done: Representative successful, empty, and malformed responses are covered by fixtures or inline mocks.

- [ ] Add offline mocked tests for PubChem, ChEMBL, IDSM, and AlphaFind
  - Goal: Cover chemical and structural similarity adapters without live services.
  - Files: `src/identifiers/identifier_resolvers/pubchem.py`, `chembl.py`, `idsm.py`, `alphafind_struct.py`, `tests/identifiers/`
  - Validation: Run identifier tests with mocked HTTP/local-executable behavior.
  - Definition of done: Default tests do not require internet or local database executables.

- [ ] Review cache behavior and corruption handling
  - Goal: Make local caching deterministic and failure-aware.
  - Files: `src/identifiers/cache_manager.py`, `tests/identifiers/`
  - Validation: Tests for cache hit, cache miss, missing database, and malformed/corrupt cache.
  - Definition of done: Cache failures are separate from no-hit database results.

## Phase 8 — Filtering/scoring

- [ ] Separate resolver score, validation score, and final confidence
  - Goal: Avoid comparing incompatible scores as if they had the same meaning.
  - Files: `src/identifiers/identifier_manager.py`, `src/verifier/verification_workers/verification_core.py`, `src/verifier/summarizer.py`, `tests/verifier/`
  - Validation: Tests assert score type and normalized confidence are separate fields.
  - Definition of done: Final confidence is derived from documented inputs, not raw resolver score alone.

- [ ] Add candidate rejection reasons and conflicts
  - Goal: Explain why candidates were rejected, downgraded, or preserved as ambiguous.
  - Files: `src/verifier/verification_workers/verification_core.py`, proposed `ValidationResult` model, `tests/verifier/`
  - Validation: Tests for no candidate, below-threshold candidate, conflicting identifiers, and multiple equivalent hits.
  - Definition of done: Rejection reasons and conflicts appear in validation output.

- [ ] Fix compound verification kind wiring
  - Goal: Ensure lipids/carbohydrates/compounds use compound verification and SMILES where appropriate.
  - Files: `src/verifier/summarizer.py`, `src/verifier/verification_workers/compound_worker.py`, `tests/verifier/`
  - Validation: Test that compound segments call `VerificationKind.COMPOUND` behavior.
  - Definition of done: Compound validation no longer routes through protein signature selection.

- [ ] Convert water and atom shortcuts into explicit validation rules
  - Goal: Keep special-case certainty explainable through evidence and provenance.
  - Files: `src/verifier/verification_workers/verification_core.py`, `tests/verifier/`
  - Validation: Tests assert water and atom outputs include evidence, source, and confidence rationale.
  - Definition of done: Special cases no longer bypass candidate evidence reporting.

## Phase 9 — Annotation output

- [ ] Add schema validation for final annotations
  - Goal: Make CLI/API/web output stable and machine-readable.
  - Files: `src/loader/results_file.py`, `src/verifier/summarizer.py`, proposed schema module, `tests/output/`
  - Validation: Schema validation tests for required fields and type errors.
  - Definition of done: Invalid annotation output fails tests before reaching users.

- [ ] Add deterministic golden-output tests
  - Goal: Catch accidental annotation schema or ordering regressions.
  - Files: `tests/output/`, proposed fixture data, `src/verifier/summarizer.py`
  - Validation: Golden JSON comparison with stable ordering.
  - Definition of done: A small known input produces repeatable output under offline conditions.

- [ ] Fix `ResultsFile.get_item` default sentinel behavior
  - Goal: Allow callers to request `None` as an intentional default.
  - Files: `src/loader/results_file.py`, `tests/loader/test_resultsfile.py`
  - Validation: Unit tests for absent paths with no default, `None` default, and non-None default.
  - Definition of done: Output/schema code can distinguish missing values from explicit null defaults.

- [ ] Include repairs, warnings, candidates, and software metadata in final output
  - Goal: Make final annotations provenance-rich enough for repository integration.
  - Files: `src/verifier/summarizer.py`, `src/loader/results_file.py`, proposed schema/model module, `tests/output/`
  - Validation: Output schema tests assert required provenance and warning fields.
  - Definition of done: Final annotations expose the evidence and uncertainty behind each selected identifier.

## Phase 10 — CLI/API/web polish

- [ ] Design the stable BioID CLI command shape
  - Goal: Move from internal task flags toward user-facing commands such as identify, validate, export, inspect, and stats.
  - Files: `main.py`, `docs/INTERFACES.md`, CLI tests
  - Validation: CLI help snapshot tests or argument parser unit tests.
  - Definition of done: Current behavior and proposed stable commands are both documented, with a migration path.

- [ ] Add explicit database-search mode to CLI
  - Goal: Let users choose offline, local, network, or all database search behavior without editing `config.ini`.
  - Files: `main.py`, `src/utils/sync_databases.py`, `src/identifiers/`, CLI tests
  - Validation: Tests mock sync/resolver behavior for each mode.
  - Definition of done: Default CLI behavior does not surprise users with unrequested network access.

- [ ] Add structured progress, error, and warning events
  - Goal: Replace log scraping as the API/web progress contract.
  - Files: `src/executor/task.py`, `src/executor/task_creator.py`, `src/utils/logger_utils.py`, `api_endpoint.py`, tests
  - Validation: Tests for successful, warning, and failed task progress records.
  - Definition of done: API/web code can consume structured events while text logs remain diagnostics.

- [ ] Review executor singleton lifecycle
  - Goal: Prevent cross-job state leaks in tests, CLI runs, and API jobs.
  - Files: `src/executor/core.py`, `src/utils/singleton.py`, `tests/executor/`
  - Validation: Tests for repeated executor creation and concurrent or sequential jobs.
  - Definition of done: Executor lifecycle is explicit and safe for API/web use.

- [ ] Replace or isolate signal-based timeouts
  - Goal: Make task timeouts safe for threaded/web contexts.
  - Files: `src/executor/task.py`, `src/executor/core.py`, `tests/executor/`
  - Validation: Tests for timeout behavior without relying on process-global signal side effects where possible.
  - Definition of done: Timeout behavior is documented and reliable for intended execution modes. This task needs confirmation for platform support.

- [ ] Define the Python API/service boundary
  - Goal: Turn `api_endpoint.run_analyze` into or wrap it with typed job submission and result retrieval behavior.
  - Files: `api_endpoint.py`, `src/executor/`, proposed service/API module, tests
  - Validation: Tests for job creation, failed input validation, completed result path, and structured error output.
  - Definition of done: API/web integrations can run BioID without depending on CLI internals.

## Phase 11 — Evaluation and examples

- [ ] Create tiny offline fixture systems
  - Goal: Provide small reproducible systems for unit and integration tests.
  - Files: `tests/data/`, proposed fixture-generation scripts, `docs/VALIDATION_PLAN.md`
  - Validation: Fixture tests for tiny protein, protein plus ligand, ions plus solvent, unknown residue, and duplicated species.
  - Definition of done: Fixtures are small, documented, and do not require network.

- [ ] Add degraded-input examples
  - Goal: Validate BioID behavior on missing elements, unknown residues, missing bonds, and unsupported file combinations.
  - Files: `tests/data/`, `tests/loader/`, `tests/error_handling/`
  - Validation: Tests assert recoverable problems produce warnings and fatal problems produce actionable errors.
  - Definition of done: Messy input behavior is tested rather than implied by docs.

- [ ] Add optional integration tests for GROMACS fixtures
  - Goal: Validate current GROMACS-oriented loader paths on known small systems.
  - Files: `tests/data/1010142/`, `tests/data/16319/`, `tests/data/35193_a/`, `tests/loader/`
  - Validation: Mark slow/integration tests and run them explicitly.
  - Definition of done: GROMACS fixture support is covered without making default tests too slow.

- [ ] Add performance smoke tests for duplicate-heavy systems
  - Goal: Catch memory/runtime regressions for large or repeated MD systems.
  - Files: `src/loader/universe_loader.py`, `src/loader/simulation.py`, tests under `tests/`
  - Validation: Mark performance tests separately from default unit tests.
  - Definition of done: Duplicate-heavy systems have runtime/memory expectations and do not emit uncontrolled duplicate annotations.

- [ ] Build publication-quality golden examples
  - Goal: Provide examples suitable for CLI/API/web documentation and evaluation.
  - Files: `docs/`, proposed examples directory, `tests/output/`
  - Validation: Golden outputs are schema-valid and reproducible offline.
  - Definition of done: At least one end-to-end example shows input files, annotations, warnings, candidates, and provenance.

## Phase 12 — Documentation

- [ ] Add implementation status labels to specification docs
  - Goal: Prevent readers from confusing proposed architecture with current behavior.
  - Files: `docs/SPECIFICATION.md`, `docs/ARCHITECTURE.md`, `docs/DATA_MODEL.md`, `docs/INTERFACES.md`
  - Validation: Documentation review against current code paths.
  - Definition of done: Each major concept is marked current, partial, proposed, or needs confirmation.

- [ ] Keep `docs/TESTING.md` synchronized with real commands
  - Goal: Make testing instructions reliable as packaging and markers evolve.
  - Files: `docs/TESTING.md`, proposed pytest config, `requirements.txt`, proposed `pyproject.toml`
  - Validation: Run documented commands or update the doc with exact blockers.
  - Definition of done: A contributor can follow testing docs without guessing commands.

- [ ] Update database adapter documentation after adapter refactor
  - Goal: Align `docs/DATABASE_ADAPTERS.md` with real adapter names, result states, and testing policy.
  - Files: `docs/DATABASE_ADAPTERS.md`, `src/identifiers/`, `tests/identifiers/`
  - Validation: Compare docs against resolver modules and tests.
  - Definition of done: Docs list actual adapters, mocked tests, optional live tests, and failure semantics.

- [ ] Add developer notes for scientific uncertainty handling
  - Goal: Give future agents clear rules for repair, inference, scoring, and annotation confidence.
  - Files: `AGENTS.md`, `docs/SPECIFICATION.md`, `docs/DATA_MODEL.md`, `docs/VALIDATION_PLAN.md`
  - Validation: Documentation review against repair/scoring tests.
  - Definition of done: Contributors know when to emit warnings, reduce confidence, or withhold annotations.

- [ ] Maintain this task list as work lands
  - Goal: Keep `TASKS.md` useful as a Codex-friendly backlog.
  - Files: `TASKS.md`, `docs/ROADMAP.md`, `docs/CODE_HEALTH_REPORT.md`
  - Validation: Review task statuses after each implemented change.
  - Definition of done: Completed tasks are only checked after code, tests, and docs are verified.
