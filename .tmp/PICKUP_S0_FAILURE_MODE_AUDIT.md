# PICKUP — Final audit of failed annotations (2026-10-08)

> Next task. Context order: read
> `.opencode/context/bat3/lookup/s0-signature-stage-case-file.md` (F-1..F-7,
> update log through 2026-10-08(5)), then `guides/stats-pods-operations.md`,
> then `lookup/a5-curation-handoff.md` + `lookup/a4-perception-gap-handoff.md`,
> then this file. Previous wave evidence trail: `.tmp/PICKUP_S0_VALIDATION.md`
> (CLOSED).

## Objective
Decompose **every residual failure fraction** in the frozen v2/v14 numbers
into audited, mutually exclusive failure modes with counts — the article's
"why aren't we at 100% (and why that's still excellent)" section. Output is
figure-grade: each mode carries n, pct, denominator, and exemplar entries.

## The gaps to decompose (frozen numbers, verified 2026-10-08)
Audit join (audit_v2, ann denominators; campaign v14 reconciles separately):
- **organic inchikey S7@1 93.8% → 6.2% gap (~400 of 6,416)**
- organic inchikey S7@10 95.8% → 4.2%
- ion S7@K 98.4% → 1.6% (flat at all K — likely discrete classes)
- pdb S7@1 96.9%, S0 93.2%; uniprot S7@1 94.0%, S0 87.0%; inchikey S0 86.3%
- entry-level any-validated@1 98.6% → 1.4% (campaign v14)

Known components already evidenced (A2/A3/A6/A7-wave):
- 71 GT unresolved via mirror+web (ghost lineage; ghost_curation.json)
- 26 annotations with no verified chem hits; 8 structures absent from hit list
- ~152 genuine rerank residue after heal (223 residual − 71 GT ghosts)
- 531 protein-GT-in-lipid/struct-only entries + 93 chem segmentation gaps
  (A5 handoff; curation-side, not metric-side)
- S0-side: below-gate histograms already in audit rows
  (`s0_below_gate_sim_hist`), NMG classes (624 rows incl. subclasses),
  OQ-5 (339), OQ-2 (525 — PRE-A4 era numbers; post-fix improvement is a
  SEPARATE measurement, never mix eras)
- ion denominator-gap = selection (837 ions in zero-verified-hit entries)

## Approach
1. Build `scripts/stats/failure_mode_audit.py`:
   - input: `per_molecule_v2.jsonl` (36,159 rows; sig/id/ver channels)
     joined where needed with audit_v2 shard rows (richer fields)
   - per-annotation failure classifier: **mutually exclusive modes with a
     documented precedence chain** (never double-count; e.g. gt_unresolved >
     structure_absent > no_verified_hits > rerank_residual > below_gate_s0 >
     curated_metadata_cohort > perception_gap_gt_side(=advisory tag,
     not metric blame))
   - counts with ab32s+pct+denominator discipline (numbers-only rule)
   - exemplar entry extraction per mode (2–5 entries each)
   - reconciliation assertion: sum(modes) == failed count PER METRIC,
     byte-compared against audit_v2 types block (self-audit pattern)
2. Tests: fixture archetype rows per mode (ion split, ghost, rerank,
   lipid cohort, perception-gap, below-gate tail) — fail-on-unfixed proof;
   reconciliation fixtures incl. overlap rows (precedence correctness).
3. E2E on pod: full 36,159-annotation pass; outputs
   `sigstage/reports/failure_mode_audit.{json,md}` + delta checks vs
   audit_v2 and campaign_stats_v14.
4. Case-file chapter + frozen figure table updated with per-mode
   attribution; nav registration.

## Watchdogs / don't-redo
- Numbers-only rule: every figure with n+pct+denominator; no naked pcts.
- Mutually exclusive modes: document the precedence chain; overlap rows
  must land in exactly one bucket (advisory tags are separate channels).
- Era discipline: OQ-2's 525 is pre-A4-era; post-fix re-measurement is a
  different artifact — never merged into the v2 denominator story.
- A6 replay verdict (zero impairment on both substrates) is CLOSED — do
  not re-litigate; residual reranks are GT-side phenomena.
- Ghost/curation cohorts are METADATA-side findings: report as advisory
  curation tags, distinct from metric-failure modes.
- Perception-gap (~10% of 525) is GT-side/perception-side, NOT a metric
  failure — advisory tag only (see a4-perception-gap-handoff.md).

## Deliverables
- `scripts/stats/failure_mode_audit.py` + tests (committed; NFS-deployed)
- `sigstage/reports/failure_mode_audit.{json,md}` (figure-grade modes)
- case-file chapter: per-mode attribution with frozen denominators
- article-ready paragraph: "the remaining N% consists of: x% (mode),
  y% (mode), ... — residual unclassified: z% (<1% if achieved)"
