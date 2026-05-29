# BioID v2 Data Model and Annotation Schema

This document defines the core conceptual objects that should move through the BioID v2 pipeline. It also maps those objects to the current implementation where possible.

The current repository does not define Pydantic models, a JSON Schema, or dataclasses for the full pipeline data model. The present implementation uses:

- `Simulation` in `src/loader/simulation.py` as the main in-memory simulation handle.
- MDAnalysis `Universe` and `AtomGroup` objects as the implicit atom/system model.
- `ResultsFile` in `src/loader/results_file.py` as a flexible JSON-backed store using slash-delimited paths.
- Enums such as `LoadStrategy`, `SegmentSupports`, `SignatureType`, `IdentifierType`, `VerificationKind`, and `SegmentMoleculeType`.
- One narrow `BlastHit` dataclass in `src/identifiers/identifier_resolvers/blast.py`.

Everything below marked **Proposed** is a target schema for future development, not a statement that the object currently exists in code.

## Design Goals

- Keep every pipeline stage explicit about inputs, outputs, confidence, warnings, and provenance.
- Preserve mappings from final annotations back to source files, atom indices, residues, segments, signatures, resolvers, and validation decisions.
- Keep local deterministic inference separate from external database lookup.
- Represent uncertainty directly instead of converting it into false certainty.
- Make output suitable for CLI, API, web, repository integration, semantic search, and downstream validation.

## Current Result Layout

Current `ResultsFile` paths observed in the code include:

- `simulation/load_strategy`
- `simulation/segments/<segment>/flags/<SegmentSupports>`
- `simulation/segments/<segment>/atoms_molecule`
- `simulation/segments/<segment>/bonds_molecule`
- `simulation/segments/<segment>/atoms`
- `simulation/segments/<segment>/bonds`
- `simulation/segments/<segment>/molecules`
- `signatures/<segment>/attempted`
- `signatures/<segment>/generated/<SignatureType>`
- `identifiers/<segment>/<signature_generator>/attempted`
- `identifiers/<segment>/<signature_generator>/<resolver>/signature`
- `identifiers/<segment>/<signature_generator>/<resolver>/hit_type`
- `identifiers/<segment>/<signature_generator>/<resolver>/hits`
- `summary/simulation_mmcif`
- `summary/segments/<segment>/simulation_mmcif`
- `summary/segments/<segment>/macromolecule_type/<type>`
- `summary/segments/<segment>/ident`
- `summary/segments/<segment>/ident_type`
- `summary/segments/<segment>/confidence`
- `summary/segments/<segment>/verification`
- `summary/segments/<segment>/db_crosslink`
- `summary/segments/<segment>/db_entry_id`
- `summary/segments/<segment>/db_type`
- `summary/segments/<segment>/image_path`
- `summary/segments/<segment>/name`
- `summary/segments/<segment>/accession`

This layout should be treated as the current implementation format, not the final versioned annotation schema.

## Proposed Top-Level Annotation Shape

**Proposed**

```json
{
  "schema_version": "bioid.annotation.v1",
  "run": {
    "bioid_version": null,
    "created_at": null,
    "configuration_digest": null
  },
  "input_bundle": {},
  "atomic_map": {},
  "repair_records": [],
  "entities": [],
  "representations": [],
  "database_candidates": [],
  "validation_results": [],
  "final_annotations": [],
  "warnings": [],
  "provenance": []
}
```

The current `ResultsFile` data can be adapted into this shape, but the adapter does not exist yet.

## Common Supporting Types

### Warning

**Proposed**

```json
{
  "warning_id": "warn_000001",
  "code": "MISSING_ELEMENT",
  "severity": "info|warning|error",
  "stage": "loading|atomic_map|repair|entity_extraction|representation|database_search|validation|annotation",
  "message": "Element inferred from atomic mass.",
  "affected": {
    "file_id": null,
    "atom_ids": [],
    "residue_ids": [],
    "chain_or_segment_ids": [],
    "entity_ids": []
  },
  "confidence_impact": "none|reduced|blocked",
  "provenance_ids": []
}
```

