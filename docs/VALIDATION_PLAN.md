# BioID v2 Validation and Evaluation Plan

This document defines a rigorous validation strategy for the current BioID v2 code and future BioID annotations. It separates local deterministic tests from database/network integration, and it treats scientific correctness as a first-class validation target.

## Current Test Baseline

Existing tests are under `tests/`:

- `tests/loader/test_universe_loader.py`: validates current loader strategy selection for local fixtures, including `ITP_GRO`, `TOP_GRO` or `ITP_GRO`, `TPR_GRO`, `TPR`, and a negative multi-TPR case.
- `tests/loader/test_simulation.py`: validates atom/residue/segment/fragment counts and `SegmentSupports` flags for current fixtures.
- `tests/loader/test_resultsfile.py`: validates `ResultsFile` creation, nested get/set, defaults, existence checks, and type checks.
- `tests/executor/test_tasks.py`: validates task execution, task-list chaining, and task-list failure behavior.
- `tests/executor/test_executor.py`: validates executor enqueueing and asynchronous task execution behavior.
- `tests/data/`: contains current local GROMACS-style fixtures: `.top`, `.itp`, `.gro`, and `.tpr` examples.

Current gaps:

- No formal tests for a versioned annotation schema.
- No dedicated tests for signature generators, identifier resolver parsing, verifier behavior, metadata fetchers, warnings/provenance, or final annotation stability.
- No PDB-only, mmCIF-only, AMBER, or deliberately degraded golden fixture set is visible in the current test data.
- Network and external-executable behavior is not isolated behind a documented test strategy.

## Validation Principles

- Local unit tests must be deterministic and must not require network access.
- Database and network tests must be mocked by default, with real-network tests marked optional.
- Scientific invariants must be tested independently from implementation details.
- Golden output tests must separate stable fields from intentionally variable fields such as runtime, timestamps, and external similarity scores.
- Any repair or inference must leave evidence in warnings/provenance and must not silently increase certainty.
- Tests should cover negative and ambiguous cases, not only successful identification.

## 1. Unit-Level Validation

### File Loading

Existing coverage:

- `tests/loader/test_universe_loader.py` validates several current `LoadStrategy` outcomes and one invalid case.

Required checks:

- Each load strategy selects the expected files.
- Loader records `simulation/load_strategy`.
- Loader records used files.
- Unsupported or ambiguous file sets fail explicitly.
- File discovery ignores irrelevant files without masking missing required files.

TODO:

- Add tests for PDB-only loading.
- Add tests for mmCIF-only loading if supported.
- Add tests for AMBER topology/coordinate loading if supported.
- Add tests for trajectory plus topology combinations.
- Add tests for multiple plausible load strategies and define expected precedence.

### Atomic Map Creation

Existing coverage:

- `tests/loader/test_simulation.py` validates atom, residue, segment, and fragment counts for fixtures.
- It also validates segment feature flags such as `ELEMENTS`, `MASSES`, `POSITIONS`, and `NAMES`.

Required checks:

- Atom counts are preserved after loading.
- Residue counts are preserved after loading.
- Segment/chain IDs are preserved and not silently merged.
- Bonds are present when topology provides them.
- Coordinates are present when coordinate files provide them.
- Missing features are reported through flags or structured warnings.

TODO:

- Add explicit tests for bond counts by segment and full system.
- Add tests that compare MDAnalysis universe counts to expected atomic map counts once `AtomicMap` exists.
- Add tests for coordinate frame availability and frame indexing.
- Add tests for chain/segment identity preservation in PDB/mmCIF fixtures.

### Element Inference

Existing coverage:

- Current simulation tests observe whether `SegmentSupports.ELEMENTS` is true or false, but do not directly validate inferred element values.

Required checks:

- Missing elements can be inferred from masses when unambiguous.
- Missing elements can be inferred from atom names/types only when chemically defensible.
- Failed inference is explicit and does not produce false element labels.
- Inferred fields are recorded in a `RepairRecord` or equivalent warning/provenance output.

