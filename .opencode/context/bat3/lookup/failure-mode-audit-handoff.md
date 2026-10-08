# Failure-mode audit handoff — where the residual S0/S7 gaps come from

> For the journal agent: complete report + data links for the "why aren't we
> at 100% (and why that's still excellent)" section. Compiled 2026-10-08 from
> the frozen `audit_v2` join (36,159 rows), reconciled byte-exact against the
> frozen types block (PASS, all 4 types). All numbers below are the tool's
> output; basis notes included where bases differ.

## Tooling
- Tool: `scripts/stats/failure_mode_audit.py` (commit `890e5174e`), deployed
  md5-verified to pod `validation-worker-86f6984689-25hlh` at
  `/tmp/failure_mode_audit.py` (md5 `a9b043da11cc3d02755cccb6d6c7919c`).
- Tests: `tests/sigstage/test_failure_mode_audit.py` — 44 offline tests incl.
  end-to-end `main()` on a synthetic fixture tree + reconciliation-fail path.
- Registry row: `scripts/stats/README.md`. Case-file entry: `lookup/s0-signature-stage-case-file.md`, update log 2026-10-08 (6).

## Data links (NFS, authoritative)
| artifact | path |
|---|---|
| Report (JSON) | `/data/validation/sigstage/reports/failure_mode_audit.json` |
| Report (Markdown, with exemplars) | `/data/validation/sigstage/reports/failure_mode_audit.md` |
| Frozen audit join (36,159 rows) | `/data/validation/sigstage/audit_v2/audit_v2.json` + `audit_v2/shards/*.jsonl` |
| OQ-1 NMG cohort (624) | `/data/validation/sigstage/casefiles/S0-OQ-1_nmg.jsonl` |
| OQ-2 unparseable cohort (525) | `/data/validation/sigstage/casefiles/S0-OQ-2_unparseable.jsonl` |
| Ghost ledger curation | `/data/validation/sigstage/casefiles/ghost_curation.{json,md}` |
| Campaign comparator (basis differs) | `/data/validation/campaign_stats_v14.json` |

Pod is ephemeral; the NFS paths above are the durable links. Re-run any time:
`python3 /tmp/failure_mode_audit.py --out-json ... --out-md ...` (defaults read
the frozen inputs above) or re-deploy from the repo copy.

## Method in one paragraph
Every attempted-but-failed annotation is assigned exactly one mode via a
fixed precedence chain, and every failed S0 annotation likewise; per-metric
mode sums are asserted equal to the frozen failed counts (hard self-audit,
exit 3 on reconciliation mismatch). GT-unresolved is classified ONLY by the
audit's own per-row signals (`s7_class=='unresolved'` or
`s0_bucket=='unresolved_gt'`). The ghost ledger is reported as static
pair-level curation stats only — using InChIKey-endpoint membership to tag
rows was found to over-tag (76% of ghost pairs are dead-CID / live-InChIKey
per A3), so it is never used for per-row classification.

## Headline numbers
- Entry level (audit basis): 13,319 / 13,497 participating entries with
  >=1 S7-validated@1 hit = **98.7%** (campaign v14 basis: 98.6% — different
  denominators, do not mix). 178 failing entries roll up to:
  rank_loss_top5 131, weak_below_gate 25, rank_loss_top10 11,
  structure_absent 6, gt_unresolved 4, no_verified_hits 1.
- Frozen per-type scores (audit_v2, M-1 era): inchikey 6,416 ann — S0 86.3 /
  S7@1 93.8 / @10 95.8; ion 2,773 — 94.2 / 98.4 / 98.4; pdb 12,403 —
  93.2 / 96.9 / 99.5; uniprot 14,567 — 87.0 / 94.0 / 98.2.

## Residual decomposition (failed annotations → mode)
### inchikey (6,416 ann; 6,226 attempted; S7@1 fail 386; S7@10 fail 261; S0 fail 878; unattempted 190)
| metric | decomposition |
|---|---|
| S7@1 (386/6,226 = 6.2%) | gt_unresolved 148 · rank_loss_top5 100 · weak_below_gate 80 · structure_absent 39 · rank_loss_top10 19 |
| S7@10 (261) | gt_unresolved 142 · weak_below_gate 80 · structure_absent 39 |
| S0 (878/6,416 = 13.7%) | unparseable_signature 525 (OQ-2) · gt_unresolved 235 · no_sig_data 68 · below_gate 0-.3: 16, .3-.6: 14, .6-.8: 3 · no_matching_generator: no_chem 11, chem_no_smiles 3, macro_only 3 |
| unattempted (190) | zero_hit_entry 152 · attempt_gate_unmet 38 |

