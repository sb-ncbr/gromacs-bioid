# CEITEC Deployment — Live Facts (ceitec-biodata-ns)

## Core Concept
Ground truth about what is ACTUALLY deployed, versus stale docs. Verified 2026-09-10.

## Cluster / Access
- Kubeconfig context: `kuba-cluster` (namespace-scoped user; `kubectl get nodes` forbidden = normal)
- Namespace: `ceitec-biodata-ns`; Ingress hosts: `bioid-ceitec.dyn.cloud.e-infra.cz`, `bat3-validation.dyn.cloud.e-infra.cz` (NOT `bioid-validation` as docs claim)

## Components & Images (pinned)
| Deploy | Replicas | Image | Notes |
|---|---|---|---|
| bat3-ceitec-bat3-worker | 20 | `cerit.io/tomsko/bat3-worker:v2.13` | helm `bat3-ceitec`; mounts runs+databases+validation-data |
| bat3-ceitec-bat3-api | 1 | `bat3-api:latest` | helm |
| bat3-ceitec-bat3-web | 1 | `bat3-frontend:latest` | helm |
| validation-api | 1 | `bat3-validation-api:v3.83` | runs `uvicorn main:app` (full validation api + scheduler); mounts validation-data at /data/validation |
| validation-worker | 10 | `bat3-validation-api:v3.83` | celery `-A tasks` |
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

## Reference
- `../../deployments/ceitec-biodata/overview.md` (stale on some points)
- `../guides/safe-helm-upgrade.md`
