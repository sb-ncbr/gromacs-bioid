# BAT3 Validation Rerun Playbook

State of world 2026-09-23. Written after the September campaign so a rerun (or
scale-up/requeue) does not re-burn days on already-solved infrastructure classes.
Read `docs/CHEMISTRY_FIX_TODO.md` for the metric history; this file is ops-only.

## 1. Preflight — check BEFORE any rerun/requeue (10 min, saves days)

| # | Check | Healthy | If not |
|---|-------|---------|--------|
| 1 | `kubectl get pods` worker fleets | all `Running`, restarts steady (0 growth/day) | chase restart reason first (describe → OOMKilled = memory class §3b) |
| 2 | `redis-cli llen celery` | 0 | claims exist but not consumed → consumers dead/deregistering |
| 3 | Fleet receipts: `logs $P --since=5m \| grep -c "Task .* received"` across a few worker pods | >0 when entries run | 0 receipts fleet-wide with `unacked>0` = vaporization class §3c |
| 4 | Completion meter: `validation_queue` completed delta over 30 min | growing | flat + receipts >0 = swallowed-crash class §3a (DO THIS FIRST) |
| 5 | results.json all-stages-done rate on last-12h mtimes | >60% of recently-touched | <5% = crash-resume loop §3a |
| 6 | PUG reachability from cluster (IDSM fallback knob) | 200, or `VALIDATION_SKIP_PUG=1` set on replays | 503 = cluster-IP blocked (standing) |
| 7 | NFS caches warm: `/data/validation/sim_cache/inchikey_smiles` key count | ≈2.7k+ growing | GT structure fetches will burn hours and `fingerprint_unavailable` residue returns |
| 8 | `bat3_runs` stale: running rows older than 3h | 0 | sweep §4.2 before dispatching more |
| 9 | Poison list: entries with `error_message LIKE '%non-linear%'` / always-fail loops | all `failed` | sweep skips only `failed`; one missed poison = fresh OOM storm |
| 10 | Sim engine pair cache (`sim_cache/pair_cache`) | 881k+ | `--sim` recomputes will take hours more than they should |

## 2. Image & fleet truth (as of 2026-09-23)

- `bat3-worker:v2.32` → bat3-ceitec-bat3-worker ×15, bat3-ui-worker ×2(ui queue only)
- `bat3-validation-api:v3.113` → validation-api ×1, validation-worker ×15
- Worker CLI (deployment-pinned, beats image CMD):
  `celery -A src_new.celery_app worker --loglevel=info --pool=threads --concurrency=2 --prefetch-multiplier=1`
  (validation-worker: `-A tasks`; ui: adds `-Q validation.ui.celery`)
- Resources both worker pools: requests 2CPU/12Gi, limits 4CPU/20Gi (15 replicas ≈ same
  cluster budget as 30×10Gi; rule: scale RAM by trading replicas, never by adding total)
- Build/push: `docker build -t cerit.io/tomsko/bat3-<worker|validation-api>:vX.Y -f Dockerfile.<worker|api> .` from repo root, on this workstation; deployment image tags set via strategic-merge patch.

## 3. Failure classes that burned days (detection → fix)

### 3a. Swallowed step-crash → crash-resume loop ("zero completions" cork)
- Cause template: an exception inside a pipeline step (e.g., AttributeError from
  dead-code-after-return in an ABC `__init__`) is swallowed by the executor into
  results.json events; task exits clean; entry resumes, redoes minutes of loading,
  crashes at the same step — forever, invisibly from celery.
- Detect: §1#4+#5. Grep the events stream of any recent results.json for the traceback.
- Fix: code fix + image bump, then requeue the crashed-but-resumable entries
  (queue rows `failed` → `queued`; they RESUME at the failing step — results.json on NFS).
- Historical: enabled_similarity cork 2026-09-20→23 (commit 2dfd5fdcb).

### 3b. OOM classes
- Stacking: threads pool + default prefetch → N×16 msg buffer per pod. Cured:
  prefetch=1 + concurrency=2 everywhere (durable in `celery_app.py` + CLI pins).
- Per-task spike: ~76.5k-bond no-CONECT systems (fasta_map always-fails class).
  2-minute 20Gi deaths possible; currently rare. Action when repeated: fail the
  entry permanently (§4.3), plan cheap-fail topology guard.

### 3c. Rollout-during-dispatch vaporization
- Never roll worker deployments while a dispatch batch is in flight (restore at
  visibility_timeout is lossy). If forced: sweep §4.2 immediately after.
- Combine ALL fixes+resource changes into one rollout per incident.

## 4. Standard operations (repo-native, use them — don't hand-roll SQL)

### 4.1 Dispatcher / intake
- Runs in validation-api, ticks 15s, claims ≤12/tick (`VALIDATION_DISPATCH_CONCURRENCY`),
  intake workers 16. `VALIDATION_DISPATCH_ENABLED=0` pauses intake without touching workers.

