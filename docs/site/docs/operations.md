# Operations

Running the BioID service on the CEITEC cluster (namespace
`ceitec-biodata-ns`). Component layout: [Architecture](architecture.md).

## Images

| Image | Built from | Deployed to |
|---|---|---|
| `cerit.io/tomsko/bat3-validation-api` | `docker build -f Dockerfile.full .` (includes BLAST, Foldseek, PyMOL, RDKit) | `bat3-ceitec-bat3-api`, `bat3-ceitec-bat3-worker`, `bat3-ui-worker` |
| `cerit.io/tomsko/bat3-frontend` | `docker build -f Dockerfile.frontend .` (`ui/`) | `bat3-ceitec-bat3-web` |
| `cerit.io/tomsko/bioid-mcp` | `docker build -f Dockerfile.mcp .` | `bioid-mcp` |
| `cerit.io/tomsko/bat3-docs` | `docker build -f Dockerfile.docs docs/site` (`mkdocs build --strict`) | `validation-docs` |

Build from a clean checkout of the commit you release (a detached worktree),
never from a working tree with local changes. Use a new tag for every build:
`kubectl set image` to an identical string is a no-op, and nodes may serve a
cached image for a re-pushed tag. Prefer digest references
(`image@sha256:…`) for the backend.

## Rollout

The backend release sets **one** backend image on the API, the fleet worker
and the UI worker (and optionally a new frontend tag), in one step:

1. **Refuse if busy**: every Celery queue (`celery`, `validation.ui.celery`,
   and any campaign queue) must be empty and no task active (a rollout
   kills running pipelines).
2. **Snapshot** each deployment's YAML before changing it.
3. `kubectl set image` on `bat3-ceitec-bat3-worker` (containers `worker` and
   `cache-seed`), `bat3-ui-worker`, `bat3-ceitec-bat3-api`, and set
   `BAT3_CODE_VERSION=git-<short sha>` on each; frontend:
   `set image deploy/bat3-ceitec-bat3-web web=…`.
4. Wait for `kubectl rollout status` on all of them.
5. **Verify**: each pod's `imageID` digest, the served `index-*.js` hash of
   the web application, and `code_version` in
   `GET https://bioid-ceitec.dyn.cloud.e-infra.cz/api/v1/capabilities`.

The maintainer's script for this (`release.sh <digest> <short sha> [frontend
tag]`) is kept outside the repository. Not covered by it, and deployed
separately:

- **Docs**: build `Dockerfile.docs`, then
  `kubectl -n ceitec-biodata-ns set image deploy/validation-docs docs=cerit.io/tomsko/bat3-docs:<tag>`.
- **MCP server**: `Dockerfile.mcp`, manifest `deploy/mcp-server.yaml`
  (deployment `bioid-mcp`).
- Their paths on the BioID host (`/documentation`, `/mcp`) are separate
  Ingresses in `deploy/bioid-ingress-extras.yaml`, because the main ingress
  `bat3-ceitec-bat3-ingress` is managed by Helm and a path patched into it
  would be lost on the next `helm upgrade`.

Never mix images across worker classes during a campaign or re-run wave
(era unity). The dark-matter worker (`bat3-darkmatter-worker`) belongs to a
separate study and is not touched by a BioID release.

## Admin page

`https://bioid-ceitec.dyn.cloud.e-infra.cz/admin` is the operations
dashboard: queues (pause, resume, purge), Celery workers and their runs,
BioID deployments and pods (scale, restart, logs), runs (cancel, delete to
trash, change retention), retention status and trash (restore), storage,
limits. Backend: `src_new/api/admin.py` (`/api/v1/admin/*`, not in the public
schema). It only touches BioID's own deployments (`DEPLOYMENTS` there); the
namespace also runs other teams' workloads and the validation stack.

The password is `BAT3_ADMIN_PASSWORD` on the API deployment, from the secret
`bioid-api-secrets` (unset = admin disabled). Sign-ins are limited to 10
failures per address per 15 minutes and 100 per hour overall; sessions last
12 hours and end when the password changes.

## Traffic statistics

`src_new/api/traffic.py`; shown on the admin page (*Traffic*). Page views come
from a beacon in the web app (`ui/src/lib/pageviews.ts`) and the docs
(`docs/site/docs/js/stats.js`); API calls from a middleware (routine status
polling is skipped, errors are always recorded). Clients identify themselves
with `X-BioID-Client` (web, mcp, docs). Events are appended to
`<runs>/_traffic/events/<day>/<host>-<pid>.jsonl` (not served, not touched by
run retention) and deleted after 90 days (`BAT3_TRAFFIC_RAW_DAYS`). No address
is stored: the keyed hash and a city-level location from the DB-IP Lite
database at `/app/databases/geoip/dbip-city-lite.mmdb`, downloaded and
refreshed monthly by the API (`BAT3_GEOIP_REFRESH=0` disables;
`BAT3_TRAFFIC=0` turns recording off).

