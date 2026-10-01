# CODER A — WAVE 2: API additive layer (provenance → /api/v1 → recents/rerun/queue → link fixes)  [model: qwen3.8-27b]

READ FIRST: .tmp/tasks/ui-rework/CONTEXT.md (rules 1-5 are LAW), PLAN.md WS6, fixtures/, contracts/openapi-live-baseline.json. Work in src_new/api/ ONLY (plus tests). Never touch pipeline/results/worker files.

## A0 — Provenance gate (do FIRST, separate commit `api: provenance check vs live ui1`)
- Generate openapi from source WITHOUT running server (repo .venv has deps): `python -c "from src_new.api.main import app; import json,sys; json.dump(app.openapi(), sys.stdout)" > .tmp/tasks/ui-rework/contracts/openapi-source-baseline.json`
- Diff vs contracts/openapi-live-baseline.json (paths + schemas). Write result to contracts/PROVENANCE.md: identical | superset | divergence list.
- If divergence in EXISTING paths: STOP, report — do not proceed (live :ui1 ≠ repo).

## A1 — /api/v1 alias + identity (commit `api: /api/v1 alias mount + creator_ip + mine filter + rerun + queue endpoints`)
1. `app.include_router(runs_router, prefix="/api/v1/runs", tags=["runs"])`; keep legacy mount untouched. Add `/api/v1/health` alias.
2. POST /runs: capture `creator_ip` (first hop of X-Forwarded-For, fallback request.client.host) → persist into run metadata (same place run_name is stored; see routes/runs.py create handler).
3. GET /runs?mine=1 → filter list by requester IP (default behavior unchanged).
4. POST /runs/{run_id}/rerun → single-run variant of rerun-all logic: requeue with stored input + config; 404 if run/input missing. Reuse, don't copy-paste the rerun-all body — extract shared helper.
5. GET /runs/{run_id}/queue → {state: queued|running|done, position: int|null, ahead: int|null}; queued = run dir exists with no results.json started marker (inspect how status endpoint derives pending); position via pending runs ordered by created_at. Keep simple; no celery internals.
6. Regenerate source openapi → diff vs baseline → additions only. Attach diff summary to commit body.

## A2 — Canonical database_url fixes (commit `api: canonical database_url for identifiers/verification`)
- In the response builders for identifiers/verification (routes/runs.py): PDB hits like `1HRC_A` / `4ZZZ_B` → strip `_CHAIN`, url https://www.rcsb.org/structure/<4ID uppercase>; CHEMBL bare digits → `CHEMBL<n>` in identifier and https://www.ebi.ac.uk/chembl/explore/compound/CHEMBL<n>; leave other types unchanged.
- Unit-test the pure helper (tests/src_new/api/): PDB chain strip incl. lowercase input, CHEMBL pad, pubchem passthrough, None/empty safe.
- Do NOT change field names or response shapes — values only.

## Validation (gate, report all outputs)
- repo .venv: `python -m pytest tests/src_new/api -x -q` → green (update tests only if additive behavior changed expectations)
- openapi-after.json diff vs baseline = ONLY new paths /api/v1/* + nothing removed/renamed
- Manual smoke (local uvicorn ok): create run w/ fake X-Forwarded-For → GET /runs?mine=1 contains it; rerun returns new run_id; queue endpoint sane on a pending run
- Tag after green: git tag api-wave2-localgreen (planner will deploy after review)
