# BioID v2 Project Specification

This document defines the intended behavior of BioID v2, the current boundaries of the project, and the way major pipeline stages are expected to interact. It is a high-level specification, not a guarantee that every item is fully implemented today.

## Motivation

Molecular dynamics simulations are expensive to create, store, curate, and reproduce. Existing simulations are often difficult to find and reuse because repository metadata is incomplete, inconsistent, or too coarse to describe the actual biomolecular content of a simulation system.

BioID v2 exists to identify biomolecules and simulation products from heterogeneous MD inputs and produce richer standardized metadata annotations. The goal is to make simulations easier to search, compare, reuse, and integrate with repositories, APIs, web tools, and future semantic or AI-driven workflows.

BioID must address these problems:

- MD simulations are expensive to create, so existing simulations should be easier to discover and reuse.
- Metadata annotations are often incomplete or disconnected from the actual contents of submitted files.
- Biomolecular content is difficult to extract from heterogeneous topology, coordinate, structure, and trajectory files.
- Simulation files may be partial, incomplete, degraded, or missing useful atom-level annotations.
- Rich semantic search and repository interoperability require stable identifiers, provenance, confidence information, and explicit uncertainty.

## Supported Input Classes

BioID v2 is intended to support these input classes:

- GROMACS files, including topology and coordinate combinations represented in the current loader by strategies such as `ITP_GRO`, `TOP_GRO`, `TPR_GRO`, `TPR`, `TOP`, and `ITP`.
- AMBER files.
- PDB and mmCIF structural files.
- Trajectories and topologies, including trajectory-only or topology-only degraded cases where scientifically useful inference is still possible.
- Partial, incomplete, or degraded inputs that require repair, inference, or reduced-confidence output.

Current implementation notes:

- The current loader code is centered on MDAnalysis `Universe` creation and has explicit `LoadStrategy` values for GROMACS-style `.top`, `.itp`, `.tpr`, `.gro`, `.xtc`, and PDB loading paths.
- TODO: Confirm the current level of AMBER support in the loader and add explicit loader strategy names if implemented.
- TODO: Confirm whether mmCIF input loading is supported directly or only mmCIF export is currently implemented.
- TODO: Confirm intended support for multi-file trajectories and coordinate/topology combinations beyond the current one-file strategy checks.

## Core Concepts and Current Terminology

The code currently uses these terms:

- `Simulation`: the in-memory analysis handle for a simulation directory, its MDAnalysis `Universe`, result file, log file, and segment filters.
- Segment: a named MDAnalysis segment, used by current code as a molecule-type or fragment grouping unit.
- Fragment: the first MDAnalysis fragment selected from a segment with `get_fragment(segment_name)`.
- Segment flags: feature checks stored per segment, including `ELEMENTS`, `MASSES`, `POSITIONS`, `NAMES`, `AMINO_ACID_RESIDUE_NAMES`, `NUCLEIC_ACID_RESIDUE_NAMES`, `NAMES_UNIQUE`, and `MULTI_ATOM_RESIDUES`.
- Signature: a generated molecular representation stored under `signatures/<segment>/generated`.
- Identifier: a database or resolver hit stored under `identifiers/<segment>/...`.
- Summary: the final per-segment output stored under `summary/segments/<segment>/...`.
- Metadata: additional fetched information from identifier results.

TODO: Decide whether future specifications should use "entity" as the public term and reserve "segment" and "fragment" for MDAnalysis/internal implementation details.

## Pipeline Stages

### 1. Loading

The loading stage reads a simulation directory and attempts to construct an MDAnalysis `Universe`.

Expected behavior:

- Detect applicable topology, coordinate, structure, or trajectory files.
- Select a deterministic load strategy.
- Record the successful load strategy under `simulation/load_strategy`.
- Record which files were used for loading.
- Fail explicitly if no valid load strategy applies.

Current implementation notes:

- `src.loader.universe_loader.load` iterates over `LoadStrategy` values until one succeeds.
- `src.executor.task_creator.TaskType.LOAD` invokes `Simulation.load_simulation`.
- `used_files.txt` and `all_files.txt` are written into simulation directories by current task setup/loading behavior.

TODO: Define the required behavior when several plausible load strategies are available.

### 2. Atomic Map Construction

Atomic map construction converts loaded files into an atom-level system description.

Expected atomic map data includes:

- Atom identifiers and names.
- Residue names and residue identifiers.
- Segment or chain identifiers.
- Elements and masses where available or inferable.
- Bonds where available or inferable.
- Coordinates and frame information where available.
- Fragment membership and molecule counts.

