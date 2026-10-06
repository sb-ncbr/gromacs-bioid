# Developers

Working on the codebase itself.

## Repository map (verified 2026-10-04)

```
bat3/
├── src_new/                 # THE pipeline package (baked into all backend images)
│   ├── api/                 #   FastAPI: uvicorn src_new.api.main:app (ceitec runs API)
│   ├── celery_app.py        #   Celery app + broker transport hardening
│   ├── config/loader.py     #   ini schema + env overrides (defaults live HERE)
│   ├── executor/            #   PipelineExecutor (stages, budgets, conditions)
│   ├── input|loader|molecules/  # discovery, MDAnalysis loading/repair, segmentation
│   ├── signatures/          #   19 generators + registry + snapshot/parallel workers
│   ├── identification/      #   registry, resolution_manager, cache, 16 resolvers
│   ├── verification/        #   manager, dedup, fetchers, scorers, workers
│   ├── pipeline_steps/      #   stage wiring (serial + parallel worker forks)
│   └── results/             #   ResultsManager (results.json contract)
├── main.py                  # LIVE validation-api (FastAPI "BAT3 Validation v1.0.0")
├── queue_processor.py       # LIVE dispatcher/settler/sweeper (APScheduler brain)
├── models.py, mddbr_client.py, tasks.py  # LIVE: DB models, MDDBR REST, worker app
├── src/                     # older generation, PARTIALLY load-bearing (F-27):
│                            #   src_new imports src.constants — do not delete
├── scripts/                 # stats/GT tooling partially dual-homed on NFS (F-28)
├── tests/                   # pytest: tests/src_new/**, n1_wave/, fixtures/data
├── validation -> ../bat3_validation/   # symlink to the web/mdfind app repo
├── docs/  (+ docs/site/)    # legacy corpus (this site supersedes selected pages)
└── Dockerfile.{worker,api,...}    # COPY . /app; role via container command
```

!!! note "Naming traps"
    Root files look like leftovers but are production (validation-api).
    `validation/api/main.py` (v2.5 lineage) currently has **no live deployment**.

## Local development

```bash
python3.11 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
pip install pytest          # NOTE: pytest is NOT in requirements (F-27-era)
python -m pytest tests/src_new -q
```

- Tests must run **from the repo root** (`tests/data/` paths are CWD-relative —
  running from a subdirectory manufactures red suites, V-21).
- Regression-proofing pattern (V-21): diff the FAILED-set against a baseline
  image run; identical red sets = zero behavioral regression.
- The `tests/n1_wave/` suite carries the campaign-era gates (e2e fixture,
  strand-select, short-identity, allow-delta list for resolver-generated
  signature diversification).

## Invariants to respect when changing code

1. **Never silently drop a channel**: generator/resolver failures must land in
   `stage_errors` (bounded) — log-only failure swallowed the RCSB outage for a
   whole campaign once.
2. **Config schema**: add new behavior behind ini keys with safe defaults;
   document effective keys (and mark dead ones). Do not add more environment
   variables for things the ini owns.
3. **results.json is the contract**: schema consumers include the stats
   tooling, the UI, the settle loop, and the replay harnesses. Additive changes
   only; never rename/restructure existing branches.
4. **Serial-first**: keep the serial stage path the reference implementation;
   the parallel worker forks must delegate to it (they currently fork — F-15 —
   unify when touching them).
5. **Snapshot discipline**: anything that mutates campaign data requires
   prerequeue snapshots + a replay-derived impact estimate first.

## Findings register

The 2026-10-04 read-only audit produced F-01…F-28 (bugs, methodology and
consistency items) — pinned in `docs/CHEMISTRY_FIX_TODO.md` (FINAL AUDIT
sections); dispositions are per-item project-lead decisions. Ops lessons
V-13…V-23 live in `.opencode/context/bat3/errors/common-issues.md`.

## Known stale docs (do not trust blindly — slated for refresh)

- `docs/ARCHITECTURE.md`, `docs/src_new_backbone.md`... describe the older
  tree/api surfaces; this site is the corrected geometry.
- `docs/CODE_HEALTH_REPORT.md` audited the old tree; findings #1 (no packaging)
  and #2 (pytest undeclared) remain valid today.