## Run retention

`src_new/api/retention.py`, run hourly by the API's reaper (one leader pod).
A finished run expires 30 days (`BAT3_RETENTION_DAYS`) after it finished, or
after its own `retention` (days, or `preserve` = never). Runs from before the
policy expire 30 days after 2026-11-10 at the earliest. Never expired: the
examples (`BAT3_EXAMPLE_RUNS` and whatever `/runs/examples` serves),
preserved runs, unfinished runs, runs written in the last hour, anything not a
plain run directory.

- **Report-only until `BAT3_RETENTION_ENFORCE=1`** is set on the API: the
  sweep only records what would expire (admin page, *Retention*).
- Expired runs are moved to `<runs>/_expired/` and purged after
  `BAT3_RETENTION_GRACE_DAYS` (7); the admin page restores them (restored runs
  are preserved).
- A sweep that would expire more than 50 runs (`BAT3_RETENTION_MAX_PER_SWEEP`)
  or more than half of all runs expires nothing and logs an error.

## Scaling

UI workers (`bat3-ui-worker`) execute every web, API and MCP run, two at a
time per pod; scale them with the expected interactive load. The fleet
worker (`bat3-ceitec-bat3-worker`) only matters for campaigns: g1 ran on 24
pods (4 vCPU, 20 GiB each, two pipelines per pod). With a large fleet,
restrict which pods consume the `celery` queue so that RCSB structure search
is not overloaded.

## Health checks

- `kubectl -n ceitec-biodata-ns get deploy` — all ready; API and both worker
  classes on the same image.
- `GET /api/v1/capabilities` — answers, with the expected `code_version`.
- Run an example: submit a small PDB file with the `quick` preset and check
  that it reaches `success` with verified hits.
- `stage_errors` and `identification/structure_search_unavailable` in recent
  results — a database channel that dies shows up here first.
- Free space on the runs and databases volumes; runs are not cleaned up
  automatically, the resolver cache has no TTL.
- Log volume of `stage_time_budget` warnings.

## Known failure classes

| Class | Symptom | Cause | Handling |
|---|---|---|---|
| Broker wedge | throughput collapses without restarts | the network keeps dead TCP connections open | socket timeouts, keepalive and health checks in `src_new/celery_app.py`; `visibility_timeout` 6 h |
| Worker OOM | pods killed on large systems | big pipelines × prefetch | `--prefetch-multiplier=1`, `--concurrency=2` |
| Stalls | a stage runs for hours | slow external services, large searches | stage budgets; slow databases deferred to the second pass |
| SIGBUS / lost tasks | a run vanishes mid-stage | memory-mapped BLAST database on a stalled NFS mount | `BLASTDB_MEM_MAP=0`; late acks; the run reaper marks orphaned runs failed |
| Wrong file URL | RCSB evidence missing on every run | `DEPLOYMENT_FILE_URL` not this deployment | fix the env; see [Internal API](api.md#the-rcsb-file-serving-contract) |
| RCSB overload | `structure_search_unavailable` records | too many concurrent structure searches | per-process cap and backoff; fewer fleet consumers |
| Clock skew | Celery ETA warnings, odd mtimes | NFS server clock ahead of the pods | harmless for result handling |

## The queue control plane (dormant)

`validation-api` (repository-root `main.py` + `queue_processor.py`) ran the
v1–v14 campaigns. Its loops, all inside the API process (APScheduler):

| Loop | Cadence | Does |
|---|---|---|
| Dispatch | 15 s | claims `queued` rows (`SELECT … FOR UPDATE SKIP LOCKED`), creates the run record, sends `run_pipeline_task` with run id `validation-<eid>-<timestamp>`; gated by `VALIDATION_DISPATCH_ENABLED=1`, throttled by `VALIDATION_DISPATCH_CONCURRENCY` (code 12, production 4) |
| Settle | 30 s | marks rows completed from Celery state, or from `results.json` itself (all stages finished, file at least 15 min old) |
| Stale sweep | 30 s | re-queues rows `processing` longer than `VALIDATION_STALE_HOURS` (code 24, production 12); after 3 such cycles the row fails permanently |

Dispatch has been off since 2026-10-09 and `validation-worker` is at 0
replicas; `validation-ui` and the Postgres database remain as the record of
those campaigns. Its routes are listed on [Internal API](api.md).
