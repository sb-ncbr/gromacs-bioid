# N1 fixtures — provenance and trim verification

Real campaign inputs copied from NFS (`/data/validation/{eid}/input`) on 2026-10-03
for the N1 fix wave (see `.tmp/PLAN_N1_FIX_WAVE.md`). No mock/synthetic data:
every gate in the wave must pass on these files (user directive).

## Entries and roles

| eid | system | why included |
|---|---|---|
| 4653 | DNA duplex, 17 rc (585 atoms), `sigtask=success` | core NA generation fixture; pdb_nucleic/fasta known-good |
| 1682 | merged duplex SYSTEM 296 rc + splitter strands `SYSTEM__v1/v2` (147 nt), blast 374 hits | Layer B design target + blast positive control |
| 1602 | 16-mer palindrome `CGCGAAAATTTTCGCG`, hitless | Layer C short-oligo case 1 |
| 1920 | tandem-repeat 18-mer pair (`SYSTEM__v1/v2`), hitless | Layer C short-oligo case 2 |
| 1549 | 29 nt, blast hit (3) | medium-length gate-positive control |
| 1553 | 26 nt, blast hit (1) | medium-length gate-positive control |
| 1567 | 112-rc merged duplex, no fasta in campaign | Layer B target class (101-500 no-sequence) |
| 4725 | single-residue `DTX`, chem-identity hits | resname/chem identity control |
| 1089 | protein 102 rc (1640 atoms) | protein parity control (INV-1) |
| 6250 | small chem molecule (75 atoms) | chem parity control (INV-2) |

## Trim policy (size)

`trajectory.xtc` reduced to frame 0 via MDAnalysis; `.trajectory.xtc_offsets.npz`
removed (loader must not see stale cache). Total set: 591 MB -> 11 MB.

## Empirical trim verification (user: no blind trust)

For every trimmed entry the wave's probe machinery (load_simulation -> repair ->
LoadedUniverse -> FragmentStore -> build_signature_snapshot ->
_generate_signatures_worker, v3.124 code) was executed on (a) the TRIMMED
fixture copy and (b) the UNTOUCHED campaign input dir; per-segment signature
payload SHA-256 maps compared: **parity = True for all 10 entries**
(log: `/data/validation/logs/`-era output captured in W0 run; script:
`/data/validation/n1_fixtures_trim.py` / `.tmp/n1_fixtures_trim.py`).

Any future fixture change REQUIRES re-running the same verification.

## Config

`config_shared.ini` = byte copy of the campaign frame config
(`/data/validation/config_shared.ini`, 2026-10-03). Note its
`deployment_file_url` points at the pre-fix host; the A1 fix tests
override via env per plan W2.

## Golden harvest + G0 (2026-10-03)
- Harvest: `.tmp/n1_golden_harvest.py` (pod, /app code v3.124, CWD=/app). 20 files
  in `golden/` (sig for all 10; ident for the 10 IDENT controls).
- G0 gate: `.tmp/n1_run_gates.py` (= `tests/n1_wave/run_gates.py`), full 10-fixture
  run on unchanged code: **GATE_RESULT: GREEN (10/10 PASS)**.
- Spot checks: 1682 SYSTEM has no fasta (Layer B reproduces), v1/v2 have fasta;
  1549 blast 3 hits; 1920 all-zero (Layer C reproduces); 4725 2-seg chem identity.

## W4 multi-record FASTA pre-test (empirical, real resolver + pdbnt)
Payload `>c1\n147mer\n>c2\n147mer` through BLASTResolverPDBNT._sanitize_sequence
-> mangled to ONE 303nt composite ('>' and '\n' -> 'N'). blastn on composite
recovered the same 42 subjects as each strand alone HERE (complementary duplex
special case) — but evalue/query-length semantics blur, N-junction artifacts
possible, and per-component provenance is lost. DECISION: W4 emits the LONGEST
linear component deterministically (b1); no resolver change; residual
(strand-loss in asymmetric assemblies) measured and reported at W7.
