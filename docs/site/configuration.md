# Configuration

Precedence (highest wins): **environment variable → ini file → code default**.
Campaign ini lives at `/data/validation/config_shared.ini` (mounted into api and
workers); the same schema applies to any run-local `config.ini`.

## ini sections (schema: `src_new/config/loader.py`)

### `[executor]`
| Key | Default | Meaning |
|---|---|---|
| `n_threads` | 10 | worker parallelism when `*_parallel` enabled |
| `signatures_parallel` / `identifiers_parallel` / `verification_parallel` | false | stage parallelism. Campaign ran **all serial**; the UI parallel-default enables signature parallelism only |
| `TPS` | 100 | legacy throttle hint |

!!! warning "Armed-but-divergent (F-15)"
    The parallel identify worker is a fork of the serial dispatcher and lacks
    the PubChem circuit breaker and the overwrite-existing skip. Do not enable
    `identifiers_parallel` until that fork is unified.

### `[identifiers]` — mostly decorative (F-21 / V-20)
Per-resolver `yes/no` toggles in this section are **not read** by the resolver
registry (one exception pair below). Resolvers run unless the *registry* gating
skips them. Effective keys:

| Key | Effect |
|---|---|
| `overwrite_existing` | if `no`, resolvers skip signatures that already have hits in results.json |
| `formula_local` | enables the local PubChem mirror resolver when the mirror DB file exists |
| `formula_chembl` | enables the ChEMBL exact-formula fallback (also auto-on when `VALIDATION_SKIP_PUG` is set) |

Treat every other `[identifiers]` toggle as inert until F-21 is dispositioned.

### `[verification]`
| Key | Campaign value | Meaning |
|---|---|---|
| `verify_top_n` | 100 | candidates verified per segment |
| `similarity_top_n` | 10 | per-resolver similarity hit cap |
| `verify_rerank_max_candidates` | 60000 | cap for the structure re-rank pass |
| `resolver_weight` / `similarity_weight` / `annotation_weight` | 0.4 / 0.4 / 0.2 | aggregation weights |
| `min_final_confidence` | **0.0** | currently vacuous (see F-17) |
| `tm_score_threshold` | 0.5 | structure-worker gate |
| `enable_annotation_quality` | yes | scorer stage |

### `[pdb]` — the RCSB wire
| Key | Meaning |
|---|---|
| `use_deployment_file_access` | publish input files via this deployment's `/files` route (preferred) |
| `deployment_file_url` | public base URL of **this** deployment's file route; mis-set value kills the RCSB channel (404). Env `DEPLOYMENT_FILE_URL` overrides |
| `ssh_host/user/key/remote_path/public_url` | SSH-upload fallback when deployment serving is disabled |

## Environment variables with behavioral effects

| Variable | Scope | Effect |
|---|---|---|
| `DATABASE_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | api/worker | core wiring (code defaults point at cluster services) |
| `DEPLOYMENT_FILE_URL` | worker/api | RCSB publish base (see above) |
| `VALIDATION_FILES_ROOT` | ceitec api | NFS root for `/files/validation-*` serving |
| `VALIDATION_DISPATCH_ENABLED`, `VALIDATION_DISPATCH_CONCURRENCY` | validation-api | dispatch loop gate/throttle |
| `VALIDATION_STALE_HOURS` | validation-api | sweeper horizon (12 in prod) |
| `VALIDATION_RESULTS_TRUTH_SETTLE`, `..._MIN_AGE_S`, `..._PER_TICK` | validation-api | NFS-truth settle tuning |
| `VALIDATION_STAGE_BUDGETS` / `VALIDATION_STAGE_BUDGET_DEFAULT_S` | worker | per-stage wall-clock budgets; `"off"` disables |
| `VALIDATION_SKIP_PUG` | worker | skip PubChem REST (mirror/offline paths only) |
| `VALIDATION_PUBCHEM_BREAKER` | worker | `0` disables the breaker |
| `VALIDATION_UI_QUEUE`, `VALIDATION_UI_BATCH_PREFIX` | api | UI batch routing (`validation.ui.celery`) |
| `MDDBR_API_BASE` | api/worker | MDDBR REST base |
| `SPIN_DEBUG` | worker | per-120s thread-stack dumps (postmortem probe; currently armed fleet-wide — F-10) |
| `BAT3_SRC` | gate scripts | **overlay-gate selector** (see warning) |
| `PIPELINE_RESUME_STAGES` | worker | nominal resume-skip switch (currently inert — F-03) |
| `CELERY_BROKER_TRANSPORT_OPTIONS` | deploy env | **dead config** — nothing reads it (F-08); transport opts are set in code |

!!! danger "`BAT3_SRC` shadowing (V-18)"
    `n1_run_gates.py`-style overlay gates do
    `sys.path.insert(0, os.environ.get("BAT3_SRC", "/app"))`. Running them
    **without** `BAT3_SRC=/tmp/gate_src` silently executes the baked image code —
    `PYTHONPATH`, `cd`, and bytecode purges do NOT protect you. Any PYTHONPATH
    pointing at an NFS code tree (e.g. the stale `/data/validation/patched_src`
    on ui-worker, F-09) is an era-mix booby trap of the same class.