Current implementation notes:

- `Simulation.load_simulation` records segment-level atom, bond, and molecule counts.
- Segment feature availability is represented by `SegmentSupports`.
- TODO: Define a formal atomic map schema separate from MDAnalysis objects and JSON result paths.

### 3. Repair and Inference

Repair and inference should improve incomplete inputs without hiding uncertainty.

Expected behavior:

- Infer missing elements from masses, names, or other scientifically justified evidence when possible.
- Repair atom names only when the correction is deterministic or explicitly reported.
- Infer bonds or molecular connectivity only when the chosen library and input evidence support it.
- Record warnings or provenance for repaired data.
- Prefer reduced-confidence output over false certainty.

Current implementation notes:

- `src.loader.repair_fragment` provides element and name repair helpers.
- `Simulation.fix_missing_elements` and related methods are part of the current repair surface.
- TODO: Define standardized warning/provenance fields for repaired atom names, inferred elements, inferred bonds, and failed repairs.

### 4. Object Extraction

Object extraction separates simulated molecular objects from the full simulation system.

Expected behavior:

- Extract proteins, nucleic acids, lipids, ligands, ions, solvent, and unknown entities where possible.
- Preserve the mapping from extracted object back to simulation atoms, residues, segments, and source files.
- Support ambiguous or mixed segments without forcing an incorrect class.
- Avoid losing transformed or simulation-generated molecular products.

Current implementation notes:

- Current extraction is segment-centered and uses `Simulation.get_segments()` and `Simulation.get_fragment(segment_name)`.
- `ResultsSummarizer._classify_segment_type` classifies segments into `PROTEIN`, `NUCLEIC`, `LIPID`, `CARBOHYDRATE`, `ATOM`, `WATER`, or `UNKNOWN`.
- TODO: Define behavior for segments containing multiple chemically distinct molecules.
- TODO: Define explicit handling for ligands/small molecules versus lipids/carbohydrates/other compounds.

### 5. Molecular Representation Generation

Representation generation creates signatures suitable for identity and similarity search.

Expected representations include, when scientifically applicable:

- PDB or mmCIF structure exports.
- FASTA sequences for proteins and nucleic acids.
- SMILES and InChI-like chemical identifiers for compounds where supported.
- Atom-level signatures for ions or single-atom entities.
- Names from chain, molecule, or segment labels.
- Fingerprints for similarity search.

Current implementation notes:

- `SignatureGeneratorManager` stores generated values under `signatures/<segment>/generated`.
- Current `SignatureType` values include FASTA, atom, SMILES, PDB, name, and fingerprint generators.
- `ResultsSummarizer` exports mmCIF files for the full simulation and per segment.
- TODO: Confirm whether InChI generation is implemented or only a future target.
- TODO: Define a public schema for signature quality, sanitization status, and applicability reasons.

### 6. Database Search

Database search resolves generated signatures to candidate identifiers.

Expected behavior:

- Use exact identity search where possible.
- Use similarity search where exact identity is not available or not appropriate.
- Keep local deterministic inference separate from external database search.
- Record which resolvers were attempted.
- Preserve all candidate hits needed for validation and downstream review.

Current implementation notes:

- `IdentifierResolutionManager` stores resolver attempts and hits under `identifiers/<segment>/<signature_generator>/...`.
- Current resolver classes include BLAST, PDB structure, AlphaFind structure, PubChem, ChEMBL, IDSM, atom, and name-based resolvers.
- Hits are stored with confidence-like scores, with exact hits currently represented as `100.0`.
- TODO: Define resolver-specific score semantics and normalize them into a documented confidence model.

### 7. Result Validation and Filtering

Validation and filtering should evaluate candidate hits against generated evidence and classify uncertainty.

Expected behavior:

- Compare candidate identifiers back against the original or generated molecular representation.
- Prefer verified candidates over unverified matches.
- Preserve ambiguous candidates when no single result can be proven.
- Report both original resolver score and observed validation confidence where available.

Current implementation notes:

- `Verifier.calculate_identifier_confidence` returns tuples containing identifier, identifier type, resolver confidence, and observed confidence.
- `VerificationKind` currently includes `PROTEIN`, `NUCLEIC`, `COMPOUND`, `WATER`, `ATOM`, and `NONE`.
- `ResultsSummarizer.summarize` writes final `ident`, `ident_type`, `confidence`, and `verification` fields for each segment.
- TODO: Confirm whether `COMPOUND` verification is fully wired for small molecules, lipids, and carbohydrates.

