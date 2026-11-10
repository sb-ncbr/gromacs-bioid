# Architecture

Components as deployed in namespace `ceitec-biodata-ns` (cluster
`kuba-cluster`, CERIT-SC), checked with `kubectl get deploy,ingress` on
2026-11-10. One backend image, `cerit.io/tomsko/bat3-validation-api`
(built from `Dockerfile.full`; the repository is copied to `/app`), serves
every backend role; the role is chosen by the container command.

```text
 bioid-ceitec.dyn.cloud.e-infra.cz                      bat3-validation.dyn.cloud.e-infra.cz
 ---------------------------------                      ------------------------------------
  /              -> bat3-ceitec-bat3-web  (ui/, nginx)    /      -> validation-ui (nginx)
  /api /files /health /docs /openapi.json                         proxies -> validation-api
                 -> bat3-ceitec-bat3-api  (src_new FastAPI)  /docs  -> validation-docs
  /mcp           -> bioid-mcp             (mcp_server/)
  /documentation -> validation-docs       (this site)

  bioid-mcp --HTTP--> bat3-ceitec-bat3-api --Celery--> bat3-redis (broker + results)
                                                          |
                     queue validation.ui.celery           |  queue celery
                 +----------------------------------------+-------------------------+
                 v                                                                  v
         bat3-ui-worker  (web/API/MCP runs)                    bat3-ceitec-bat3-worker (campaigns)
                 \                                                                  /
                  +--> src_new pipeline: load -> segment -> signatures -> identify --+
                       (2 passes) -> verify -> export -> render
                                   |
     volumes: /app/databases (BLAST, Foldseek, PubChem/ChEMBL mirrors, indexes)
              /app/runs (web/API runs)   /data/validation (campaign entries)
     external: RCSB, AlphaFind, PubChem, ChEMBL, IDSM, LIPID MAPS, GlyCosmos

  validation-api (root main.py) --> validation-postgres;  dispatch OFF since 2026-10-09
```

## Deployments

| Deployment | Replicas (2026-11-10) | Runs | Job |
|---|---|---|---|
| `bat3-ceitec-bat3-api` | 1 | `uvicorn src_new.api.main:app --workers 4` (command pinned in the deployment; the image's default CMD is the validation API) | public runs API, `/files` serving, run reaper |
| `bat3-ui-worker` | 10 | `celery -A src_new.celery_app worker --pool=threads --concurrency=2 -Q validation.ui.celery` | executes every run submitted through the web application, the REST API or the MCP server (`VALIDATION_UI_QUEUE` on the API routes them here) |
| `bat3-ceitec-bat3-worker` | 8 | `celery -A src_new.celery_app worker --pool=threads --concurrency=2 --prefetch-multiplier=1` (default queue `celery`) | campaign runs (directly dispatched), re-runs |
| `bat3-ceitec-bat3-web` | 1 | `bat3-frontend` image (`Dockerfile.frontend`: `ui/` built with Vite, served by nginx) | the web application; proxies `/api` and `/files` to the API |
| `bioid-mcp` | 1 | `bioid-mcp` image (`Dockerfile.mcp`, `python -m mcp_server`) | MCP server, a client of the public API |
| `validation-docs` | 1 | `bat3-docs` image (`Dockerfile.docs`) | this site, at `/documentation/` on the BioID host and `/docs/` on the validation host |
| `bat3-redis` | 1 | `redis:8-alpine` | Celery broker and result backend (`bat3-ceitec-bat3-redis` is an unused leftover at 0) |
| `validation-api` | 1 | `uvicorn main:app` (image `v3.132`) | campaign queue control plane; dispatch disabled |
| `validation-worker` | 0 | `celery -A tasks worker` | campaign worker of the queue path (scaled to 0 on 2026-10-09) |
| `validation-ui` | 1 | static nginx (`Dockerfile.validation-ui`, source in the separate `bat3_validation` repository) | campaign dashboards |
| `validation-postgres` | 1 | `postgres:15-alpine` | queue and entry state of the campaign control plane |

Replica counts change with load; the workers' resource limits are 4 CPU and
20 GiB (fleet) or 10 GiB (UI workers). Other deployments in the namespace
(`mdpc-*`, `pdbcharges-toolkit-2`, `bat3-darkmatter-worker`) belong to
other projects or to the separate dark-matter study and are not part of BioID.

Kubernetes manifests: the Helm chart in `bat3-chart/` (release
`bat3-ceitec`: API, web, fleet worker, PVCs, the main ingress, and the
unused chart Redis), plus `deploy/` for what lives outside the chart
(`ui-worker.yaml`, `mcp-server.yaml`, `validation-docs.yaml`,
`bioid-ingress-extras.yaml` for the `/mcp` and `/documentation` paths, nginx
configs) and `k8s/` for the database build Jobs. Live deployments have drifted
from the chart (images and env set with `kubectl set`); compare with the
live object before a `helm upgrade`.

## Storage

| Volume | Mounted at | Holds |
|---|---|---|
| databases PVC | `/app/databases` | BLAST databases (nr, nt, core_nt, pdbaa, pdbnt, Swiss-Prot, UniRef50), Foldseek databases, PubChem and ChEMBL SQLite mirrors, SIFTS/SwissLipids/ChEBI indexes |
| runs PVC | `/app/runs` | one directory per web/API run: `input/`, `config.ini`, `results.json`, logs, `render/`; `_adhoc/` for RCSB query files |
| validation PVC (NFS) | `/data/validation` | campaign entries `<eid>/input/`, `<eid>/results*.json`, campaign configs, statistics artifacts, backups |
| pod-local | `/app/cache` | resolver cache (`BAT3_IDENTIFIERS_CACHE_DIR`; SQLite WAL does not work on NFS) |

## Life of a run

1. `POST /api/v1/runs` validates the upload and settings, writes
   `runs/<id>/input/`, `config.ini` and a `queued` `results.json`, and sends
   `run_pipeline_task` to `validation.ui.celery`.
2. A UI worker takes a per-run Redis lock and runs the pipeline in a child
   process with a wall-clock limit. Stages run serially; each expensive stage
   has a budget.
3. Progress and results are written **only** to `results.json`
   (`ResultsManager`, atomic writes). Celery task state is not a completion
   signal.
4. The API reads `results.json` for every response; the reaper marks runs
   failed whose task disappeared (worker killed).

Campaign runs follow the same steps on the fleet worker, with inputs and
results under `/data/validation/<eid>/` (see
[Running validations](running-a-validation.md)).

## Invariants

- **Era unity**: during a campaign or re-run wave, every worker that executes
  pipeline code runs the same image. Mixed-image fleets corrupt comparisons.
- **Results are the truth**: never mark completion from queue or Celery state
  alone.
- **No silent channels**: every generator or database failure must reach
  `results.json` `stage_errors`, not just the log.
- **Workers that run BLAST keep `BLASTDB_MEM_MAP=0`**: BLAST then reads the
  NFS volume with `read()`; a memory-mapped page on a stalled NFS mount kills
  the process with SIGBUS (OQ-16, 2026-10-19).
