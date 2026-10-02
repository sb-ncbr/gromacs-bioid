# Common Issues — Validation Incident Signatures (2026-09)

## Core Concept
Failure signatures from the Sept-2026 incident (P0-1..P0-6, P1 family), how to detect and fix. Full log: `bat3_validation/docs/INCIDENT_REGISTRY_2026-09.md`.

## P0-1: BLAST "database not found" but PVC Bound
- Signature: results.json warnings `identifier_resolver_failed ... BLAST database not found at /app/databases/...`; `ls /app/databases` empty in worker
- Cause: helm chart templates ignored `storage.*.existingClaim` → mounted auto-created empty PVC, real DBs in legacy claim
- Fix: templates honor `existingClaim` (chart ≥0.1.1); check `helm get values -a` + template `--dry-run` claimName output
- Verify: `kubectl exec <worker> -- ls /app/databases/pdbaa | head`

## P0-4/P1-11: Zero hits with "identified: true", no warnings
- Signature: pipeline success, `verified_hits=[]`, identify step finishes in seconds, no errors
- Cause: resolvers `tempfile.mkstemp(dir=working_directory)` → PermissionError on non-writable run dir (uid mismatch) → swallowed by base generic except
- Fix: `safe_tmp_dir()` (falls back to system temp) + `_last_error` surfaced as `identifier_resolver_failed` warning (worker ≥v2.12)

## P0-5: Every resolver fails with "file is not a database"
- Signature: ALL resolvers (even non-BLAST) error `file is not a database` after parallel campaign starts
- Cause: shared `resolver_cache.sqlite3` on NFS corrupted by concurrent writes (WAL over NFS = never safe)
- Check: `sqlite3.connect cache; PRAGMA integrity_check` → error
- Fix: per-pod caches (`identifiers_cache.directory` empty in config); never share sqlite over NFS; archive corrupt file

## P0-6: Proteins silently invisible to identification (no attempt recorded)
- Signature: identifiers block has NO attempted entry for sequence signatures; manual blastp of the signature finds perfect hits
- Cause: `_is_applicable` alphabet gate rejected the whole protein over ONE non-standard char (`X` from unknown residues is routine)
- Check: `invalid_chars = set(seq) - valid_aa` non-empty on affected sigs
- Fix: tolerant gate (>50% invalid → reject) + sanitize to wildcard before blast (worker ≥v2.13)

## P1: Scheduler state corruption
- Zombies: `bat3_runs` stuck 'running' (celery result keys expire ~24h → never observed). Fix: `sweep_stale_validations()` in 30s tick
- Duplicate runs per entry (pairs 1-3s apart): was double background thread + unlocked SELECT. Fix: single thread, `FOR UPDATE SKIP LOCKED`
- Failed rows with empty `last_error`: was `pass # error_message not available`. Fix: errors persisted everywhere
- Batches stuck "running" with 0 done: counters only moved on successful redis reads. Fix: sweeper recomputes from queue rows
- Entry/queue/run counts divergent: models lacked mapped columns the migration added (`run_id`, `retry_count`, `last_error`). Fix: models synced

## Session 2 (full-scale GO) signatures — P2-11..P2-16

### P2-11: 100% of download claims fail with upstream "404"
- Signature: every claim retries `download failed (attempt N)` fast; MDposit probe: `/projects/<canonical>` 200 + filenotes n>0, but logs show 404 on a DIFFERENT (legacy `local`) accession
- Cause: claimer remapped canonical `MD-A*` accession to the project's legacy `local` field before filenotes fetch
- Fix: direct canonical accession (v3.84); verify with `requests.get(f"{base}/projects/{acc}/filenotes")`

### P2-12: EPERM waves on `.part` / `results.log` / `results.json` across pods
- Signature: `[Errno 13] Permission denied` on files *just created by another pod*; `stat` shows different uid than the failing writer
- Cause: per-entry files written by TWO pools with different uids (bat3-worker=1000 vs validation-worker=65534) owning 0600/0644 artifacts + `input/` dirs at 2755
- Fix recipe: (1) `find /data/validation -maxdepth 2 -type d -name input ! -perm -o+w -exec chmod 777 {} +` (from 65534-owner pod); (2) files `a+r` then `o+w` same way; (3) unify both pools to one uid (deployments patched to uid 1000); (4) legacy 65534 leftovers → dedicated `kubectl run` pod at uid 65534 for the final chmod pass

### P2-13: `float32 not JSON serializable`
- Fix: numpy normalization in `src_new/utils/file_utils.py::_sanitize_for_json`
- Trap: BOTH celery consumer deployments run the same pipeline task — rebuild BOTH images (worker v2.14 + validation-api v3.86) or the stale pool keeps failing ~1/3 of items

### P2-15 (open): "failed" rows that aren't
- Signature: queue items flip to failed exactly at :27/:57 (sweeper ticks); entry's `input/` and `results.log` mtimes keep advancing afterwards
- Hypothesis: sweeper re-attaches stale Redis celery exceptions — VERIFY live file mtime / current run row before trusting or re-queueing a "failed" item

### P2-16: image built from dirty working tree
- Signature: crashloop `Could not import module "main"` right after a rebuild
- Cause: uncommitted WIP line `RUN mv /app/main.py /app/main.py.old` in `Dockerfile.api`
- Policy: `git show HEAD:Dockerfile.<x> > /tmp/… && docker build -f /tmp/<x>` — never build from the dirty tree

## 2026-09-11 wave signatures

### OOMKill churn on web-tier-sized workers
- Signature: pods flapping "missed heartbeat"→"joined the party"; `lastState.terminated.reason = OOMKilled`; thousands of zombie `bat3_runs.status='running'` while queue completions ≈0; celery depth 0 but nothing moving
- Cause: validation-worker sized at web tier (0.5-2CPU/4Gi) then put on BAT3 pipeline tasks (MDAnalysis multi-GB) → mass OOM; tasks die mid-flight, replicas reconsuen
- Fix: match payload sizing (validation-worker → req 1CPU/6Gi, lim 4CPU/10Gi as bat3-worker); zombies reclaimed with VALIDATION_STALE_HOURS=3 sweeps

