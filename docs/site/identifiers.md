# Identification & verification

The chemistry core: how a fragment of a simulation becomes a ranked, verified
identifier table.

## Stage 1 — signatures (per fragment)

19 generators produce complementary views of each fragment (subset shown):

| Class | Generators | Feeds |
|---|---|---|
| Sequence | `fasta_map_protein/nucleic`, `fasta_resname_*` | BLAST family, sequence verify |
| Structure | `pdb_protein`, `pdb_nucleic`, `pdb_backbone_*` (±sanitized), `topology_less_pdb`, `ca_only_pdb`, `mmcif` | RCSB structure search, AlphaFind, Foldseek (3Di via `tdi`) |
| Chemical | `smiles` (±sanitized), `inchi_key`, `morgan_fingerprint`, `selfies`, `molecular_formula`, `skeleton_fp`, `glycan_composition`, `lipid_shorthand` | PubChem/ChEMBL/ChEBI/IDSM, mirror DBs |
| Names/elements | `name_molecule`, `name_chain`, `name_segment`, `atom`, `fingerprint` | CCD/maps/manual name resolvers, element identity |

Generator applicability is flag-gated per segment (e.g. `IS_NUCLEIC`,
`HAS_ELEMENTS`, `HAS_UNIQUE_NAMES`). Strand-aware segmentation (W4) splits
merged multi-component assemblies into largest-component sequences —
deterministically (BFS order), which is why sibling entries produce identical
results. Failures are persisted under `stage_errors/signatures/<segment>`
(never log-only — F-N1e contract).

Generator names map to canonical signature types
(`pdb_backbone_nucleic → pdb_nucleic`, `fasta_map_protein → residue_sequence_protein`,
`molecular_formula → formula`, `tdi → 3di_sequence`, ...) — the map resolver
lookup consumes.

## Stage 2 — resolvers (per signature)

~26 resolvers, each declaring `accepted_signatures` and identity/similarity
modes. Dispatch: canonical signature type → applicable identity resolvers, then
similarity resolvers. All hits land under
`identifiers/<segment>/<generator>/<resolver>`.

| Family | Resolvers | Backend | Notes |
|---|---|---|---|
| BLAST | `blast_pdb_protein`, `blast_swissprot_protein`, `blast_uniprot`, `blast_nr_protein`, `blast_pdb_nucleic`, `blast_core_nt`, `blast_nt` | local BLAST DBs in image/NFS | e-value gates + content-gated **exact short-identity acceptance** for ≤~25 nt (W5); resolver-level coverage/identity filters |
| RCSB structure | `pdb_struct_protein`, `pdb_struct_nucleotide`, `mmcif_struct` | RCSB Search API v2 | fetches the published input file by URL; see channel status below |
| Fold/meta-structure | `alphafind_struct`, `foldseek_3di` | AlphaFind API, Foldseek | protein workhorses (10,920/16,087 and strong complement to BLAST) |
| Small-molecule | `pubchem`, `chembl`, `idsm_pubchem/chembl/chebi`, `inchikey_pubchem`, `inchikey_self`, `formula_pubchem`, `formula_local` (mirror), `formula_chembl`, `formula_hfamily` | mirror DBs preferred; PUG guarded by a **circuit breaker** | local PubChem mirror = primary formula channel; breaker skips PUG-dependent resolvers during outages, bypassed only by offline-capable backends. ⚠ **F-07 known deviation:** pubchem-family hit *scores are a constant stub* (equal to `similarity_threshold`; the PUG similarity API returns CIDs without per-compound scores). They are ordinal-only **within** that resolver and are **not comparable** to blast/uniprot scores — do not rank-mix across families. Real Tanimoto scoring is a TODO (fetch canonical SMILES + RDKit) |
| Names/elements | `name_ccd`, `name_maps`, `name_manual`, `atom` | CCD JSON, local maps | feeds the single-residue/ion identity class |

Resilience guards: per-stage deadline is propagated into resolver loops;
the PubChem circuit breaker self-heals every 30 s (probe to a fixed CID).
Resolver errors are collected into `stage_errors/identifiers/<segment>`.

