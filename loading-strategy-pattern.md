# Simulation-Loading Strategy: Probe → Rank → Exhaustive Attempt → Stripped Recovery

## Core Concept
Turn a messy deposited directory (multiple simulations, ambiguous names, mixed engines) into **exactly one loaded MDAnalysis Universe** — readable, ≥1 frame, protein present — by probing files, generating engine-compatible topology×trajectory candidates, ranking them deterministically, and attempting them **exhaustively** until first success. Atom-count mismatches (protein-only trajectory vs solvated topology) are recovered by writing an exact-count **stripped GRO**. Proven over a 13,257-dataset, 5-engine corpus (mdpc).

## Canonical Suffix Sets
```python
TOPOLOGY_EXTS   = {".tpr": gromacs, ".gro": gromacs,
                   ".prmtop": amber, ".parm7": amber,
                   ".psf": charmm, ".pdb": generic}
TRAJECTORY_EXTS = {".xtc": gromacs, ".trr": gromacs,
                   ".mdcrd": amber, ".nc": amber,
                   ".dcd": charmm}
```
Trajectory headers (`n_atoms`, `n_frames`) are probed with the dedicated
MDAnalysis **readers without a topology** (`XTCReader`, `TRRReader`,
`DCDReader`, `MDCRDReader`, `NCDFReader`) — stable across versions,
**deliberately no error-message parsing**. Topology atom counts are NOT
probed; parsing is deferred to the executor's Universe cache.
Unreadable/zero-frame files are still recorded (`rejected_probe` + reason).

## Engine Compatibility Matrix (first match wins)
| row | topology | trajectory | engine |
|---|---|---|---|
| 1 | {.tpr, .gro} | {.xtc, .trr} | gromacs |
| 2 | {.prmtop, .parm7} | {.mdcrd, .nc} | amber |
| 3 | {.psf, .pdb} | {.dcd} | charmm/namd |
| generic | .pdb | **any** recognized trajectory | trajectory's engine (lowest priority) |

## Deterministic Ranking
1. **tier 0** (topology and trajectory in same directory) **before tier 1** (cross-dir);
2. within a tier: engine-specific topology beats `.pdb`;
3. then lexicographic (topology path, trajectory path).
Same input → same candidate order, always.

## Attempt Executor (per ranked candidate, stop at first failure)
1. **Topology parse** via per-path Universe cache (parse once ever);
2. **Atom-count relation** (the corpus's defining quirk):
   - `traj_n == topo_n` (or header count unavailable) → load topology directly;
   - `topo_n > traj_n` AND a canonical selection matches exactly → **stripped-GRO recovery**;
   - `traj_n > topo_n` → `rejected_atoms` (trajectory holds MORE atoms than topology — hopeless);
3. **Universe build** (failure → `load_failed`);
4. **≥1 frame** with first AND last frames readable (failure → `no_frames`);
5. **protein** selection nonempty (failure → `no_protein`) → **SUCCESS**,
   universe positioned on frame 0.

Zero candidates → raise immediately with the probe summary. Exhaustion →
`SimulationLoadError` whose message IS the full attempt table
(pair + outcome + why, one line each). Outcome vocabulary:
`rejected_probe | rejected_atoms | topology_unloadable | load_failed |
no_frames | no_protein | success`.

## Stripped-GRO Recovery (trjconv-style corpora)
```python
_STRIPPED_SELECTIONS = ("protein",
                        "not resname SOL HOH WAT TIP3 TIP3P SPC SPCE OPC")
```
First selection whose atom count **equals the trajectory header exactly** is
written to `<topo.stem>__stripped-<traj_n>.gro` (atom order follows the
original topology, mirroring `gmx trjconv`). GRO carries **no segids** —
downstream protein segments collapse to `'SYSTEM'`; code must not rely on
segid presence after recovery. This path is the **norm**, not an anomaly:
protein-only XTC + solvated TPR is how most stripped corpora are shipped.

## Measured Corpus Evidence (13,257 datasets, 337k files, mdfind)

**Trajectory formats in the wild** (files / datasets):
| format | files | datasets | engine |
|---|---|---|---|
| .xtc | 43,112 | 12,391 | gromacs |
| .dcd | 3,849 | 1,907 | charmm |
| .nc | 505 | 416 | amber |
| .trr | 911 | 166 | gromacs |
| .mdcrd | 14 | 3 | amber |

**Loadable topologies present** (datasets): .tpr 5,762 · .prmtop/.parm7 2,609 · .psf 1,647 · structure-only .gro 6,614 · .pdb 9,437.

**Engine mix**: gromacs 81.6% · namd/charmm 14.4% · amber 3.4% · desmond ~0% · pdb-only/unclassified 0.7%.

**Loadability by deposit shape** (pipeline outcomes, full population):
| file-group combination | datasets | loaded+analyzed | share |
|---|---|---|---|
| checkpoint+run_input+structure+topology+trajectory | 4,608 | 2,001 | 43% |
| structure+topology+trajectory | 5,163 | 1,784 | 35% |
| structure+trajectory (no topology) | 1,557 | 127 | 8% |
| trajectory only | 407 | 16 | 4% |

→ the matrix and .psf/.tpr requirement are not pedantry: deposits lacking an
engine topology fail >90% of the time. Dominant exact failure classes on the
cluster: `pipeline_error` = "no engine-compatible pair" (421; figshare
DCD-only deposits), `no_protein`, `no_simulation_files` (15), plus
`rejected_atoms` where a `.pdb` declares fewer atoms than the trajectory.

## Porting Checklist
- [ ] Copy the resolver: probe (`_READER_BY_SUFFIX` header trick) → matrix → ranking → executor (~450 lines in `md_cluster/loading.py`, MDAnalysis-only dependency)
- [ ] Keep the stripped-GRO recovery AND the "GRO collapses segids" caveat in downstream selection code
- [ ] Emit the same outcome vocabulary; make exhaustion errors carry the full attempt table (our primary debugging tool across 13k datasets)
- [ ] Write provenance (`input_discovery`: chosen pair + all attempts + probes) into every result — auditability is what kept a 400-job batch debuggable
- [ ] Regression tests F1–F4 in `tests/test_loading.py` cover: figshare DCD-only, trajectory-greater-than-topology, stripped recovery, no-protein

## Verification
```bash
python -m md_cluster <entry_dir> --stride 10 --no-pymol
# loading exhaustion prints the ranked attempt table with outcomes
```

## Reference
- Implementation: `md_cluster/loading.py` (this repo, ~1,270 lines incl. legacy API)
- Concept note (internal of-record): `.opencode/context/mdpc/concepts/loading-strategy.md`
- Deep contract: `.opencode/context/mdpc/.archive/mdpc-1/v3-contracts.md`
- Corpus evidence: `reports/corpus/corpus_stats.json`, `reports/corpus/entry_file_matrix.csv`
- Companion transport doc: `docs/download-resolution-pattern.md`
