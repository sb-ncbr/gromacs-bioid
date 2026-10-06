# Methodology & statistics

How campaign-wide trust numbers are produced, and how to reproduce/audit them.

## Ground truth (GT)

MDDBR annotations per simulation entry (PDB IDs, UniProt, InChIKeys,
ion names...), harvested by `scripts/harvest_chemical_gt.py` /
`gt_rules.py` into frozen GT sets at the start of a statistics era.
**Frozen denominator rule**: an era's GT annotation/attempted counts never
change inside the era (the InChIKey window 5,784 annotations / 5,768 attempted
was held exact from v11 to v12); growth waves advance GT deliberately, in a
documented step.

## Metric: similarity hit@K

Per entry, per GT annotation: does any pipeline hit (merged over the entry's
fragments) cover this annotation within the top-K candidates?
The family-aware scorer checks each annotation against **its own identifier
family first** (a same-family candidate anywhere in the list counts), falling
back to a shallow global window (depth 25) only when no same-family candidate
exists. Raw row = (entry, annotation, hit@1/5/10, matched identifier...).

Reported in two forms, always together:

- **raw** — e.g. 5,358/5,768 verified hits @10
- **normalized (pct)** — e.g. 92.9%

## The S7 run-window caveat (V-23)

Some blocks (chemical verified percentages, ion counts) are computed over
**entries that ran in the current era and have ≥1 hit** — denominators grow
legitimately when requeue waves add entries. Always present absolute numbers
next to percentages when comparing eras; a pct dip with an abs rise (e.g.
pdb @10 99.6%→99.5% while 11,035→11,130) usually means the window moved, not
regression.

## Tooling (figure-data pipeline)

Official generators (run against NFS results):

| Tool | Purpose |
|---|---|
| `campaign_stats.py` (also `scripts/` in repo, md5-synced) | throughput + S7 hit@K vs GT (`--full --sim`) |
| `bag_funnel.py` / `bag_funnel_v12_run.py` | funnel: entries → molecules → hits → verified, with why-missing classes |
| `coverability_probe.py` | chem residual scoring: regen candidates vs **anchor** era; hard gate that previously-published rows never flip (`PROBE_ANCHOR_JSON` selects the anchor, e.g. v11 after the v12 wave) |
| `assemble_stats_package(_v12).py` | merges the above into `stats_package_vNN.{json,md}` |
| `n1_*.py` | N1-wave audit/gates/replay harnesses |

Figure artifacts land on NFS (`/data/validation/stats_package_v12.*`,
`campaign_stats_v12.json`, `bag_funnel_v12.json`, `coverability_probe.json`,
`residual_failing_rows_v8.jsonl`, `n1_*.json`).

!!! success "Tooling provenance (F-28, resolved 2026-10-05)"
    Statistics/wave tooling is now under version control at
    **`scripts/stats/`** (34 byte-identical md5-verified copies of the NFS set
    + adopted audit tools; tag **`v12-stats-generators`** marks the exact
    code era). Gold e2e: the repo-copy `assemble_stats_package_v12.py`
    regenerates the official `stats_package_v12.json/.md` byte-identically
    (timestamp-normalized). Repo is edit-first; NFS keeps execution copies
    and data. `bag_funnel.py`/`bag_funnel_v12_run.py` are a known hand-fork
    pair, pinned as-is.

## Guardrails in force (campaign rules)

- **GT-blind tuning**: thresholds/order changes are validated on hit-level
  evidence and anomaly audits, never fitted against GT numbers directly.
- **Snapshots before mutation**: prerequeue result tarballs + PG dumps exist
  under `/data/validation/backups/` for every wave.
- **Replay-first**: before any requeue, the W7 replay harness
  (`n1_w7_replay.py`: identify+verify in shadow roots, zero mutation) measures
  expected deltas and proves *nothing is lost*.
- **Era unity**: a wave's requeued entries must be processed by a single image
  era (fleet-wide canary → rollout order: api → validation workers → ceitec
  workers).
- **Coverability non-regression**: the chem residual set (410 rows) is a hard
  gate at every statistics era — new pairs allowed, previously-failing rows
  must not re-fail... and must not be silently "fixed" either (both directions
  are reported).

## Interpreting headline numbers (v12)

- InChIKey @10 92.9% exact — frozen window, comparable across eras.
- UniProt/PDB ≈ 98–99.5% — the structural class channels (BLAST/AlphaFind) are
  saturated; remaining misses are content-absence classes.
- Nucleic 19.75% — bounded by verifiable content: short designed oligos have no
  exact-matchable deposit (e-value floor physics) and mixed assemblies lack
  RCSB coverage (see identifiers page); strata detail lives in
  `n1_postwave_rate.json`.
