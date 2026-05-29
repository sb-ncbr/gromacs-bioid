# BioID v2 Architecture

This document describes the current BioID v2 repository architecture and a cleaner conceptual architecture for continued development. It is intentionally honest about where the current code and the desired architecture do not yet match.

## Current Repository Map

### CLI and API Entry Points

- `main.py`: command-line entry point. It parses run/stat options, initializes logging, syncs databases when configured, creates tasks, and runs the executor.
- `api_endpoint.py`: API-facing helper exposing `run_analyze(directory, task_uuid)`, which creates and runs the full analysis task chain for one directory and returns the `results.json` path when successful.

### Packages and Modules

- `src/__init__.py`: loads `config.ini` into the global `core_config`.
- `src/constants.py`: shared constants for residue codes and MDAnalysis/RDKit-related behavior.
- `src/loader/`: simulation loading and local input repair.
  - `universe_loader.py`: selects a `LoadStrategy` and builds an MDAnalysis `Universe`.
  - `simulation.py`: wraps a simulation directory, active MDAnalysis universe, segment flags, results file, and repair helpers.
  - `repair_fragment.py`: element/name inference and repair helpers.
  - `results_file.py`: JSON-backed result storage using slash-delimited paths.
- `src/executor/`: task orchestration.
  - `task_creator.py`: maps `TaskType` values into a chained pipeline.
  - `task.py`: task and task-list primitives.
  - `core.py`: executor runtime.
- `src/signatures/`: molecular representation generation.
  - `signature_manager.py`: iterates `SignatureType` generators over simulation segments.
  - `signature_generators/`: FASTA, SMILES, PDB, atom, name, and fingerprint generators.
- `src/identifiers/`: identifier resolution.
  - `identifier_manager.py`: applies resolver classes to generated signatures.
  - `identifier_resolvers/`: BLAST, PDB structure search, AlphaFind, PubChem, ChEMBL, IDSM, atom, and name resolvers.
  - `cache_manager.py`: SQLite cache for identity and similarity resolver results.
- `src/verifier/`: result validation, summary generation, and metadata support.
  - `summarizer.py`: exports mmCIF snapshots, classifies segment molecule type, runs verification, and writes summary fields.
  - `verification_workers/`: protein/nucleic and compound verification workers plus shared verifier logic.
  - `metadata_fetchers/`: fetchers for atom, PDB, InChIKey, and simulation snapshot metadata.
  - `metadata_downloader.py`: metadata orchestration placeholder; much of the current logic is commented out.
- `src/stats/`: stats aggregation.
- `src/utils/`: filesystem, logging, string, time, singleton, and database-sync helpers.

### Tests

- `tests/loader/`: tests for universe loading, `Simulation`, and `ResultsFile`.
- `tests/executor/`: tests for task and executor behavior.
- `tests/data/`: local MD fixture directories used by loader tests.

### Data and Configuration Files

- `config.ini`: runtime configuration for database sync, executor settings, task timeouts, enabled signatures/resolvers, BLAST paths, cache paths, similarity thresholds, PDB upload behavior, temporary directory behavior, and verification limits.
- `requirements.txt`: pinned Python dependencies.
- `src/quotes.txt`: message/text resource used by utility code.
- `AGENTS.md`: repository-level guidance for future agents and contributors.

### Documentation Files

- `docs/SPECIFICATION.md`: high-level project specification.
- `docs/ARCHITECTURE.md`: this architecture document.

## Current Runtime Pipeline

The current executor pipeline is task-based. `TaskType` values are chained in this order when `ALL` is requested:

1. `INPUT`
2. `CREATE`
3. `LOAD`
4. `GENERATE_SIGNATURES`
5. `RESOLVE_IDENTIFIERS`
6. `SUMMARIZE`
7. `METADATA`
8. `UNLOAD`

The current concrete flow is approximately:

```text
simulation directory
  -> file listing and archive unpacking
  -> Simulation + ResultsFile
  -> MDAnalysis Universe
  -> segment flags and fragment statistics
  -> generated signatures
  -> resolver hits
  -> summary classification and verification
  -> optional metadata placeholders/fetching
  -> results.json, logs, exported structures/images where applicable
```

This maps only partially to the desired scientific architecture because the current implementation uses MDAnalysis segments/fragments as the main entity boundary and does not yet expose a formal atomic map model or versioned annotation schema.

## Conceptual Architecture

