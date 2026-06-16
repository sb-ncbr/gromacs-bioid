# BioID v2 Testing Strategy

This document explains how contributors and Codex agents should test BioID v2. It reflects the current repository state and marks missing test infrastructure as TODOs.

## Current Test Infrastructure

Inspected root files:

- No `pyproject.toml` found.
- No `setup.cfg` found.
- No `tox.ini` found.
- No `noxfile.py` found.
- No `Makefile` found.
- No `.github/` CI configuration found.
- No `pytest.ini` found.
- `requirements.txt` exists, but does not currently list `pytest`.

Current tests are pytest-style files under `tests/`:

- `tests/loader/test_universe_loader.py`
- `tests/loader/test_simulation.py`
- `tests/loader/test_resultsfile.py`
- `tests/executor/test_tasks.py`
- `tests/executor/test_executor.py`

Current local fixture data is under `tests/data/` and includes GROMACS-style `.top`, `.itp`, `.gro`, and `.tpr` examples.

## 1. Running the Current Test Suite

No repository-defined test command was found.

The test files are written in pytest style, so the expected command after installing pytest is:

```bash
python -m pytest tests
```

Current local environment note:

```bash
python -m pytest --version
```

returned:

```text
No module named pytest
```

TODO:

- Add `pytest` to development dependencies.
- Add a project-defined test command in `pyproject.toml`, `Makefile`, or CI.
- Add pytest markers for unit, integration, slow, and network tests.

## 2. Fast Smoke Test

Until a dedicated smoke marker exists, use the smallest deterministic tests that do not load large MD fixtures:

```bash
python -m pytest tests/loader/test_resultsfile.py tests/executor/test_tasks.py
```

Purpose:

- Verify `ResultsFile` JSON path behavior.
- Verify basic task/task-list execution.
- Avoid database, network, and large loader behavior.

TODO:

- Add a `smoke` marker or a dedicated `tests/smoke/` directory.
- Keep smoke tests network-free and under a few seconds.

## 3. Slower Integration Tests

Current loader/simulation tests load real fixture systems and are slower than pure unit tests:

```bash
python -m pytest tests/loader/test_universe_loader.py tests/loader/test_simulation.py
```

These tests currently cover:

- loader strategy selection
- invalid load case
- atom/residue/segment/fragment counts
- segment support flags

TODO:

- Add an `integration` marker once pytest configuration exists.
- Add integration tests for PDB-only, mmCIF-only, AMBER, topology plus trajectory, and intentionally degraded inputs.
- Keep live database calls out of integration tests unless explicitly marked as network tests.

## 4. Network-Access Tests

Default tests must not require network access.

Network tests should be marked and skipped by default. Proposed marker:

```python
import pytest

@pytest.mark.network
def test_pubchem_live_lookup():
    ...
```

Recommended skip policy:

```python
import os
import pytest

requires_network = pytest.mark.skipif(
    os.environ.get("BIOID_RUN_NETWORK_TESTS") != "1",
    reason="network tests require BIOID_RUN_NETWORK_TESTS=1",
)
```

Then:

```python
@requires_network
@pytest.mark.network
def test_live_database_query():
    ...
```

TODO:

- Add pytest marker registration when a pytest config file exists.
- Document the exact command for live tests after markers are configured.
- Ensure live tests use small stable queries and tolerant assertions.

## 5. Testing Database Adapters With Mocks

Database adapter tests should not call live services by default.

Adapters to cover:

- `BLAST_PDB_PROT`
- `BLAST_PDB_NT`
- `BLAST_UNIPROT`
- `PDB_STRUCT_PROTEIN`
- `PDB_STRUCT_NUCLEOTIDE`
- `ALPHAFIND_STRUCT`
- `PUBCHEM_STRUCT`
- `CHEMBL_STRUCT`
- `IDSM_PUBCHEM`
- `IDSM_CHEMBL`
- `IDSM_CHEBI`
- `ATOM`
- `NAME_CCD`
- `NAME_MAPS`
- `NAME_MANUAL`

Mock testing rules:

- Mock `requests.get`, `requests.post`, `pubchempy.get_compounds`, ChEMBL client calls, SPARQL calls, and subprocess BLAST/curl calls.
- Use fixed response fixtures for exact hit, similarity hit, no hit, malformed response, timeout, and conflicting hits.
- Test parser functions directly where possible.
- Use temporary SQLite files for `ResolverCache`.
- Assert that failure is distinct from no-hit.

TODO:

- Add fixtures under a path such as `tests/fixtures/database/`.
- Add resolver-specific parser tests.
- Add candidate schema validation once normalized `DatabaseCandidate` output exists.

## 6. Testing File-Format Loading

Current file-format coverage:

- `ITP_GRO` fixture: `tests/data/16319`
- `TOP_GRO` or `ITP_GRO` fixture: `tests/data/1010142`
- `TPR_GRO` fixture: `tests/data/35193_a`
- `TPR` fixture: `tests/data/14976_a`
- invalid/multiple TPR fixture: `tests/data/14976`

Required assertions:

- selected `LoadStrategy`
- used files
- atom count
- residue count
- segment count
- fragment count
- segment names
- segment flags
- bond counts where relevant
- coordinate availability
- no silent chain/segment merge

TODO:

- Add PDB-only fixture tests.
- Add mmCIF-only fixture tests if supported.
- Add AMBER fixture tests if supported.
- Add trajectory plus topology fixture tests.
- Add degraded fixture tests for missing elements, missing bonds, unknown residues, and unsupported files.

## 7. Creating Small Fixture Systems

Fixture systems should be tiny, deterministic, and scientifically clear.

