# S0 Signature-Stage Validation — Case File

## Core Concept
S0 = ground truth (MDDBR) compared against BAT3 **signature-stage** outputs
(`data.signatures[segment]["generated"]`) — pre-identification, pre-database,
pre-ranking. Complement to S5/S7 (post-verification `verified_hits`). Created
2026-10-06 to (a) quantify the small-molecule reranking pain suspected in S5/S7,
(b) build the error-decomposition frame for methodology improvement. **Goal of
this file:** living ledger of findings; every open item is an actionable
methodology fix. Update + extend as work progresses; keep sections append-only
where possible (log at bottom).

## Infrastructure (built, tested, deployed)
- `scripts/stats/sigstage_probe.py` — S0 scorer; 50-shard fan-out on
  validation-worker pods; STRICT anchor gate vs `campaign_stats_v13.json`;
  thresholds = S7 currency (skelfp>=0.7 chem, align-identity>=0.9 seq, ion
  element channel); deterministic shards; replay-protocol scratch outputs.
- `scripts/stats/sigstage_audit.py` — per-annotation S0×S7 joined re-scorer
  (verbatim campaign machinery) + S5 membership + cross-tabs.
- Tests: `tests/sigstage/` (33 offline tests, all green).
- Artifacts (NFS, scratch): `/data/validation/sigstage/sigstage_v1.json`,
  `sigstage/audit/audit_v1.json`, `sigstage/audit/shards/shard_000.jsonl`
  (36,159 joined rows), `sigstage/casefiles/`.
- Commits (oct 06-07): `909cf15f6` probe, `3d2180b88` pattern fix,
  `a0fc78c8c` pilot fixes, `0fbecefd7` aligner thread race, `c02a05b5f` shard
  metadata, `2c2fa307d` audit, `a39d0e2f0` registry. Full detail in git log.

## Frozen numbers (full GT-covered set, 2026-10-07, 35,121 annotations / 13,957 entries)
| type | annotations | attempted | validated | note |
|---|---|---|---|---|
| ion | 2,726 | 97.2% | **95.8%** | element channel; near-ceiling |
| inchikey organic | 6,463 | 94.3% | **85.7%** | skelfp>=0.7 |
| pdb | 11,895 | 91.6% | **86.1%** | entity seq identity |
| uniprot | 14,037 | 87.6% | **80.1%** | construct divergence dominant |
| entry any-validated | 13,957 | | **91.1%** | |

Buckets: validated 29,632 · below_gate 1,771 · no_matching_generator 2,413 ·
unparseable_signature 525 · no_sig_data 586 · unresolved_gt 194.
Anchor STRICT delta: +5/+5 entries (live-campaign drift, documented).

## Findings ledger

**F-1 (ion ceiling)** — ion channel validates 95.8%; hypothesis "signature
stage near-perfect for ions" CONFIRMED. No action.

**F-2 (chem reranking pain CONFIRMED + QUANTIFIED)** — on S7 denominator
subset: S0 88.6% vs S7@1 60.2% → **2,143 annotations (34%) are input-correct
but reranked away at verified rank 1**; only 225 persist as lost @10.
Small-molecule problem is ranking, not finding. Supports near-tie tie-break
improvements in verification (_fid_key ordering / skeleton-gate placement).

**F-3 (ion denominator gap = selection)** — 837 ion annotations sit in
zero-verified-hit entries; S7 never counts them. S7 ion 1,876 vs S0 2,773
explained; NOT class drift (audit found zero organic↔ion flips).

**F-4 (protein S0<S7 split = selection + oracle)** — uniprot: S0 77.2 → 84.6
on S7 subset (selection, 1,433 zero-hit annotations) → 94.0 S7@1 (oracle:
1,526 rows S0✗/S7@1✓ where DB recovers exact reference, e.g. P03695 input
sim 0.46 vs hit 1.0). pdb same shape (1,367 oracle rows). Below-gate mass at
0.3–0.6 identity = homolog-level construct divergence, not tag noise.
**Implication: S0 and S7 measure different quantities; present as
complementary axes, never confusion of the two.**

**F-5 (verification loss @10 is tiny)** — S0✓ & S7@10✗: uniprot 33 (0.25%),
pdb 34 (0.3%), organic 225 (3.6%). Once input is right, verified_hits depth 10
nearly always retains it.

## Open items (methodology improvement queue)
- **S0-OQ-1** `no_matching_generator` (2,413) — entries lacking the segment
  signature family their GT needs (e.g., uniprot GT but no fasta_map_protein),
  with stage_errors_present=0. Cause census in progress (casefiles/S0-OQ-1).
  Suspected: segmentation/fasta-generator coverage gaps for some system types.
- **S0-OQ-2** `unparseable_signature` (525) — segment `smiles` values RDKit
  can't parse (valence warnings). Signature-generator output defect; harvest
  raw strings + error classes (casefiles/S0-OQ-2) → fix generator.
- **S0-OQ-3** `unresolved_gt` (194) — GT inchikey→SMILES resolution failures
  (mirror+cache+budget exhausted). Recoverable re-pass with higher budget.
- **S0-OQ-4** `below_gate` uniprot/pdb (1,771 total w/ chem) — divergent
  constructs; census by sim band ✓ (F-4) — evaluate whether MDDBR annotation
  or deposit really intends homolog (curation angle).
- **S0-OQ-5** @10 pipeline-loss cases (292 rows total across types) — each is
  a verification false-negative with input present; list for verification team.

## Update log
- 2026-10-06 — probe built+tested; pilot (n=100) run; 4 pilot-driven fixes.
- 2026-10-07 — full 50-shard run (aforementioned numbers); thread-race fix;
  audit built+run (36,159 joined rows); F-1..F-5 recorded.
