# Operations

Running the fleet day-to-day; failure taxonomy; when to worry.

## Fleet layout (steady state)

- 1× validation-api (control plane brain: dispatch gate + settle + sweep)
- 164× validation-worker, 15× ceitec-worker, 2× ui-worker — all on one image
  (`bat3-validation-api:v3.125-N1`), `--concurrency=2 --prefetch-multiplier=1`
- 2× static UIs, postgres, redis (single broker `bat3-redis`; the second
  `bat3-ceitec-bat3-redis` is dormant at 0/0 — F-13)

## The three background loops (validation-api)

| Loop | Cadence | What it does | Failure signature |
|---|---|---|---|
| Dispatch | 15s | claims `queued` rows (SKIP LOCKED), creates bat3_runs, sends celery tasks; gated by `VALIDATION_DISPATCH_ENABLED=1`, throttle 4–12/tick | queue grows while workers idle → check gate env + api logs |
| Completion + truth-settle | 30s | celery metadata settle; NFS-truth settle (all stages done in results.json, mtime ≥ start−600s, file ≥15min old) | stuck `processing` with done results.json — check NFS mounts/clock skew |
| Stale sweep | 30s | >`VALIDATION_STALE_HOURS`(12h) `processing` rows → requeued; runs → failed; counters reconciled | repeats of the same entries = pathology class below |

## Known failure classes (from the incident registry)

| Class | Symptom | Mechanism | Response |
|---|---|---|---|
| Broker wedge | throughput collapses, 0 restarts | cluster middlebox keeps dead TCP ESTABLISHED | fixed in code (socket timeouts, keepalive, health checks); visibility_timeout=6h |
| Poison entries | worker OOMKills | multi-GB pipelines × prefetch | prefetch=1, concurrency=2 (fixed) |
| Stalls | stages parked hours | resolver/fetch fan-out | stage budgets (fixed); budget warnings are searchable |
| Stragglers (pathological) | same entries requeue every 12h indefinitely | **sweeper has no retry cap** (F-05); underlying cause = per-entry hard hangs outside budgeted stages | manual triage cohort; a stale-cycle cap + quarantine is pending decision |
| Clock skew (NFS vs pods, ~7200s) | celery ETA warnings; settle delayed | NFS server clock ahead | benign for settle (conservative); keep in mind when reading mtimes |
| Replay-vs-serve 404s | offline replay "invalid entry_id" | derived payloads not under served input/ (V-22) | prove wire changes publicly, separately |

## Rollout procedure (era rule)

1. Build & push a single image tag; never mix tags across worker classes.
2. Update **apis first** (they only dispatch), then validation-worker fleet,
   then ceitec workers, then ui-worker — last executor class finishes the era flip.
3. Verify: pod image uniform, `config_shared.ini [pdb] deployment_file_url`
   matches the serving instance, public smoke (a `/files/validation-...` GET 200
   + an RCSB 204 fetched-ok POST).
4. Keep rollback: deployment yamls snapshotted pre-change (`.tmp/w6b/*.bak.yaml`).

## Health checks worth running weekly

- `kubectl get deploy` — all ready, image uniform
- Queue: no batch stuck `running` with all rows terminal; straggler requeue count flat
- `stage_errors` volume sample (dead-channel early warning — the N1 lesson)
- sim_cache growth on NFS (no TTL — watch capacity)
- Log scan for `[SPIN_DEBUG]` noise level and `stage_time_budget` frequency trend

## Current parked decisions (owner: project lead)

- NA-mode RCSB containment (dead-by-design attempts → short-circuit?)
- W10 all-class RCSB-benefit requeue (expected yield bounds from audit:
  channel serves protein-only entries, 10-row truncation)
- Audit fix queue F-01…F-28 dispositions (see `docs/CHEMISTRY_FIX_TODO.md`,
  FINAL AUDIT section)