Guidelines:

- Prefer minimal systems with known atom, residue, chain, segment, and bond counts.
- Include a short README or comment file describing expected content.
- Keep fixtures small enough for routine test runs.
- Avoid generated binary churn unless the binary file is essential.
- Do not require external databases to validate fixture behavior.
- Include degraded variants only when the expected warnings are explicit.

Recommended fixture classes:

- tiny protein
- protein plus ligand
- membrane or lipid-only system
- ions plus solvent
- nucleic acid
- ambiguous or unknown residue
- duplicated molecular species
- intentionally degraded input

For each fixture, record:

- input file roles
- expected load strategy
- expected counts
- expected entity classes
- expected representations
- expected warnings

## 8. Comparing Output Annotations

Current output is flexible `ResultsFile` JSON. Future output should use a versioned annotation schema.

Comparison rules:

- Compare stable fields exactly.
- Normalize or ignore runtime-specific fields such as timestamps, absolute paths, log paths, and temporary filenames.
- Use numeric tolerances for similarity scores and confidence values when database or algorithm behavior can vary.
- Compare candidates by stable keys, not by list order, unless sorting is part of the contract.
- Assert warnings and provenance for degraded inputs.
- Keep golden output files small and reviewable.

TODO:

- Add a versioned JSON schema.
- Add a tolerant JSON comparison helper.
- Add golden output fixtures for representative systems.
- Define which fields are stable, tolerated, or ignored.

## 9. Avoiding Fragile Tests

Avoid tests that depend on:

- live network responses
- live database ranking order
- wall-clock timing
- absolute local paths
- thread scheduling order
- unordered dict/set iteration
- random temporary names
- full logs as exact strings
- large binary fixture changes

Prefer tests that:

- use local fixtures
- mock external services
- assert scientific invariants
- assert normalized data structures
- use stable IDs or sorted outputs
- check clear failure modes
- isolate filesystem writes in temporary directories

## 10. Coverage That Matters Most

### Loading

Must cover:

- load strategy selection
- supported and unsupported file combinations
- atom/residue/segment/fragment counts
- coordinate and bond availability
- source file provenance

Current coverage exists for several GROMACS-style fixtures.

### Repair and Inference

Must cover:

- element inference from masses
- element inference from names/types
- failed inference
- atom-name repair
- inferred-field provenance
- confidence reduction for repaired data

TODO: add direct tests for `src/loader/repair_fragment.py` and `Simulation.fix_missing_elements`.

### Object Extraction

Must cover:

- proteins
- nucleic acids
- lipids/membranes
- ligands/small molecules
- ions
- solvent
- unknown/ambiguous entities
- duplicated molecular species

TODO: add explicit entity extraction tests once an entity layer exists. Until then, test segment/fragments and summary classification.

### Representation Generation

Must cover:

- FASTA sequence correctness
- PDB/mmCIF export correctness
- SMILES validity and failure behavior
- fingerprint determinism
- name and atom fallback signatures
- representation applicability decisions

TODO: add tests for each `SignatureType`.

### Candidate Validation

Must cover:

- exact hits
- similarity hits
- no hits
- conflicting hits
- duplicate candidates
- validator confidence
- database failure behavior

TODO: add mocked resolver and verifier tests.

### Annotation Output

Must cover:

- final annotation schema
- entity IDs
- candidate lists
- confidence fields
- evidence/provenance fields
- warnings
- stable JSON serialization

TODO: add schema validation and golden output tests.

## Contributor Checklist

Before submitting a change:

- Run the fastest relevant tests for the edited code.
- Run loader/integration tests if loading, simulation, or fixture behavior changed.
- Add or update tests for every behavior change.
- Mock network/database behavior by default.
- Do not add fragile live-service assertions to unit tests.
- Document any tests that could not be run and why.
- Keep fixtures small and scientifically interpretable.

---

## 11. BLAST End-to-End Test

The BLAST integration can be tested end-to-end using the dedicated test file:

```bash
PYTHONPATH=/home/tomsko/tmp/BAT3_new pytest tests/src_new/test_blast_to_api_e2e.py -v
```

This test verifies:
- BLAST databases are accessible
- Sequence extraction works correctly
- BLAST search executes and returns hits
- Identifiers are properly exposed via the API

### Key BLAST Integration Test Files

| Test File | Purpose |
|-----------|---------|
| `tests/src_new/identification/test_blast_integration.py` | Core BLAST resolver integration tests |
| `tests/src_new/verification/test_dedup.py` | Hit deduplication verification |
| `tests/src_new/verification/test_fetchers.py` | Database fetcher tests |
| `tests/src_new/verification/test_workers.py` | Worker pool tests for verification |
| `tests/src_new/test_blast_to_api_e2e.py` | Full end-to-end BLAST pipeline test |

### Running BLAST Tests

```bash
# All identification tests including BLAST
PYTHONPATH=/home/tomsko/tmp/BAT3_new pytest tests/src_new/identification/ -v

# Specific BLAST integration tests
PYTHONPATH=/home/tomsko/tmp/BAT3_new pytest tests/src_new/identification/test_blast_integration.py -v

# End-to-end test
PYTHONPATH=/home/tomsko/tmp/BAT3_new pytest tests/src_new/test_blast_to_api_e2e.py -v
```

### Prerequisites for BLAST Tests

BLAST tests require:
1. BLAST+ executables installed (`blastp`, `blastn`)
2. BLAST databases downloaded and accessible at configured paths
3. Sufficient disk space for database files

For local development without full databases, mock-based unit tests in `test_resolvers.py` can be used instead.
