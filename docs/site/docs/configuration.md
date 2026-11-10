# Configuration

## Where settings come from

| Layer | Applies to |
|---|---|
| code defaults (`src_new/config/loader.py`, dataclasses) | everything not named elsewhere |
| `config.ini` at the repository root (baked into the image) | web, API and MCP runs: `RunConfig.from_default_ini()` |
| campaign config (`/data/validation/config_<label>.ini`, `config_shared.ini`) | campaign runs; not in the repository |
| run preset, then the user's overrides | web, API and MCP runs (below) |
| environment variables | a few paths and service URLs (e.g. `DEPLOYMENT_FILE_URL`), and process behaviour (budgets, breaker, cache) |

The ini loader reads **declared fields only**; an unknown key is silently
ignored. A run's effective configuration is written to
`runs/<id>/config.ini`.

## Per-run settings and presets

Since 2026-11-10 (`src_new/config/presets.py`), a web/API/MCP run may change
only the fields in `TUNABLE`:

- `[identifiers]`: every database switch (except `overwrite_existing` and
  `formula_chembl`);
- `[verification]`: `verify_top_n` (1–200), `verify_top_n_supplementary`
  (0–100), `similarity_top_n` (1–50), the three weights (0–100),
  `tm_score_threshold`, `min_final_confidence` (0–100),
  `enable_annotation_quality`, `annotation_live_fetch`;
- `[blast]`: the `exact_match_*` and `similarity_match_*` thresholds;
- `[chembl]`, `[idsm]`, `[pubchem]`: `similarity_threshold` (0–100);
- `[pdb]`: `rcsb_include_mixed_complexes`;
- `[signatures]`: `smiles_maximum_number_of_atoms`, the FASTA partial/strict
  modes, `enhanced_nucleic_acid_recognition`;
- `[loader]`: the `guess_missing_*` switches, `tpr_resid_from_one`,
  `quick_structure_search`, `unwrap_periodic_boundaries`,
  `element_mass_tolerance`, `bond_guess_vdw_factor`.

Anything else (paths, executables, URLs, threads, timeouts, the
`[executor] *_parallel` flags) is rejected with 422, unless the value equals
the server's. Presets (`balanced`, `quick`, `exact`, `deep`) are overrides in
the same module; `GET /api/v1/runs/config/options` serves both. A test
checks that every preset key is tunable.

## Sections

Defaults below are the code defaults; where the web application's
`config.ini` differs, its value is given as *ini*.

### `[identifiers]` — database switches

Each database `<key>` (see [Databases](databases.md)) has two switches,
read on every attempt: `<key>` for identity searches and `<key>_similarity`
for similarity searches. Defaults are `yes`, except:

- `atom_similarity`, `name_ccd_similarity`, `name_maps_similarity`,
  `name_manual_similarity`: `no`;
- `formula_chembl`: `no` (the resolver is also built when
  `VALIDATION_SKIP_PUG=1`);
- supplementary `blast_uniref50`, `foldseek_pdb`, `swisslipids`,
  `chebi_local`, `sifts_uniprot` (both switches): `no` in code; *ini* `yes`
  except `foldseek_pdb` (identity) `no`.

Other keys:

| Key | Default | Meaning |
|---|---|---|
| `deferred_resolvers` | `""`; *ini* `blast_nr_protein, blast_nt, blast_core_nt` | databases moved from the first identify pass to the end of the second |
| `sifts_mode` | `corroborate` | `corroborate`: SIFTS UniProt accessions become candidates; `xref`: only recorded |
| `sifts_db`, `swisslipids_db`, `chebi_db` | `/app/databases/{sifts,swisslipids,chebi}/*.sqlite` | supplementary indexes |
| `formula_local` | `yes` | use the local PubChem mirror for formula search (needs `[pubchem] local_db_path`) |
| `mmcif_struct_mode` | `full` | how structure-search evidence (`mmcif_struct`, `pdb_struct_*`, `foldseek_3di`, `alphafind_struct`) scores: `full` counts it as a corroborating source; `tiebreak` strips it from scoring so it only orders otherwise equal candidates |
| `overwrite_existing` | `no` | re-search signatures that already have hits (resumed runs) |

### `[verification]`

| Key | Default | Meaning |
|---|---|---|
| `verify_top_n` | 100 | candidates verified per molecule |
| `verify_top_n_supplementary` | 20; *ini* 40 | extra candidates found only by the second identify pass |
| `similarity_top_n` | 10 | similarity hits kept per database search |
| `resolver_weight` / `similarity_weight` / `annotation_weight` | 0.4 / 0.4 / 0.2 | confidence weights, normalised to sum 1 |
| `min_final_confidence` | 0.0 | confidence (0–100) a hit needs to be verified; 0 = no gate |
| `tm_score_threshold` | 0.5 | structural comparison gate |
| `enable_annotation_quality` | yes | compute the annotation term |
| `annotation_live_fetch`, `annotation_live_budget_per_segment`, `annotation_fetch_timeout_s` | yes, 25, 3.0 | live record fetches for the annotation term |
| `verify_rerank_max_candidates`, `verify_rerank_wall_cap_s` | 25000, 30 | limits of the chemical skeleton re-rank |
| `belief_source_normalize` | no | experimental agreement normalisation (off) |

### `[blast]`

