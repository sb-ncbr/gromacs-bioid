# BioID UI Rework — Master Plan (v1, 2026-10-01)

Thinking/planning/QA/copy: **kimi-k3** · Implementation: **qwen3.8-27b** (precise: scaffold, API, nginx) · **qwen3.8-flash-next** (fast: UI components)

## Locked user decisions
- Rewrite `./ui` from scratch (backup: git tag `ui-legacy-pre-rework`). No parallel deployment — replace live in waves.
- Design system: `@e-infra/design-system@0.1.9` PINNED, custom 3-color theme keeping BioID green `#2E7D32`.
- Right results panel = **verification hits only**, done smarter. Browser-side human names WITH truncation strategy (names up to 300+ chars).
- API changes **additive-only**. Queue position in scope. Mol* PNG fallback in scope (timeout detection). "Structural data not available" gray state in scope.
- Visual pass by user after every wave; deployed directly to `ceitec-biodata-ns` (internal tool, downtime OK).
- Audience: biologists — simple, sleek, readable, no raw internals.

## Reference validation runs (live)
| Run | Kind | Use |
|---|---|---|
| a524e039-a890-4dc7-9b09-cf4317395d17 | pdb, 4 seg (protein/small/2×nucleic) | main fixture; degraded resolvers case |
| bce4a0fa-0a80-4ad0-ac33-04e78407711a | gromacs MDR00042100 | gromacs + verification data |
| 787bb198-bcf2-405e-af61-ffbc1931fda4 | gromacs POPC | lipid iconography |
| 4964c437-7d7d-43c9-af65-0af5d74d ea11 | gromacs FAILED | error UX validation |

## Workstreams & tasks

### WS0 Foundations (Planner, kimi) — status: mostly done
- [x] UI backup (tag + tarball)
- [x] Live openapi baseline → contracts/openapi-live-baseline.json (43 paths)
- [x] Fixtures (30 files) → fixtures/
- [x] WS5: worker error/warning catalog → errors/error-catalog.json (16 codes)
- [x] WS5: molecule-type vocabulary → 8 types incl. water/unknown

