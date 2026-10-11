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
- 2026-10-09 **CP2a ✓ (early, via fixtures)**: .rst7→`format="RESTRT"`, .mdcrd→TRJReader (no natom
  header line, box line required), prmtop→amber-aware TOPParser; ALL native, **no parmed needed**.
- 2026-10-09 **CP2 ✓** (`934ca1394`, `c855a7936`, `85db70c2e`): probe layer (mdpc port, topology-free
  readers; `.mdcrd` unprobed by design — TRJReader needs n_atoms upfront → defers to build);
  AMBER rst7/mdcrd + GROMACS trr strategies; AMBER validation gating; probe wired into
  `load_simulation`; `rejected_atoms` e2e (psf 36 vs dcd 30) records both counts; `_record_attempts`
  dedup. Suite rows: 81/81.
- 2026-10-09 **CP3 ✓** (`4500ccd59`, `a04944fc6`): post-build gates (empty_universe, no_positions —
  NoDataError mapped); NO protein gate (empty-catalog = valid success, verified by solvent-only e2e:
  pipeline succeeds, molecules catalog = water only). Note: 0-atom TEXT structures fail at parse time
  (MDAnalysis IndexError → load_exception); gates guard binary/strategy edge paths.
- 2026-10-09 **CP4 ✓** (`926985462`, `83bf9fc84`, `70696faea`): LAMMPS `.data` (file-declared
  atom_style first, then full/molecular/charge/atomic retries, all failures compiled in message).
  Predicted consequence HIT: resname-less universes crashed `extract_molecule_instance` /
  `_build_whole_system_instance` (NoDataError) → guarded to UNK placeholders; catalog then carries
  no resname-driven identifications (valid semantic). Suite: 93/93.
- 2026-10-09 **CP5 ✓** (`6d96791b1`, `0fd7db606`, `cd3eb30b7`, `bddef5a4b`): legacy `src/loader`
  frozen (README + module headers + src_new↛src.loader guard test); production path verified
  (celery→src_new.api.tasks only). UI whitelist + per-engine copy (was behind backend); tsc clean.
  **Live prod bug found & fixed**: gemmi ≥0.7 dropped `num_models()` — MMCIF strategy crashed on .cif;
  compat shim added, mmcif_single fixture + e2e cover it.
- 2026-10-09 **Final gate ✓**: engine-matrix invocation 97/97 (input + all loader suites + guards).

## Release Notes (2026-10)
1. **Rollout**: ui-worker + api images rebuild picks up loader + UI copy together (UI parity was the
   load-bearing risk); no new pip deps (gemmi/MDAnalysis already shipped; no parmed).
2. **Environment quirk discovered**: this MDAnalysis install can't read coordinates from the fixture
   TPRs (`No coordinate reader found ... Skipping`) — GROMACS_TPR now fails the `no_positions` gate
   and correctly routes to `_GRO` alternates or fails honestly. Previously it silently produced
   coordinate-less universes (root cause of pre-existing `TestFacade14976a::test_segment_flags`
   failure, which now skips instead of crashing via `_load_and_facade`'s guard).
3. **Manual release gate (owner)**: replay regression — run `scripts/replay_*.py` slice of known-good
   deposits; signatures for pre-existing formats must be byte-identical (additive-change guarantee).
4. **Deferred**: pair-level ranking, recursion/multi-dir, Desmond, corpus census (stats task),
   .mdcrd probing (TRJReader n_atoms circularity), dcd-only deposits (honest failure by design).

## Deploy State (2026-10-10, FINAL — deployed 4/4)
- Images: `bat3-validation-api:v3.133` + `bat3-frontend:w13` built+pushed (digests in
  pickup/journal; ui-worker canary green).
- **Gate 1 (replay) PASS 5/5** — `/data/validation/replay_gate/` artifacts;
  v3.132≡v3.133 byte-identical on deposits; sep-17 drift = pre-existing interim changes.
- Rolled out: `bat3-ui-worker`(2) + `bat3-ceitec-bat3-worker`(15) + `bat3-ceitec-bat3-api`(1)
  all v3.133; `bat3-ceitec-bat3-web`(1) w13 (dropzone accept incl. .psf/.dcd/.data/.rst7/.mdcrd),
  deployments green.
- **E2E gates (live, POST /api/v1/runs → ui-worker)**: charmm_psf_pdb → input_kind=charmm,
  strategy=charmm_psf_pdb, SUCCESS; solvent pdb baseline → input_kind=pdb, SUCCESS
  (no regression). amber prmtop+mdcrd AND prmtop+rst7 → loading stack green
  (input_kind=amber, correct strategies, unwrap warning only) but generate_signatures
  spins 1 core ≥20 min on the synthetic unnamed-residue fixtures → both cancelled;
  **OQ-15 opened** (not a regression: amber-coords input is new in v3.133).
- **Root-cause correction to earlier PENDING note**: api crashloop had TWO faults:
  (a) DATABASE_URL env absent (F-06 creds-out-of-repo default localhost:5432) AND
  (b) v3.133 image bakes CMD `uvicorn main:app` (validation API, only /health) while
  ceitec api requires `uvicorn src_new.api.main:app` (probes /health/live+/health/ready);
  v3.132 image had the src_new CMD. Fixed at ops level: deployment now pins
  command/args (src_new, --workers 4) + DATABASE_URL env. Ops lesson V-28.
- Worker/ui-worker DATABASE_URL: intentionally left absent — full successful pipelines
  (charmm+pdb E2E incl. export) run healthy without it; api is the only DB initializer.
- Ops: `validation-worker` scaled 244→0 + VALIDATION_DISPATCH_ENABLED=0 (MDDBR OFF,
  intentional; reverse = scale 244 + env 1). Rancher control-plane API flapped twice
  during deploy (transient e-infra side, self-healed in 2-10 min; workloads unaffected).
  Rancher quota `default-d8pcb` was re-mangled 10-09 (infra ticketed).

## Reference
- `/loading-strategy-pattern.md` (repo root) — mdpc source pattern + corpus evidence
- `code-layout.md` — three API copies; src_new = pipeline
- `../lookup/failure-mode-audit-handoff.md` — stats-tooling context
