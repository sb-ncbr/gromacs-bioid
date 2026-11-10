# Developers

Working on the code. Repository:
[github.com/sb-ncbr/gromacs-bioid](https://github.com/sb-ncbr/gromacs-bioid)
(branch `master`).

## Repository map

```text
src_new/                 the pipeline and the BioID API (in every backend image)
  api/                   FastAPI app (src_new.api.main:app), runs router, Celery task, run reaper
  config/                loader.py (ini schema, defaults), presets.py (per-run allowlist, presets)
  input/ loader/ molecules/   file discovery, MDAnalysis loading and repair, segmentation
  signatures/            generators, registry, bond-order perception, fingerprints
  identification/        registry.py, resolution_manager.py, supplementary.py, resolvers/
  verification/          manager.py, dedup.py, fetchers/, scorers/, workers/
  pipeline_steps/        stage wiring, budgets, stage_errors
  executor/ results/ export/ render/   stage executor, results.json, mmCIF export, PNG renders
  celery_app.py          Celery app and broker hardening
ui/                      web application (React, Vite, Mol*)
mcp_server/              MCP server (python -m mcp_server)
tests/                   pytest suites (tests/src_new/, tests/mcp_server/, …)
scripts/                 database builders, statistics and audit tools (scripts/stats/)
docs/site/               this documentation (mkdocs)
bat3-chart/ deploy/ k8s/ Helm chart, extra manifests, database build Jobs
config.ini               settings of web/API runs
main.py, queue_processor.py, models.py, tasks.py, mddbr_client.py
                         campaign control plane (validation-api), dormant
Dockerfile.full, .frontend, .mcp, .docs   images in use
```

Legacy, not used by anything deployed: `src/` (the previous pipeline; its
constants were copied into `src_new/constants.py`, F-27), `web/` (old React
UI, see `web/DEPRECATED.md`), `cli/`, `api/`, `__old_deployment/`,
`Dockerfile.{api,worker,web,ui}`, and most Markdown files at the root and in
`docs/` (written for older states of the code). `validation` is a symlink to a
separate repository (`bat3_validation`, the validation UI).

## Setup and tests

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e '.[dev]'            # pytest, pytest-xdist

.venv/bin/python -m pytest tests/src_new -q   # run from the repository root
.venv/bin/python -m pytest tests/mcp_server -q
cd ui && npm ci && npx vitest run
```

Run tests from the repository root: fixture paths under `tests/data/` are
relative to it. Some tests need BLAST databases, GROMACS fixtures or network
access and fail without them; compare the set of failures with the same run
on the previous commit rather than expecting zero.

## Running locally

```bash
# API (runs are written to ./runs; Celery needs a Redis broker)
docker run -d -p 6379:6379 redis:8-alpine
export CELERY_BROKER_URL=redis://localhost:6379/0 CELERY_RESULT_BACKEND=redis://localhost:6379/0
.venv/bin/uvicorn src_new.api.main:app --port 8000

# a worker, in another shell (same env)
.venv/bin/celery -A src_new.celery_app worker --pool=threads --concurrency=2

# web application: Vite proxies /api, /runs, /files, /health to localhost:8000
cd ui && npx vite

# MCP server against the local API
BIOID_API_URL=http://localhost:8000 BIOID_PUBLIC_URL=http://localhost:5173 .venv/bin/python -m mcp_server
```

Without the local databases (`/app/databases`) only the remote resolvers
and the bundled name tables work; paths are set in `config.ini`.

## Rules for changes

1. **No silent channels**: a generator or database failure must land in
   `stage_errors` (bounded), not only in the log.
2. **Config**: new behaviour goes behind a declared ini field with a safe
   default (undeclared keys are ignored). A field users may change per run
   must be added to `TUNABLE` in `src_new/config/presets.py`, with bounds.
3. **results.json is a contract** read by the API, the web application, the
   MCP server and the statistics tools: add fields, never rename or
   restructure existing ones.
4. **Serial path is the reference**: the parallel stage workers delegate to
   the serial implementation (F-15); keep it that way.
5. **Campaign data**: anything that changes campaign results needs a
   snapshot and a replay-measured impact first.

## Findings registers

- `docs/CHEMISTRY_FIX_TODO.md`: the 2026-10-04 audit, F-01…F-28.
- `.opencode/context/bat3/`: operational lessons (V-xx), deployment facts,
  design records of later waves.
- Commit messages carry the identifiers used in the code comments
  (`BH-xxx` bug hunt, `D-xx`/`C-xx` red-team items, `G1`…`G9` API additions,
  `W3.x` waves); `git log --grep` finds the reasoning behind a change.
