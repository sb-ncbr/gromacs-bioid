# A5 curation handoff — MDDBR GT metadata issues (S0/A2/A3 evidence)

> Handoff artifact for MDDBR curation. Every cohort references a machine-readable
> case file under `/data/validation/sigstage/casefiles/`. Compiled 2026-10-08
> from sigstage S0 (M-1, 35,121 rows), pair-cache heal (A2), PubChem mirror
> refresh + ghost classification (A3). Contact: validation-stats pipeline owner.

## 1. Lipid/struct-only entries carrying protein GT — 531 annotations
- Class `struct_only_no_fasta_generator`: **530 rows** (511 with lipid
  generators present); protein GT: **499 uniprot + 32 pdb**.
- Pattern: MDDBR annotates project-level protein context, but the deposited
  files are membrane-only — signatures carry `lipid_shorthand`, `fingerprint`,
  `mmcif` generator outputs only, no protein fasta channel.
- Action: annotate GT at segment level, not project level (or mark these GTs
  as context-only). Source: `S0-OQ-1_nmg.jsonl` (rows carry entry_id,
  gt_type, gt_value, generators list, nmg_class).

## 2. Chem segmentation gaps — 93 inchikey annotations
- `macro_only_no_ligand_signature` and adjacent classes
  (`chem_present_but_no_smiles` 75, `no_chem_signatures` 11,
  `macro_only_no_ligand_signature` 7): files carry chem GT but no usable
  ligand signature channel.
- Source: `S0-OQ-1_nmg.jsonl` (gt_type=inchikey rows).

## 3. Ghost GTs — deprecated/deleted PubChem records
- 6,782 pair keys unresolvable via mirror AND full web chain
  (`warmup_ghosts.json`); **7,298 distinct identifiers** classified in
  `ghost_curation.{json,md}`:
  - `unresolved_legacy` 7,298 — candidates: deprecated/deleted records or
    withdrawn GTs; **dominant lineage: dead CID side / live InChIKey side
    (76% of sampled pairs)** → curation should map successor CIDs.
  - `cid_zero`: ONE malformed identifier (`cid:0`) over **645 pairs** —
    single upstream emitter; strip/fix at source.
  - 153 pairs fully dead (both sides).
  - 33 `smiles_unparseable` (cross-ref OQ-2/A4).
- Post-mirror-refresh measurement (v2026-10-07): `ghosts_post_mirror.json`.

## 4. Charge-corrupted SMILES in GT harvest — see A4 discovery handoff
(`a4-perception-gap-handoff.md`): 525-row OQ-2 class; 517/525 salvageable
upstream of GT curation; ~10% of the class additionally carry
graph-vs-GT mismatches that only automatic skeleton comparison surfaces.
