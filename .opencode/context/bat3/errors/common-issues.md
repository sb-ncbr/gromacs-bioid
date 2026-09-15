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