TODO:

- Add unit tests for `src/loader/repair_fragment.py`.
- Add fixtures with known missing elements and expected inferred values.
- Add negative fixtures where masses/names are ambiguous.
- Add tests that ensure inference does not mutate original input files.

### Residue Classification

Existing coverage:

- `SegmentSupports.AMINO_ACID_RESIDUE_NAMES` and `SegmentSupports.NUCLEIC_ACID_RESIDUE_NAMES` are implemented, but no dedicated tests for residue-code edge cases were found.

Required checks:

- Standard amino acid residues classify as protein evidence.
- Standard nucleic acid residues classify as nucleic-acid evidence.
- Unknown or non-standard residues do not silently become standard residues.
- Mixed residue sets produce ambiguous or reduced-confidence classifications.

TODO:

- Add direct tests for known amino acid, nucleic acid, ligand, ion, water, and unknown residue names.
- Add tests for non-standard residues and modified residues.
- Add tests for mixed protein/ligand or protein/water segments.

### Entity Extraction

Existing coverage:

- Current code is segment-centered through `Simulation.get_segments()` and `Simulation.get_fragment(segment_name)`.
- No standalone entity extraction tests exist.

Required checks:

- Entity extraction preserves atom selections and source segment/chain IDs.
- Repeated molecules are counted and deduplicated correctly.
- Mixed segments are not forced into one incorrect entity.
- Water, ions, proteins, nucleic acids, lipids, ligands, and unknowns can be represented.

TODO:

- Add an explicit entity extraction layer or adapter tests for current segment/fragments.
- Add tests for duplicated molecular species.
- Add tests for mixed or ambiguous segments.
- Add tests for simulation products/transformed molecules when their intended detection rules are defined.

### Representation Generation

Existing coverage:

- No dedicated signature generator tests were found.

Required checks:

- FASTA sequence matches residue order and residue mapping.
- SMILES is generated only when connectivity and chemistry are valid.
- PDB/mmCIF exports preserve atom/residue/chain data needed for downstream use.
- Fingerprints are deterministic for the same molecule and settings.
- Failed generation records applicability/failure information.

TODO:

- Add tests for each `SignatureType` in `src/signatures/signature_manager.py`.
- Add tests for sanitized and non-sanitized SMILES paths.
- Add tests for PDB and mmCIF representation generation.
- Add tests for name-based and atom-based fallback signatures.
- Add tests for representation limitations and warnings once structured output exists.

### Database Adapter Parsing

Existing coverage:

- No dedicated resolver parsing tests were found.
- `BlastHit` parsing logic exists in `src/identifiers/identifier_resolvers/blast.py`.

Required checks:

- BLAST JSON parsing handles expected hits, empty hits, malformed results, multiple accessions, and threshold filtering.
- PubChem, ChEMBL, IDSM, PDB, AlphaFind, atom, and name resolvers parse responses deterministically.
- Resolver failures are distinct from no-hit results.
- Resolver output includes enough provenance to reproduce candidate creation.

TODO:

- Add mocked response fixtures for each resolver.
- Add tests for `_process_blast_results`, identity filtering, and similarity filtering.
- Add tests for resolver cache hit/miss behavior.
- Add tests for timeout, rate-limit, malformed JSON, and unavailable-service cases.

### Candidate Filtering

Existing coverage:

- BLAST filtering thresholds are implemented, but dedicated tests were not found.
- Identifier hits are sorted and stored by `IdentifierResolutionManager`.

Required checks:

- Exact-match candidates meet exact thresholds.
- Similarity candidates meet similarity thresholds.
- Scores are sorted consistently.
- Duplicate candidates from multiple resolvers are preserved or merged according to a documented rule.
- Candidate provenance includes representation, resolver, database, method, and score type.

TODO:

