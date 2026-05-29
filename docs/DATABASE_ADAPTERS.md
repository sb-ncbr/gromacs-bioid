# BioID v2 Database Adapter Specification

This document defines how BioID v2 should interact with external and local identity/similarity databases. It describes the current resolver architecture and the target adapter contract for future development.

## Current Implementation Baseline

Current database-related code is under `src/identifiers/` and `src/verifier/metadata_fetchers/`.

Current resolver registry:

- `IdentifierType.BLAST_PDB_PROT`
- `IdentifierType.BLAST_PDB_NT`
- `IdentifierType.BLAST_UNIPROT`
- `IdentifierType.PDB_STRUCT_PROTEIN`
- `IdentifierType.PDB_STRUCT_NUCLEOTIDE`
- `IdentifierType.ALPHAFIND_STRUCT`
- `IdentifierType.IDSM_PUBCHEM`
- `IdentifierType.IDSM_CHEMBL`
- `IdentifierType.IDSM_CHEBI`
- `IdentifierType.CHEMBL_STRUCT`
- `IdentifierType.PUBCHEM_STRUCT`
- `IdentifierType.ATOM`
- `IdentifierType.NAME_CCD`
- `IdentifierType.NAME_MAPS`
- `IdentifierType.NAME_MANUAL`

Current base abstraction:

- `IdentifierResolver` accepts a generated signature string and a signature type.
- It exposes `is_applicable(signature, signature_type, as_similarity)`.
- It exposes `resolve_signature(signature, as_similarity, working_directory)`.
- It delegates implementation to `_resolve_identity()` and `_resolve_similarity()`.
- It stores and fetches cached results through `ResolverCache`.

Current result storage:

- Attempted resolvers are stored under `identifiers/<segment>/<signature_generator>/attempted`.
- Resolver results are stored under `identifiers/<segment>/<signature_generator>/<resolver>/`.
- Stored fields include `signature`, `hit_type`, and `hits`.
- Exact hits are stored as `(identifier, 100.0)`.
- Similarity hits are sorted and stored with score-like values.

Current limitations:

- Resolver output is not a normalized candidate object.
- Resolver score semantics differ by resolver.
- Raw responses are not generally preserved.
- Failure/no-hit/unavailable states are often collapsed into `None`, empty lists, or logs.
- Metadata fetchers are separate from resolver candidate output.

## Adapter Responsibilities

Every database adapter should be responsible for one clearly defined database/search capability.

Required responsibilities:

- Accept a `MolecularRepresentation` or current signature string.
- Check applicability for representation type and search mode.
- Run identity and/or similarity search.
- Parse database-specific responses.
- Normalize each hit into a `DatabaseCandidate`.
- Report provenance, database name, resolver name, search method, query representation, score type, and source response pointer.
- Handle failure cleanly without turning infrastructure errors into false no-hit results.
- Respect configuration for enabled/disabled adapters, thresholds, retry behavior, cache policy, and network policy.
- Avoid mutating molecular input data.

Adapters must distinguish:

- adapter disabled
- representation not applicable
- query malformed
- no hits
- database unavailable
- request timeout
- rate limited
- parse failure
- local executable missing
- cache hit
- cache miss

## Candidate Databases

### PDB/RCSB

Current adapters:

- `BLAST_PDB_PROT`: sequence search against PDB protein BLAST database.
- `BLAST_PDB_NT`: sequence search against PDB nucleotide BLAST database.
- `PDB_STRUCT_PROTEIN`: RCSB structure similarity search for protein PDB signatures.
- `PDB_STRUCT_NUCLEOTIDE`: RCSB structure similarity search for nucleic-acid PDB signatures.

Expected supported searches:

- Sequence identity and similarity search for proteins and nucleic acids.
- Structure similarity search against RCSB.
- Exact or near-exact structure matching when supported.
- Metadata expansion to RCSB URL, entry ID, image, name, and accession.

Reliability notes:

- PDB entries may contain redundant structures, chains, engineered constructs, partial structures, obsolete entries, or multiple biological assemblies.
- Structure search may require upload or accessible file URLs.
- Results should preserve entity type filters and query structure provenance.

### UniProt

Current adapter:

- `BLAST_UNIPROT`: sequence search against a configured UniProt BLAST database.

Expected supported searches:

- Protein sequence identity search.
- Protein sequence similarity search.
- Cross-reference expansion from PDB or other identifiers where applicable.

Reliability notes:

- UniProt accessions can be merged, obsolete, or isoform-specific.
- Search results should preserve accession, database version if known, identity, coverage, e-value, and bit score.

