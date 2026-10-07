# PICKUP — S0 Signature-Stage Validation: Methodical Findings Queue

> Resume point for the post-compaction session. Context: read
> `.opencode/context/bat3/lookup/s0-signature-stage-case-file.md` FIRST
> (findings F-1..F-7, M-1, frozen numbers), then
> `.opencode/context/bat3/guides/stats-pods-operations.md` (ops playbook),
> then this file. Owner goal: convert findings into better results.

## Current state (2026-10-07, end of session)

- S0 campaign complete under methodology M-1; artifacts:
  `/data/validation/sigstage/sigstage_v1.json` (35,121 rows, full GT set),
  `sigstage/audit/audit_v1.json` (36,159 joined rows),
  `sigstage/casefiles/{S0-OQ-1_nmg,S0-OQ-2_unparseable,chemrerank,heal_summary}.json*`,
  `sigstage/sigstage_report_v1.{md,json}`, pilot preserved at `sigstage_pilot/`,
  pre-M-1 at `sigstage/run_v1/`.
- Tooling committed in `scripts/stats/`: sigstage_probe, sigstage_audit,
  sigstage_casefiles, sigstage_report, sigstage_chemrerank, sigstage_heal
  (all tested offline — 84 tests in `tests/sigstage/`, all green;
  NFS copies deployed, md5-verified at deploy time).
- Case file current through F-7 (pair-cache poisoning) + closures.

## Action queue (ordered; each item = commit(s) + evidence expectation)

### A1. Engine rule: never persist sim=0.0 on resolution failure  [CODE, small]
- File: `scripts/validation_similarity.py` (canonical; NFS copy lags — note
  in README drift table already; deploy to NFS after commit).
- Change: in `SimEngine._entity_sim`, on `LookupError`/exception → do NOT
  write to `self.pairs`/`_save_pair`; count as `unmapped` and return 0.0
  transiently (or persist under a distinct, TTL'd `neg` record).
- Acceptance: unit test — resolver raising LookupError leaves pairs file
  untouched and a second call retries; existing tests still green.

### A2. Purge poisoned pairs + corrected S7  [OPS + METRICS]
- Run `sigstage_heal.py --purge --dry-run` on NFS pair cache; inspect; then
  real purge (auto backup `.bak-pre-heal-*`).
- Rerun campaign S7 (`campaign_stats.py --full --sim`, same anchors protocol),
  expect organic S7@1 ≈ ~91% (heal evidence: 89.6% of 2,143 cohort heals@1).
- Corrected figures: numbers currently quoted in
  `lookup/publication-journal.md` (v13 S7) are affected — coordinate with the
  manuscript owner before regenerating official figures (replay protocol).
- Acceptance: campaign_stats_v14.json with documented heal lineage;
  delta table vs v13 attached to case file.

### A3. PubChem mirror refresh + ghost-GT curation list  [DATA OPS]
- Evidence: 71 cohort GTs + 112 unique OQ-3 GTs unresolvable via mirror AND
  web chain (deprecated/deleted records). Mirror at
  `/app/databases/pubchem/current/pubchem.sqlite` (build scripts:
  `scripts/populate_pubchem_mirror.py`).
- Deliver: list of ghost keys to MDDBR curation (from `casefiles` rows +
  OQ-3 measurement), refresh mirror, re-measure unresolved count.

### A4. smiles-generator normalization  [CODE, src_new]
- Evidence: 525/525 unparseable rows, single class `explicit_valence`,
  charge-explicit zwitterionic SMILES (`S0-OQ-2_unparseable.jsonl`).
- Fix: post-generation normalization in smiles generator
  (sanitize=False → NormalizeCharges/Aromatize → canonical emit) or emit
  companion neutral canonical smiles; keep `smiles_not_sanitized` as raw.
- Acceptance: the 525 case rows re-parse clean on generator rerun;
  regression test from 3 raw strings in the case list.

### A5. Curation: lipid-only systems carrying protein GT  [CURATION]
- Evidence: ~530 rows, gensets lipid_shorthand/fingerprint/mmcif only
  (`S0-OQ-1_nmg.jsonl` residual). MDDBR metadata annotates project-level
  protein context; deposited files are membrane-only.
- Also: 93 chem segmentation gaps (macro_only_no_ligand_signature et al.).

### A6. Verification ranking: evidence-count tie-break  [CODE, optional]
- Evidence: residual ~223 genuine rerank rows post-heal; confidence is
  plateau-quantized with resolver-family ordinal stubs setting plateaus
  (code self-warns in `manager.py` F-07 note).
- Change: within same-skeleton cluster (skel_sim tie), order by
  supporting_evidence_count desc before final_confidence; evaluate on the
  residual cohort (acceptance: rerank cohort shrink measured with chemrerank).

### A7. Case-file closeouts (after A2/A4)
- Re-run S0 probe + audit after A2 purge (denominators anchored; STRICT
  gate expected +5/+5 drift window); update frozen numbers (v2),
  mark S0-OQ-3/4/5 with final counts; reference corrected S7 (v14).

## Known watchdogs / don't-redo
- STRICT anchor gate aborts on full-set denominator mismatch — expected
  +5/+5 vs v13 (live campaign); document deltas, never bypass silently
  (`--anchor-lax` only for narrowed runs, warnings recorded).
- `next(iter(align(...)))` + thread-local aligner + prewarm imports +
  capture lock are REGRESSION-GUARDED — keep those tests green.
- `tests/validation/` is gitignored (bare `validation` rule) — sigstage
  tests live in `tests/sigstage/` by design.
- Numbers-only rule: every figure quoted must carry ab32s+pct+denominator.

## Session hygiene state
- Workspace `.tmp/` diagnostics cleaned except this file + pod lists.
- Pod `/tmp` logs removed (sig*/probe*/cf*/heal*/audit*). NFS artifacts
  under `/data/validation/sigstage/` are the durable record.