The desired long-term architecture should separate scientific stages with clear inputs, outputs, side effects, and test boundaries.

### 1. Input Loaders

Input loaders read raw simulation files and produce a loaded system representation.

Responsibilities:

- Discover candidate files.
- Select a deterministic load strategy.
- Build an MDAnalysis `Universe` or equivalent loaded representation.
- Record source files and load strategy.
- Report unsupported or ambiguous file combinations.

Current location:

- `src/loader/universe_loader.py`
- `src/loader/simulation.py`

Desired boundary:

- Loaders may touch the filesystem.
- Loaders should not perform database lookup or final annotation decisions.
- Format-specific logic should be extensible without changing unrelated stages.

### 2. Atomic Map Model

The atomic map should be a normalized, internal, atom-level model derived from loaded inputs.

Responsibilities:

- Store atom IDs, names, elements, masses, coordinates, residues, segments/chains, bonds, fragments, frames, and source provenance.
- Decouple later pipeline stages from direct MDAnalysis access where possible.
- Preserve mappings back to source files and original atom indices.

Current location:

- Partially implicit in `MDAnalysis.Universe`.
- Partially recorded through `Simulation.load_simulation` into `results.json`.

Mismatch:

- There is no formal atomic map class or schema today.
- Later stages read directly from `Simulation` and `MDAnalysis.AtomGroup`.

### 3. Repair and Inference Layer

Repair and inference should operate on the loaded system or atomic map and produce a repaired atomic map plus warnings.

Responsibilities:

- Infer missing elements from masses, names, and chemically valid rules.
- Repair atom names when deterministic.
- Infer bond topology only where evidence supports it.
- Record confidence, provenance, and warnings for each repair.

Current location:

- `src/loader/repair_fragment.py`
- repair methods in `src/loader/simulation.py`

Desired boundary:

- This layer should be deterministic and network-free.
- It should emit structured warnings instead of only logs or implicit state changes.

### 4. Entity Extraction Layer

Entity extraction should convert the atomic map into biomolecular entities.

Responsibilities:

- Extract proteins, nucleic acids, lipids/membranes, ligands/small molecules, ions, solvent, unknown entities, and transformed simulation products.
- Preserve atom/residue/source provenance.
- Allow ambiguous and mixed entities without forcing a single class too early.

Current location:

- Mostly implicit through `Simulation.get_segments()` and `Simulation.get_fragment(segment_name)`.
- Type classification occurs in `ResultsSummarizer._classify_segment_type`.

Mismatch:

- Current extraction is segment-centered.
- Segments containing multiple molecule types or repeated molecules are not represented as first-class entities.

### 5. Representation Generators

Representation generators convert extracted entities into search and annotation signatures.

Responsibilities:

- Generate FASTA, SMILES, PDB/mmCIF, atom, name, fingerprint, and future InChI/InChIKey representations when applicable.
- Record applicability, generation failures, sanitization status, and representation provenance.

Current location:

- `src/signatures/signature_manager.py`
- `src/signatures/signature_generators/`

Desired boundary:

- Most generators should be pure and deterministic for a given entity and configuration.
- Generators may use local chemistry/structure libraries but should not contact external databases.

### 6. Database Adapters

Database adapters resolve representations to candidate identifiers.

Responsibilities:

- Run local or remote identity and similarity search.
- Return candidate identifiers with resolver-specific evidence.
- Handle timeouts, rate limits, unavailable services, empty results, and schema changes.
- Use cache where configured.

Current location:

- `src/identifiers/identifier_manager.py`
- `src/identifiers/identifier_resolvers/`
- `src/identifiers/cache_manager.py`

Desired boundary:

- This is the primary layer allowed to touch the network or external executables such as BLAST.
- It should be easy to mock in tests.
- Resolver scores should be normalized or clearly documented before downstream scoring.

### 7. Candidate Validation and Scoring Layer

Validation and scoring evaluate database candidates against generated evidence.

Responsibilities:

- Re-check candidates against local signatures.
- Rank exact, similar, and weak matches.
- Keep multiple candidates when evidence is conflicting.
- Preserve both original resolver score and observed validation score.

Current location:

- `src/verifier/verification_workers/`
- `src/verifier/summarizer.py`

Desired boundary:

- Validation should be deterministic when it uses local data only.
- Validation that performs reverse database lookup should use injectable adapters and be mocked in unit tests.

