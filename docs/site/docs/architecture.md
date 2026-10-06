# Architecture

Component geometry as running in production (namespace `ceitec-biodata-ns`,
cluster `kuba-cluster`), verified 2026-10-04. One container image serves every
backend role: `cerit.io/tomsko/bat3-validation-api:v3.125-N1` (the repo root is
copied to `/app`; role is chosen by the container command).

```
                        +----------------------+
   MDDBR (mdposit) <--->|  mddbr_client (HTTP) |
                        +----------+-----------+
                                   |
        +----------------+   +-----v------+        +--------------------+
        | validation-api |-->|  Postgres  |<-------| APScheduler loops  |
        | root main.py   |   | (queue DB) |        | (in validation-api)|
        | queue_processor|   +-----+------+        | 15s dispatch /     |
        | models.py      |                         | 30s settle+sweep   |
        +-------+--------+                         +---------+----------+
                |  REST (/api/queue, /entries,               |
                |   /api/stats, /api/queue/files)            | send_task
        +-------v--------+        +-----------------+        |
        | validation-ui  |        | bat3-redis      |<-------+
        | (v7.43, nginx) |        | (Celery broker) |
        +----------------+        +--------+--------+
                                           |
              +----------------------------+-------------------+
              |                            |                   |
     +--------v---------+       +----------v----------+ +------v------------+
     | validation-worker|       | bat3-ceitec-worker  | | bat3-ui-worker    |
     | x164  -A tasks   |       | x15  -A src_new.    | | x2  -A src_new.   |
     | (campaign queue) |       |   celery_app        | |   celery_app      |
     +--------+---------+       | (default queue)     | | -Q validation.ui. |
              |                 +----------+----------+ |   celery          |
              |                            |            +-------------------+
              v                            v
     +---------------------------------------------------------+
     | src_new pipeline: loader -> signatures -> identify ->    |
     | verify -> export   (serial per entry; stage budgets)     |
     +---------------------------+-----------------------------+
                                 |
        +----------------+-------+---------+-------------------+
        |  NFS /data/validation  |  bat3-ceitec-bat3-api       |
        |  <eid>/input+results,  |  src_new FastAPI (runs API, |
        |  sim_cache, stats,     |  /files serving for RCSB)   |
        |  config_shared.ini     |  x1, bioid-ceitec host      |
        +------------------------+----------------------------+
```

## Roles (all mutable only via image + deployment)

| Deployment | Code entrypoint | Job |
|---|---|---|
| validation-api ×1 | repo-root `main.py` (FastAPI "BAT3 Validation API v1.0.0") + `queue_processor.py` | Campaign control plane: queue/state DB API, background dispatch (gated by `VALIDATION_DISPATCH_ENABLED=1`), completion settle, stale sweep |
| validation-worker ×164 | `celery -A tasks worker --concurrency=2 --prefetch-multiplier=1` | Executes `schedule_validation` (download inputs) and `src_new.api.tasks.run_pipeline_task` (the pipeline) |
| bat3-ceitec-bat3-api ×1 | `uvicorn src_new.api.main:app` | Interactive runs API (UI), `/files/...` public file serving used by RCSB structure search |
| bat3-ceitec-bat3-worker ×15 | `celery -A src_new.celery_app ...` | Interactive/UI run execution (default queue) |
| bat3-ui-worker ×2 | `celery -A src_new.celery_app -Q validation.ui.celery` | UI-tagged batches (dedicated queue) |
| validation-ui / bat3-web | static frontends (nginx) | Dashboards; no compute |
| validation-postgres, bat3-redis | infra | Queue/state DB; broker+result backend |

## Data layout (NFS `/data/validation`)

- `<eid>/input/` downloaded simulation inputs per MDDBR entry (served publicly as
  `/files/validation-<eid>-<ts>/input/<name>` by the ceitec API for RCSB fetches)
- `<eid>/results.json` the single source of truth per entry (no DB copy of results)
- `sim_cache/` external-API caches (RCSB etc., no TTL)
- `config_shared.ini` campaign configuration (mounted into api+workers)
- `backups/`, `logs/`, stats tooling and figure artifacts (see Methodology)

## Execution lifecycle of one entry

1. Dispatcher (`process_validation_queue`, 15s tick) claims a `queued` row
   (SELECT ... FOR UPDATE SKIP LOCKED), creates a `bat3_runs` row, dispatches
   `run_pipeline_task` with a **timestamped** run id `validation-<eid>-<14-digit ts>`.
2. Worker downloads inputs (mddbr_client) if absent, then runs the pipeline
   stages: discover input → load/repair → segment → generate signatures →
   identify → verify → export mmCIF. Serial per entry; each stage has a wall-clock
   budget (default 900–1200s, `VALIDATION_STAGE_BUDGETS`).
3. Progress and results persist **only** to `<eid>/results.json`
   (`ResultsManager`, atomic writes). Celery task state is not a completion signal.
4. Settlement (30s tick): `check_task_completions` from Celery metadata +
   `settle_by_results_truth` (NFS-truth): all stages success/skipped/warning,
   file mtime ≥ attempt start − 600s, file ≥ 15 min old → queue row `completed`.
5. Sweep (same tick): rows stuck `processing` > `VALIDATION_STALE_HOURS` (12h)
   → requeued (see known limitations, Operations).

## Hard-won invariants (do not violate)

- **Era unity**: during any re-queue, ALL components that execute pipeline code
  (every worker class) must run the same image. Mixed-era fleets corrupt comparisons.
- **Results are truth**: never mark completion from queue/Celery alone (V-17).
- **No silent channels**: every generator/resolver failure must reach
  `results.json` `stage_errors` (bounded), not just logs (F-N1e contract).
- **`BAT3_SRC=/tmp/gate_src` required** when running overlay gate scripts, or the
  baked image code silently executes instead (V-18 mechanism).