- Add candidate-level tests for exact, weak, duplicate, conflicting, and no-hit cases.
- Add tests for score normalization across resolver types.
- Add tests for redundant candidate resolution.

### Final Annotation Schema Validation

Existing coverage:

- `ResultsFile` read/write behavior is tested.
- No versioned final schema exists yet.

Required checks:

- Final output validates against a documented schema.
- Required fields are present.
- Optional fields use `null` instead of misleading empty strings.
- Entity IDs and candidate IDs are stable enough for downstream references.
- Warnings/provenance cross-references are valid.

TODO:

- Add schema validation tests after a versioned annotation schema is implemented.
- Add an adapter test that converts current `ResultsFile` output into the proposed `FinalAnnotation` data model.
- Add tests for missing identifiers, ambiguous entities, and repaired inputs.

## 2. Integration Validation

Integration tests should run the pipeline across small, representative systems. They may be slower than unit tests, but should still avoid live network dependency unless explicitly marked.

### Small PDB-Only Example

Purpose:

- Validate PDB loading, atom/residue/chain preservation, protein/nucleic/ligand classification, and PDB-derived representations.

TODO:

- Add a tiny PDB fixture with known atom/residue counts.
- Add expected segment/entity classification.
- Add expected FASTA or fallback representation where applicable.

### Small mmCIF-Only Example

Purpose:

- Validate mmCIF structural input handling and chain/residue preservation.

TODO:

- Confirm whether mmCIF input loading is supported.
- Add a tiny mmCIF fixture.
- Add expected output or mark unsupported with an explicit error contract.

### Topology + Trajectory Example

Purpose:

- Validate topology/trajectory relationships, frame availability, sampling policy, and memory behavior.

TODO:

- Add a small topology plus trajectory fixture.
- Define whether the pipeline uses first frame, sampled frames, or all frames.
- Add tests that expensive frame iteration is explicit and bounded.

### GROMACS Example

Existing coverage:

- Current fixtures under `tests/data/` cover GROMACS-style `.top`, `.itp`, `.gro`, and `.tpr` combinations.

Required checks:

- Preserve current loader strategy expectations.
- Extend beyond loading into signatures, identifiers with mocks, summary, and final annotation output.

TODO:

- Add end-to-end local GROMACS pipeline tests with mocked resolver responses.
- Add golden output comparison for stable fields.

### AMBER Example

Purpose:

- Validate AMBER topology/coordinate input behavior once support is defined.

TODO:

- Confirm current AMBER support.
- Add minimal AMBER fixture.
- Add tests for load strategy, atom/residue counts, and entity extraction.

### Intentionally Degraded Input Example

Purpose:

- Validate partial, incomplete, or degraded inputs without false certainty.

Required degraded cases:

- Missing elements.
- Unknown residues.
- Missing or broken bonds.
- Missing coordinates.
- Unsupported extra files.
- Ambiguous segment naming.

TODO:

- Add fixture variants derived from tiny systems.
- Add expected warnings and confidence reduction.
- Add tests that local deterministic stages still run when database stages are unavailable.

## 3. Golden Test Datasets

Golden datasets should be small enough for routine CI and scientifically clear enough for exact expectations.

Required golden datasets:

- Tiny protein: known sequence, atom count, residue count, chain IDs, expected FASTA.
- Protein + ligand: distinct protein and ligand entities, known ligand identity, no silent merge.
- Membrane system: lipid/membrane entity classification, duplicate lipid species handling.
- Ions + solvent: ions identified as atoms/elements, water/solvent classified separately.
- Nucleic acid: known nucleotide sequence, chain preservation, nucleotide FASTA.
- Ambiguous/unknown residue: explicit unknown or ambiguous result with warning.
- Duplicated molecular species: copy number and deduplication behavior.

For each golden dataset, store:

- Raw input files.
- Expected input file roles.
- Expected atom/residue/segment/entity counts.
- Expected generated representations.
- Mocked database responses.
- Expected candidates.
- Expected final annotations.
- Expected warnings/provenance.