### queue/runs accounting skews
- `bat3_runs.status='running'` alone ≠ in-flight: includes dispatch-killed tasks until the sweeper (30s tick, VALIDATION_STALE_HOURS threshold) reconciles; trust `processing` + celery depth for liveness
- completed_at batch-marks on :27/:57 seconds = sweeper tick artifacts, not run finishes

### Chemical class blind spot (fixed)
- One MoleculeInstance per topology segid → solutes/cofactors invisible in segid-coarse sims (membrane+solute under one segid); name/shorthand signatures parrot topology labels ("LIPID", "Protein in water"); computed fingerprints unconsumed by resolvers
- Fix: `LoadedUniverse._discover_virtual_segments()` (F1, worker ≥v2.15) + smiles coordinate-perception fallback (≤150 atoms)
- Known residual nits: `PUBCHEM_CID 0` junk hits pass verification (filter falsy ids); no structure-consuming lipid resolver yet

### Dockerfile.api HEAD poison (P2-16 variant, fixed)
- HEAD `Dockerfile.api` ITSELF contained `RUN mv /app/main.py /app/main.py.old` (stray commit `12bebebd1`): any image built from HEAD crashes (`Could not import module main`). "Build from HEAD snapshot" is unsafe for Dockerfile.api; the known-good snapshot (`/tmp/opencode/Dockerfile.api.fixed`) is the build source. Poison removed in `0a3079a79`.
- Rollout chown stall: worker pods took 15+ min in ContainerCreating -> kubelet chowning the entire 191k-file NFS pvc per pod. Fix: `fsGroupChangePolicy: OnRootMismatch` on worker deployments (rollouts now instant past pulls).

### Chemistry misidentification (root-caused + phase-1 fixed)
- Failure stack: bond perception garbage SMILES -> formula protonation drift (sim species vs neutral literature) -> formula fastsearch returns ~100-300 formula-mates -> verification `hit_type=="identity"` free-pass auto-verified ALL of them @conf40 -> chemical hit lists flooded with junk (att~84%, Tanimoto~0).
- GT frame class: MDDBR annotates prodrug (azilsartan medoxomil) while MD sim carries the active acid; not a pipeline error.
- Phase-1 fix pattern (worker>=v2.16, api>=v3.95b): skeleton_fp signature (H-scrub skeleton Morgan FP, tolerance like protein alignment), F7 verification gate (chemicals need skeleton-Tanimoto>=0.7 corroboration vs fetched candidate SMILES), F9 hfamily resolver (H+-4 formula candidates). Evidence: 2207 replay junk 0.14-0.28 rejected, acid 1.0, prodrug 0.73.
- Secondary crater OPEN: membrane lipids fragment into ~14-atom junk clusters (F11, parked).
- Ops: PubChem rate-limits the whole cluster egress after heavy waves (503 everywhere incl. trivial CIDs); ChEMBL unaffected. Mitigation shipped v3.96: min-interval requests, 429/503 backoff, batch CSV prefetch (50 CIDs/call), NFS smiles cache `_cache_read` reuse. Gate fails closed (fingerprint_unavailable) during outages and self-heals once cache warms / PUG recovers.

### NCBI/PUG pressure series (2026-09-12/13)
- IPv6 PUG endpoint blackholes cluster egress (name-503 vs literal-IP-200 identical URL): prefer_ipv4() installed in all PUG consumers (v2.19/v3.99)
- Sustained per-source-IP block by NCBI after heavy days (laptop 200 / cluster 503 even at 3s pacing): pacing cannot cure a standing block; only alternation to alternates does
- Structure source matrix (PUG-independent): CID -> NFS cache -> PUG -> IDSM SPARQL mirror (ELIXIR-CZ); InChIKey -> cactus -> chembl -> PUG; ChEMBL/CHEBI native
- Concurrency-side pressure: pubchem_struct + formula_pubchem disabled in config_shared.ini ini (heaviest POST consumers); workers reduced 40->16 to re-earn reputation
- Circuit breaker (VALIDATION_PUBCHEM_BREAKER=1) skips PUG-dependent resolvers when unhealthy
- Celery ghost fleet (P2-19): storm-era duplicate tasks re-executed after redeploys forgot revoke lists; 23.7k tasks purged, 5,181 NFS-truth completions settled; settle path itself needed MGET batching (api v3.98)

### Duplicate intake storm (P2-18, fixed)
- Signature: same accession `Downloading files` >=2x within milliseconds; `Key (run_id) already exists` bursts; `running` runs >> queue `processing`; S7 unmapped-pairs explosion; ~1 run/min ceiling despite idle fleet
- Cause: batch claim loop issuing N `SELECT ... FOR UPDATE SKIP LOCKED` in ONE transaction while `sessionmaker(autoflush=False)` keeps the pending status-UPDATE invisible to following SELECTs; SKIP LOCKED never skips locks owned by our own transaction -> same row claimed N times -> N threads download/race one entry's input dir
- Fix: claim-time reserve (`status='processing'` before commit) + claim-loop filter `~ValidationQueue.id.in_(claimed_ids)` + `_release_reserved_item` crash path (api >=v3.94)
- Cleanup pattern: per entry keep queue-linked (else newest) live run, `revoke(terminate=True)` the rest and mark failed; requeue race casualties (`Stale file handle` / `No such file or directory` / `.part` / `download_failed`) with `retry_count=0`

### Similarity-module dev traps
- Bio PairwiseAligner: `alignment.counts()` → AlignmentCounts object with `.identities` & `.aligned` ints (not dict, not `.identical`); PubChem Fingerprint2D = **base64** (not hex)
- Pair cache is append-only JSONL on NFS: stale wrong values persist — delete `sim_cache/pairs.jsonl` after fixing scorer logic (self-poisoning)

### Working over kubectl exec
- Long jobs: launch `nohup ... > /tmp/x.log 2>&1 &` (même when wifi drops, the process survives in-pod; kubectl exec ties dispgui stdio)
- Deploying scripts/writing file: policy layer blocks local writes often — heredoc via `kubectl exec -i pod -- sh -c "cat > path"` or base64-encode payload locally, `base64 -d | python3` in pod

## Ownership / NFS gotchas
- dirs/files split root/1000/65534, often 0600 → cross-service "Permission denied"; read via the pod with matching uid (validation-worker=65534, bat3-worker=1000)
- `results.json` modes vary by writer; analysis scripts may get EPERM on a subset
- Transient EPERM wave on `results.log` across 20 pods observed once (NFS attribute-cache timing); re-dispatch recovered

