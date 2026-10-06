# API reference (orientation)

Two FastAPI surfaces exist; they are **not interchangeable**. Route tables were
verified live (2026-10-03/04).

## validation-api — campaign control plane

Root `main.py`, served at the validation host. Key groups:

| Area | Routes | Notes |
|---|---|---|
| Queue | `/api/queue`, `/api/queue/list`, `/api/queue/status`, `/api/queue/files` (POST scan), `/api/queue/bulk-action`, `/api/queue/start-processing` | bulk actions are the supported batch interface |
| Batches | `/api/batches*` | counters reconciled by sweeper |
| Entries | `/api/entries*` | entry state mirror |
| Stats | `/api/stats/*`, `/api/queue/worker-stats`, `/api/stats/throughput` | dashboard feeds |
| Failure analysis | `/api/failure-analysis` | log-signature triage tool |

Background loops run **inside this process** (APScheduler): dispatch (15s, gated
by `VALIDATION_DISPATCH_ENABLED=1`), completion+sweep+truth-settle (30s).

!!! danger "Legacy armed endpoint (F-26)"
    `POST /validation/queue/start-processing` in the *src_new* API (below) uses a
    legacy dispatch path that builds **untimestamped** run ids (breaks RCSB file
    serving) and re-downloads inputs into an unserved layout. Prefer the
    production `/api/queue/*` surface above. A consolidation fix is pending.

## ceitec runs API — interactive runs + file serving

`uvicorn src_new.api.main:app`, host `bioid-ceitec.dyn.cloud.e-infra.cz`.
Routers mounted twice (`/runs` and `/api/v1/runs`).

| Area | Routes | Notes |
|---|---|---|
| Runs | `POST /runs`, `GET /runs`, `GET /runs/{id}` (+`/status`, `/loading`, `/molecules`, `/signatures`, `/identifiers`, `/verification`, `/render`, `/files`, `/logs`) | full per-run introspection |
| Actions | `POST /runs/{id}/cancel`, `POST /runs/{id}/rerun`, `POST /runs/rerun-all`, `DELETE /runs/{id}` | reruns create fresh run dirs |
| Config | `GET /runs/config/default`, `GET /runs/config/parallel-default` | parallel-default enables signature multiprocessing |
| Files | `GET /files/{path}` (runs dir), `GET /files/validation-<eid>-<ts>/input/...` | the second form is the **RCSB-facing** public file channel |

### The RCSB file-serving contract (F-N1a)

RCSB structure search needs a publicly fetchable URL of the query structure:

- Resolvers publish URLs shaped
  `<deployment_file_url>/files/<run_id>/input/<filename>`.
- For validation runs, `run_id = validation-<eid>-<timestamp>`; the API maps that
  to `/data/validation/<eid>/input/<filename>` with strict guards (numeric eid,
  `input/` prefix, no traversal, no listings; unresolved → 404).
- `deployment_file_url` **must** point at the instance that serves this
  deployment's files (env `DEPLOYMENT_FILE_URL` wins over ini; wrong value =
  RCSB reports "received a 404 from the underlying service" and the whole
  structure-search channel silently dies — campaign incident, fixed in W2).
- Fallback when deployment serving is disabled: SSH/SCP upload to a configured
  static host (`ssh_*` config fields), with delete-after-use.

## Public/static surfaces

`validation-ui`, `bat3-web` (frontends), and the ceitec host's static mounts.
All are read-only viewers over the same Postgres + NFS data.
