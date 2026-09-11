---
description: Live BAT3 validation campaign statistics from ceitec-biodata-ns (pulse SQL, S1-S6 full scan, detached S7 similarity scoring). Runs kubernetes as a subtask; read-only.
agent: kubernetes
subtask: true
---

Collect live BAT3 validation campaign statistics. This is READ-ONLY monitoring: never requeue, patch, delete, or modify cluster/DB/NFS state.

Mode (from $ARGUMENTS, default: `pulse`):
- `pulse`   - quick SQL counts only (seconds)
- `full`    - campaign_stats.py --full (S1-S6 + NFS results scan, 1-8 min, foreground kubectl exec)
- `sim`     - launch campaign_stats.py --full --sim DETACHED via nohup in-pod (adds S7 similarity hit@K; ~10 min), then report launch PID
- `log`     - tail the detached sim log and report progress/final S7 section
- `entry N` - campaign_stats.py --entry N drilldown for a single entry

Cluster facts:
- Namespace: ceitec-biodata-ns (context kuba-cluster)
- Stats script lives on NFS at /data/validation/campaign_stats.py; run inside deploy/validation-api (has the /data/validation mount and the NFS cache dirs)
- Postgres: kubectl exec deploy/validation-postgres -- psql -U validation -d bat3_validation (user/db come from secret validation-postgres-secret; password not needed in-pod)

Mode recipes:

pulse:
  kubectl exec deploy/validation-postgres -n ceitec-biodata-ns -- psql -U validation -d bat3_validation -c "SELECT (SELECT count(*) FROM validation_queue WHERE status='queued') AS queued, (SELECT count(*) FROM validation_queue WHERE status='processing') AS inflight, (SELECT count(*) FROM validation_queue WHERE status='completed') AS completed, (SELECT count(*) FROM validation_queue WHERE status='failed') AS failed, (SELECT count(*) FROM bat3_runs WHERE status='completed' AND started_at > now()-interval '1 hour') AS done_last_hour, (SELECT count(*) FROM bat3_runs WHERE status='failed' AND started_at > now()-interval '1 hour') AS failed_last_hour;"

full:
  kubectl exec deploy/validation-api -n ceitec-biodata-ns -- python3 /data/validation/campaign_stats.py --full
  (If the frontend truncates long output, rerun ending with: | tail -80)

sim (detached; foreground --sim would block too long):
  kubectl exec deploy/validation-api -n ceitec-biodata-ns -- sh -c 'cd /data/validation && nohup python3 campaign_stats.py --full --sim --json-out /data/validation/stats_full_sim.json > /data/validation/stats_full_sim.log 2>&1 & echo "launched pid $!"'

log:
  kubectl exec deploy/validation-api -n ceitec-biodata-ns -- sh -c 'tail -40 /data/validation/stats_full_sim.log'
  Finished reports end with: "JSON written to /data/validation/stats_full_sim.json". If that line is present, also show the S7 section: grep -A8 "S7 SIMILARITY" the log.

entry N:
  kubectl exec deploy/validation-api -n ceitec-biodata-ns -- python3 /data/validation/campaign_stats.py --entry N

Report format for the caller:
- Quick pulse table (queued/inflight/completed/failed, last-hour done+failed, implied runs/min)
- For full/sim: the key sections (S1 pace, S2 failure taxonomy, S3 export deep-reach %, S4 molecules/entry + verified-rate, S5 exact hit@K, S7 similarity validated@K when present), not raw dumps
- Flag anomalies: failed_last_hour > ~10% of done_last_hour, new failure-taxonomy classes, inchikey att% not climbing over days, S7 pdb validated@1 < 90%
- Remind the caller: S5 exact hit@K is a pessimistic lower bound; S7 similarity is the quality number that matters
- ETA printed by the script uses the 24h window and is distorted after incidents; prefer last-1h rate

Mode requested:
$ARGUMENTS