### 8. Annotation Schema and Output Layer

The output layer turns validated entities and evidence into stable machine-readable annotations.

Responsibilities:

- Produce versioned JSON or other standardized output.
- Include stable identifiers where possible.
- Include candidate hits, confidence/scoring, warnings, provenance, source files, load strategy, generated representations, attempted resolvers, and validation details.
- Export supplemental structural representations where applicable.

Current location:

- `src/loader/results_file.py`
- `src/verifier/summarizer.py`
- metadata fetchers under `src/verifier/metadata_fetchers/`

Mismatch:

- `ResultsFile` is a flexible JSON store, not a formal schema.
- Result paths are currently spread across pipeline stages.
- There is no explicit output schema version.

### 9. CLI/API/Web Interfaces

Interfaces should orchestrate the pipeline without owning scientific behavior.

Current location:

- CLI: `main.py`
- API helper: `api_endpoint.py`
- Web integration appears implied by task progress files and API behavior but no web package is present in this repository.

Desired boundary:

- Interfaces should validate user input, select configuration, start jobs, report progress, and return output locations.
- They should not contain molecule identification logic.

## Data Flow

Desired high-level data flow:

```text
raw files
  -> MDAnalysis universe
  -> atomic map
  -> repaired atomic map
  -> entities
  -> representations
  -> database candidates
  -> validated annotations
```

Current approximate implementation flow:

```text
raw files
  -> MDAnalysis Universe
  -> Simulation segment flags and fragments
  -> signatures per segment
  -> identifiers per segment/signature
  -> summary classification, verification, and metadata fields
```

The largest architectural gap is between `MDAnalysis Universe` and `entities`: the desired atomic map and entity extraction layers are currently implicit rather than explicit.

## Boundaries

### Pure and Deterministic Layers

These layers should be deterministic and should not touch the network:

- File discovery decisions after the file list is known.
- Atomic map construction from loaded data.
- Repair/inference based on local evidence.
- Entity extraction.
- Representation generation using local libraries.
- Local validation/scoring rules.
- Annotation schema assembly.

Some of these currently write to `ResultsFile` directly. Longer term, prefer returning structured objects and writing output at stage boundaries.

### Layers Allowed to Touch the Network

Network access should be limited to:

- Database adapters/resolvers.
- Metadata fetchers.
- Database synchronization utilities.
- External structure search services that explicitly require upload or remote lookup.

Current network-capable areas include identifier resolvers, metadata fetchers, and `src/utils/sync_databases.py`.

### Layers to Mock in Tests

Mock or isolate these in unit tests:

- Remote database adapters such as PubChem, ChEMBL, IDSM, PDB structure search, AlphaFind, and online metadata fetchers.
- BLAST subprocess calls and local database availability.
- PDB upload/delete commands.
- Snapshot generation if it depends on external tools or heavyweight rendering.
- Database sync.

Prefer local fixture tests for:

- Loader strategy selection.
- `ResultsFile` paths.
- Repair/inference logic.
- Entity classification.
- Representation generation.
- Scoring rules with fixed candidate inputs.

### Expensive Trajectory Operations

Expensive trajectory operations belong in explicit loader, atomic map, or analysis stages with clear limits.

Rules:

- Avoid full-trajectory loading unless the task requires it.
- Do not hide frame iteration inside representation generators or database adapters.
- Cache derived per-frame or per-entity data when scientifically valid.
- Keep expensive operations visible in task names, logs, timeouts, and configuration.

Current risk:

- Several loader strategies use `in_memory=True`, which may be inappropriate for large systems or long trajectories.

## Error and Warning Flow

BioID should treat warnings as structured scientific evidence, not just log text.

Desired warning fields should include:

- warning code
- severity
- affected file/entity/atom/residue/segment
- stage
- message
- whether output confidence was reduced
- provenance of the decision

Current state:

- Errors and warnings are mostly represented through logs, exceptions, task failures, and some result fields.
- `UNLOAD` collects `ERROR` and `CRITICAL` lines into `errors.log`.
- There is no formal warning schema today.

Expected handling by case:

### Missing Element

- Repair/inference should attempt element inference from masses, names, or topology.
- If inference succeeds, record inferred element provenance and a warning.
- If inference fails, keep the entity processable where possible but reduce applicability of structure/chemistry generators.

### Unknown Residue

