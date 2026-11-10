# Running validations

A validation campaign runs the pipeline over many repository deposits and
scores the results against the deposits' annotations. Single runs (web
application, REST API, MCP server) are covered in [Using BioID](index.md).

## Two ways to dispatch a campaign

| Path | Used for | State (2026-11-10) |
|---|---|---|
| **Direct dispatch** to the fleet worker: `run_pipeline_task` sent to the `celery` queue of `bat3-ceitec-bat3-worker`, with a campaign config file on NFS | the g1 campaign (Nov 2026) and targeted re-runs | current method |
| **Queue control plane**: `validation-api` (repo-root `main.py` + `queue_processor.py`) dispatching rows of its Postgres `validation_queue` to `validation-worker` | campaigns v1–v14 (Aug–Oct 2026) | dormant: `VALIDATION_DISPATCH_ENABLED=0` since 2026-10-09, `validation-worker` at 0 replicas |

### Direct dispatch (g1 method)

Each deposit is one Celery task, `src_new.api.tasks.run_pipeline_task`, with

- `input_dir=/data/validation/<eid>/input` (inputs downloaded once from
  MDposit),
- `results_path=/data/validation/<eid>/results-<label>.json` (one file per
  campaign label, so campaigns never overwrite each other),
- `run_id=<label>-<eid>`,
- the campaign's config file, e.g. `/data/validation/config_<label>.ini`.

The dispatch script used for g1 is kept with the paper's analysis material,
not in this repository. Its rules are worth keeping: skip deposits whose
results file already exists (resume-safe); before re-sending a deposit, move
its previous result aside as `results-<label>.json.attempt<N>`; re-send only
a selection chosen by a measured defect (failed runs, lost RCSB evidence,
a listed set).

### Queue control plane (dormant)

The `validation-api` loops are described in [Operations](operations.md#the-queue-control-plane-dormant).
Its UI (`validation-ui`, `bat3-validation.dyn.cloud.e-infra.cz`) still
serves the campaign history. To revive it, scale `validation-worker` up on the
current image and set `VALIDATION_DISPATCH_ENABLED=1` on `validation-api`;
both still run the older `v3.132` image, so rebuild first (era-unity rule,
[Operations](operations.md#rollout)).

## What a run costs

g1 campaign, 15,034 deposits with complete timing: median 3.8 min, p95
10.1 min, slowest 71 min per deposit. Identification takes about three
quarters of the time (external services and BLAST), verification about a
seventh. CPU per deposit is modest (median 4.7 CPU-minutes); peak memory of
the whole process tree is about 4 GB.

Stage budgets (`VALIDATION_STAGE_BUDGETS`, JSON map, seconds): code default
1200 s for `generate_signatures`, `identify_molecules` and `verify_results`,
`VALIDATION_STAGE_BUDGET_DEFAULT_S` (900 s) for the other stages. The web
application's worker (`bat3-ui-worker`) raises identification to 4500 s,
because its configuration searches more databases.

## Reading a results.json

Campaign results are ordinary `results.json` files (one per deposit and
label); their structure is described in the
[results.json reference](results-json.md). For campaign analysis the
branches that matter most are `pipeline.code_version` (which build produced
the file), `tasks` (stage statuses), `stage_errors` (bounded per-molecule
failure records: a database or generator that failed shows up here, never
only in the log) and `verification/<molecule>/verified_hits`.

### The verified_hits table

Stored order **is** display order. Each record carries

- `identifier`, `ident_type` (`PDB_ID`, `UNIPROT_ID`, `PUBCHEM_CID`,
  `CHEMBL_ID`, `CHEBI_ID`, `ALPHAFOLD_ID`, `ELEMENT`, …), `database`, `name`,
  `organism`, `hit_type`;
- `final_confidence` (0–100) and its terms: `belief` / `resolver_score`
  (database agreement), `similarity_score` with `similarity_details`,
  `annotation_quality_score`; for chemicals `skeleton_sim` and
  `skeleton_method`;
- `supporting_evidence_count` (distinct sources), `equivalence_class_id`
  (rows describing the same structure; the UI collapses them);
- `is_verified`, and for rejected candidates `rejection_reason`:
  `fingerprint_mismatch`, `fingerprint_unavailable`, `below_similarity_floor`,
  `below_threshold`, `verification_failed`, `no_worker`,
  `similarity_unmeasured`, `water_duplicate_identity`;
- `ground_truth_override` (`element_monoatomic`, `water_triatomic`) where
  the confidence was set to 100 by rule;
- `verified_without_corroboration`: a non-chemical identity hit that
  verified without any similarity measurement (see below).

!!! note "What `is_verified` means"
    A candidate is verified when its confidence is at least
    `min_final_confidence` (0–100; default 0, so in practice no gate) **and**
    there is positive evidence: chemical candidates need skeleton-fingerprint
    Tanimoto ≥ 0.7; other candidates need a non-degenerate similarity
    measurement, or an identity claim from the database search. In the last
    case (F-17, ruled 2026-10-04: identity stays identity) the hit is flagged
    `verified_without_corroboration: true`; the flag changes no score or count.

## Re-runs

- Web/API runs: `POST /runs/{id}/rerun` creates a new run with a new id.
- Campaign runs: re-dispatch with the same label after moving the result
  aside (see above), or under a new label.
- A restarted run re-executes the context chain (discover → load → repair →
  unwrap → analyze) and export, and skips `generate_signatures`,
  `identify_molecules` and `verify_results` only where their persisted status
  is exactly `success`. `PIPELINE_RESUME_STAGES=0` forces a full run.
- Never re-run part of a campaign while workers run different images
  (era-unity rule).