### AlphaFind or Structural Similarity Services

Current adapter:

- `ALPHAFIND_STRUCT`: remote AlphaFind structure search for protein PDB signatures.

Expected supported searches:

- Structure similarity search.
- Identity-like detection when aligned percentage or equivalent score indicates exact/near-exact structural match.

Reliability notes:

- Service availability and response schema may change.
- Current implementation uses a remote `curl` request and retry polling.
- Adapter output must record endpoint, retry policy, timeout, and raw response pointer where possible.

### PubChem, ChEMBL, LipidMaps, and Similar Small-Molecule/Lipid Resources

Current adapters:

- `PUBCHEM_STRUCT`: PubChem SMILES identity and 2D similarity search.
- `CHEMBL_STRUCT`: ChEMBL SMILES identity-like and similarity search.
- `IDSM_PUBCHEM`: IDSM/Sachem-backed PubChem similarity search.
- `IDSM_CHEMBL`: IDSM/Sachem-backed ChEMBL similarity search.
- `IDSM_CHEBI`: IDSM/Sachem-backed ChEBI similarity search.
- `NAME_MAPS`: local MAPS name database lookup, likely lipid-oriented depending on database contents.

Expected future adapters:

- LipidMaps-specific adapter if LipidMaps is used directly.
- ChEBI adapter if ChEBI identity/synonym lookup is used directly.

Expected supported searches:

- Chemical identity lookup from valid SMILES, InChI, or InChIKey.
- Chemical similarity search.
- Name/synonym lookup for curated local resources.
- Cross-reference expansion between PubChem CID, ChEMBL ID, ChEBI ID, InChIKey, and other identifiers.

Reliability notes:

- Small-molecule databases can contain salts, mixtures, stereochemistry variants, tautomers, neutralized forms, and duplicate records.
- Similarity thresholds are not equivalent across PubChem, ChEMBL, and IDSM.
- Ligands and lipids must not be identified from weak names alone when structural evidence is available.

### Local Indexes and Caches

Current local resources:

- `ResolverCache`: SQLite cache with `CACHE_IDENTITY` and `CACHE_SIMILARITY` tables.
- Local BLAST database paths configured in `config.ini`.
- Local name databases configured as `ccd_db`, `maps_db`, and `manual_db`.
- Database sync helper in `src/utils/sync_databases.py`.

Expected behavior:

- Cache identity and similarity results separately.
- Include resolver name and query signature in cache keys.
- Record whether candidate output came from live resolver or cache.
- Never require network calls in default tests.
- Treat stale or missing local indexes as explicit adapter failures, not no-hit results.

## Search Types

### Exact Identifier Lookup

Input:

- Existing identifier, name, InChIKey, element symbol, or curated local name.

Expected output:

- One or more exact database candidates.
- Method marked as `identity` or `exact_lookup`.
- Score marked as exact only when the adapter guarantees exactness.

Current examples:

- `ATOM` returns an element identifier from an element signature.
- `NAME_CCD`, `NAME_MAPS`, and `NAME_MANUAL` map names to InChIKeys.

### Sequence Search

Input:

- Protein or nucleic-acid FASTA/sequence representation.

Expected output:

- Database identifiers with sequence identity, coverage, e-value, bit score, and threshold decisions.

Current examples:

- `BLAST_PDB_PROT`
- `BLAST_PDB_NT`
- `BLAST_UNIPROT`

### Structure Similarity Search

Input:

- PDB or equivalent structure representation.

Expected output:

- Structure identifiers with database-specific structure scores and normalized score fields.

Current examples:

- `PDB_STRUCT_PROTEIN`
- `PDB_STRUCT_NUCLEOTIDE`
- `ALPHAFIND_STRUCT`

### Chemical Similarity Search

Input:

- Valid SMILES, future InChI, future InChIKey, or fingerprint.

Expected output:

- Small-molecule identifiers with similarity score, score type, threshold, and chemical normalization notes.

Current examples:

- `PUBCHEM_STRUCT`
- `CHEMBL_STRUCT`
- `IDSM_PUBCHEM`
- `IDSM_CHEMBL`
- `IDSM_CHEBI`

### Residue, Name, and Synonym Search

Input:

- Segment names, molecule names, residue names, chain names, or curated aliases.

Expected output:

- Candidate identifiers with low or descriptive confidence unless backed by stronger structural evidence.

Current examples:

- `NAME_CCD`
- `NAME_MAPS`
- `NAME_MANUAL`

Rule:

- Name-derived candidates must remain distinguishable from structure-derived or sequence-derived candidates.

### Cross-Reference Expansion

Input:

- A known identifier from one database.

Expected output:

- Cross-linked identifiers and metadata from other databases.

Current examples:

- Metadata fetchers can expand PDB IDs and InChIKeys into links, names, images, accessions, and database entry IDs.

Proposed:

- Treat cross-reference expansion as a separate adapter mode from primary identity/similarity search.

## Adapter Input Contract

Current input:

```python
signature: str
signature_type: str
as_similarity: bool
working_directory: str
```

Proposed input:

```json
{
  "representation_id": "repr_000001",
  "entity_id": "entity_000001",
  "representation_type": "SMILES",
  "signature_type": "smiles",
  "content": "CCO",
  "path": null,
  "generation_method": "SimpleSmilesGenerator",
  "limitations": [],
  "provenance_ids": []
}
```

Adapter applicability must consider:

- representation type
- entity type
- search mode
- configuration flags
- network policy
- local executable/database availability
- known representation limitations

## Adapter Output Contract

Current output:

- Identity: `list[str]`
- Similarity: `list[tuple[str, float]]`
- Stored as `hits` under `ResultsFile`.

Proposed normalized candidate:

```json
{
  "candidate_id": "cand_000001",
  "entity_id": "entity_000001",
  "representation_id": "repr_000001",
  "database": "PubChem",
  "resolver": "PUBCHEM_STRUCT",
  "identifier": "962",
  "identifier_type": "PUBCHEM_CID",
  "entity_name": "water",
  "synonyms": [],
  "score": 100.0,
  "score_type": "identity|similarity|percent_identity|coverage|structure_score|adapter_threshold",
  "method": "identity|similarity|cross_reference|name_lookup",
  "match_kind": "exact|near_exact|similar|weak|descriptive",
  "url": "https://pubchem.ncbi.nlm.nih.gov/compound/962",
  "raw_response_pointer": "responses/pubchem/cand_000001.json",
  "raw_metadata": {},
  "confidence": {
    "adapter_confidence": 1.0,
    "evidence_level": "sequence|structure|chemistry|name|element|cross_reference",
    "thresholds": {},
    "notes": []
  },
  "provenance": {
    "query_representation_id": "repr_000001",
    "adapter_version": null,
    "database_version": null,
    "cache_status": "miss|hit|disabled",
    "network_used": true,
    "timestamp": null
  },
  "warnings": []
}
```

Required normalized fields:

- database name
- identifier
- identifier type
- entity name when available
- synonyms when available
- score
- score type
- method
- URL when available
- raw response pointer or raw metadata pointer
- confidence/evidence fields
- provenance

## Score and Confidence Semantics

Adapters must not imply that all scores mean the same thing.

Required score fields:

- `score`: numeric value as normalized for sorting within a method.
- `score_type`: exact meaning of score.
- `raw_score`: original database score when different from `score`.
- `threshold`: threshold applied by the adapter.
- `match_kind`: exact, near-exact, similar, weak, or descriptive.

Examples:

- BLAST should preserve e-value, bit score, identity fraction/percent, and query coverage.
- PubChem similarity currently returns threshold values rather than per-hit similarity in some paths; this must be documented in candidate output.
- ChEMBL similarity returns similarity values from ChEMBL records.
- IDSM returns Sachem scores converted to percentages.
- RCSB structure search returns database-specific structure scores.
- Exact local name lookup should not be treated as strong molecular identity unless corroborated.

## Failure Handling

Adapters should return structured status, not only empty lists.

Proposed statuses:

- `success`
- `not_applicable`
- `disabled`
- `no_hits`
- `cache_hit`
- `cache_miss`
- `network_error`
- `rate_limited`
- `timeout`
- `parse_error`
- `auth_error`
- `local_resource_missing`
- `local_executable_failed`
- `invalid_query`

Current behavior:

- `IdentifierResolver.resolve_signature()` catches `IdentifierResolutionError` and generic exceptions, logs them, and returns `None`.
- Some resolver implementations return empty lists for service failures.

Required future behavior:

- Preserve failure reason in warnings/provenance.
- Do not treat failure as no-hit.
- Allow local deterministic annotations to proceed when external databases are unavailable.

## Reliability Concerns

### Uncurated or Redundant Entries

Databases may contain redundant structures, duplicate compounds, predicted structures, synthetic constructs, salts, mixtures, and partial records.

Rules:

- Preserve source database and evidence type.
- Prefer curated or reviewed records when that metadata is available.
- Do not collapse distinct candidates unless a documented merge policy applies.