### 4.2 Reclaim stale/zombie claims (safe, idempotent)
On validation-api pod:
```python
from sqlalchemy import create_engine; from sqlalchemy.orm import sessionmaker
import os, queue_processor
e = create_engine(os.environ['DATABASE_URL'])
db = sessionmaker(autocommit=False, autoflush=False, bind=e)()
stats = queue_processor.sweep_stale_validations(db, stale_hours=1)  # 24h is prod default
```
Always: fail poison ALWAYS-FAIL entries first (sweep requeues anything 'processing').

### 4.3 Failing a poison entry permanently
Set `bat3_runs.status='failed'` (+error_message, completed_at),
`validation_queue.status='failed'` (+last_error), `mddb_entries.status='failed'`
for that entry id — all three tables, or the sweeper/dispatcher resurrects it.

### 4.4 Replay/re-verify waves (post-fix measurement runs)
- Tool: `scripts/replay_verification.py` (in coverage: `--entries-file`, `--threads`, in-loop write block).
- NFS copies/lists/logs; idempotent; resume = `tail -n +(lastMarker+1)`.
- Launch: `setsid nohup env VALIDATION_SKIP_PUG=1 python3 replay_verification.py --entries-file X --threads 4 > LOG 2>&1 </dev/null &` on a worker pod; jobs die with pods — never co-schedule a wave with a pending rollout.
- threads=4 with a 2-slot celery pod is the proven safe coexistence.

### 4.5 Metrics
- Rank audit: `/data/validation/rank_audit_fresh2.py` (read-only, ~1 min, needs sim_cache).
- S7 recompute: `python3 /data/validation/campaign_stats.py --full --sim` on a worker pod
  with `DATABASE_URL` exported (from validation-api env). 1–4h; log is the artifact; JSON at end.

## 5. Healthy-signal dashboard (what "working" looks like)
- receipts/min fleet-wide ≫ 0 during dispatch; `llen celery` = 0 (slot-bound), unacked small.
- Completed meter grows ≥ intake over time; per-entry wall ~10–60 min heavy class.
- Worker memory: single-digit Gi steady; >15Gi sustained = watch.
- results.json all-stages-done rate on fresh files ≈ success rate.
- Replay waves: `[N/total] SECONDSs` markers advancing.

## 5b. Replay/resume mechanics added 2026-09-23

- **strip_for_reidentify.py** (`scripts/`): flips `tasks.{identify_molecules,verify_results,export_results}.status` to `'failed'` atomically in results.json; executor resume re-executes only those stages on the next natural dispatch (upstream `success` stages stay skipped). This is THE production-native redo for broken identify/verify — do NOT build custom resolver harnesses; resolver DB paths (`databases/`) resolve via CWD inside pods only.
- After stripping, requeue = queue rows to `queued` + entries to `pending`; dispatcher creates fresh runs (~12/tick). Messages persist in redis db0 across incidents.
- **Offline-PUBCHEM fallback stack live** (`src_new/identification/resolvers/`): `inchikey_self` (InChIKey signature is itself an identity candidate; no network) + `formula_chembl` (EBI REST exact-formula -> CHEMBL_ID; gated by `identifiers.formula_chembl` in config or `VALIDATION_SKIP_PUG=1`). Production config: enabled in `config_shared.ini`.
- **Zombie-client freeze class**: after network resets, check `redis-cli client list` idle histogram BEFORE assuming pipeline stall; `CLIENT KILL id` zombies, else `rollout restart` both worker pools (messages persist).

## 5c. Lessons 2026-09-24 (mirror day)

- **Consumer wedge survives client-side keepalive**: after the keepalive rollout,
  a second CERIT reset wedged workers inside BRPOP on dead half-flows (middlebox
  keeps them alive client-side). Server-side floor: `redis-cli CONFIG SET timeout 60`
  reaps idle-blocked clients in 60s (verified 32->2). Wedged workers do NOT
  self-recover even when their conn is closed - remedy is still `rollout restart`
  both worker deps. TODO: k8s liveness watchdog (probe = "tasks completed in N min").
- **celery redis transport is FIFO**: requeued/proof entries wait at the back of
  the list; for instant proof exec the same code paths in-pod instead of a run.
- **Requeue-before-drain double-runs**: flipping 'processing' rows while their
  messages still sit in the list creates duplicate runs on one entry (idempotent
  stages save correctness, but avoid when possible - flip only 'failed'/'completed').
- **PubChem mirror ops**: DB at /app/databases/pubchem/current/ (symlink); rebuild
  via `scripts/download-databases.sh pubchem`; parity via scripts/check_pubchem_parity.py
  (fixture captured from clean IP); ops CLI scripts/pubchem_lookup.py.
- **broker timeout 60 is runtime-only** - redis has no persistence; persistence to
  deployment args is folded into the next planned maintenance (with dispatcher pause).

## 6. Current frontier (post-verdict, 2026-09-23)

- inchikey validated@10 = 19.0% purified to an era artifact (PUG block since
  09-12). Legacy reid wave (3,367) rehabilitates in-flight; success marker:
  identify-done -> 100% chem candidates. Watch completion + recompute.
- Rerank = solved (audit: evidence@1 wins everywhere) — do not invest there.
- Watch-class: rare 2-min 20Gi OOM deaths on the monster topology class.
- Registry: `/home/tomsko/work/bat3_validation/docs/INCIDENT_REGISTRY_2026-09.md` sessions 1–16.
