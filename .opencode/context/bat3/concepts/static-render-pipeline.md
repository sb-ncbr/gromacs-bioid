<!-- Context: concepts/static-render-pipeline | Priority: high | Version: 1.0 | Updated: 2026-10-19 -->
# Static Render Pipeline (v3.137): worker PNGs, Mol* fallback, landing examples

The full path of a rendered preview: worker task → on-disk contract → API →
UI consumers. Sister records: V-32 in errors/common-issues.md (build/deploy
discipline), status.md 10-19b..d.

## 1. Worker: render_png task (src_new/render/png_renderer.py)
- Runs AFTER export_results (registered last in build_load_and_export_tasks;
  TaskBar groups it under the existing "Export results" stage — intentionally
  NO new taskbar dot). Task id `render_png` also in error-catalog's export group.
- Inputs: exported mmcifs at run root (system.mmcif, <seg>.mmcif) so the
  static image equals what Mol* would show.
- Outputs: runs/<id>/render/system.png + render/segments/<seg>.png; paths
  recorded to data.render.system_png / data.render.segments.<seg>.png (same
  convention + relativization as the mmcif render paths).
- Style: Mol* MVS-like — cartoon polymer, sticks ligands (organic & not
  polymer & not solvent), spheres for salt ions, chain colors, transparent
  background, 1600×1200 ray. ≥1M total atoms (data.simulation/n_atoms) →
  reduced system style (cartoon only, 1200×900).
- Budgets (env BAT3_RENDER_*: _TOTAL_BUDGET_S=900, _SYSTEM_TIMEOUT_S=300,
  _SEGMENT_TIMEOUT_S=120, _REDUCED_AT_ATOMS=1000000, _PYMOL_BIN): per-image
  timeout + total task budget; failures/timeouts → warnings only; missing
  pymol/mmcifs/facade → warning + success. A RENDER PROBLEM CAN NEVER FAIL
  A RUN. Pure core (plan_renders/build_pymol_script/summarize) + thin IO
  shell; 25 tests with a stub pymol binary.
- PyMOL (pymol-open-source==3.1.0a0 wheel): needs libgl1/libegl1/libglib2.0-0
  even in batch (links libGL.so.1 at import); `pymol -cq -` IGNORES stdin
  scripts — write a .pml temp file (both proven by container gate 10-19).

## 2. Degenerate-input class (A003ZR family)
Whole-family input corruption: system.mmcif byte-size-identical across runs
(6 221 075 B), coordinates compressed to a few Å³ (residue-1 atoms ~6 Å);
pymol hangs INSIDE load (spatial hashing explosion) — catchable only by the
per-image timeout (retried ray=0 also hangs; load is the choke point, NOT the
ray). These were also the 10-13 SIGBUS-zombie producers. Policy is CORRECT
as shipped: warning + missing PNG for those runs.

## 3. API (v3.137)
- GET /api/v1/runs/{id}/render += system_png, segment_pngs (dict), 
  total_atom_count (None for pre-wave runs; UI treats null gracefully).
- GET /api/v1/runs/examples?limit=N (declared BEFORE /{run_id} — route order
  matters; Starlette inserts match in definition order): newest *successful*
  runs with render/system.png on disk; name parse "Title>Description" (no ">"
  → description null); explicit curation override env BAT3_EXAMPLE_RUNS =
  JSON run-id list (deploy-time, no code change; documented in docstring).
- images ride the existing /files/<run>/... static mount — zero new plumbing.

## 4. UI consumers (w14)
- MolstarViewer modes still loading|interactive|static|unavailable; NEW:
  per-segment static png priority (utils/static-render.ts pure helpers,
  7 vitest cases: segment png → system png → legacy render/system.png
  fallback; gate boundary at exactly 1M + null tolerance); atom gate
  ATOM_INTERACTIVE_LIMIT=1_000_000 → default static + amber banner with
  exact counts + "Load interactive view anyway" (forceInteractive state,
  opt-in).
- Frontpage "Example analyses": 3 cards (image/title/desc/link) from
  /runs/examples; silently absent on empty/error (frontpage never breaks).
- types.ts is OPENAPI-BASELINE-generated; additive fields use the local
  delta-interface pattern (RenderPathsV37 in hooks.ts per QueueState).

## 5. Deploy/build discipline (hard-won this wave)
- V-32: build the image ONCE after the wave's LAST commit; content gate must
  probe the NEWEST feature (e.g. grep -c get_run_examples), not just binaries.
- Same-tag re-deploy: `kubectl set image` to an identical string is a SPEC
  NO-OP → `kubectl rollout restart` then VERIFY pod imageID digest.
- port-forward dies on api rollout; always re-establish + curl /health.
- e2e example seeding: rerun healthy past runs; CHECK geometry sanity first
  (file size + a coord line) for non-A003ZR lineage.

## State at close (2026-10-19)
Examples live: POPC 4ef9a8cc, OSF q4m9w 2abd8adf (209 838 atoms), A001UD
9f4ed38a. Workers/ui on first v3.137 digest, api on 46c71596 (API-only diff;
next wave unifies). Descriptions all null until runs are named Title>Desc.
