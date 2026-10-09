# Loading Strategy: Widening MD Simulation Coverage

## Core Concept
bat3's pipeline is structure-centric: everything downstream of `load_simulation`
reads ONE MDAnalysis Universe via the `LoadedUniverse` facade — the Universe is
the unified internal format. Widening coverage therefore means adding more
**paths into a well-formed Universe**, confined to `src_new/input/` +
`src_new/loader/strategies.py` (+ normalization tables + UI whitelist).

Pattern source: mdpc's "Probe → Rank → Exhaustive attempt → Stripped recovery"
(13,257-dataset corpus; see `/loading-strategy-pattern.md`, repo root).
We port the *topology-scoped subset* — no stripped-GRO recovery, no pair-level
ranking, no recursive discovery (user uploads dedicated per-simulation files).

## Locked Decisions (2026-10-09)
- Topology-centric: trajectory files (`dcd/nc/mdcrd/xtc/trr`) are valid as
  **frame-0 coordinate sources only** — never analyzed as trajectories.
- Engine order: CHARMM → AMBER coord-sources → probe/vocab → LAMMPS (all now).
- No per-engine feature flags. Strategy-first (census deferred post-launch).
- Legacy `src/loader/` → deprecated/frozen (marked, not deleted).
- No protein gate: bat3 catalogs ALL molecules; empty-catalog = valid success.

## Target Engine Matrix
| Engine | Topology | Coordinate sources (priority) | Status |
|---|---|---|---|
| GROMACS | .tpr / .top+.gro / .itp+.gro | .gro / .trr-f0 / .xtc-f0 | exists (+trr added P2) |
| CHARMM/NAMD | .psf | .pdb → .crd → .dcd-f0 | **P1 (new)** |
| AMBER | .prmtop/.parm7 | .nc-f0/.xtc-f0 (exist) + .rst7/.inpcrd/.mdcrd-f0 | **P2 (new)** |
| PDB/mmCIF | .pdb/.cif | self | exists |
| LAMMPS | .data (topo+coords in one) | self, ordered atom_style attempts | **P4 (new)** |
| Desmond/GROMOS/TINKER | — | — | excluded (MDAnalysis lacks readers / ~0 prevalence) |

## Key Changes
- `input/models.py`: `InputKind.CHARMM`, `InputKind.LAMMPS` (free-text kinds, no DB migration).
- `input/discovery.py`: single canonical suffix table (fixes `.xtc` duplicate-key
  bug: `AMBER_XTC` overwrote `GROMACS_XTC`); CHARMM branch ordered BEFORE PDB —
  deliberate delta: `{psf,pdb}` deposits previously loaded as flat PDB.
- `loader/strategies.py`: `CHARMM_PSF_{PDB,CRD,DCD}`; `AMBER_*_{RST7,MDCRD}`;
  `GROMACS_TPR_TRR`; `LAMMPS_DATA` (ordered atom_style retries). Additive only —
  existing fallback chains unchanged.
- `loader/probe.py` (new): n_atoms via topology-free readers (`DCDReader`,
  `XTCReader`, `MDCRDReader`, `NCDFReader`); mismatch → `rejected_atoms`
  (both counts in message); unreadable → `probe_failed`.
- Outcome vocabulary (additive): `validation_failed | rejected_atoms |
  probe_failed | empty_universe | no_positions | load_exception | success`.
- Success gates: `n_atoms > 0` + positions present. NO protein gate.
- DCD as coords: `in_memory=False` + realize frame 0 (GB-scale guard); if
  downstream iterates trajectory → fallback in_memory + size cap (report-first).
- Normalization (`constants.py`/`repair.py`): CHARMM naming (HSE/HSD, TIP3,
  SOD/CLA, na names) extended only for probe-observed misses; central tables
  only (F-27 lesson — no subset copies).
- UI: `web/src/Components/Dropzone.tsx` accept list + `Frontpage.tsx` copy —
  UI already lagged backend (rejects working .prmtop/.nc/.cif today).

## Phases & Checkpoints
| Gate | Content | Verifies |
|---|---|---|
| CP0 | design record + synthetic fixtures (`tests/data/`, via `make_fixtures.py`) | fixtures parse |
| CP1 | CHARMM strategies + discovery | 2 CHARMM e2e green; `{psf,pdb}` delta reviewed |
| CP2a | spike: MDAnalysis reader coverage rst7/inpcrd/mdcrd | native vs `parmed` decision |
| CP2 | AMBER coords + probe layer | mismatch → rejected_atoms e2e; dcd-only → honest fail |
| CP3 | success gates + vocabulary | solvent-only fixture → empty-catalog success |
| CP4 | LAMMPS .data | atom_style ordering e2e |
| CP5 | legacy deprecation + UI + docs | UI build; src_new ↛ src.loader guard test |
| Final | full e2e engine matrix + replay regression (byte-identical for old formats) | release |

## Out of Scope
Pair-level/cartesian ranking (single-simulation uploads assumed), stripped-GRO
recovery, recursive/multi-dir discovery, multi-simulation deposits, Desmond,
trajectory analysis, corpus census (post-launch stats task).

## As-Built Log
_(filled per phase)_
- 2026-10-09: design record created; plan approved.
- 2026-10-09 **CP0 ✓** (`63c73bb5e`): 9 synthetic fixtures + `make_fixtures.py` generator, self-verifies 9/9.
  MDAnalysis 2.10 facts: prmtop parse needs `%FLAG TITLE` + bond/angle/dihedral flags;
  `.mdcrd` TRJReader wants no natom header + trailing box line; `.rst7`/`RESTRT` explicit format.
- 2026-10-09 **Phase 1 ✓** (`10c5240e1`, `0f755a658`, `04db2165e`, `b82faf422`): CHARMM discovery +
  3 strategies; {psf,pdb}→CHARMM precedence; 20-test battery green; e2e psf+pdb & psf+dcd green
  (frame-0 DCD universe passes unwrap/analyze/export, in_memory=False confirmed safe).
- **Normalization probe result: zero misses** — existing tables already cover CHARMM
  (HSD/HSE/HSP→H in KNOWN_RESIDUE_CODES); PROA segment flagged is_protein, segids preserved,
  no 'SYSTEM' collapse (PSF carries segids). NO constants change required (probe skipped commit 3).
- Fixture-suite note: `test_inspect_with_gromacs_files` was failing before Phase 1 too
  (asserted the unreachable `GROMACS_XTC` value shadowed by the old duplicate dict key).
- MDAnalysis 2.10 nomenclature: `TOPParser` handles AMBER PRMTOP/PARM7 — NOT broken dispatch;
  GROMACS .top uses `topology_format="ITP"` (existing behavior correct).

## Reference
- `/loading-strategy-pattern.md` (repo root) — mdpc source pattern + corpus evidence
- `code-layout.md` — three API copies; src_new = pipeline
- `../lookup/failure-mode-audit-handoff.md` — stats-tooling context