| Key | Default | Meaning |
|---|---|---|
| `*_db` | `/app/databases/<name>/<name>` | database prefixes |
| `timeout_s` | 300; *ini* 3600 | per-search limit (also clipped to the stage budget) |
| `uniref50_num_threads`, `uniref50_timeout_s` | 1, 900; *ini* 4, 900 | UniRef50's own limits |
| `max_target_seqs` | 500 | hits per search |
| `exact_match_*` | e-value 1e-50, bits 51, identity 0.99, query coverage 0.99 | identity thresholds |
| `similarity_match_*` | e-value 0.1, bits 20, identity 0.4, query coverage 0.15 | similarity thresholds |
| `local_instance_run_short_search_if_under_X_residues` | 30 | short-query BLAST task below this length |

### `[pdb]` — RCSB structure search

| Key | Default | Meaning |
|---|---|---|
| `use_deployment_file_access` | yes | publish query structures through this deployment's `/files` route |
| `deployment_file_url` | `https://bioid.dyn.cloud.e-infra.cz` | public base URL of that route; **must** be this deployment (env `DEPLOYMENT_FILE_URL` overrides; set on every worker) |
| `ssh_*`, `[PDB_UPLOAD_*]` | — | SCP fallback when deployment serving is off |
| `rcsb_include_mixed_complexes` | no | an additional query for mixed protein/nucleic-acid entries (F-24); on in the *Deep search* preset |

### Other sections

- `[chembl]` `similarity_threshold` 60, `local_db_path` (ChEMBL mirror);
  `[idsm]` `similarity_threshold` 80; `[pubchem]` `similarity_threshold` 95,
  `local_db_path` (PubChem mirror), `hfamily_local_max_*`.
- `[foldseek]` `mode` (`local` / `remote` / `off`), `db_path` (AlphaFold
  Swiss-Prot), `pdb_db_path` (for `foldseek_pdb`), `remote_url`,
  `max_target_hits` 20, `search_timeout_s` 300.
- `[alphafind]` `url` (the AlphaFind search API), retry and polling limits.
- `[names]` `ccd_db`, `maps_db`, `manual_db` (JSON tables under `databases/`).
- `[identifiers_cache]` `directory` (empty: `BAT3_IDENTIFIERS_CACHE_DIR`,
  pod-local), `file`.
- `[executor]` `n_threads`, `signatures_parallel` / `identifiers_parallel` /
  `verification_parallel` (all `no`). The parallel paths share the serial
  implementation (F-15) but have not been validated on production runs;
  they cannot be enabled per run.
- `[loader]`, `[signatures]`: input repair, periodic-boundary unwrapping and
  generator switches.

## Environment variables

| Variable | Where | Effect |
|---|---|---|
| `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `DATABASE_URL` | API, workers | service wiring |
| `DEPLOYMENT_FILE_URL` | workers | RCSB publishing base (above) |
| `VALIDATION_UI_QUEUE` | API | queue for web/API runs (`validation.ui.celery`) |
| `VALIDATION_STAGE_BUDGETS`, `VALIDATION_STAGE_BUDGET_DEFAULT_S` | workers | stage budgets: JSON map over the defaults 1200 s (signatures, identify, verify) and 900 s (others); `off` disables. The UI worker sets `{"identify_molecules": 4500}` |
| `VALIDATION_SKIP_PUG` | workers | skip PubChem REST in compound fetches; also builds `formula_chembl`. Set on the production workers |
| `VALIDATION_PUBCHEM_BREAKER` | workers | `0` disables the PubChem circuit breaker |
| `BLASTDB_MEM_MAP` | workers | keep `0` on NFS (see [Architecture](architecture.md#invariants)) |
| `BAT3_IDENTIFIERS_CACHE_DIR` | workers | pod-local resolver cache (wins over the run config) |
| `BAT3_RUNS_DIR`, `BAT3_ADHOC_DIR`, `BAT3_ADHOC_RETENTION_DAYS` | API, workers | run and RCSB-query directories |
| `BAT3_CODE_VERSION` | API, workers | stamped into `pipeline.code_version` and `/capabilities` (`git-<sha>`, set by the release) |
| `BAT3_EXAMPLE_RUNS`, `BAT3_TYPICAL_DURATION_MIN/MAX` | API | front-page examples, advertised run duration |
| `BAT3_RUN_REAPER`, `BAT3_RUN_REAPER_INTERVAL_S` | API | zombie-run reaper |
| `PIPELINE_RESUME_STAGES` | workers | `0` disables skipping stages that already succeeded |
| `SPIN_DEBUG` | workers | `1` dumps thread stacks every 120 s (diagnostics; set on the UI workers) |
| `VALIDATION_FILES_ROOT` | API | NFS root for `/files/validation-*` |
| `VALIDATION_DISPATCH_ENABLED`, `VALIDATION_DISPATCH_CONCURRENCY`, `VALIDATION_STALE_HOURS`, `VALIDATION_LEGACY_DISPATCH` | validation-api | campaign control plane (dormant) |
| `MDDBR_API_BASE` | validation-api, workers | MDposit REST base |
| `CELERY_BROKER_TRANSPORT_OPTIONS` | fleet worker | not read by any code (F-08); transport options are set in `src_new/celery_app.py` |

!!! danger "`BAT3_SRC` and code shadowing (V-18)"
    Overlay gate scripts do `sys.path.insert(0, os.environ.get("BAT3_SRC",
    "/app"))`. Without `BAT3_SRC=<overlay dir>` they silently run the image's
    code. Any `PYTHONPATH` pointing at a code tree on NFS is the same trap.
