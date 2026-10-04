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

### `[identifiers]` — per-resolver pair toggles (F-21 corrected 2026-10-04)
Every resolver honors a **pair** of toggles, read per attempt:

| Key pattern | Gates | Default |
|---|---|---|
| `<resolver_name>` | **identity** attempts | `yes` |
| `<resolver_name>_similarity` | **similarity** attempts | `yes`, except `atom_similarity` and `name_*_similarity` (default `no`) |

So `<name>: no` suppresses identity attempts while similarity attempts keep
running under `<name>_similarity: yes` — this pair semantics (not dead code)
explains the old V-20 observation of "resolver still ran despite `no`".

All 27 resolver names are valid keys: `pubchem_struct`, `chembl_struct`,
`idsm_pubchem/chembl/chebi`, `inchikey_pubchem`, `inchikey_self`,
`formula_pubchem`, `formula_hfamily`, `blast_pdb_protein`, `blast_uniprot`,
`blast_nr_protein`, `blast_swissprot_protein`, `blast_pdb_nucleic`,
`blast_core_nt`, `blast_nt`, `pdb_struct_protein`, `pdb_struct_nucleotide`,
`alphafind_struct`, `foldseek_3di`, `mmcif_struct`, `lipid_maps`,
`glycan_composition`, `atom`, `name_ccd`, `name_maps`, `name_manual`.

!!! warning "ini keys only work if declared"
    The ini loader reads **declared config fields only** — unknown keys are
    silently ignored. F-21 completion (2026-10-04) declared the 8 previously
    missing pairs; before that, toggling e.g. `mmcif_struct: no` did nothing.
    Unrecognized keys still do nothing — the table above is the valid set.

Special keys:

| Key | Effect |
|---|---|
| `overwrite_existing` | if `no`, resolvers skip signatures that already have hits in results.json |
| `formula_local` | construction gate for the local PubChem mirror resolver (also needs the mirror DB file) |
| `formula_chembl` | gates the ChEMBL exact-formula fallback: construction needs this `yes` **or** `VALIDATION_SKIP_PUG=1`, and identity attempts need the field `yes` — with env-only construction and a fleet ini lacking the flag, the resolver exists but stays inert (known quirk, reported) |

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
| `PIPELINE_RESUME_STAGES` | worker | resume-skip switch; `0` forces full re-run. Active since v3.126-audit2 (revised F-03 semantics): only `generate_signatures`/`identify_molecules`/`verify_results` skip, and only on persisted `success` |
| `CELERY_BROKER_TRANSPORT_OPTIONS` | deploy env | **dead config** — nothing reads it (F-08); transport opts are set in code |

!!! danger "`BAT3_SRC` shadowing (V-18)"
    `n1_run_gates.py`-style overlay gates do
    `sys.path.insert(0, os.environ.get("BAT3_SRC", "/app"))`. Running them
    **without** `BAT3_SRC=/tmp/gate_src` silently executes the baked image code —
    `PYTHONPATH`, `cd`, and bytecode purges do NOT protect you. Any PYTHONPATH
    pointing at an NFS code tree is an era-mix booby trap of the same class
    (real case: `/data/validation/patched_src` pre-W4 shadow tree on ui-worker
    — removed 2026-10-04, F-09).