Current status: warnings are mostly logs or implicit failures. There is no formal warning object.

### ProvenanceRecord

**Proposed**

```json
{
  "provenance_id": "prov_000001",
  "stage": "loading",
  "operation": "LoadStrategy.ITP_GRO",
  "inputs": ["file_000001", "file_000002"],
  "outputs": ["atomic_map_000001"],
  "software": {
    "name": "MDAnalysis",
    "version": null
  },
  "parameters": {},
  "timestamp": null
}
```

Current status: some provenance is present through `simulation/load_strategy`, `used_files.txt`, `all_files.txt`, generated signatures, attempted resolvers, and logs. There is no unified provenance table.

## 1. InputBundle

**Proposed**

`InputBundle` represents the raw files submitted for one simulation analysis and the loader metadata derived from those files.

Fields:

- `input_bundle_id`: stable ID for the submitted bundle.
- `root_directory`: simulation directory path or repository-relative location.
- `files`: list of input files.
- `relationships`: topology/trajectory/structure relationships selected or inferred by the loader.
- `loader_metadata`: selected strategy, attempted strategies, used files, ignored files, and loader warnings.

Example:

```json
{
  "input_bundle_id": "input_000001",
  "root_directory": "tests/data/16319",
  "files": [
    {
      "file_id": "file_000001",
      "path": "tests/data/16319/topol.top",
      "original_path": "tests/data/16319/topol.top",
      "file_type": "GROMACS_TOP",
      "role": "topology",
      "size_bytes": null,
      "checksum": null
    },
    {
      "file_id": "file_000002",
      "path": "tests/data/16319/md.gro",
      "original_path": "tests/data/16319/md.gro",
      "file_type": "GROMACS_GRO",
      "role": "coordinates",
      "size_bytes": null,
      "checksum": null
    }
  ],
  "relationships": [
    {
      "relationship_type": "topology_coordinates",
      "topology_file_id": "file_000001",
      "coordinate_file_id": "file_000002",
      "trajectory_file_ids": []
    }
  ],
  "loader_metadata": {
    "selected_load_strategy": "ITP_GRO",
    "attempted_load_strategies": [],
    "used_file_ids": ["file_000001", "file_000002"],
    "ignored_file_ids": [],
    "warnings": []
  }
}
```

Current mapping:

- `LoadStrategy` in `src/loader/universe_loader.py`.
- `simulation/load_strategy` in `ResultsFile`.
- `used_files.txt` written by `save_used_files`.
- `all_files.txt` written by task creation.

Missing today:

- Formal file IDs.
- File checksums.
- Structured file roles.
- Attempted load strategy list.
- Explicit ignored-file list.

## 2. AtomicMap

**Proposed**

`AtomicMap` is the normalized atom-level model produced from a loaded simulation system. It should reduce direct coupling between later stages and MDAnalysis.

Fields:

- `atomic_map_id`
- `source_input_bundle_id`
- `loader_universe_ref`: optional implementation reference, not intended for final output.
- `atoms`
- `residues`
- `chains_or_segments`
- `coordinates`
- `bonds`
- `inferred_fields`
- `warnings`
- `provenance_ids`

Example:

```json
{
  "atomic_map_id": "atomic_map_000001",
  "source_input_bundle_id": "input_000001",
  "atoms": [
    {
      "atom_id": "atom_000001",
      "source_atom_index": 0,
      "name": "CA",
      "type": null,
      "element": "C",
      "mass": 12.011,
      "charge": null,
      "residue_id": "res_000001",
      "chain_or_segment_id": "seg_A",
      "coordinates_ref": "coord_000001",
      "inferred_fields": [],
      "provenance_ids": []
    }
  ],
  "residues": [
    {
      "residue_id": "res_000001",
      "source_resid": 1,
      "resname": "ALA",
      "chain_or_segment_id": "seg_A",
      "atom_ids": ["atom_000001"],
      "is_standard_amino_acid": true,
      "is_standard_nucleic_acid": false
    }
  ],
  "chains_or_segments": [
    {
      "chain_or_segment_id": "seg_A",
      "source_id": "A",
      "kind": "segment",
      "atom_ids": ["atom_000001"],
      "residue_ids": ["res_000001"]
    }
  ],
  "coordinates": [
    {
      "coordinates_id": "coord_000001",
      "frame_index": 0,
      "unit": "angstrom",
      "atom_positions": {
        "atom_000001": [0.0, 0.0, 0.0]
      }
    }
  ],
  "bonds": [
    {
      "bond_id": "bond_000001",
      "atom_ids": ["atom_000001", "atom_000002"],
      "order": null,
      "source": "topology|inferred|unknown",
      "confidence": 1.0
    }
  ],
  "inferred_fields": [],
  "warnings": [],
  "provenance_ids": []
}
```

Current mapping:

- MDAnalysis `Universe` and `AtomGroup` hold the actual atom/residue/segment/coordinate/bond data.
- `Simulation.load_simulation` records per-segment flags and counts under `simulation/segments/<segment>/...`.
- `SegmentSupports` captures whether elements, masses, positions, names, known residue names, unique names, and multi-atom residues are available.

Missing today:

- A standalone `AtomicMap` class.
- Stable atom/residue/entity IDs.
- Structured coordinate frames.
- Structured inferred-field annotations.
- Structured warnings/provenance.

## 3. RepairRecord

**Proposed**

`RepairRecord` describes a repair or inference operation applied to atomic data. Repairs should be explicit even when they mutate the in-memory object.

Fields:

- `repair_record_id`
- `atomic_map_id`
- `target_kind`: `atom|residue|bond|segment|entity|system`
- `target_ids`
- `missing_or_invalid_field`
- `original_value`
- `inferred_value`
- `method`
- `evidence`
- `confidence`
- `reversible`
- `applied_to_working_model`
- `warnings`
- `provenance_ids`

Example:

```json
{
  "repair_record_id": "repair_000001",
  "atomic_map_id": "atomic_map_000001",
  "target_kind": "atom",
  "target_ids": ["atom_000001"],
  "missing_or_invalid_field": "element",
  "original_value": null,
  "inferred_value": "C",
  "method": "estimate_elements_from_mass",
  "evidence": {
    "mass": 12.011,
    "atom_name": "CA"
  },
  "confidence": 0.95,
  "reversible": true,
  "applied_to_working_model": true,
  "warnings": [],
  "provenance_ids": ["prov_000002"]
}
```

Current mapping:

- `src/loader/repair_fragment.py` contains element and name inference helpers.
- `Simulation.fix_missing_elements` tries mass-based, name-based, type-based, and multi-method element inference.

Missing today:

- Formal record of what was missing.
- Formal confidence per repair.
- Formal distinction between mutation and annotation-only repair.
- Reversibility tracking.

## 4. SimulatedObject / Entity

**Proposed**

`SimulatedObject` or `Entity` represents an extracted molecular object from the system. Use `Entity` as the preferred public name and keep `segment`/`fragment` as implementation details when possible.

Fields:

- `entity_id`
- `entity_type`
- `classification_confidence`
- `atom_selection`
- `atom_ids`
- `residue_ids`
- `residue_range`
- `chain_or_segment_ids`
- `copy_number`
- `parent_system`
- `deduplication_key`
- `source_segment`
- `source_fragment_index`
- `warnings`
- `provenance_ids`

Allowed `entity_type` values should include:

- `protein`
- `nucleic_acid`
- `lipid`
- `membrane`
- `ligand`
- `small_molecule`
- `ion`
- `solvent`
- `water`
- `carbohydrate`
- `unknown`
- `ambiguous`
- `simulation_product`

Example:

```json
{
  "entity_id": "entity_000001",
  "entity_type": "protein",
  "classification_confidence": 0.98,
  "atom_selection": "segid A",
  "atom_ids": ["atom_000001", "atom_000002"],
  "residue_ids": ["res_000001", "res_000002"],
  "residue_range": {
    "start": 1,
    "end": 120,
    "source_numbering": true
  },
  "chain_or_segment_ids": ["seg_A"],
  "copy_number": 1,
  "parent_system": "atomic_map_000001",
  "deduplication_key": "protein:A:1-120",
  "source_segment": "A",
  "source_fragment_index": 0,
  "warnings": [],
  "provenance_ids": []
}
```

Current mapping:

- `Simulation.get_segments()` returns segment names.
- `Simulation.get_fragment(segment_name)` returns the first MDAnalysis fragment for a segment.
- `ResultsSummarizer._classify_segment_type` uses `SegmentMoleculeType`: `PROTEIN`, `NUCLEIC`, `LIPID`, `CARBOHYDRATE`, `ATOM`, `WATER`, `UNKNOWN`.
- Current output stores segment-level molecule type booleans under `summary/segments/<segment>/macromolecule_type/...`.

Missing today:

- First-class entity IDs.
- Copy-number model independent of segment name.
- Explicit ambiguous entity type.
- Formal ligand/small molecule/membrane/simulation-product classes.
- Deduplication key.

## 5. MolecularRepresentation

**Proposed**

`MolecularRepresentation` is a generated representation of an entity used for search, validation, display, or export.

Fields:

- `representation_id`
- `entity_id`
- `representation_type`
- `content`
- `path`
- `format`
- `signature_generator`
- `generation_method`
- `generator_type`
- `sanitized`
- `limitations`
- `applicability`
- `warnings`
- `provenance_ids`

Representation types should include:

- `PDB`
- `mmCIF`
- `FASTA`
- `SMILES`
- `InChI`
- `InChIKey`
- `sequence`
- `fingerprint`
- `atom`
- `name`

Example:

```json
{
  "representation_id": "repr_000001",
  "entity_id": "entity_000001",
  "representation_type": "FASTA",
  "content": "MSTNPKPQR...",
  "path": null,
  "format": "plain_sequence",
  "signature_generator": "FASTA_MAP_PROTEIN",
  "generation_method": "MapFastaGeneratorProtein",
  "generator_type": "ANALYTICAL",
  "sanitized": null,
  "limitations": [],
  "applicability": {
    "applicable": true,
    "reason": null
  },
  "warnings": [],
  "provenance_ids": []
}
```

Current mapping:

- `SignatureGenerator` has `generator_name`, `generator_type`, and `signature_type`.
- `SignatureType` includes FASTA, atom, SMILES, PDB, name, and fingerprint generator variants.
- Current generated signatures are stored as strings under `signatures/<segment>/generated/<SignatureType>`.
- Current attempted generators are stored under `signatures/<segment>/attempted`.
- `ResultsSummarizer` exports `simulation.mmcif` and `<segment>.mmcif` paths into summary fields.

Missing today:

- Representation IDs.
- Structured limitations and applicability reasons.
- Distinction between inline content and file paths in the signature schema.
- Formal InChI/InChIKey generation as a representation type.

## 6. DatabaseCandidate

**Proposed**

`DatabaseCandidate` represents one candidate database hit from a resolver.

Fields:

- `candidate_id`
- `entity_id`
- `representation_id`
- `database`
- `resolver`
- `identifier`
- `identifier_type`
- `name`
- `synonyms`
- `score`
- `score_type`
- `method`
- `match_kind`
- `url`
- `raw_metadata`
- `provenance_ids`
- `warnings`

Example:

```json
{
  "candidate_id": "cand_000001",
  "entity_id": "entity_000001",
  "representation_id": "repr_000001",
  "database": "UniProt",
  "resolver": "BLAST_UNIPROT",
  "identifier": "P12345",
  "identifier_type": "UNIPROT_ID",
  "name": null,
  "synonyms": [],
  "score": 97.4,
  "score_type": "percent_identity",
  "method": "similarity",
  "match_kind": "similarity",
  "url": null,
  "raw_metadata": {},
  "provenance_ids": [],
  "warnings": []
}
```

Current mapping:

- Resolver registrations live in `IdentifierType`.
- Resolver base fields include `resolver_name`, `identifier_type`, and accepted signature types.
- Current identifiers are stored under `identifiers/<segment>/<signature_generator>/<resolver>/...`.
- Current exact hits are stored as `(identifier, 100.0)`.
- Current similarity hits are sorted and converted into percentage-like scores when needed.
- `BlastHit` stores BLAST accessions, e-value, bit score, identity fraction, and coverage fraction internally.

Missing today:

- Candidate IDs.
- Structured database name separate from resolver name.
- URL field at candidate stage.
- Name/synonyms at candidate stage.
- Raw metadata attached to each candidate.
- Standard score semantics across resolvers.

## 7. ValidationResult

**Proposed**

`ValidationResult` records whether and how a candidate was validated.

Fields:

- `validation_result_id`
- `candidate_id`
- `entity_id`
- `passed`
- `validation_method`
- `validation_kind`
- `conflicts`
- `score_contribution`
- `observed_score`
- `explanation`
- `warnings`
- `provenance_ids`

Example:

```json
{
  "validation_result_id": "val_000001",
  "candidate_id": "cand_000001",
  "entity_id": "entity_000001",
  "passed": true,
  "validation_method": "reverse_sequence_lookup",
  "validation_kind": "PROTEIN",
  "conflicts": [],
  "score_contribution": 0.92,
  "observed_score": 92.0,
  "explanation": "Candidate sequence matched generated FASTA above configured threshold.",
  "warnings": [],
  "provenance_ids": []
}
```

Current mapping:

- `VerificationKind` includes `PROTEIN`, `NUCLEIC`, `COMPOUND`, `WATER`, `ATOM`, and `NONE`.
- `Verifier.calculate_identifier_confidence()` returns `(identifier, identifier_type, confidence, observed_confidence)`.
- `summary/segments/<segment>/verification` stores the list of verification tuples.
- `summary/segments/<segment>/confidence` stores the resolver confidence of the selected top hit.

Missing today:

- Candidate-level validation IDs.
- Explicit pass/fail field.
- Structured conflicts.
- Human-readable explanation.
- Clear difference between resolver score, validation score, and final confidence.

## 8. FinalAnnotation

**Proposed**

`FinalAnnotation` is the normalized annotation emitted for one BioID entity.

Fields:

- `annotation_id`
- `bioid_entity_id`
- `entity_type`
- `best_identifiers`
- `confidence`
- `confidence_explanation`
- `candidate_ids`
- `evidence`
- `standardized_metadata`
- `warnings`
- `provenance_ids`

Example:

```json
{
  "annotation_id": "ann_000001",
  "bioid_entity_id": "entity_000001",
  "entity_type": "protein",
  "best_identifiers": [
    {
      "identifier": "P12345",
      "identifier_type": "UNIPROT_ID",
      "database": "UniProt",
      "candidate_id": "cand_000001",
      "validation_result_id": "val_000001"
    }
  ],
  "confidence": 0.92,
  "confidence_explanation": "Best candidate selected from resolver score and validation score.",
  "candidate_ids": ["cand_000001", "cand_000002"],
  "evidence": {
    "input_bundle_id": "input_000001",
    "atomic_map_id": "atomic_map_000001",
    "representation_ids": ["repr_000001"],
    "repair_record_ids": []
  },
  "standardized_metadata": {
    "name": null,
    "synonyms": [],
    "accession": "UniProt: P12345",
    "db_crosslink": null,
    "db_entry_id": "P12345",
    "db_type": "UniProt",
    "image_path": null,
    "structure_path": null
  },
  "warnings": [],
  "provenance_ids": []
}
```