!!! warning "formula_chembl contained (OQ-1, 2026-10-05) — dead upstream"
    EBI ChEMBL REST removed molecular-formula support (payloads carry no
    formula fields; the coded exact filter returns HTTP 400, previously
    swallowed silently to `[]`). Identity attempts were contained via the
    `[identifiers] formula_chembl: no` ini toggle — formula signatures are
    now served by the working **local PubChem mirror** + `formula_hfamily`.
    The resolver code stays dormant; planned revival = local ChEMBL mirror
    (OQ-11, pubchem-mirror pattern).

!!! note "Declared verdicts in stage_errors (not failures)"
    `na_mode_unsupported` (F-23, 2026-10-04): an RCSB structure-search call
    was skipped *by design* because the payload class is unsupported upstream
    (pure nucleic acid). These previously appeared as fake-fixable HTTP 400
    error spam with a guaranteed zero-hit outcome. Treatment: count
    separately from real errors (rate-limit/crash classes); no action needed.

!!! info "RCSB structure-search channel — current truth (F-23/24/25)"
    - Query shape: structure node `similarity_type: local`,
      `target_search_space: assembly`, `number_of_candidates: 10000`.
    - **F-25 fixed 2026-10-04**: payload now carries
      `request_options.paginate.rows=10000` — previously RCSB silently
      returned its default **10 rows** regardless of `number_of_candidates`
      (live-probed: same query = 464 total / 10 rows without paginate, 100
      with). Universes >10 now actually reach the parser.
    - `pdb_struct_*` adds a composition filter
      (`selected_polymer_entity_types in ["Protein (only)"]` / NA-only) which
      **excludes mixed-composition entries** (protein+NA complexes, RCSB enum
      `Protein/NA`) in both modes — **F-24, addon decision pending** (additive
      design only; ruled 2026-10-04).
    - **F-23 containment deployed 2026-10-04**: the structure-search backend
      is protein-centric and rejects pure nucleic-acid payloads by design
      (HTTP 400; proven live: 1BNA → 400, 1UBQ → 200/464). NA-mode calls are
      now **short-circuited before the request**: `pdb_struct_nucleotide`
      always (mode = NA payload), `mmcif_struct` when the mmCIF contains only
      NA polymer entities (mixed protein+NA still queries — the engine can
      handle the protein part). Instead of 400 spam, stage_errors receives
      the declared verdict **`na_mode_unsupported`** — a countable,
      non-failure containment class. Guarantee: these verdicts replace
      attempts that historically produced **zero** hits.
    - `mmcif_struct` sends the same query shape **without** the composition
      filter (attempts every class that passes the NA-only guard); until F-23
      this produced e.g. 1,691 zero-hit NA attempts.

## Stage 3 — verification (candidate → verdict)

1. **Collect + deduplicate** all resolver hits for the fragment; hits normalize
   (`1FZX_A`,`1FZX_B` → `1FZX` — safe: the sequence fetcher returns *all*
   polymer entities and the worker verifies best-of-all).
   Consensus score = best resolver score × log2(1 + distinct resolvers), capped 100.
2. **Structure-aware re-rank** (chemicals): skeleton-Tanimoto lifts real isomers
   out of formula floods before the window cut (raise-only, inert without a
   molecule fingerprint).
3. **Window**: top `verify_top_n` (100) candidates are verified.
4. **Fetch canonical data** per identifier (RCSB/UniProt/PubChem-mirror; batch
   prefetch for chemicals; per-process API rate limiting + on-disk cache).
5. **Score**: worker similarity (sequence identity×coverage, structure align,
   skeleton fingerprint, element match) + annotation-quality scorer;
   `final = 0.4·consensus + 0.4·similarity + 0.2·annotation` (weights configurable).
6. **Verdict**: chemical hits require skeleton-sim ≥ gate (hard). Others follow
   the positive-evidence rule — **identity hits verify largely on resolver
   self-assertion today** (see F-17 on the running-validations page).
7. **Order**: verified chemical hits first, fidelity-sorted (skeleton-sim →
   confidence → identifier); everything else preserves relative order.

### Hit-type semantics

- `identity` hits: resolver asserts exact match (e.g. InChIKey equality,
  100%-identity full-length BLAST, RCSB ≥99.9 structural similarity).
- `similarity` hits: resolver returns ranked near-neighbours with scores;
  capped at `similarity_top_n` (10) per resolver to bound downstream cost.
