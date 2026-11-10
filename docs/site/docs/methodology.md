# Methodology & statistics

How the validation figures are produced, and how to reproduce or audit them.
This covers the MDDBR/MDposit validation only; other studies run on the same
cluster (such as the dark-matter survey of unannotated deposits) are separate
and never mixed into these numbers.

## Ground truth

The curated annotations of each MDposit deposit — PDB IDs, UniProt
accessions, InChIKeys, ion names — harvested by
`scripts/stats/harvest_chemical_gt.py` and `scripts/stats/gt_rules.py`. For g1: PDB and
UniProt harvested 4–6 Aug 2026, InChIKeys 10 Sep 2026.

**Frozen denominators**: within one statistics era the annotation set does
not change; it grows only in a documented step between eras.

## Metric: validated hit@K (S7)

Every annotation of a scanned deposit with at least one verified hit is
compared with the deposit's **verified** hits of the matching family (PDB,
UniProt, small molecule, ion), in BioID's reported order; it counts as
validated at K if one of the first K hits describes the annotated entity
(same identifier, or sequence/structure equivalence above the threshold;
ions by element). If no same-family hit exists, a shallow global window is
searched. Annotation–hit pairs whose identities cannot be resolved score
0 and stay in the denominator, so unresolvable pairs can only understate the
result.

Always report the count next to the percentage (e.g. 6,389 of 6,736). Some
blocks are computed over deposits that ran in the current era and have at
least one hit; when such a window grows, a percentage can dip while the
count rises — that is a moving window, not a regression.

Complementary views used in the paper:

- **Equivalence**: does the top hit describe the molecule as well as the
  curated entry does (`v4_equivalence_*.json`).
- **Funnel**: molecules → signatured → with a candidate → verified, per
  molecule class.
- **Failure analysis**: for annotations not validated at rank 1, whether
  the annotation is not accessible (does not resolve in PubChem/ChEMBL),
  below threshold, or absent from the files.

## Tooling

`scripts/stats/` holds the statistics generators under version control (tag
`v12-stats-generators` marks the v12 code era); the cluster keeps execution
copies and data under `/data/validation/`.

| Tool | Purpose |
|---|---|
| `scripts/stats/campaign_stats.py` (+ `validation_similarity.py`) | throughput and S7 hit@K against ground truth |
| `scripts/stats/bag_funnel*.py` | molecule funnel with why-missing classes |
| `scripts/stats/coverability_probe.py` | small-molecule residual: candidates against an anchor era; previously published rows must not flip |
| `scripts/stats/failure_mode_audit.py` | per-type decomposition of the residual |
| `scripts/stats/assemble_stats_package*.py` | merges the above into `stats_package_vNN.{json,md}` |
| `scripts/stats/sigstage_*.py`, `molecule_export.py` | signature-stage audit and the per-molecule export |
| `scripts/stats/replay_identify_verify.py`, `scripts/stats/replay_verification.py`, `replay_gate_*.py` | identify/verify replays in shadow directories, no mutation |

The g1 figure data (`s7_full_g1_verified.json`, `fig2_panels_cd_g1*.json`,
`fig3_basis_g1.json`, …) were produced with these tools plus scripts kept
with the manuscript; they are not in this repository.

## Rules followed during campaigns

- **Ground-truth-blind tuning**: thresholds and ordering are changed on
  hit-level evidence and anomaly audits, never fitted to the ground-truth
  numbers.
- **Snapshots before mutation**: result tarballs and database dumps before
  every re-run wave; previous results kept as `*.attemptN`.
- **Replay first**: before a re-run, a replay measures the expected change and
  shows that nothing is lost.
- **Era unity**: one image for every worker during a wave; each targeted
  re-run set is chosen by a measured defect and recorded with its commit.
- **Non-regression of the residual**: previously validated rows must not
  fail in a new era; changes in either direction are reported.

## Reading the g1 figures

The current figures are on the [overview](validation.md#current-figures-campaign-g1-2026-11-07).

- PDB and UniProt are close to saturation; the remaining UniProt misses are
  mostly antibody constant regions and near-identical histone paralogs just
  under the identity threshold.
- About 226 curated small-molecule InChIKeys resolve in neither PubChem nor
  ChEMBL ("not accessible"); they bound the small-molecule rate.
- Nucleic acids (39.7 % of molecules identified) are bounded by content:
  most hitless ones are short designed oligonucleotides (≤ 25 nt) without an
  exact database record.

!!! note "History"
    The v12 (2026-10-04) and v14 (2026-10-09) campaigns used the
    `validation-api` queue path and earlier scoring rules (v12: hit@10 over
    all candidates). Their packages (`stats_package_v12.*`,
    `campaign_stats_v14.json`) remain on the validation volume.