## Reference
- `../lookup/ceitec-deployment.md` — live facts
- `../guides/validation-reprocessing.md` — recovery workflow

### ChEMBL inchikey-search poisoning (fixed)
- `standard_inchi_key=<ik>` returned IDENTICAL bogus SMILES for unrelated queries (probe-proven country scale incl. ions): anything using it for GT structure fetches gets silently wrong truth. KEPT OUT of chains (only native CHEMBL_ID lookups retained). Legacy S7 low-sim waves partly attributed to this poison.
- GT charged-species InChIKeys (-Q/-S/-O/-J) miss on neutral registers: try the -N form first (92% coverage unlocked).

### Average-frame destruction (F13)
- PDB-only input dirs with time-averaged coordinates (average.pdb) break coordinate-based structure work: flexible rings smeared, perception produces wrong valences/aromaticity, skeleton sim vs GT ≈ 0.01 while formula stays correct. Instantaneous trajectory frame restores exact structure (sim=1.0). Fixed via trajectory frame-0 sourcing (loader v2.24+).

### Ion annotations vs organic GT metrics (M9)
- GT InChIKeys contain ions (Ca/Mg/Zn/Ni/K/Cl) at ~45% of the inchikey 'no molecule visible' class in fresh SSRs usefully wrong: organic structure similarity cannot see them and drags metrics. Ion GT entries must be presence-scored (element evidence in fragments.unique, e.g. `Cl=22`), not structure-scored. Classifier + route lives in scripts/gt_rules.py + S7 routing.


### Shared-celery fast lane (UI manual runs)
- Manual web-submitted runs die in thousands-deep shared-celery backlog; claim loop consumes them but execution FIFO delays hours. Lane built: dedicated `validation.ui.celery` + `bat3-ui-worker`. Activation path: dispatch claims batch_id LIKE 'ui%' AND portal sends endpoint-created tasks with `queue=validation.ui.celery` when `VALIDATION_UI_QUEUE` set.
- Rollback: `VALIDATION_UI_QUEUE=''` + `kubectl delete deploy bat3-ui-worker`. Campaign untouched by construction.

### Chronic silent freeze + task boot-loop (serious class)
- Pattern: celery consumers alive but silent ~30min+; consumers stop registering received tasks; log streams die; rolling restarts temporarily restore. Fixes shipped: keepalive env options for broker sockets, executor resume (PIPELINE_RESUME_STAGES=1 to skip completed stages).
- Residual open: despite resume on, completions still zero for long windows and celery backlog keeps inflating. Face-off tasks ahead: (a) find where pipeline tasks actually stop before export (stage-level timing), (b) cap intake to drainationally match computation, (c) observe worker thread-/task-level observability for heavy chemistry entries.

### R-state tar-pit freeze — NOT a broker freeze (root-caused 2026-09-20, fixed)
- Signature: pods "Running" + ~1 core CPU burning, but consumers deregister one by one; zero task execution, no crashes, no network errors, log file mtime goes dead hours-ago. Diagnosis: `/proc/1/task/*/stat` — ONE thread `state=R` for hours, utime ~wall-clock, IO counters flat; other threads waiting on futex.
- Cause class: a single unbounded C-library compute call inside ONE generator on `__v`-class fragments (RDKit kekulization in `smiles.py::Chem.SanitizeMol`; cell-level evidence: `[SPIN] SYSTEM__v4/smiles START` then never DONE; utime pinning ~15h+, utf8 glacier). Killed by smiles kekulization-elimination (partial sanitize + kekuleSmiles=False) in `fix(spin-class)` commit (v2.29/v3.111 lineage). Pods drained normally after.
- Confounder treasure: broken log-handler cross-wiring makes 4 entries' debug.logs share one writer (looks like "every entry is frozen", actually one stuck per slot).

### Data-loss via child-process isolation timeouts (wave-3.5 self-inflicted, reverted)
- Pattern: entries complete (stage green) with fully-empty signature/identification/verification blocks; results.log full of `isolated timeout (120s) for segment SYSTEM[__vN]; skipping generators for it`. Splices via: silent `continue` inside the isolation helper returning None.
- Fix: FULL REVERT (commit `1de6860e0`): no more segment isolation tampering; content regenerated immediately on redeploy (sig 28-47/entry, verified chemistry 73-300 res landing). Lesson: ANY "skip silently if guard trips" mechanism under load becomes a mass data-loss channel; failures must land errors not silent skips.

### Stage-level stall cascade (boot-loop engine, mitigated)
- Resolvers/verifier fan-out (hundreds per-entry HTTP) parked individual stages 1-4h+, collided with 12h sweeper: every attempt aborted at exactly 12h and re-queued (queue rows all matching CREATE/complete=invalid 12h deltas). Stage state per census: generate_signatures/verify_results/identify each hours-class.
- Mitigation: cooperative stage deadline at THREE depths (outer loop, verification manager per-segment+per-candidate, resolution-manager/resolver interiors), honest stage_time_budget warnings + partial export; 0 firings since shipped because front stages now cost seconds.

### Split-brain completion counter (nfs-truth janitor, conservative)
- Runs settled via redis task-meta ONLY (~24h TTL) vs tasks taking longer: queue stuck at completion-flat-days while results.json今天 out to disk. Janitor `settle_by_results_truth` settles those from head-parsed stage map with strict guards (file freshness, started_at vs artifact age, success-skipped-warning terminal set only).
- Silent note: replay writesverification into results.json on completed entries does NOT interfere (queue row is already complete/settled).

### Swallowed-step-crash resume loop (THE invisible cork — deadliest class of Sep 2026)
- **Signature**: celery receipts flow, workers burn CPU, results.json mtime updates constantly — yet `bat3_runs completed`=0 for days. Diagnostic: scan N recent results.json — if <5% have all-stages-done, you have a swallowed step-crash; the results.json `events` stream literally contains the traceback (grep for `attributeerror`/`unhandled exception in step`).
- **Instance**: `IdentifierResolver.__init__` — a method insertion left `enabled_similarity = ...` AFTER `return` (dead code); every `_identify_molecules` raised AttributeError; executor caught it → step exception recorded → task exits "fine" → entry resumes → reloads multi-GB universe (minutes) → crashes at the identical step → repeat for DAYS (entry 5290: 12 days). 2,325 files touched/12h, 0/400 complete, queue completed flat.
- **Root pattern**: stage-budget/feature insertion into the MIDDLE of `__init__` bodies; python never warns. Code-review rule: any edit inserting a method between `__init__` assignments = verify nothing orphaned below.
- **Fix discipline**: the crash used a resolver ATTRIBUTE — always init attributes on the ABC, never in subclass-only paths (FormulaResolver had none). Commit 2dfd5fdcb, images v2.32/v3.113.