### WS1 Scaffold & shell (Coder A, qwen3.8-27b) — GATE for Coder B integration
- [ ] New ui: Vite + React 19 + TS strict, Tailwind v4, @e-infra/design-system@0.1.9 pinned
- [ ] Custom theme (green #2E7D32 primary), lucide icons
- [ ] TanStack Query + react-router v7; deep-linkable state `/runs/:id?segment=X&tab=Y`
- [ ] API client: hand-rolled typed fetch wrapper + types generated from openapi-typescript (npm script, re-runnable)
- [ ] Shell: Header (BioID title, real links — no docs link (none exist yet), remove google.com), Footer (ELIXIR copy preserved), Layout
- [ ] vitest + eslint + prettier baseline
- [ ] Dockerfile.frontend + deploy/nginx-frontend.conf: proxy `/api` → api:8000
- GATE: `npm run build` clean, DS components render, deploy smoke OK

### WS2 Frontpage (Coder A)
- [ ] Hero copy simplified (biologist tone, concise), supported formats
- [ ] Dropzone (react-dropzone) + file table + remove
- [ ] Run name field; Fast Mode switch; Advanced config dialog (port generic editor, DS-styled; presets deferred v1.1)
- [ ] Recent Annotations: **IP-bound** (needs WS6-A1), status badges, per-run **Rerun** (WS6-A1), delete via DS AlertDialog, run name shown. Re-run-all REMOVED.
- [ ] Empty states & skeletons
- GATE: live submit of real run; recents show it; rerun re-queues

### WS3 Results core (Coder B, flash-next; Mol* integration 27b)
- [ ] TaskBar: 4-state steps (ok/info/warning/failed), precise per-step info (task summaries as chips), click → Warnings tab anchor. Canonical 5 steps w/ member-task tooltips; fallback to raw task list when mapping unknown.
- [ ] Run title = run_name (fallback short id); queued state shows **queue position** chip (WS6-A2)
- [ ] MoleculeSelector: type icons (protein, nucleic, lipid, carbohydrate, **water/solvent own category**, ion, small molecule, other), segment label + counts
- [ ] ResultsPanel: `Segment: X` title; type chip; atoms/residues; best-confidence bar; **verification-only table**: ✓/✗ (+ⓘ rejection) · human name (browser lookup, truncated w/ tooltip; cache) · identifier w/ FIXED link · type/db (muted) · similarity · confidence; order = API stored order VERBATIM (fidelity-first, backend-owned; NO client re-sort; ✓/✗ = column only)
- [ ] Mol*: single plugin instance; per-segment MVS swap; 25s timeout → PNG fallback `/files/{id}/render/system.png`; no mmcif → gray "Structural data not available"
- [ ] Link fixes (mirror API fixes): PDB strip chain suffix `_A`; CHEMBL ensure `CHEMBL` prefix; verified clickable for all hit types
- GATE: no polling storms (status-driven refetch only); 4 reference runs reviewed visually

### WS4 Tabs (Coder B, flash-next)
- [ ] Overview: run meta + task durations only (no identifiers)
- [ ] Input & Files (merged): loading strategy compact card; **input files highlighted**; key outputs row (results.json highlighted JSON, logs normal/debug, config.ini) as clean icon links (no chunky buttons); full file list collapsible
- [ ] Signatures: segment select; grouped buttons (Sequence/Structure/Chemical/Name/Fingerprint) with HUMAN names; attempted-but-failed = dashed disabled w/ reason ⓘ; dialog w/ blurred backdrop: explainer line, mono preview + copy, download (ext map)
- [ ] Identifiers: segment select; clean table (hide N/A metric cols for non-BLAST hits); ⓘ provenance hover; attempted/failed resolvers chips block
- [ ] Verification: full table + score-breakdown hover (weights resolver 0.4 / similarity 0.4 / annotation 0.2); rejection tooltips; working links
- [ ] Warnings & Errors: grouped by pipeline stage, catalog-driven human copy (title → what → action); anchor from TaskBar
- [ ] Results export: JSON + TSV download (client-side from verification data)
- GATE: fixture-driven vitest for utils (name maps, link builders, formatters, sort/merge); visual pass on 4 runs

### WS5 Error catalog (Planner, kimi) — parallel, read-only
- [ ] Inventory all worker warning/error codes (pipeline_steps, executor, task framework)
- [ ] Classify: stage × severity × user-actionable; map raw codes → human copy ("file is not a database" → "structure search unavailable")
- [ ] Molecule-type vocabulary → icon map source of truth
- [ ] Output: errors/error-catalog.json + warnings copy deck → feeds WS4

### WS6 API additive (Coder A, qwen3.8-27b) — small waves, contract-gated
- [ ] A0 Provenance: build repo image, diff `/openapi.json` vs baseline (reassurance before touching)
- [ ] A1 `include_router(..., prefix="/api/v1")` alias + `creator_ip` capture on POST /runs + `GET /runs?mine=1` IP filter + `POST /runs/{run_id}/rerun`
- [ ] A2 queue position: `GET /runs/{run_id}/queue` → {state, position?, total?} (celery inspect on validation.ui.celery or pending-run ordering; simple impl)
- [ ] A3 canonical `database_url` fixes (PDB `_A` strip, CHEMBL prefix) — fix values, keep response shape
- GATE per step: openapi diff vs baseline shows ONLY additions; old paths untouched; curl matrix on live

### WS7 nginx/ingress (Coder A w/ Planner verify)
- [ ] nginx-frontend.conf: SPA fallback EXCEPT `/api` (proxied)
- [ ] bat3-chart/templates/ingress.yaml: only `/api` → api svc; `/` → web svc
- GATE: `curl /runs/bce4a0fa...` Accept: text/html → HTML; `curl /api/v1/runs` → JSON. Deep-link bug dead.

### WS8 Mol* robustness — merged into WS3 tasks above

### WS9 Cutover & polish
- [ ] Dead-code purge inherent (new codebase); remove rxjs/mui deps
- [ ] Perf pass (bundle: molstar manual chunk kept), a11y basics
- [ ] Final 4-run matrix + user acceptance; tag `ui-production-v1`

## Risks / watchlist
- Live API image drift (`bat3-api:ui1`) → A0 provenance gate mandatory
- Worker molecule-type vocabulary unknown until WS5 (icon map: ship with fallback icon)
- IP-bound recents: shared-IP collab environments — accepted tradeoff (user decision)
- External name lookups (browser→PubChem/ChEMBL/ChEBI/RCSB): CORS/availability — graceful fallback to raw id; >300-char names truncated, full in tooltip

## Decision log
- 2026-10-01: No docs link anywhere (docs don't exist yet — independent way-later TODO).
- 2026-10-01: Error catalog v1 landed (errors/error-catalog.json): 9 fail/warn + executor codes, 5 stage groups, molecule types confirmed incl. water & unknown. New TaskBar grouping REPLACES legacy keyword matching (repair/unwrap/analyze previously fell into "Unknown" — legacy bug).

- 2026-10-01: Backend relay (verification/manager.py worker): hits will be stored fidelity-first. UI MUST render stored order verbatim (no client re-sort) — realizes the chemical-fidelity UX win; re-sorting by confidence = zero-benefit. Verified flag demoted to display-only column. Contract: backend owns ranking, UI owns presentation. Ask: keep ordering deterministic (documented tie-break).
