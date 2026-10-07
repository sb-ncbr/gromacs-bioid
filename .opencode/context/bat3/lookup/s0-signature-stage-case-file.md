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

## Frozen numbers (full GT-covered set, **M-1 era, 2026-10-07**; 35,121 annotations / 13,957 entries)
| type | annotations | attempted | validated | note |
|---|---|---|---|---|
| ion | 2,726 | 97.2% | **95.8%** | element channel; near-ceiling |
| inchikey organic | 6,463 | 94.3% | **85.7%** | skelfp>=0.7 |
| pdb | 11,895 | 98.4% | **97.2%** | +11.1pt after M-1 |
| uniprot | 14,037 | 94.5% | **90.3%** | +10.2pt after M-1 |
| entry any-validated | 13,957 | | **96.9%** | |

Buckets: validated 32,390 · below_gate 802 · no_matching_generator 624 ·
unparseable_signature 525 · no_sig_data 586 · unresolved_gt 194.
Anchor STRICT delta: +5/+5 entries. v1 (pre-M-1) artifacts preserved at
`/data/validation/sigstage/run_v1/` — do not quote pre-M-1 protein numbers.

## Methodology rulings
- **M-1 (2026-10-07)** — pairing accepts `fasta_resname_{protein,nucleic}`
  (resname-fallback sequence signatures) alongside `fasta_map_*`. Evidence:
  casefiles harvest — 96% of no_matching_generator came from entries having
  ONLY resname variants (probe blind spot `51083a621`). Effect: pdb
  86.1→97.2%, uniprot 80.1→90.3%, NMG 2,413→624, oracle cells collapse
  (uniprot 1,526→225; pdb 1,367→119).

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
- **S0-OQ-1** `no_matching_generator` — **CLOSED with census** (post-M-1
  residual 624): (a) ~530 protein-free **lipid-only systems** carrying protein
  GT annotations (gensets: lipid_shorthand/fingerprint/mmcif only) —
  MDDBR annotation-semantics case for curation, list at
  `casefiles/S0-OQ-1_nmg.jsonl`; (b) 93 chem-side gaps (75
  chem_present_but_no_smiles, 11 no_chem, 7 macro_only_no_ligand) — real
  segmentation gap for ligands, owner: signature team. Root cause of the v1
  bulk: probe blind spot (M-1).
- **S0-OQ-2** `unparseable_signature` (525) — **root-caused**: ALL 525 are
  `explicit_valence`; every raw string is charge-explicit zwitterionic SMILES
  ([NH+]/[C-]/[CH+]...) from the smiles generator (cf. generator
  `smiles_not_sanitized` exists separately). Action: post-generation
  normalization (sanitize=False + NormalizeCharges/Aromatize + re-emit) or
  emit neutral canonical SMILES alongside. Raw strings + segments at
  `casefiles/S0-OQ-2_unparseable.jsonl`, owner: signature team.
- **S0-OQ-3** `unresolved_gt` (194) — GT inchikey→SMILES resolution failures
  (mirror+cache+budget exhausted). Recoverable re-pass with higher budget.
- **S0-OQ-4** `below_gate` uniprot/pdb (802 post-M-1) — divergent constructs;
  census by sim band ✓ (F-4) — evaluate whether MDDBR annotation
  or deposit really intends homolog (curation angle).
- **S0-OQ-5** @10 pipeline-loss cases (292 rows total across types) — each is
  a verification false-negative with input present; list for verification team.

## Update log
- 2026-10-06 — probe built+tested; pilot (n=100) run; 4 pilot-driven fixes.
- 2026-10-07 — full 50-shard run (aforementioned numbers); thread-race fix;
  audit built+run (36,159 joined rows); F-1..F-5 recorded.
- 2026-10-07 (2) — casefiles harvest: OQ-2 root-caused (525/525
  explicit_valence zwitterionic SMILES); OQ-1 exposed probe blind spot →
  M-1 (`51083a621`); casefiles fd-deadlock fixed (`aee680791`); full S0
  rerun + audit rerun under M-1; report pack generated
  (`/data/validation/sigstage/sigstage_report_v1.{md,json}`; tool
  `9d3c572f3`). Residual NMG census closed; F-4 oracle framing superseded
  by M-1 numbers (oracle ~= methodology artifact for uniprot/pdb).