### 8. Standardized Annotation Output

Final output should be machine-readable and suitable for CLI, API, web, and repository integration.

Expected output:

- A JSON annotation result, currently represented by `ResultsFile`.
- Machine-readable annotations per simulation and per extracted entity.
- Stable identifiers where possible, such as PDB, UniProt, PubChem, ChEMBL, ChEBI, element identifiers, or other resolver outputs.
- Candidate hits with confidence or scoring information.
- Provenance for each decision, including source files, load strategy, generated signatures, attempted resolvers, validation results, and repair/inference warnings.
- Warnings for ambiguous, incomplete, inferred, or repaired data.
- Exported structural snapshots where applicable.

Current implementation notes:

- `ResultsFile` stores JSON data through slash-delimited paths.
- Current top-level result areas include `simulation`, `signatures`, `identifiers`, `summary`, and metadata-related output.
- TODO: Define a stable versioned annotation schema for external consumers.
- TODO: Define required versus optional output fields.

## Entity Classes

BioID v2 should represent these entity classes:

- Proteins.
- Nucleic acids.
- Lipids and membrane components.
- Ligands and small molecules.
- Ions and single atoms.
- Solvent, including water.
- Unknown or ambiguous entities.
- Simulation products, transformed molecules, or molecules altered by the simulation workflow.

Current implementation notes:

- Current summary classification uses `SegmentMoleculeType` with `PROTEIN`, `NUCLEIC`, `LIPID`, `CARBOHYDRATE`, `ATOM`, `WATER`, and `UNKNOWN`.
- TODO: Add or document explicit categories for ligands/small molecules, membranes, solvent beyond water, ambiguous entities, and simulation products.

## Output Expectations

BioID output should be:

- Machine-readable.
- Deterministic for the same input files, configuration, local databases, and resolver responses.
- Explicit about stable identifiers where they are available.
- Explicit about candidate hits and confidence/scoring information.
- Explicit about provenance for every decision.
- Explicit about warnings for ambiguous, incomplete, inferred, repaired, or degraded data.

The output must not claim certainty where the evidence only supports a candidate, similarity, or weak inference.

TODO: Define a schema-level distinction between identity, similarity, classification, repair, warning, and metadata fields.

## Non-Goals and Limitations

BioID v2 should not:

- Pretend uncertain annotations are certain.
- Require every input to be perfect before producing useful partial output.
- Conflate local deterministic inference with external database search.
- Treat database availability as a prerequisite for local parsing, repair, representation generation, or structural summary.
- Replace expert scientific review for ambiguous, degraded, or novel molecular systems.
- Guarantee complete molecule identity when required evidence is missing.

Known or unclear limitations:

- TODO: Define formal guarantees for AMBER input handling.
- TODO: Define formal guarantees for mmCIF input handling.
- TODO: Define support boundaries for large multi-frame trajectories.
- TODO: Define behavior for coarse-grained simulations and non-standard residues.
- TODO: Define how transformed simulation products should be detected and distinguished from input molecules.

## Success Criteria

BioID v2 is successful when it is:

- Robust on messy MD inputs.
- Reproducible across repeated runs with the same inputs and resolver state.
- Testable with local fixtures and mocked external services.
- Useful from CLI, API, and web workflows.
- Useful for future repository integration and semantic search.
- Honest about uncertainty, ambiguity, missing information, and repaired data.
- Able to preserve provenance from raw files through final standardized annotation.

## Implementation Alignment

The current repository layout relevant to this specification is:

- `main.py`: CLI-style entry point for run and stats modes.
- `api_endpoint.py`: API-facing analysis function.
- `src/loader/`: loading, `Simulation`, `ResultsFile`, and repair helpers.
- `src/signatures/`: signature generation.
- `src/identifiers/`: identifier resolution and database/search adapters.
- `src/verifier/`: metadata fetching, verification workers, and result summarization.
- `src/executor/`: task creation and execution pipeline.
- `tests/loader/` and `tests/executor/`: current local test coverage.
- `tests/data/`: local MD simulation fixtures.

The current task pipeline is represented by `TaskType` values:

1. `INPUT`
2. `CREATE`
3. `LOAD`
4. `GENERATE_SIGNATURES`
5. `RESOLVE_IDENTIFIERS`
6. `SUMMARIZE`
7. `METADATA`
8. `UNLOAD`

TODO: Confirm whether documentation should present this task pipeline as the stable public workflow or as an implementation detail behind the higher-level pipeline stages above.
