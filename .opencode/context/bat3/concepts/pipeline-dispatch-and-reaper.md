<!-- Context: concepts/pipeline-dispatch-and-reaper | Priority: high | Version: 1.0 | Updated: 2026-10-19 -->
# Pipeline Dispatch Model & Crash Robustness (OQ-16 era)

How a run becomes work, what kills it, and what stops zombies.
Sister records: V-30/V-31 in errors/common-issues.md, OQ-16 in
docs/CHEMISTRY_FIX_TODO.md.

## Dispatch model (src_new)
- POST /api/v1/runs → writes runs/<id>/ (input, config.ini, results.json
  status=queued) → run_pipeline_task.apply_async(task_id=run_id), optionally
  routed to queue VALIDATION_UI_QUEUE=validation.ui.celery (UI lane = 2
  ui-workers; the 15 ceitec workers consume the default queue; BOTH fleets
  run the same v3.13x image and join the same broker bat3-redis).
- ONE celery task drives the ENTIRE pipeline in-process (thread-pool per
  stage), i.e. the task IS the run; its hard death = the whole run dies
  mid-stage. Stage sub-steps are functions, not broker tasks.
- Verify stage fans out per-segment temp ResultsManagers (identifiers +
  signatures + universe/segments/<seg>/properties as of 9ba873ec8 — V-30
  taught that minimal-payload workers silently drop run-wide facts).

## Ack / crash semantics (celery_app.py)
- task_acks_late=True + task_reject_on_worker_lost=True (since v3.136):
  broker redelivers hard-killed pipeline tasks within visibility_timeout
  (6h cap to protect long runs from mid-flight redelivery). Replay-safe:
  stages re-execute and overwrite their results.json sections.
- Before v3.136 (default early-ack) = silent tombstones on ANY hard kill.
- worker_prefetch_multiplier=1 pinned (OOM storm history, 2026-09-22).
- Broker sockets hardened for CERIT middlebox stalls (socket_timeout 180,
  health_check 30) — docstring in redis_broker_transport_opts().

## Crash taxonomy (observed, 2026-10)
- SIGBUS exit 135 on ui lane (3x within 5h, 2026-10-13): blast_core_nt vs
  NFS-backed PVC org.democratic-csi.nfs-client → NFS stall → mmap page
  fault can't be satisfied → bus death, NO traceback. New then because the
  NT-blast path only went live with the v3.134 blastp restore.
  Mitigations live: BLASTDB_MEM_MAP=0 (mmap→read(), io errors catchable)
  + faulthandler SIGBUS all-thread dump armed (next crash leaves a stack).
- CPU wedge (OQ-15, open): amber coords generate_signatures spins 1 core
  20+ min on synthetic unnamed-residue fixtures; pod restart to release.
- Half-dead broker flows: see transport-opts docstring (2026-09 wedge).

## Zombie-run reaper (src_new/api/run_reaper.py, v3.136)
- FastAPI lifespan background task; Redis leader lock
  `bat3:run_reaper:leader` (px=1.5×interval; one sweeper across --workers 4).
- Every 300s (BAT3_RUN_REAPER_INTERVAL_S): runs whose pipeline.status ∈
  {running,queued} AND run_id ∉ fleet live tasks (inspect
  active+reserved+scheduled) for 2 consecutive sweeps → finish_run failed +
  critical error code worker_lost + event. Terminal runs untouched; 2-miss
  hysteresis; no auto-redispatch (poison inputs would thrash) — operator
  reruns via /runs/{id}/rerun (inputs persisted).
- Env: BAT3_RUN_REAPER=0 disables. Smoke/e2e: tests/src_new/api/test_run_reaper.py.

## Fast diagnosis playbook (queue "stuck")
1. kubectl get pods (all Ready?) → 2. celery -A tasks inspect active/reserved
   (empty everywhere?) → 3. API runs?limit= for non-terminal older than stage
   norms → 4. Redis keys: real queue lists missing entirely + dangling
   unacked_index member scored at victim's enqueue = task-loss signature →
   5. kubectl logs <pod> --previous + .lastState.terminated (exit 135 SIGBUS,
   137 OOM). Remedy: POST cancel zombies; cancel+rerun for message-less
   queued runs. Since v3.136, the reaper does this automatically; manual
   path remains for retained-history forensic reads only.

## Image/discipline lessons applied
- V-28: ceitec api pins command/args src_new.api.main:app (shared image CMD
  = validation main:app; chart now pins too).
- V-29: post-build package-content gate (`docker run --rm img which blastp`,
  dpkg diff vs previous tag); canonical Dockerfile.full lives IN repo.
