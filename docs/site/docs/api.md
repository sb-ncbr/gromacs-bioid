# Internal API

The public runs API is documented in [REST API](rest-api.md). This page
covers what is **not** meant for users: the campaign control plane, the
operator routes of the BioID API, and the file-serving contract RCSB
structure search depends on. Route tables checked against the code on
2026-11-10.

## validation-api — campaign control plane

Repository-root `main.py` ("BAT3 Validation API"), deployment
`validation-api`, image `bat3-validation-api:v3.132`. The validation UI's
nginx (`deploy/nginx-validation-ui.conf`) proxies these paths on
`bat3-validation.dyn.cloud.e-infra.cz`; `/api/<path>` is rewritten to
`/<path>`.

| Area | Routes |
|---|---|
| Queue | `GET /validation/queue/status`, `/validation/queue/list`, `/validation/queue/workers`; `POST /validation/queue/start-processing`, `/validation/queue/bulk-action` |
| Workers | `GET /validation/workers/status`, `/validation/workers/metrics`; `POST /validation/workers/scale`, `/validation/workers/{name}/restart`, `/api/validation/queue/workers/ping` |
| Entries and results | `GET/POST /entries`, `GET /entries/{id}`, `/entries/failed`, `POST /entries/{id}/validate`, `/entries/{id}/retry`; `GET /results/{id}` |
| Runs | `GET /runs`, `/runs/active`, `/runs/{id}`; `POST /runs/batch`, `/runs/{id}/retry` |
| MDDBR index and ground truth | `/index/*`, `/ground-truth/*`, `/import/*` |
| Stats | `GET /stats`, `/database/stats`, `/validation/stats/failure-analysis`, `/api/failure-analysis`, `/validation/activity-log/stream` |
| Misc | `GET /health`, `GET /tasks/{id}` |

Background loops run inside this process (APScheduler, see
[Operations](operations.md#the-queue-control-plane-dormant)). Dispatch has
been off since 2026-10-09 (`VALIDATION_DISPATCH_ENABLED=0`).

Since 2026-10-06 (F-26), `start-processing` delegates to
`queue_processor.process_validation_queue` (timestamped run ids, queue
linkage, retry budget), and the legacy dispatch endpoints (`validate`,
`runs/batch`, `runs/{id}/retry`, `entries/{id}/retry`) answer 410 unless
`VALIDATION_LEGACY_DISPATCH` allows them (`src_new/api/legacy_guard.py`).

!!! warning "No authentication"
    These routes, including the mutating ones (`workers/scale`,
    `queue/bulk-action`), have no authentication; they are reachable through
    the validation UI host.

## BioID API — operator routes

`uvicorn src_new.api.main:app` (deployment `bat3-ceitec-bat3-api`). The runs
router is mounted twice, at `/runs` and `/api/v1/runs`; the BioID ingress
only routes `/api`, `/files`, `/health`, `/docs` and `/openapi.json` to it, so
the unprefixed routes below are reachable only inside the cluster.

| Route | Purpose |
|---|---|
| `GET /runs/config/default` | the server's full run configuration (deployment fields included) |
| `GET /runs/config/parallel-default` | the same with the `*_parallel` flags on; such a config is rejected by `POST /runs` since 2026-11-10 |
| `POST /runs/rerun-all` | re-queues every run in the runs directory (also mounted under `/api/v1/runs`, so publicly reachable) |
| `GET /runs/{id}/task` | Celery task state of a run |
| `GET /stats`, `/stats/dashboard` | run statistics |
| `/validation/*`, `/batch-runs*` | a second copy of the campaign queue routes, on the same Postgres; `POST /validation/queue/start-processing` uses the canonical dispatcher (F-26) |
| `GET /health/live`, `/health/ready` | Kubernetes probes (only this app has them) |
| `GET /files/adhoc/{name}` | temporary query structures for RCSB (below) |
| `GET /files/validation-<eid>-<ts>/input/<name>` | campaign input files for RCSB (below) |

The API also runs the zombie-run reaper (marks runs failed whose Celery task
vanished; `BAT3_RUN_REAPER=0` disables, `BAT3_RUN_REAPER_INTERVAL_S`
default 300) under a Redis leader lock.

## The RCSB file-serving contract

RCSB structure search fetches the query structure from a public URL, so the
deployment must serve the files its workers search with:

- Resolvers publish URLs of the form `<deployment_file_url>/files/...`.
  `DEPLOYMENT_FILE_URL` (set on all workers to
  `https://bioid-ceitec.dyn.cloud.e-infra.cz`) overrides `[pdb]
  deployment_file_url`.
- Query structures are staged in `BAT3_ADHOC_DIR` (`/app/runs/_adhoc`) and
  served by `/files/adhoc/<name>`; files are kept `BAT3_ADHOC_RETENTION_DAYS`
  (7) days. Since W3 A9 (2026-10-28) this no longer depends on the run
  registry.
- Campaign runs (`run_id = validation-<eid>-<timestamp>`) map to
  `/data/validation/<eid>/input/<name>` with strict guards (numeric eid,
  `input/` prefix, no traversal, no listings; anything else 404).
- A wrong `deployment_file_url` makes RCSB answer "received a 404 from the
  underlying service", and the structure-search channel silently returns
  nothing. Runs record such losses under
  `identification/structure_search_unavailable`.
- Fallback when deployment serving is off (`use_deployment_file_access =
  no`): upload by SSH/SCP to a static host (`[PDB_UPLOAD_*]` sections).
