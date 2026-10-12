# CEITEC Deployment — Live Facts (ceitec-biodata-ns)

## Core Concept
Ground truth about what is ACTUALLY deployed, versus stale docs. Verified 2026-09-10.

## Cluster / Access
- Kubeconfig context: `kuba-cluster` (namespace-scoped user; `kubectl get nodes` forbidden = normal)
- Namespace: `ceitec-biodata-ns`; Ingress hosts: `bioid-ceitec.dyn.cloud.e-infra.cz` (SPA on /, API on /api+/files+/health+/docs+/openapi.json; /runs/* deep-links are SPA routes since ui-rework WS7), `bat3-validation.dyn.cloud.e-infra.cz`

## Components & Images (pinned; verified 2026-10-12)
| Deploy | Replicas | Image | Notes |
|---|---|---|---|
| bat3-ceitec-bat3-worker | 15 | `cerit.io/tomsko/bat3-validation-api:v3.135` | celery pipeline workers (src_new); NO DATABASE_URL needed; blast chain restored (v3.134+); element ground truth live |
| bat3-ceitec-bat3-ui-worker | 2 | `cerit.io/tomsko/bat3-validation-api:v3.135` | celery pipeline workers (src_new); NO DATABASE_URL needed; same v3.135 |
| bat3-ceitec-bat3-api | 1 | `cerit.io/tomsko/bat3-validation-api:v3.134` | **pins command/args `uvicorn src_new.api.main:app --workers 4` + DATABASE_URL env** — image CMD is `main:app` (validation API), wrong app + probes 404 otherwise (V-28); v3.134 ships ground_truth_override passthrough, api unchanged in v3.135 |
| bat3-ceitec-bat3-web | 1 | `cerit.io/tomsko/bat3-frontend:w13` | UI w/ widened dropzone (.psf/.dcd/.data/.rst7/.mdcrd/.cif) |
| validation-api | 1 | `bat3-validation-api:v3.132` | `uvicorn main:app`; **VALIDATION_DISPATCH_ENABLED=0 — MDDBR dispatch OFF (intentional, 2026-10-09)** |
| validation-worker | **0 (was 244)** | `bat3-validation-api:v3.132` | **scaled to 0 2026-10-09 (MDDBR OFF); reverse: scale 244 + dispatch env 1** |
| validation-ui | 1 | `bat3-validation-ui:latest` | |
| validation-postgres | 1 | `postgres:15-alpine` | DB `bat3_validation` |
| bat3-redis | 1 | `redis:8-alpine` | broker+backend; orphan `bat3-ceitec-bat3-redis` scaled 0 |

## Storage (PVCs)
- `bat3-databases-data-ceitec` (2Ti) = REAL BLAST DBs (2.1TB: nr/, nt/, core_nt/, pdbaa/, pdbnt/, swissprot/ symlinks → `.staging/`)
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
