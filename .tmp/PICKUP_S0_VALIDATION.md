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

### A1. Engine rule: never persist sim=0.0 on resolution failure  [DONE 2026-10-07]
- Commit `86f696418` (md5 `45dc529416b860c2c8fda9024155ba15`, deployed + verified
  on NFS; live pairs.jsonl untouched, md5 `733a0c4cab3de33fe316c3f9ee67151a`
  before/after).
- Implemented: LookupError/Exception → transient 0.0 (memory + disk untouched,
  retried next call/run); computed zeros on success still persist; budget counts
  distinct first-attempts via `_attempted` (recurrences can't re-burn budget).
- Discovered + pinned: empty-alignment pairs raise IndexError (LookupError
  subclass) → were a second poisoning class in seq space; now transient.
- Evidence: `tests/sigstage/test_engine_failure_cache.py` — 7 tests, 4 verified
  to fail on the unfixed engine (each pins a defect), 91/91 suite green post-fix;
  deployment E2E on pod (live construct read-only 1,185,518 pairs; forced-fail
  transient in real runtime; real aspirin chain RESOLVED+PERSISTED into tmp ROOT).

### A2. Purge poisoned pairs + corrected S7  [DONE 2026-10-07]
- Purge (dry-run == real, byte-deterministic): healed 20,385 / kept 88,537
  computed zeros / dropped 9,504; backup `pairs.jsonl.bak-pre-heal-20261007`.
- Purge driver bug found by dry-run checkpoint + fixed (`a3ee1a450`);
  warmup tool (`0394300d3`) resolved 2,683/9,486 dropped keys (ghost list →
  A3: `sigstage/casefiles/warmup_ghosts.json`, 6,782 keys + cid:0 class 645).
- v14 stalled twice → A1.1 in-run negative memo (`749ed73bc`) fixed the
  single-thread-loop ghost-rechain amplifier (proven by 5 fail-on-unfixed
  tests + deployment E2E); rerun then completed in ~2h.
- **campaign_stats_v14.json: organic inchikey S7@1 60.2 → 94.0** (+5/+5
  denominators vs v13 exactly as STRICT gate predicted); entry any@1 → 98.6;
  ion/uniprot/pdb unchanged. Delta table attached to case file (update log 7).
- OPEN follow-through: v13 organic figures in `lookup/publication-journal.md`
  are SUPERSEDED — manuscript figure regeneration must be coordinated with
  the owner (replay protocol); that edit was deliberately NOT made here.

### A3. PubChem mirror refresh + ghost-GT curation list  [DONE 2026-10-08]
- Mirror v2026-10-07 built/validated/activated (lifecycle patch `c23e8079c`,
  gated --defer/--activate-only); ghost classifier `5a08617f9` →
  `casefiles/ghost_curation.{json,md}`: cid:0=645-pair single emitter,
  unresolved_legacy 7,298 (dead-CID lineage 76% → successor-CID mapping),
  153 fully dead; post-mirror measurement in `ghosts_post_mirror.json`.

### A4. smiles-generator normalization  [DONE 2026-10-07]
- Tiered salvage on the partial-sanitize failure path (`1f379895c`): neutral
  canonical + skeleton-collapse/minimal-charge repair; success path
  byte-identical. 517/525 (98.5%) re-parseable, graph-fidelity 100%,
  8 junk fallbacks. 26 tests. NEW finding: ~10% of the class carry
  graph≠GT perception defects (`lookup/a4-perception-gap-handoff.md`,
  article motivation).

### A5. Curation: lipid-only systems carrying protein GT  [CURATION]
- HANDOFF WRITTEN: `lookup/a5-curation-handoff.md` (+NFS
  `sigstage/reports/A5-curation-handoff.md`) — 531 protein-GT-in-lipid
  cohort + 93 chem segmentation gaps + ghost ledger syndicated.
  Remaining: MDDBR-side curation decisions (owner action).
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

### A7. Case-file closeouts (after A2/A4)  [DONE 2026-10-08]
- v2 probe rerun 50/50 shards → STRICT +0/+0 vs campaign_stats_v14
  (`sigstage_v2.json`, 35,121 rows) via permanent merger
  (`4fe6fb76b`+`2d92c7f4c`+`cda1daa1b`+`2d46ab6d1`).
- audit_v2 36,159 joined rows (`9804c26e6`); per_molecule_v2 export
  (36,159 rows, sig/id/ver channels, `ba7804c7c`).
- Frozen v2 numbers in case file (inchikey s7@1 93.8 vs 60.2 v1).
- Manuscript figures: v14 campaign stats + audit_v2 + per_molecule_v2 are
  the figure corpus; journal regeneration still owner-gated.

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
