# Running validations

Three submission surfaces, all funnelling into the same `validation_queue` table
unless noted:

| Surface | Where | Use for |
|---|---|---|
| Validation UI | `https://validation-ui host` | Interactive browsing, batches, rerun/retry buttons |
| Queue REST API | validation-api `/api/queue/*` | Scripted batches (`POST /api/queue/files`, bulk actions) |
| Interactive runs | ceitec API `POST /runs` (or `/api/v1/runs`) | Ad-hoc uploads outside the campaign queue |

## What a single run costs

- Contract: ~10 minutes per entry on a healthy worker (heavier systems longer).
- Per-stage wall-clock budgets (defaults: signatures/identify/verify 1200s each,
  other stages 900s) cap worst-case burn; a stage that hits its budget records a
  `stage_time_budget` warning and continues with partial output.
- Dispatcher concurrency is throttled (`VALIDATION_DISPATCH_CONCURRENCY`, default
  12 per 15s tick in code; production sets 4).

## Lifecycle states (queue row)

`queued → processing → completed`
&nbsp;&nbsp;`↘ failed` (dispatch exhausted retries or explicit failure)
&nbsp;&nbsp;`↘ requeued by 12h stale sweeper` (see Operations § stragglers)

Entry-level mirror states live on the entries table; batch counters are
recomputed by the sweeper (never trust stale counters mid-run).

## Reading a results.json

Top-level branches (all paths slash-delimited):

| Branch | Content |
|---|---|
| `pipeline` | run status/timestamps, config snapshot, input files |
| `tasks` | per-stage status (`success`/`warning`/`failed`/`skipped`), summaries |
| `signatures/<segment>/generated/<generator>` | raw signature strings the fragment produced |
| `identifiers/<segment>/<generator>/<resolver>` | resolver output: `hits`, `hit_type` (`identity`/`similarity`), metadata |
| `identifiers/<segment>/<generator>/attempted` | resolver names actually attempted |
| `verification/<segment>/verified_hits` | **ranked final table** (see below) |
| `stage_errors/signatures/<segment>`, `stage_errors/identifiers/<segment>` | bounded failure records (observability contract) |
| `warnings`, `critical_errors`, `events` | run journal |

### The verified_hits table

Stored order **is** display order (backend owns ranking). Each record:

- `identifier`, `ident_type` (PDB_ID / UNIPROT_ID / PUBCHEM_CID / CHEMBL_ID / ...)
- `is_verified` — see semantics note below
- `final_confidence` (0–100), `resolver_score`, `similarity_score`,
  `annotation_quality_score`, `skeleton_sim`
- `supporting_evidence_count` (distinct resolvers), and for rejected candidates
  `rejection_reason` (`verification_failed`, `no_worker`, `fingerprint_mismatch`,
  `fingerprint_unavailable`, `below_threshold`)

Chemical candidates additionally pass a hard skeleton-fingerprint gate
(Tanimoto ≥ threshold against the simulated molecule); structure-blind floods
are re-ranked by skeleton similarity before the verify window is cut
(raise-only: chemistry can only be rescued, never demoted).

!!! warning "`is_verified` semantics (F-17)"
    `min_final_confidence` defaults to `0.0`, so the aggregate-confidence gate is
    **vacuous**. For non-chemical *identity* hits, `is_verified` currently means
    "a resolver classified this as an identity match" — corroboration failure
    (fetch/worker outage) does not flip it to false; only `similarity_score: null`
    betrays the case. Chemical identity always requires the skeleton gate.
    Treat `is_verified` + null `similarity_score` as "verified on
    self-assertion". A hardening change is pending decision.

## Re-runs and reprocessing

- Re-queueing an entry creates a **new attempt with a fresh timestamped run id**;
  old artifacts remain on NFS until cleaned (results.json is overwritten on the
  next attempt).
- `skip_if_output_exists` stage caching applies within a run directory only.
- A restarted run (≥ v3.126-audit2) re-executes the **context chain**
  (`discover→load→repair→unwrap→analyze`) plus `export`, and **skips**
  `generate_signatures`/`identify_molecules`/`verify_results` *only* where the
  persisted status is exactly `success` — the expensive resolution compute is
  what resume saves (measured 45s → 15s on a completed entry). Warning/failed/
  pending statuses always re-execute. Disable via `PIPELINE_RESUME_STAGES=0`.
- Never requeue while any worker runs a different image era (era-unity rule).

## Where to watch progress

- UI dashboard (queue counts, batch progress, failure analysis)
- `GET /api/queue/status`, `/api/queue/worker-stats`, `/api/stats/throughput`
- Logs: API pod (dispatch/settle/sweep lines), worker pods (stage logs;
  `stage_time_budget` and resolver-failure warnings are searchable).
