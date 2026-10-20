# CEITEC Deployment — Live Facts (ceitec-biodata-ns)

## Core Concept
Ground truth about what is ACTUALLY deployed, versus stale docs. Verified 2026-09-10.

## Cluster / Access
- Kubeconfig context: `kuba-cluster` (namespace-scoped user; `kubectl get nodes` forbidden = normal)
- Namespace: `ceitec-biodata-ns`; Ingress hosts: `bioid-ceitec.dyn.cloud.e-infra.cz` (SPA on /, API on /api+/files+/health+/docs+/openapi.json; /runs/* deep-links are SPA routes since ui-rework WS7), `bat3-validation.dyn.cloud.e-infra.cz`

## Components & Images (pinned; verified 2026-10-20, v3.138 wave)
| Deploy | Replicas | Image | Notes |
|---|---|---|---|
| bat3-ceitec-bat3-worker | 15 | `bat3-validation-api@sha256:053c2d8f` (tag `v3.138`) | celery pipeline workers (src_new); blast chain restored; v3.138: gemmi/tmtools/mini3di/numpy<2 + static foldseek (avx2/sse2 wrapper, curl for `databases`) |
| bat3-ceitec-bat3-ui-worker | 2 | `bat3-validation-api@sha256:053c2d8f` (tag `v3.138`) | celery pipeline workers (src_new); same v3.138 |
| bat3-ceitec-bat3-api | 1 | `bat3-validation-api@sha256:053c2d8f` (tag `v3.138`) | **pins command/args `uvicorn src_new.api.main:app --workers 4` + DATABASE_URL env** — image CMD is `main:app` (validation API), wrong app + probes 404 otherwise (V-28) |
| bat3-ceitec-bat3-web | 1 | `cerit.io/tomsko/bat3-frontend:w14` | UI w/ widened dropzone (.psf/.dcd/.data/.rst7/.mdcrd/.cif) |
| validation-api | 1 | `bat3-validation-api:v3.132` | `uvicorn main:app`; **VALIDATION_DISPATCH_ENABLED=0 — MDDBR dispatch OFF (intentional, 2026-10-09)** |
| validation-worker | **0 (was 244)** | `bat3-validation-api:v3.132` | **scaled to 0 2026-10-09 (MDDBR OFF); reverse: scale 244 + dispatch env 1** |
| validation-ui | 1 | `bat3-validation-ui:latest` | |
| validation-postgres | 1 | `postgres:15-alpine` | DB `bat3_validation` |
| bat3-redis | 1 | `redis:8-alpine` | broker+backend; orphan `bat3-ceitec-bat3-redis` scaled 0 |

NOTE (v3.138): worker/ui-worker/api specs now carry a DIGEST ref (`@sha256:053c2d8f...`) — same-tag re-push + `set image` is a spec no-op and node image caches serve OLD tag content (ate 2 foldseek-db Job attempts). Future revisions: prefer digest refs, else `rollout restart` + imageID verification (V-32 corollary).

## Storage (PVCs)
- `bat3-databases-data-ceitec` (2Ti) = REAL BLAST DBs (2.1TB: nr/, nt/, core_nt/, pdbaa/, pdbnt/, swissprot/ symlinks → `.staging/`) + **foldseek Swiss-Prot AFDB at `foldseek/swissprot*`** (v3.138, seeded 2026-10-20 by `k8s/foldseek-db-seed-job.yaml`, ~1GB; refresh = delete + re-apply the Job)
- `bat3-ceitec-bat3-databases-data` (2Ti) = EMPTY (chart bug artifact; cleanup candidate)
- `bat3-runs-data-ceitec` (500Gi) + empty twin; `validation-data-ceitec` (1Ti) = entries dir (~10.8k entry dirs)
- Mounts in bat3-worker: `/app/databases`, `/app/runs`, `/data/validation`

## Key Paths / Files
- `/data/validation/<id>/{input/,results.json}` = old layout; `entries/ <id>` + `results/<id>` = Aug-13 layout
- `/data/validation/config_shared.ini` = tuned config (nr/core_nt/nt OFF, pdbaa/swissprot ON, per-pod resolver cache)
- `/data/validation/offline_hit_k.py` = deployed scorer (repo copy: `bat3_validation/scripts/offline_hit_k.py`)
- DB: `postgresql://validation:***@validation-postgres:5432/bat3_validation` (rotate creds; currently default `validation-password-change-me`)

## Gotchas
- Ownership on NFS: dirs/files split root/1000/65534 with 0600 — analysis needs the matching pod
- Celery result keys expire ~24h → anything older is invisible to completion checks (sweeper covers)
- Deployments have `kubectl-set` drift (image, env); use `helm upgrade ... --force-conflicts` with values frozen from live
- Validation-worker TZ lags bat3-workers by 2h (celery gossip "drift" warnings are cosmetic)
- **Image CMD trap (V-28)**: one `bat3-validation-api` image serves TWO entrypoints; CMD = validation `main:app`. Ceitec api/web-facing pipeline needs `src_new.api.main:app` — pin command/args per-deployment (done for bat3-api 2026-10-10). Probes /health/live+/health/ready exist ONLY in src_new app.
- 2026-10-09 Rancher quota incident: `default-d8pcb` limits.memory mangled (admission-blocked all new pods; infosec-ticketed, user restored).
- Rancher control-plane API flaps transiently (2× during 2026-10-10 deploy; self-heals in minutes; workloads unaffected).

## Reference
- `../../deployments/ceitec-biodata/overview.md` (stale on some points)
- `../guides/safe-helm-upgrade.md`


## UI Rework Facts (2026-10-01, production)
- UI source: `ui/` (NOT deprecated `web/`). Prod guide: `docs/BIOID_UI.md`. Rollback: `bat3-frontend:legacy-pre-rework`, git tags `ui-rework-w1..w8`, `ui-production-v1`.
- nginx-frontend: SPA fallback + proxy ONLY `/api` and `/files` → `bat3-ceitec-bat3-api:8000`; old per-path proxies removed (deploy/nginx-frontend.conf).
- UI image/tag discipline: build from clean worktree only; unique tags per wave; never recycle `:latest`.
- Old UI drift tag `:ui1` retired via provenance diff (source ≡ live, FULL DOCUMENT identical).
- **Gotcha (2026-10-19, OQ-16)**: worker fleets pin `BLASTDB_MEM_MAP=0` — blast reads the NFS-mounted `/app/databases` via read() not mmap; without it an NFS stall on a mapped page = SIGBUS process death. Keep this env on any blast-capable worker fleet.
- **Reaper**: api runs zombie-run reconciler from startup (`BAT3_RUN_REAPER=0` disables, interval env `BAT3_RUN_REAPER_INTERVAL_S` default 300s). Redis leader lock `bat3:run_reaper:leader`.

### v3.137 (2026-10-19) — static renders + landing examples (UI/PNG wave)
- **`pymol-open-source==3.1.0a0` wheel NEEDS system mesa libs** (`libgl1 libegl1 libglib2.0-0`) even in batch mode — import links libGL.so.1. Wheel = only PyPI cp311 Linux build.
- **`pymol -cq -` (script on stdin) silently no-ops** — feed .pml file. New `render_png` task (after export_results) renders runs/<id>/render/{system.png,segments/<seg>.png}; mol*-style, transparent; budgets 300s/120s/900s env knobs `BAT3_RENDER_*`; >=1M atoms -> reduced system style. Never fails a run (warnings only).
- API: `GET /{run_id}/render` += system_png, segment_pngs, total_atom_count; NEW `GET /runs/examples?limit=N` (auto = newest success+png; env `BAT3_EXAMPLE_RUNS` JSON list overrides, deploy-time curation of landing cards).
- UI w14: TaskBar groups render_png under Export; MolstarViewer per-segment static fallback + 1M-atom gate (static + opt-in banner); Frontpage examples cards.
- **Same-day deploy hazard hit twice**: port-forward dies when the api deployment rolls; re-establish before API work (known pattern).
- **Same-tag redeploy trap**: `kubectl set image` to the identical string is a spec no-op — use `kubectl rollout restart` and VERIFY pod `.status.containerStatuses[0].imageID` digest (v3.137 hit this for the api re-roll to `46c71596`).