### Multiple Hits for the Same Molecule

Multiple identifiers can represent the same or equivalent molecule.

Rules:

- Keep all candidates initially.
- Group candidates by exact identifier, cross-reference, InChIKey, sequence identity, or structural equivalence only when evidence supports it.
- Preserve the provenance of each source hit.

### Obsolete Identifiers

Databases may retire or merge entries.

Rules:

- Adapters should detect obsolete/secondary identifiers where APIs expose that status.
- Candidate output should include replacement identifiers when known.
- Final annotations should prefer current identifiers.

### Missing Metadata

Some hits may lack names, synonyms, images, cross-links, or entry descriptions.

Rules:

- Missing metadata should not invalidate a scientifically strong hit.
- Missing metadata should be explicit as `null` or empty lists.
- Metadata fetching should not overwrite identifier evidence.

### Network Errors

Network errors include DNS failure, HTTP errors, dropped connections, and malformed responses.

Rules:

- Use timeouts.
- Retry only where configured.
- Report the failure reason.
- Do not block local deterministic output.

### API Rate Limits

Rules:

- Respect retry-after headers where available.
- Apply configured retry counts and delays.
- Record rate-limit events in warnings/provenance.
- Avoid repeated queries through cache and deduplication.

## Caching and Local Indexes

Current cache:

- `ResolverCache` stores identity and similarity results in SQLite.
- Cache keys include resolver name and signature.

Required cache behavior:

- Cache identity and similarity separately.
- Include query representation digest in future cache keys.
- Include database version when known.
- Preserve whether a result came from cache in candidate provenance.
- Provide a way to bypass cache for validation or debugging.
- Never require cache files to be committed to the repository.

Local indexes:

- BLAST databases are configured in `config.ini`.
- Name databases are configured in `config.ini`.
- Database sync may download local database files when enabled.

Rules:

- Missing local indexes must produce `local_resource_missing`.
- Missing executables must produce `local_executable_failed`.
- Local index version or checksum should be recorded when available.

## Testing Strategy

### Default Tests

Default tests must not require network calls, external database services, or large downloads.

Default tests should use:

- mock responses
- local cached fixtures
- temporary SQLite caches
- tiny synthetic signatures
- local parser fixtures

### Mock Responses

For each adapter, maintain response fixtures for:

- exact hit
- similarity hits
- no hits
- malformed response
- timeout or failure
- multiple conflicting hits
- obsolete or redirected identifiers if supported

### Cached Fixtures

Cache tests should verify:

- cache miss stores identity results
- cache miss stores similarity results
- cache hit avoids resolver execution
- identity and similarity caches do not mix
- cache paths are configurable and test-local

### Optional Live Tests

Live tests may be useful but must be opt-in.

Requirements:

- Mark as integration or live-network.
- Require an explicit environment flag.
- Use small, stable queries.
- Avoid exact ranking assertions unless the database guarantees stable order.
- Record service name, query, expected tolerance, and date-sensitive assumptions.

### Schema Validation

Adapter output tests should validate:

- normalized candidate required fields
- score type and method fields
- raw response pointer or raw metadata
- provenance fields
- failure status fields
- warnings for degraded or uncertain responses

Current TODOs:

- Add unit tests for BLAST parser and filters.
- Add mocked tests for PubChem, ChEMBL, IDSM, RCSB, AlphaFind, name, and atom resolvers.
- Add cache tests with temporary SQLite files.
- Add normalized candidate schema tests once the schema is implemented.

## Adapter Registration and Extension

Current extension path:

1. Implement an `IdentifierResolver` subclass in `src/identifiers/identifier_resolvers/`.
2. Register it in `IdentifierType` in `src/identifiers/identifier_manager.py`.
3. Add configuration flags under `[identifiers]`.
4. Add threshold or database-specific configuration in `config.ini`.
5. Add tests with mocked responses or local fixtures.

Future extension path:

1. Implement an adapter with typed input/output contracts.
2. Declare supported representation types and search types.
3. Declare network/local-resource requirements.
4. Declare score semantics.
5. Register through a plugin or adapter registry.
6. Add schema validation tests and mocked failure tests.

## Implementation Notes

- Keep database adapters separate from representation generation.
- Keep metadata expansion separate from candidate discovery unless the database search response already includes metadata.
- Make all network and subprocess behavior mockable.
- Preserve raw database evidence where possible, but expose normalized candidate fields for downstream validation.
- Do not hard-code database responses in production code.
- Do not allow database search failures to erase local evidence or produce false certainty.