### Celery prefetch-stacking OOM class (threads pool)
- `--pool=threads --concurrency=N` without `--prefetch-multiplier=1` = up to 4×N buffered tasks per pod; heavy multi-GB pipeline entries stack inside ONE container (10Gi) → OOM; `acks_late` redelivery then ping-pongs the heaviest entries across the fleet ("poison storm" 2026-09-22, 9 pods/1h).
- Cure (CLI pins + durable `celery_app.py: worker_prefetch_multiplier=1`): `--concurrency=2 --prefetch-multiplier=1`; per-task RAM headroom doubled. RAM sizing under budget: fewer replicas × more Gi (30×10Gi → 15×20Gi, budget unchanged).

### Rollout-during-dispatch vaporization (ops discipline)
- Rolling worker deployments while a fresh dispatch batch is in flight = task messages die in the visibility_timeout restore (33 unacked → only 6 redelivered, ~27 vaporized). Workers show **0 receipts** with broker `unacked` non-empty, fleet idle, DB rows stuck 'running'.
- Rules: (1) never roll workers within ~15min of a reclaim/dispatch; (2) combine fix+resource changes into ONE rollout; (3) after any forced rollout: sweep orphans — `queue_processor.sweep_stale_validations(db, stale_hours=1)` (fails runs, requeues queue, resets entries; poison entries must be failed FIRST so sweep skips them).

### Poison-entry class (always-fails-after-heavy-load)
- ~76.5k-bond systems with no CONECT: MDAnalysis bond-guess (~25s, multi-GB) THEN `fasta_map_protein` always fails ("degree > 2 or 0, sequence is non-linear"). Identify via one OOMing pod's `Task run_pipeline_task[uuid] received` → `bat3_runs.celery_task_id` lookup. Action: fail entry+run+queue permanently with reason, EXCLUDE from requeue sweeps. Cheap-fail topology guard still OPEN (detect non-linear before guessing).

### In-pod nohup job deaths (replay/wave ops)
- Any kubectl-exec `nohup ... &` job dies with its pod (OOM/rollout). Pattern that works: `setsid nohup env ... python3 TOOL --entries-file F --threads 4 > LOG </dev/null 2>&1 &`; keep list files on NFS; tool counters `[N/total]`; resume = `tail -n +(N+1) FILE > trimmed` and relaunch — idempotent (reverified entries skip fast).
- Probe traps: `ps` absent in containers (use /proc cmdline scan; NEVER pattern-match your own probe command — use disjoint pattern); heredoc needs `kubectl exec -i`; piping exec output locally breaks on CRLF (base64 in-pod, decode locally).

### Task-message loss forensics (kombu redis QoS)
- Truth order: pod receipts grep → redis `hlen unacked`/`llen celery` → `celery inspect active|reserved` (NOTE: inspect is unreliable under threads pool — returns empty while tasks visibly execute; trust receipts+CPU+stage logs instead) → DB `bat3_runs.celery_task_id` ↔ `celery-task-meta-*` diff.
- `unacked>0` + `inspect=empty` = orphans from dead consumers; they redeliver at visibility_timeout (~3600s default) but the restore is lossy under fleet churn.

### Zombie celery clients after network resets (freeze-without-failure)
- **Signature**: `llen celery` big and growing, receipts ≈ 0, run-level "started" high but completions ~0, pods silent (no heartbeat lines for 10+ min), broker `client list` shows tens of connections idle >8000s while unacked ≈ 0-2.
- **Mechanism**: TCP half-death after network/lb resets: consumers hold dead sockets, broker keeps them registered, BRPOPs never deliver. Celery's own heartbeats stop logging (frozen MainProcess), so it looks like a content stall.
- **Ops sequence**: 1) `redis-cli client list` idle histogram (fastest detector); 2) `CLIENT KILL id` every zombie (idle>8000) as first aid; 3) if no revival in ~3 min: `kubectl rollout restart deploy` on BOTH worker pools (RollingUpdate, messages persist in redis db0). Expect unacked to jump to ~60 and receipts/completions to resume within minutes.
- **Claim≫drain note**: dispatcher claims ~960/h bash irrespective of drain capacity: transient celery backlog growth is normal (messages persist); do NOT misread as stall — receipts/completions per minute are the truth meter.


## Wedge class (2026-09-24): consumer stuck IN BRPOP even with client keepalive