TODO:

- Create a `tests/golden/` or equivalent fixture layout.
- Add expected JSON files for stable output comparison.
- Add fixture documentation explaining scientific content and expected identities.

## 4. Scientific Correctness Checks

These checks should run at unit and integration levels.

Required checks:

- Atom counts are preserved from load through atomic map and entity extraction.
- Residue counts are preserved unless an explicit filtering stage says otherwise.
- Chains/segments are not silently merged.
- Entity extraction respects biological molecules and does not classify by names alone when stronger evidence is available.
- Generated FASTA matches residue identity and order.
- Generated SMILES/InChI are emitted only when chemically valid connectivity is available.
- Candidate database hits include provenance linking them to representation, resolver, database, and score.
- Repairs and inferred fields are visible in output and lower confidence when appropriate.
- Unknown or ambiguous entities remain explicit.

TODO:

- Add invariant tests that compare counts before and after each stage.
- Add tests that fail if generated output drops atoms, residues, chains, or source provenance.
- Add tests for invalid chemistry blocking SMILES/InChI output.

## 5. Database Validation

### Mocked Database Responses

Default database tests must use mocked responses.

Required checks:

- Exact match.
- Similarity match.
- No match.
- Malformed response.
- Empty response.
- Timeout/rate-limit response.
- Multiple conflicting candidates.

TODO:

- Add resolver-level fixture responses for all database adapters.
- Add tests that parsed candidates include raw metadata and provenance once the schema supports it.

### Cached Responses

Current cache:

- `ResolverCache` stores identity and similarity results in SQLite.

Required checks:

- Cache miss stores resolver output.
- Cache hit returns stored output without calling network/subprocess code.
- Identity and similarity caches remain separate.
- Cache values preserve resolver name, signature, identifier, and similarity.

TODO:

- Add temporary-directory SQLite cache tests.
- Add cache corruption or missing-table handling tests if intended.

### Real-Network Optional Tests

Real-network tests are useful but must not be part of default unit runs.

Rules:

- Mark as optional/integration.
- Require explicit environment flag.
- Record service, query, date, expected tolerance, and failure policy.
- Never assert exact live ranking unless the service contract guarantees it.

TODO:

- Define marker or naming convention for real-network tests.
- Add skip-by-default behavior.

### Failure Handling

Required checks:

- Database unavailable is not treated as a confident no-hit.
- Partial resolver failures do not invalidate local deterministic annotations.
- Logs and output warnings distinguish network failure, parser failure, no hit, and disabled resolver.

TODO:

- Add resolver failure tests for exceptions, timeouts, bad status, and missing local executable.

### Redundant Candidate Resolution

Required checks:

- Same identifier found by multiple resolvers is either merged with combined evidence or preserved as separate evidence records.
- Conflicting identifiers remain visible.
- Final annotation explains why the top candidate was selected.

TODO:

- Define and test duplicate candidate merge policy.
- Add conflict-resolution fixtures.

## 6. Regression Validation

### Stable JSON Outputs

Required checks:

- Current `ResultsFile` output remains stable for unchanged behavior.
- Future versioned schema output has deterministic field names and types.
- Lists are sorted where order matters for reproducibility.

TODO:

- Add golden output snapshots for small fixture runs.
- Normalize timestamps, paths, runtime durations, and external scores before comparison.

### Versioned Schema

Required checks:

- Every final annotation document includes a schema version once implemented.
- Schema migrations are tested.
- Unknown schema versions fail explicitly in consumers.

TODO:

- Add JSON Schema or typed model validation.
- Add schema compatibility tests.

### Golden Output Comparison

Required checks:

- Compare exact stable fields.
- Compare tolerant numeric fields with configured tolerances.
- Compare candidate ordering only when deterministic.
- Compare warnings/provenance for expected degraded cases.

TODO:

- Add a tolerant JSON comparison helper.
- Add allowlists for nondeterministic fields.

## 7. Performance Validation