Current mapping:

- `summary/segments/<segment>/ident`
- `summary/segments/<segment>/ident_type`
- `summary/segments/<segment>/confidence`
- `summary/segments/<segment>/verification`
- `summary/segments/<segment>/db_crosslink`
- `summary/segments/<segment>/db_entry_id`
- `summary/segments/<segment>/db_type`
- `summary/segments/<segment>/image_path`
- `summary/segments/<segment>/name`
- `summary/segments/<segment>/accession`

Missing today:

- Annotation IDs.
- BioID entity IDs independent of segment names.
- Structured best identifier list.
- Structured evidence object.
- Versioned standardized metadata schema.

## Proposed Current-to-Future Mapping

| Current term/path | Proposed object/field |
| --- | --- |
| simulation directory | `InputBundle.root_directory` |
| `all_files.txt` | `InputBundle.files` |
| `used_files.txt` | `InputBundle.loader_metadata.used_file_ids` |
| `simulation/load_strategy` | `InputBundle.loader_metadata.selected_load_strategy` |
| MDAnalysis `Universe` | `AtomicMap` source model |
| `simulation/segments/<segment>/flags/*` | `AtomicMap` availability and warning inputs |
| `Simulation.get_fragment(segment)` | `Entity.atom_selection` and `Entity.atom_ids` |
| `signatures/<segment>/generated/*` | `MolecularRepresentation` |
| `identifiers/<segment>/<signature>/<resolver>/hits` | `DatabaseCandidate` |
| `summary/segments/<segment>/verification` | `ValidationResult` |
| `summary/segments/<segment>/ident` | `FinalAnnotation.best_identifiers` |
| `summary/segments/<segment>/confidence` | `FinalAnnotation.confidence` |
| metadata fields under `summary/segments/<segment>/...` | `FinalAnnotation.standardized_metadata` |

## Annotation Confidence Rules

**Proposed**

BioID should distinguish these score types:

- `resolver_score`: score returned by an identifier resolver or normalized from exact match.
- `validation_score`: score from candidate validation or reverse lookup.
- `repair_confidence`: confidence in repaired/inferred data used as evidence.
- `classification_confidence`: confidence in entity type classification.
- `final_confidence`: final annotation confidence computed from evidence.

The final confidence must not exceed what the available evidence supports. If critical input fields are inferred, missing, or ambiguous, final confidence should be reduced or explained.

Current status:

- Exact identifier hits are stored as `100.0`.
- Similarity hits are stored as rounded percentage-like values for many resolver outputs.
- Validation returns observed confidence where available.
- There is no documented unified confidence model.

## Schema Versioning

**Proposed**

Every exported annotation document should include:

- `schema_version`
- `bioid_version`
- `created_at`
- optional `configuration_digest`

Schema changes should be additive where possible. Breaking changes should increment the schema version and include a migration note.

Current status:

- `ResultsFile` has no schema version field.

## Serialization Rules

**Proposed**

- Use JSON-compatible primitive types in final output.
- Represent unavailable values as `null`, not empty strings.
- Use stable IDs for cross-references.
- Preserve raw resolver metadata under `raw_metadata`, but keep normalized fields available at the top level.
- Store large representations by path when inline content would be excessive.
- Record file paths relative to the simulation output directory when possible.

Current status:

- `ResultsFile` writes JSON with `json.dump(..., indent=4)`.
- Some generated outputs are stored by filename in summary paths.
- Tuple-like values may serialize as JSON arrays.

## Implementation Notes

- This document does not require immediate migration from `ResultsFile`.
- A practical next step is to add typed adapters that read current `ResultsFile` output and emit the proposed schema.
- New pipeline code should prefer structured objects at stage boundaries and write to `ResultsFile` only at controlled output points.
- Unit tests should validate schema adapters with local fixtures and mocked database results.
