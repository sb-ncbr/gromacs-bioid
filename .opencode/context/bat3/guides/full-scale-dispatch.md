# Guide: Full-Scale Validation Dispatch (all ~14.4k MD sims)

## Core Concept
Kickoff procedure for processing the full validation queue with the fixed pipeline. Queue is READY; dispatch is gated OFF by default. Enable, monitor, and control with the commands below. Context: incident remediated 2026-09-10 (see `../errors/common-issues.md`, registry doc).

## Pre-flight (verify before enabling)
```bash
kubectl rollout status deployment/validation-api -n ceitec-biodata-ns          # healthy, APScheduler ticks in logs
kubectl exec <bat3-worker> -- ls /app/databases/pdbaa | head -3                 # BLAST DBs visible
kubectl exec <worker-pod> -- test -f /data/validation/config_shared.ini         # tuned config present
kubectl exec validation-postgres-... -- psql -U validation -d bat3_validation \
  -c "select status,count(*) from validation_queue group by 1"                  # ~14.5k queued
```
Also confirm worker image is current pinned tag (see `lookup/ceitec-deployment.md`; post-GO pins: worker **v2.14**, validation-api/validation-worker **v3.86**) and NFS has headroom (`df -h /data/validation` in a worker).

Entry-dir write precondition (learned 2026-09-10, P2-12): `input/` dirs must be o+w and both celery pools must share one uid (uid 1000). If a fresh perm wave appears, re-run the sweeps from `../errors/common-issues.md#p2-12`.

## GO
```bash
kubectl set env deployment/validation-api VALIDATION_DISPATCH_ENABLED=1 -n ceitec-biodata-ns
kubectl rollout status deployment/validation-api -n ceitec-biodata-ns
# watch it start claiming + sweeping:
kubectl logs -l app=validation-api -n ceitec-biodata-ns --tail=50 -f | grep -E "Dispatch|sweep|started"
```

## Expected behavior
- Intake: up to 5 claims per 15s tick (downloads then celery dispatch; `input/` skipped when already present and non-empty). Dead downloads fail terminal-fast as `project_not_found` — they are real upstream gaps, not bugs
- Throughput: 120 celery slots (20 bat3-workers ×4 + 10 validation-workers ×4, same queue); observed peak ~10 completions/min during GO#2; downloads dominate intake early. Worker logs are DEBUG-flooded — grep server-side, never by eye
- Download-needed entries: ~3.8k of 14.4k (10.8k already on NFS) — first hours are download-heavy
- Metrics land per-entry `results.json`; hit@K later via `offline_hit_k.py --pattern results.json --write-db`
- Batches (67/68 "running") complete via sweeper counters as items settle

## Monitoring
```bash
kubectl exec <postgres-pod> -- psql -U validation -d bat3_validation -c "
  select status,count(*) from validation_queue group by 1"                  # queue drain
kubectl exec <bat3-worker> -- python3 -c "
import redis;r=redis.Redis(host='bat3-redis.ceitec-biodata-ns.svc.cluster.local',port=6379,db=0);print('depth',r.llen('celery'))"
kubectl logs -l app=validation-api -n ceitec-biodata-ns --tail=20 | grep -E "error|Error"  # dispatch errors
```

## Safety valves
- Pause intake: `kubectl set env deployment/validation-api VALIDATION_DISPATCH_ENABLED=0 -n ceitec-biodata-ns` (in-flight runs finish)
- Throttle: scale workers `kubectl scale deployment bat3-ceitec-bat3-worker --replicas=N -n ceitec-biodata-ns`
- If failures spike: check signatures in `../errors/common-issues.md` (cache corruption, EPERM waves, DB-mount loss)

## After the run
- Re-score: `offline_hit_k.py --pattern results.json --write-db` (bat3-worker pod)
- Update `lookup/status.md` + registry log
- Decide retention: keep inputs? cleanup policy (P2-3)
