# Identification & verification

How a molecule in a simulation becomes a ranked table of verified database
hits. Code: `src_new/signatures/`, `src_new/identification/`,
`src_new/verification/`.

## Stage 1 — signatures

27 generators describe each molecule; which ones apply depends on the
molecule's type (protein, nucleic acid, small molecule, lipid, glycan, ion,
water). Each generator's output maps to a **signature type**, which is what
databases accept:

| Signature type | Generators |
|---|---|
| `residue_sequence_protein` / `_nucleotide` | `fasta_map_*`, `fasta_resname_*` |
| `pdb_protein` / `pdb_nucleic` | `pdb_protein`, `pdb_nucleic`, `pdb_backbone_*` |
| `topology_less_pdb`, `ca_only_pdb`, `mmcif`, `3di_sequence` | `topology_less_pdb`, `ca_only_pdb` (Cα model), `mmcif`, `tdi` |
| `smiles`, `selfies`, `inchikey` | `smiles`, `smiles_not_sanitized`, `selfies`, `inchi_key` |
| `formula`, `skeleton_fp` | `molecular_formula`, `molecular_formula_heavy`, `skeleton_fp` |
| `lipid_shorthand`, `glycan_composition` | `lipid_shorthand`, `glycan_composition` |
| `name`, `element`, `hash` | `name_chain`, `name_molecule`, `name_segment`, `resname`, `atom`, `fingerprint` |

The map is `get_signature_type_map()` in `src_new/signatures/registry.py`.
Chemistry (SMILES, InChIKey, …) comes from bond-order perception on the
simulated structure, with net charge, united-atom hydrogens and
stereochemistry from 3D handled explicitly; polymer segments get no
chemistry signatures. Small segments are processed first, so one slow molecule
cannot starve the rest of the stage budget. Failures are stored under
`stage_errors/signatures/<molecule>`.

## Stage 2 — database searches

Each database search (a *resolver*) declares the signature types it
accepts. For every signature, the identity search runs first, then the
similarity search, each only if its switch is on. All hits land under
`identifiers/<molecule>/<generator>/<key>`. The full list of databases,
with what each searches and where it runs, is on the
[Databases](databases.md) page.

The stage runs in two passes (`src_new/pipeline_steps`,
`src_new/identification/supplementary.py`):

1. the main databases on every molecule;
2. the **supplementary** databases (UniRef50, Foldseek PDB, SwissLipids,
   ChEBI, SIFTS), then the **deferred** ones
   (`[identifiers] deferred_resolvers`), on what is left of the stage
   budget. This pass can only add evidence.

Safeguards:

- the stage deadline is checked inside the resolver loops; a search cut by
  the budget is recorded, the stage continues;
- BLAST failures are cached for the run, identical signatures are searched
  once;
- RCSB overload answers (5xx, 429, timeouts) back off and retry, and oversized
  query assemblies are split per chain; lost structure evidence is recorded
  under `identification/structure_search_unavailable`;
- `stage_errors/identifiers/<molecule>` holds bounded failure records.
  `na_mode_unsupported` there is a declared skip (RCSB does not search
  pure nucleic-acid structures), not an error.

## Stage 3 — verification

`VerificationManager.verify_all` (`src_new/verification/manager.py`), for
each molecule, smallest first:

1. **Collect and deduplicate** every hit of the molecule. Identifiers are
   normalised (`1FZX_A`, `1FZX_B` → `1FZX`); hits from different resolvers
   that read the same database (e.g. `blast_uniprot` and
   `blast_swissprot_protein`, or the PubChem formula searches) count as one
   evidence source.
2. **Database agreement** (`belief`, 0–100) from how many independent
   sources propose the candidate, identity claims counting fully and
   similarity claims a third:
   `belief = 100 · (1 − 0.5^(n_identity + n_similarity/3))`. One identity
   source gives 50, two give 75, three 87.5; it never reaches 100.
3. **Window**: candidates are ordered by agreement and interleaved across
   identifier families (PDB, UniProt, PubChem, …) so that one family's flood
   cannot fill the window; chemical candidates are first re-ranked by skeleton
   similarity (raise-only). The top `verify_top_n` (100) are verified, then up
   to `verify_top_n_supplementary` (code 20, `config.ini` 40) that only the
   second identify pass found.
4. **Fetch** each candidate's record (sequence, structure, SMILES,
   annotation) — UniProt sequences from the local BLAST databases first,
   compounds from the local PubChem mirror first, with retries, a per-run memo
   and an on-disk cache.
5. **Compare**: sequence identity × coverage (local alignment), structural
   TM-score (`tm_score_threshold`, 0.5), skeleton-fingerprint Tanimoto for
   chemicals (gate 0.7, plus a second-tier fingerprint that separates e.g.
   DPPC from DMPC), element match for ions.
6. **Confidence** (0–100):
   `final = w_r · belief + w_s · similarity + w_a · annotation`, with the
   weights (`resolver_weight`, `similarity_weight`, `annotation_weight`,
   default 0.4 / 0.4 / 0.2) normalised to sum 1. A term that could not be
   measured (fetch failure, no comparison for that type) is left out and the
   remaining weights are re-normalised; it never counts as zero. The
   annotation term scores how complete the database record is.
   Ground-truth rules set 100 for a one-atom ion matched to its element and
   for the first exact water hit on a water molecule.
7. **Verdict**: see [`is_verified`](running-a-validation.md#the-verified_hits-table).
   Chemical candidates always need the skeleton gate.
8. **Order**: verified hits first, by fidelity: skeleton similarity (in
   0.05 steps), identity before similarity, second-tier fingerprint, measured
   similarity, agreement, number of sources, confidence; the stored order is
   the display order. Rows that describe the same structure share an
   `equivalence_class_id`.

The formula version and the effective weights are recorded in
`verification/_meta` (current `confidence_formula_version`: `v3.144.0`).

### Hit types

- `identity`: the database search claims an exact match (InChIKey equality,
  a BLAST hit passing the exact thresholds, RCSB structural similarity
  ≥ 99.9 %).
- `similarity`: ranked near neighbours; at most `similarity_top_n` (10) per
  database search are kept.

!!! note "History"
    Until v3.142 (2026-10-22) the agreement term was
    `best resolver score × log2(1 + distinct resolvers)`. Resolver scores no
    longer enter the confidence, which matters because PubChem similarity
    hits still carry a constant placeholder score (F-07: the PubChem API
    returns no per-compound similarity).
    The RCSB structure-search fixes of 2026-10-04/06 (F-23 nucleic-acid
    short-circuit, F-24 optional mixed protein/NA query
    `[pdb] rcsb_include_mixed_complexes`, F-25 result pagination) are in
    place; the mixed query is on in the *Deep search* preset.