Symptoms: unacked ~0-6, llen stable thousands, 0 completions, pods Running, sockets look
ESTABLISHED, redis client list shows 30 conns cmd=brpop idle~hours. Cause: CERIT network
reset kills server-side half-flow; NAT answers our TCP keepalive probes so client never
learns. Server-side fix: `redis-cli CONFIG SET timeout 60` (reaps; verified). Remedy for
already-wedged processes: `rollout restart` (they don't self-recover). Defensive posture:
server timeout 60 runtime + deployment-arg persistence TODO + liveness watchdog TODO.
Diagnosis quickies: `redis-cli client list | grep -oE 'cmd=[a-z]+' | sort | uniq -c`,
`redis-cli monitor 20s`, inspect `.active()` worker count vs pods.

## Wedge class RESOLUTION (2026-09-25, commit aeced4bfb, images v2.41/v3.119)
- Root-mech fix: shared `redis_broker_transport_opts()` in `src_new/celery_app.py` now used by
  ALL THREE Celery constructions (bat3 app, root `tasks.py` validation app — which had NO
  transport hardening at all — and the queue_processor producer). `socket_timeout=180` bounds
  blocking broker READS (BRPOP) only — never task execution; `retry_on_timeout=True` absorbs
  transients and still surfaces dead flows on retry-write; `visibility_timeout=6h` so a long
  task never causes its prefetched neighbour to redeliver mid-flight (same-entry duplicates);
  `broker_connection_retry(_on_startup)=True`. Server-side `timeout 60` stays as-is.
- Detection caveats learned: celery broadcast ping/inspect is UNRELIABLE under saturation
  (busy workers don't answer; 2/32 responders observed while running 1,367 completions/h).
  Use instead: per-pod log freshness (`kubectl logs --tail=1 --timestamps`), `kubectl top
  pods` (~1000m per active pipeline thread), DB completion histograms, redis list drain.
- Wedge watches since deploy: zero; benign `SERVER_CLOSED_CONNECTION_ERROR` churn = redis
  reaping idle gossip conns, consumers reconnect (that IS the self-heal path working).

## Spin class (2026-09-25): verify-stage per-candidate PUG annotation stall (CPU-hot, log-silent)
- **Signature**: pods at ~1000m CPU for 3-6h+ with ZERO log lines, no completions, entry dirs
  not written; /proc fds show 1-2 entries × results.{log,debug.log} open; whole fleet
  degrades to ~15 concurrent and no success lines. Triggered by entries whose verify loop
  iterates (up to verify_top_n=100) candidates: 2 PUG HTTP calls per CID with `timeout=10s`
  against the rate-limiting NCBI blackhole = unbounded silent wall-clock per fragment.
- **Evidence pattern (reusable)**: `SPIN_DEBUG=1` env in `run_pipeline_task` (pre-existing,
  commit eefeff9c5) arms `faulthandler.dump_traceback_later(120, repeat=True)`; reproduce
  isolated via `.apply()` against a copied run dir (`/tmp/repro<ID>`); consecutive dumps
  pinned the frame at `verification/scorers/pubchem_scorer.py:78`.
- **Resolution** (commit 7196cd45c, images v2.42/v3.120): `PubChemAnnotationScorer` reads the
  local PubChem mirror FIRST (`_local_db()`, PUBCHEM_LOCAL_DB override; ~1ms offline;
  mirror-path max score 70 vs PUG 100 — no IUPAC/synonyms offline), PUG fallback kept with
  timeouts cut 10s→3s. Acid test: canonical stuck entry 7277 completed identify+verify+export
  in 215s (was 5h+), zero PUG HTTP. Zero re-fences after.
- **Ops playbook that worked**: fence spinning entries (cheap-fail queue+entry+run with
  `stuck_cpu_spin` reason, 32 rows) BEFORE worker restart so the sweeper skips them; fleet
  restart only frees slots temporarily — the celery list re-deals the same poison FIFO;
  after the code fix deploys, requeue the fenced set with last_error LIKE pattern to prove.
- **Residual**: per-pod ~1 active pipeline thread (prefetch=1×2 QoS shape under threads pool)
  is capacity, not a bug; `verify_top_n 100→20` NOT needed post-fix (verify is economical
  offline). Queue-completion attribution gap: old redelivered run_ids complete under their
  ORIGINAL bat3_runs rows — queue rows flip only when their LINKED new run finishes.

### Spin-class observability (2026-09-26 upgrade) + residual sibling
- `SPIN_DEBUG=1` now fleet-wide on validation-worker: per-generator `[SPIN] START/DONE`
  markers stream in kubectl logs (eefeff9c5 instrumentation) — hung generator = START
  with no DONE, names itself live. faulthandler dumps re-arm per task start (churn
  suppresses them by design; markers are the reliable signal).
- Sibling variant seen once (entries 9189/9190, >15h CPU-hot logless, virtual-minority->
  non-strict-sequence tail): a compute-side loop independent of the annotation stall. Not
  yet localized; detection = per-pod results.debug.log tail + unmatched [SPIN] START.
  If it recurs at scale: fence the entry (cheap-fail pattern), isolate-repro with
  SPIN_DEBUG, extend eefeff9c5 child-isolation to the named generator path.
- Intermediate audits derisk long drains: `campaign_stats.py --full --sim
  --sim-budget 150000 --json-out ...` in-pod nohup (~2h; 901k pair cache warm).
  v6.5 verdict pre-full-drain: inchikey 19.0%->44.2% validated@10, att 84.8%.
- `signature_isolated_timeout` x3996 in S6 log = generator child-isolation guard
  firing normally at scale; count is expected, not alarming.
## Metrics trap (2026-09-26): stale-file denominator pollution in S7 audits
- **Symptom**: S7 numbers look catastrophic (inchikey 44%, ion 34%) while live code is healthy.
- **Root**: `campaign_stats.py` NFS scan reads EVERY results.json with hits — including stale files of `processing` entries (claimed but not re-finished), which still hold legacy failed/partial contents (Sep-10 load_failed, bug-era partials). 5,347/7,342 GT-inch entries were in that state mid-drain.
- **Liveness filter (correct protocol)**: score an entry's annotations only when `tasks.load_simulation==success && tasks.verify_results==success` in results.json (or queue status completed with fresh mtime). With it, v6.5-era data resolves to inchikey @10 ≈ 75.2%, ion ≈ 72.1% — matching the fresh-era ~77% anchor.
- Rule: **never interpret S7 over an unfiltered NFS pile**; also expect `critical_errors` inside results.json to be CUMULATIVE across attempts (not current-state truth; tasks status is).

## gt_absent anatomy (2026-09-26): candidate plumbing, not absence
- Live `gt_absent` (best candidate sim <0.5, n=341) breaks down: 77% "present-but-windowed-out" (261), 16% GT-unresolvable keys, 4% cache poison, 4% true absence.
- **C2 (62%)**: protonation frame — fragment formula ≠ GT's PubChem frame (H differs); exact-formula lookup can't bridge. `formula_hfamily` has a local-mirror backend but is SKIPPED by the PUG circuit breaker (`_PUBCHEM_RESOLVERS` in resolution_manager) since the 2026-09-24 blacklist.
- **C1 (35%)**: formula-family floods (median ~3k isomer-mates) vs `verify_top_n=100` cut on consensus_score; formula candidates are identity-typed (consensus 100 each), so the cut is a structural lottery. GT-block CID median rank 3,097.
- Fixes = F13 (ungate local hfamily + raise local caps) + F14 (skeleton-aware rerank of chemical window before top_n, raise-only when any skel≥0.7 else byte-identical legacy) + F15 (mirror block-range fetch for INCHIKEY self-variants). Design+acceptance: docs/CHEMISTRY_FIX_TODO.md "WAVE 5".
- Audit artifacts: /data/validation/audit_chem_ion.json, audit_gt_absent.json(+rows.jsonl); scripts .tmp/audit_chem_ion.py, .tmp/audit_gt_absent.py (liveness-filtered; reusable for post-fix cohort measurement).

## smiles canonicalization spin class (2026-09-27): MolToSmiles on junk cage/ring clusters
- **Signature**: pod ~1 core CPU-hot for hours, last log line always `[SPIN] <seg>/<gen>
  START` (never DONE) on virtual `SYSTEM__vN` fragments; entries redeliver (visibility
  6h) and re-stick FRESH workers — waves capture 30-50% of the fleet in worse episodes.
- **Root**: RDKit canonical SMILES ranking on small dense fused-ring/cage junk from
  virtual-minority SYSTEM fragments. NOT size-correlated (4,247-atom systems poisoned),
  hits both `smiles` and `smiles_not_sanitized` (canonicalization shared). Sibling stages
  `selfies`/`inchi_key` spin on the same fragments. 2026-09-20 kekulize fix excluded
  KEKULIZE ops only; MolToSmiles canonicalization itself was the residual sibling all
  along (this IS the "9189-class", now localized).
- **Parallel class**: hung external HTTP with no timeout (cactus.nci.nih.gov 10.4h,
  uniprot FASTA fetches, PUG fastsimilarity POSTs) — tails end at urllib3 "Starting new
  HTTPS connection" hours old.
- **Mitigation (no app-code change)**: fence-watchdog `/tmp/fence_watchdog_v2.py` on
  validation-api (10-min cycles): live `processing` entries whose results.debug.log tail
  is stale `[SPIN] ... START` (>30 min) or stale HTTP-connect (>75 min) → UPDATE queue
  `failed/quarantined` + append `/data/validation/quarantine_smiles_spin_2026-09-27.txt`
  + LREM every redis celery message for listed entries. Corpus file = single source of
  truth (re-read each cycle). Manual reaper = delete pods stuck on fenced entries.
- **Fix-to-come (F17)**: subprocess-isolated generator budget (child killed on overrun;
  NO per-thread timeouts — that class of patch broke before). ~420 quarantined entries
  preserved on NFS as the regression corpus; replay them after the fix ships.
- py-spy unattributable in these pods (uid 1000, no SYS_PTRACE). faulthandler SPIN_DEBUG
  never arms: celery `LoggingProxy` has no `fileno` (silent except at task end).

## Kombu zombie pods (2026-09-28): silent consumers after dead broker flows
- Pods alive, ~0 CPU, last log = `missed heartbeat`/`sync with`/"Restoring N
  unacknowledged" 7-20h stale. Consumer threads dead; celery never picks new work.
  Sept-24/25 wedge-class surviving without restarts. Detection: per-pod last-log age +
  `kubectl top` 0-300m. Fix: plain `kubectl delete pod` (Deployment recreates healthy).

## RS quota coexistence trap (2026-09-28/29): scale/patch ordering deadlocks rollouts
- Sequence `kubectl scale N` + `kubectl patch resources` lets the OLD-shape ReplicaSet
  claim quota first; the new RS's creation then fails quota admission (FailedCreate,
  NOT Pending — pods never appear), rollout stalls ("progress deadline exceeded"), and
  the controller simultaneously balloons the old RS's desired count proportionally.
- **Fix**: `kubectl scale rs <old-shape> --replicas=0` → quota frees → new RS takes the
  fleet in one wave. Losing running jobs this way is safe under celery visibility
  (messages restore, stages resume from results.json). Watch quota math on BOTH request
  and limit sides during double-count windows.

## Duplicates-as-refresh (2026-09-28): the redis backlog is a legitimate recompute fleet
- entries completed pre-F13/F14/F15 hold pre-fix results; their duplicate backlog
  messages (~31k) re-execute the FULL pipeline with fixed code and rewrite results.json
  (proof: 6533 re-ran every stage 19:20 while DB row showed yesterday's completion).
- Purging "duplicate" messages would have destroyed the cohort-wide refresh. Correct
  gauges: rows-completed = first-time claim coverage; **llen = refresh progress**.
- Re-runs do NOT update queue rows (max(completed_at) freezes once all rows touched).
- results.json is REWRITTEN in place → mid-flight files are PARTIAL for hours → any
  stats pass must liveness-filter (tasks.load_simulation==success && verify_results
  ==success) or risk counting partial states (same class as the v6.5 metrics trap).

## Molecule-type stomp class (2026-09-30): composition fallback overwrote polymer verdicts

- `extract_molecule_instance`: the element-composition fallback (lipid/
  carbohydrate/small-molecule) ran UNCONDITIONALLY after flag-based typing.
  DNA has C/O ~2.4, inside the lipid 1-3 band -> segment flagged
  is_nucleic=true but instance stamped LIPID -> `lipid_shorthand`
  signature emitted for DNA strands. Water/ion were equally stompable to
  small_molecule. Found via Phase-7 E2E signature inventory diff.
- Fix (bfc077fdb): fallback runs only for UNKNOWN. Lesson: a block whose
  comment says "non-polymer classification" must CODE that guard; atom
  heuristics are fallbacks, never overrides.

## nginx upstream landmine + mutable-tag trap + .dockerignore silent-drop (2026-09-30 rollout)

- nginx resolves `proxy_pass` hostnames ONLY at startup. A pod whose API
  service was renamed after it started can run for months on a cached
  resolution; ANY restart then fails with "host not found in upstream"
  and looks like a fresh-code regression (frontend crashloop class).
  Always diff conf upstreams vs live `kubectl get svc` before rolling.
- Mutable `latest` tags make rollback impossible: `rollout undo` re-pulls
  the mutated tag under imagePullPolicy: Always. Tag immutably (or record
  digests before push: the old digest survives orphaned in the registry).
- `.dockerignore` silently dropped `**/deploy/**` from build contexts;
  builds reported success while the conf COPY failed -> pushing stale
  digests. After every docker build: verify the digest CHANGED and run an
  in-image functional gate before pushing.

## Long stats processes: zombie exit-hang + OOM from raw retention (2026-09-30/10-01)

- campaign_stats.py full runs (and the audit cousin) complete ALL work then hang
  as Z-state zombies; pod PID 1 doesn't reap. Outputs are complete and valid
  (JSON verified parseable) — SIGKILL is safe and required before any sentinel
  gated on /proc/PID can proceed. Do NOT sentinel on liveness of a PID that may
  already be a zombie; sentinel on the artifact.
- OOM kill (exit 137) pattern in ad-hoc audit scripts: keeping raw results.json
  text (or big parsed docs) in per-entry dicts across ~13k entries blows pod
  memory. Compute any raw-text-derived booleans INSIDE the parse frame and drop
  the raw string immediately. Moderate thread counts (16) also keep RSS sane.

## Metric ordering: skeleton ties make @10 a noisy metric (2026-10-01)

- Verified chemical hits frequently form tie clusters of 12+ candidates at
  skeleton_sim=1.0 (isomer/salt/family clusters). Within a tie, sim-to-GT
  varies 0.01->1.0 — GT-specific score separated from entry-molecule fidelity.
  Any rank-based cutoff (@10) then moves +-1-2pp purely on tie-break order
  (projection-stable 88.5 vs official identifier-tie 90.6 measured; flip
  dissection: 147 tie_reposition + 23 window_membership of 649 flips).
- Consequences: quote ONE canonical ordering (we canonicalized identifier-asc
  in campaign_stats.py patched _fid_key); prefer depth-invariant frames (@15,
  in-window) for cross-run comparisons; UI shows stored order verbatim — ties
  are presentation, not ranking errors.

## SimEngine cache mechanics (2026-09-30/10-01)

- SimEngine(budget=0) computes ONLY cache hits? No — budget counts NEW pair
  computations; budget=0 still ALLOWS them (observed 29k-66k "new_pairs" across
  budget=0 runs). pairs.jsonl (NFS) is the shared accumulative cache; every
  run enriches it (~1.107M pairs at v8). Concurrent sim runs = contention +
  interrupting a run loses NOTHING except time (pairs idempotent).
- First run over the cohort is slow (v7: 8,582s wall, mo104 cached pairs);
  cache-warm reruns are ~700s for the same 13,324 entries.
- unmapped count is informative (mirrors mirror coverage: v7 2269 -> v8 25
  after gcs/inchikey_smiles caches grew).

## Shadowing the S7 metric: empty-hits guard + web-chain classification (2026-10-01)

- Official campaign_stats.py counts GT annotations ONLY for entries with
  NON-EMPTY verified hits (`if sim_engine is not None and r["hits"]:` guards
  the whole S7 loop, ions included). A shadow re-implementation missing that
  guard counts one extra annotation per empty-hits entry WITH ZERO validated
  delta — manifested as a 5,785-vs-5,784 "phantom" that reproduced every pct
  anchor only after exclusion. When replicating the metric for hard-gated
  regen, replicate ALL guards (liveness, hits-non-empty, family windows,
  fallback, gates) verbatim — residual_anatomy2 had it right
  (`if r and r["hits"]`), the first coverability draft didn't.
- `gt_rules.gt_class_for` resolves inchikey->SMILES via a WEB chain
  (cactus -> pug -> chemspider -> idsm; only POSITIVE results cached in
  NFS sim_cache/inchikey_smiles). Behavior is POD-DEPENDENT: the API pod's
  egress fails fast (sub-second), so v7/v8 ran classification in seconds;
  worker pods egress for real, so ~160 uncached GT keys cost full timeout
  chains (~300-450s) and fetches that fail there are retried EVERY run
  (negatives never cached). Classification can therefore flip ion<->organic
  between pods/runs on network weather. Deterministic pattern (used by the
  coverability probe): cache-warm verdict where an NFS cache entry exists
  (same sha1 path, no fetch), else MIRROR-FIRST (PubChemDB.by_inchikey ->
  skeletize.from_smiles -> same ion rule) — 4,311 keys in ~45s offline.
  Never run web-dependent classification/sim-resolution cold from worker pods.

## S7 full-scan numbers are resolution-cache-state sensitive (2026-10-02)

- Re-running campaign_stats --full --sim on an UNCHANGED cohort can move
  organic inchikey @k by tenths of a point. Sim GT<->candidate resolution
  chains are web-backed with POSITIVES-ONLY NFS caches (inchikey_smiles,
  pubchem_smiles); any audit/probe run on a worker pod (egress works) keeps
  adding positives, so pairs unresolvable at v8-time later compute sims >0.
  Observed same-cohort rerun: inchikey @1 56.3->56.9 (~35 ann), @10 90.6->90.8.
- The ION channel is elements-token-based (no web sims) -> it is the
  sensitive control: F19 no-move check had ion/pdb/uniprot/entry-any
  BIT-IDENTICAL while organic drifted. Resolution-dependent channels drift
  with cache growth; resolution-independent ones don't.
- Hygiene rules: official numbers live with their run artifact + cache state
  (v8 = 90.6 stays canonical); no-move/regression gates must compare
  token-based channels bit-exact and treat organic deltas with disclosed
  cache-growth provenance; for quote-level prose prefer the PUBLISHED run,
  and when a fresher rerun is wanted, run it as a new official version
  (v9...) rather than silently re-quoting.

## kubectl strategic-merge patch matches containers BY NAME (phantom trap, 2026-10-02)

- `-p '{"spec":{"template":{"spec":{"containers":[{"name":"validation-api","image":...}]}}}}'`
  on a deployment whose only container was named `api` did NOT patch it —
  strategic merge keyed by name CREATED a second, phantom container (new
  image, default CMD, no env/mounts) while the workhorse stayed old. Rollout
  even succeeded (2/2 ready) and admission was satisfied by the phantom's
  compliant securityContext.
- Rules: always `kubectl get deploy X -o jsonpath` the ACTUAL container
  names before patching; prefer `kubectl set image deploy/X <name>=img`;
  after any strategic patch, verify the RESULTING template has the intended
  container count and each container's image/mounts.

## Ephemeral ops scripts belong on NFS, not pod /tmp (2026-10-02)

- The fence watchdog lived at /tmp/fence_watchdog_v2.py on the validation-api
  pod and was lost on the api-pod roll (v3.123). Corpus on NFS
  (quarantine_smiles_spin_2026-09-27.txt, 437) survived because it was NFS.
  Rule: any ops script meant to survive pod churn gets an NFS home
  (/data/validation/) and pod restarts only re-launch pointers. Watchdog
  revival is bundled with the F17 wave (it guards that replay; fleet is
  idle meanwhile — exposure accepted by ruling).

## WAVE-7 refactor class: tuple-unpack missed call sites (2026-10-02)

- _compute_flags() -> (flags, na_meta) since WAVE-7; the virtual-segment
  branch kept assigning the whole tuple to props.flags -> AttributeError in
  extract_molecule_instance on __vN universes. Fixed f7baeb734 + regression
  tests. Post-refactor rule: after changing a helper's return signature,
  grep ALL call sites (including feature branches: virtual segments,
  _discover_* paths) and add an integration test per consumer. NOTE: the 7
  pre-existing master failures in test_fragment_store/test_universe_facade
  are a DIFFERENT class and REMAIN OPEN for triage (A/B-verified before and
  after this fix).

## FE/metal vdw radii poison global bond guessing (known, deferred)

- MDA DefaultGuesser raises on unknown vdw types (FE in HEM, other metals),
  aborting guess_bonds for the ENTIRE universe -> whole topology-less sim
  bondless -> map-based FASTA dead metalloprotein-wide, silent except one
  warning. User ruling (2026-09-30): known story; metal radii alone will
  not fix it. Deferred to a later wave (likely per-region guessing or
  guesser hardening).

## P2 family: UI-rework era landmines (2026-10-01)

## P2-1: Files build locally, missing in clean tree (.gitignore collision)
- Signature: local typecheck/tests pass; docker/worktree build fails "Cannot find module"; `git log -- <file>` empty
- Cause: python-era `.gitignore` `lib/` matched `ui/src/lib/`; similar: history-tracked `ui/node_modules`, `ui/dist`
- Fix: path-scoped negations at end of `.gitignore`; purge index (`git rm -r --cached`); verify via `git ls-tree -r HEAD -- ui/`

## P2-2: Design-system custom theme silently ignored (purple persists)
- Signature: `data-theme="custom"` + seed vars set, UI still DS default purple
- Cause: `@e-infra/design-system@0.1.9` `setup.css` declares theme at UNLAYERED `:root`; `custom_setup.css` is `@layer`-wrapped (layered always loses)
- Fix: override tokens UNLAYERED on `html[data-theme="custom"]` (specificity > :root). Reported upstream candidate.

## P2-3: kubectl set image with nonexistent tag (outage)
- Signature: rollout timeout, ImagePullBackOff, Recreate strategy killed old pod first
- Cause: `cmd | tail` masked exit codes in deploy chain; no image preflight
- Fix: `set -o pipefail`, `docker image inspect` check before `set image`, timeout ⇒ immediate rollback to last good tag

## P2-4: Long headless opencode agent sessions die silently
- Signature: log EOF mid-task, no result block, uncommitted partial edits; ~15–60 min runtime
- Cause: gateway stream drop (also triggered by client network resets)
- Fix: per-deliverable commit discipline; resume with explicit done/remaining state; inspect disk salvage before relaunch. flash-next model additionally stalls (0 edits) — use qwen3.8-27b for long briefs


## P2-5: Flex h-full chains can't cap grid/flex rows inflated by content
- Signature: `h-full` on cell+card, but a 1800-row table still stretches the page (no scroll)
- Cause: circular constraint — the overflowing item itself determines the row height; flex-1/min-h-0 chains never engage
- Fix: on the constrained cell, `position: relative` + child `absolute inset-0` (removes it from row-height math; other column drives height); media-query it if stacked layout must flow (e.g. `xl:absolute`)
- Verify: long-content sibling never exceeds driver column's bottom edge

## P2-6: worktree add fails "Could not reset index file"
- Cause: stale worktree registrations (removed dirs w/o `worktree remove`, crashed sessions)
- Fix: `git worktree remove <path> --force` leftovers + `git worktree prune`; retry. Verify with `git worktree list`


## P2-7: kubectl set image to the SAME tag string = silent no-op (no rollout)
- Signature: repeated `set image x=:production-v1` after retagging; rollout "succeeds" instantly; pod serves OLD content; html asset hash inside image != live html asset hash
- Cause: deployment spec unchanged (same string) -> no new ReplicaSet; pod keeps old pull
- Fix: deploy with UNIQUE tag strings (:w12); verify parity: live html asset == image html asset (docker run --rm --entrypoint sh IMG -c "cat /var/www/app/index.html"). Use moving tags (production-v1) as registry pointers only, never as rollout trigger

## V-13: never co-schedule campaign_stats + audit scripts on the api pod (OOMKill)
- Signature: api container restart exit 137 (OOMKilled) mid-run; nohup'd long-runs dead; log tails stop mid-phase; `lastState.terminated.reason=OOMKilled`
- Cause: audit (GT classification structures) + full-frame stats (~1.15M pairs + entry parse) together exceed pod memory; they ran solo fine for months
- Fix: serialize heavy NFS loads on the api pod — stats first, audit after; if parallelism needed, put one job on a WORKER pod (memory headroom + separate limit)

## V-14: long-run artifacts + scripts on /tmp = lost on any container restart (generalized)
- Signature: after pod roll/OOM/restart, progress logs and helper scripts vanished; rerun from scratch
- Cause: /tmp is container-ephemeral; deployments/pods cycle without warning (rollouts, node drains, OOM)
- Fix: ALL long-run inputs, scripts, and logs live on NFS (/data/validation/logs/...); wrapper commands reference NFS paths only. Extends the fence-watchdog lesson; 2026-10-02: F-residual 3-chunk logs + audit script both lost this way and re-homed

## V-15: results.json pipeline payload is DOUBLE-NESTED (analysis scripts read empty)
- Signature: diff/audit scripts report "0 changes" or empty verification even though pipeline data exists
- Cause: results.json top level is schema_version/tasks/artifacts/data; the pipeline payload lives under the "data" key — verification at results["data"]["verification"], identifiers at results["data"]["identifiers"]; reading results["verification"] (top level) silently yields None
- Fix: always d.get("data",{}).get("verification") (or the ResultsManager accessors); assert non-empty before concluding "no change" — a 0-vs-0 match is indistinguishable from a missed path
