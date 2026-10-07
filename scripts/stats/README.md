# scripts/stats — provenance copies of the live statistics/audit tooling (F-28)

**Why this exists.** Pre-F-28, the official methodology generators lived ONLY on
NFS (`/data/validation/*.py`) — ~34 single copies with **no version control**,
and visible in-place mutation history (`campaign_stats.py.bak-pre-fidelity`,
`.bak-pre-metals`, `.bak-pre-v7`). Every official number traced to mutable
unversioned scripts. F-28 (ruled 2026-10-04): bring the generator set under git
provenance; NFS keeps authoritative data + execution copies.

**Scope rule.** Files here are **provenance copies** of the NFS live set as of
**2026-10-05** (34 `*.py`, byte-identical, md5-verified at copy time — see
`MANIFEST.csv`). From now on, changes to statistics/audit tooling are edited
**here first** (commit), then deployed to NFS. The reverse direction (NFS →
repo) is how we found drift — see below.

**Dual-home drift measured at copy time (2026-10-05):**

| file | state |
|---|---|
| `campaign_stats.py` | identical to `scripts/campaign_stats.py` (the pre-existing single synced case) |
| `gt_rules.py`, `harvest_chemical_gt.py`, `strip_for_reidentify.py`, `replay_identify_verify.py`, `replay_verification.py` | byte-identical to their `scripts/` copies |
| `validation_similarity.py` | **repo newer**: repo has `inchikey_smiles` in DIRS + `makedirs` fix; NFS copy lags (reverse drift). Repo copy is canonical. |
| all `n1_*.py`, `audit_*.py`, `rank_audit*.py`, `residue_scan.py`, `offline_hit_k.py`, `coverability_probe.py`, `assemble_stats_package*.py`, `bag_funnel*.py` | **NFS-only** (no repo lineage until now) |

Note: `bag_funnel.py` vs `bag_funnel_v12_run.py` differ by small edits
(same size, different md5) — the v12 runner is a hand-fork of its predecessor;
exactly the in-place-mutation pattern this change retires.

**Version pins.** Tag `v12-stats-generators` on this repo marks the exact code
that generated the official v12 figures (copy of the meta-state at deployment
time). See `docs/CHEMISTRY_FIX_TODO.md` §F3.

**Do not** regenerate official artifacts from these copies without the replay
protocol: frozen denominators, timestamp normalization in diffs, scratch
outputs only (never overwrite `/data/validation/*.json` official artifacts).

## Registered additions

| file | added | purpose | deploy state |
|---|---|---|---|
| `sigstage_probe.py` | 2026-10-06 (909cf15f6) | S0 analysis: MDDBR ground truth vs **signature-stage** outputs (`data.signatures`) — pre-identification, pre-ranking complement to S5/S7; skelfp>=0.7 chem / align-identity>=0.9 seq / ion element channel; STRICT anchor gate vs `campaign_stats_v13.json`; deterministic shards to `/data/validation/sigstage/` (scratch only). Offline tests: `tests/sigstage/`. | repo-first; deployed (full run 2026-10-07) |
| `sigstage_audit.py` | 2026-10-07 (2c2fa307d) | S0×S7 audit: verbatim S7/S5 re-scoring per annotation joined to S0 rows; decomposes S0-vs-S7 split into selection / oracle / pipeline-loss / ion-denominator effects. Outputs to `/data/validation/sigstage/audit/` (scratch only). Offline tests in `tests/sigstage/`. | repo-first; deployed (audit run 2026-10-07) |
| `sigstage_casefiles.py` | 2026-10-07 | Case-list harvester for S0 open items: S0-OQ-1 no_matching_generator (generator census + stage_errors classification) and S0-OQ-2 unparseable_signature (raw SMILES + RDKit error classes, fd-level capture). Outputs to `/data/validation/sigstage/casefiles/` (scratch only). Offline tests in `tests/sigstage/`. | repo-first; NFS deploy pending |