### ion (2,773 ann; 2,677 attempted; S7@1 fail 42; S0 fail 162; unattempted 96)
| metric | decomposition |
|---|---|
| S7@1 and S7@10 (42) | structure_absent 39 · no_verified_hits 3 |
| S0 (162) | no_matching_generator:chem_no_smiles 72 · no_sig_data 47 · below_gate:0-.3 39 · nmg:macro_only 4 |
| unattempted (96) | attempt_gate_unmet 72 · zero_hit_entry 24 |

### pdb (12,403 ann; 11,549 attempted; S7@1 fail 355; S7@10 fail 60; S0 fail 841; unattempted 854)
| metric | decomposition |
|---|---|
| S7@1 (355) | rank_loss_top5 206 · rank_loss_top10 86 · weak_below_gate 43 · structure_absent 17 · gt_unresolved 3 |
| S7@10 (60) | weak_below_gate 43 · structure_absent 17 |
| S0 (841) | no_s0_row 508 · no_sig_data 153 · below_gate .8-.9: 119, .6-.8: 23, 0-.3: 1, .3-.6: 1 · nmg:struct_only 32 · gt_unresolved 4 |
| unattempted (854) | zero_hit_entry 846 · attempt_gate_unmet 8 |

### uniprot (14,567 ann; 13,104 attempted; S7@1 fail 790; S7@10 fail 233; S0 fail 1,888; unattempted 1,463)
| metric | decomposition |
|---|---|
| S7@1 (790) | rank_loss_top5 406 · weak_below_gate 208 · rank_loss_top10 151 · gt_unresolved 21 · structure_absent 4 |
| S7@10 (233) | weak_below_gate 208 · gt_unresolved 21 · structure_absent 4 |
| S0 (1,888) | no_s0_row 530 · nmg:struct_only 498 · no_sig_data 251 · below_gate .3-.6: 226, .8-.9: 188, .6-.8: 171, 0-.3: 1 · gt_unresolved 22 · nmg:nucleic_only 1 |
| unattempted (1,463) | zero_hit_entry 1,433 · attempt_gate_unmet 30 |

## Advisory cohorts (NOT metric blame; separate channel in the report)
- A5 curation, lipid/struct-only protein GTs: **531** annotations
  (handoff: `lookup/a5-curation-handoff.md`).
- A5 curation, chem segmentation gaps: **93** annotations.
- OQ-2 perception gap (unparseable zwitterionic SMILES): **525** annotations
  (handoff: `lookup/a4-perception-gap-handoff.md`).
- Ghost ledger (pair-level, curation input): cid_zero 1 id / 645 pairs;
  unresolved_legacy 7,298 ids / 6,782 pairs; smiles_unparseable 33 ids /
  21 pairs. Source: `casefiles/ghost_curation.json`.

## Framing notes for the article
- The dominant organic S7@1 residual is GT-side (gt_unresolved 148 of 386)
  and ranking-depth (rank_loss 119 of 386) — not similarity weakness.
  A6's zero-impairment result (case file 2026-10-08 (4)) means the ranking
  loss is pre-existing depth/plateau behavior, not regression.
- S0's biggest organic gap is OQ-2 unparseable signatures (525) — a
  generator-side defect with a 98.5% salvageable fix (A4), not a
  discrimination weakness.
- Protein (pdb/uniprot) S7@1 gaps are overwhelmingly rank_loss_top5 —
  verification finds the right family, the exact construct just isn't ranked
  #1; @10 gaps are ~6x smaller, showing it's depth, not detection.
- Unattempted channel: 3,603 annotations are never S7-scored, mostly
  zero-verified-hit entries (selection, not crash) — consistent with OQ-6
  census (706/1,373 zero-hit entries clean-but-empty).
- Basis caution: entry any-validated@1 here is 98.7% (audit join basis) vs
  98.6% in `campaign_stats_v14.json` (campaign scan basis). Quote one basis
  per figure; the report carries both with labels.