- Entity extraction and representation generation should preserve the residue as unknown instead of dropping it.
- FASTA generation should report whether the sequence is partial, inferred, or failed.
- Candidate identity should not be treated as exact if unknown residues affect the evidence.

### Broken Bond Topology

- Loading or repair should report missing or inconsistent bonds.
- SMILES/fingerprint generation should be skipped or marked low-confidence if connectivity is not reliable.
- Structure-based or sequence-based paths may still proceed if applicable.

### Unsupported File Type

- Loaders should ignore irrelevant files when safe and report unsupported required file combinations.
- If no strategy applies, loading should fail with a clear error identifying the available file classes.

### Ambiguous Entity Type

- Entity extraction should allow `UNKNOWN` or ambiguous classifications.
- Representation generation should try applicable non-destructive signatures.
- Summary output should not force a specific molecule type without evidence.

### Database Unavailable

- Database adapters should return explicit unavailable/failure state rather than false no-hit results.
- Local deterministic stages should still be able to complete.
- Tests should mock this behavior.

### Multiple Conflicting Identifiers

- Validation should preserve conflicting candidates and their evidence.
- Summary may choose a top candidate only when scoring justifies it.
- Output should expose alternatives and observed confidence, not only the selected identifier.

## Extension Points

### New File Format

Add a new file format by extending the loader layer:

- Add or update load strategy logic in `src/loader/universe_loader.py`.
- Keep format detection deterministic.
- Record used files and strategy.
- Add local fixture tests under `tests/loader/`.
- Avoid changing downstream stages unless the new format exposes new atomic map fields.

Longer term, file format handlers should be separated into independent loader classes or modules.

### New Representation

Add a new representation by extending signature generation:

- Implement a `SignatureGenerator` subclass under `src/signatures/signature_generators/`.
- Add it to `SignatureType` in `src/signatures/signature_manager.py`.
- Add a configuration flag in `config.ini`.
- Define applicability rules and failure behavior.
- Add tests with local fixtures or constructed fragments.

### New Database

Add a new database by extending identifier resolution:

- Implement an `IdentifierResolver` subclass under `src/identifiers/identifier_resolvers/`.
- Register it in `IdentifierType`.
- Add config flags for identity and similarity modes.
- Use `ResolverCache` where appropriate.
- Mock network calls in tests.
- Document identifier type, score semantics, rate limits, and failure modes.

### New Validation Rule

Add validation through the verifier layer:

- Add or extend a `VerificationWorker`.
- Keep local scoring deterministic where possible.
- Mock reverse lookup or remote validation.
- Preserve both resolver score and observed validation score.
- Add tests for conflicting, weak, and exact candidates.

### New Output Schema

Add an output schema through the annotation/output layer:

- Define schema version and required fields.
- Map existing `ResultsFile` data into the schema.
- Preserve backward compatibility where possible.
- Add schema validation tests.
- Keep source provenance and warnings first-class.

## Architecture Debt / Risks

- No formal atomic map model exists; MDAnalysis objects are used directly across stages.
- Entity extraction is segment-centered and may not handle mixed segments, repeated molecules, transformed products, or membrane/ligand distinctions cleanly.
- `ResultsFile` is a flexible JSON writer, not a validated annotation schema.
- Result paths are written from many stages, making schema evolution risky.
- Network-capable resolvers, local caches, subprocess BLAST, and external upload behavior are close to core pipeline code and need stronger test seams.
- Some configuration contains deployment-specific paths, hosts, upload commands, and TODO comments.
- Loader strategies currently expect narrow file combinations in several cases and may not support multi-file trajectories robustly.
- `in_memory=True` in loader strategies can be a memory risk for large MD systems.
- Metadata downloading appears partially disabled or transitional.
- Confidence values from different resolvers are not clearly normalized into one documented scoring model.
- Warning/provenance handling is incomplete; important scientific uncertainty can be present only in logs or implicit behavior.
- There is no explicit public distinction between internal terms (`segment`, `fragment`) and user-facing annotation entities.

## Development Direction

Near-term work should focus on making implicit boundaries explicit without a broad rewrite:

- Define a minimal atomic map data contract.
- Define a minimal entity data contract separate from MDAnalysis segments.
- Add structured warnings to `ResultsFile`.
- Introduce a versioned annotation schema while preserving current output.
- Isolate network/database adapters behind mockable interfaces.
- Keep loader, repair, representation, resolver, verifier, and output tests local and deterministic by default.