Performance tests should be separate from fast unit tests but run regularly before releases or major pipeline changes.

### Large Systems

Required checks:

- Loader memory usage stays within documented limits.
- Entity extraction and representation generation avoid unnecessary all-vs-all operations.
- Long trajectories are not loaded fully unless explicitly configured.

TODO:

- Add benchmark fixtures or generated synthetic systems.
- Add memory and runtime budgets.
- Track peak memory for loader strategies that currently use `in_memory=True`.

### Duplicate-Heavy Systems

Required checks:

- Repeated lipids, solvent molecules, ions, and duplicated proteins do not cause redundant expensive searches.
- Deduplication keys reduce repeated representation/database work when scientifically valid.

TODO:

- Add duplicate-heavy fixtures.
- Add tests for representation and candidate reuse.

### Trajectory Frame Sampling

Required checks:

- Frame sampling policy is explicit.
- Sampling preserves provenance of frame index/time.
- Representation generation does not accidentally iterate all frames.

TODO:

- Define frame sampling configuration.
- Add tests for first-frame, sampled-frame, and no-coordinate cases.

### Memory Usage

Required checks:

- Memory usage is bounded for large inputs.
- Temporary files are cleaned up.
- Large generated representations are stored by path rather than duplicated inline when appropriate.

TODO:

- Add memory regression tests or benchmarks.
- Add temporary-file cleanup tests.

### Runtime Logging

Required checks:

- Long-running stages log start, end, elapsed time, and useful counts.
- Error logs contain enough context to identify simulation, file, entity, resolver, and stage.
- Logs are not noisy inside atom/frame loops.

TODO:

- Add log-capture tests for common failures.
- Add performance log review criteria.

## 8. Manual Evaluation

Manual evaluation should complement automated tests with expert review.

### Benchmark Systems With Known Content

Use curated systems with trusted expected content:

- Protein-only system.
- Protein-ligand system.
- Membrane protein or membrane-only system.
- Nucleic acid system.
- Solvent/ion-rich system.
- Non-standard residue or modified molecule system.
- Degraded real-world simulation submission.

For each system, record:

- Expected entities.
- Expected identifiers.
- Acceptable alternative identifiers.
- Known ambiguous regions.
- Required warnings.
- Expected failure modes.

### Expert Review Fields

Manual review should inspect:

- Entity boundaries.
- Molecule type classification.
- FASTA/SMILES/InChI validity.
- Identifier correctness.
- Candidate ranking relevance.
- Confidence explanation.
- Repair/inference warnings.
- Source provenance.
- Missing annotations that should have been detected.

### False Positives

Track cases where BioID assigns an identifier or entity type that is not supported.

Required review fields:

- Input system.
- Wrong annotation.
- Evidence that misled the pipeline.
- Stage responsible.
- Whether confidence should have been lower.
- Proposed test to prevent recurrence.

### False Negatives

Track cases where BioID fails to identify known content.

Required review fields:

- Missing entity or identifier.
- Available evidence.
- Stage that failed.
- Whether missing data or unsupported format caused the failure.
- Proposed fixture or resolver improvement.

### Relevance of Ranked Results

Evaluate whether candidate ranking is useful, not just technically valid.

Review questions:

- Is the top candidate scientifically plausible?
- Are close alternatives preserved?
- Are redundant database records grouped or explained?
- Are weak similarity hits clearly marked?
- Does confidence reflect ambiguity?

## Release Readiness Checklist

Before a release or major validation milestone:

- Existing loader and executor tests pass.
- Unit tests cover modified loader, repair, representation, resolver, verifier, and schema code.
- Golden fixture outputs are updated intentionally and reviewed.
- Network tests are either skipped by default or pass in the integration environment.
- Large-system performance benchmarks are within agreed budgets.
- Documentation describes new supported inputs, limitations, and schema changes.
- Known scientific limitations are recorded as explicit TODOs or warnings, not hidden behavior.
