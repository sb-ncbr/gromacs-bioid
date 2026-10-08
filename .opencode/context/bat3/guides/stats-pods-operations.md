# Stats Harvester Operations Playbook (pods + NFS)

## Core Concept
How to run heavy offline statistics tools (campaign_stats-era) safely and fast
on the validation cluster. Distilled from the S0 signature-stage campaign
(2026-10-06/07), which hit and fixed every failure mode below. All tools live
in `scripts/stats/` (provenance rule: edit there first, commit, then deploy).

## Deployment
- **Identity-deploy (idempotent)**: `kubectl cp` fails on existing targets;
  pipe over exec stdin instead:
  `kubectl exec -i -n ceitec-biodata-ns POD -- sh -c "cat > PATH.tmp && mv -f PATH.tmp PATH" < local_file`
- **md5-verify fleets**: after deploying to N pods, count md5s — expect one
  bucket: `xargs -P10 -I{} sh -c 'kubectl exec ... md5sum PATH' | sort | uniq -c`
- **Long runs**: `nohup ... >/tmp/X.out 2>/tmp/X.err &` — then poll the logs.
  `kubectl exec` sessions die with YOUR tool timeout and take children with
  them; never run multi-minute work attached.
- **Processes**: `pgrep` absent in worker images; enumerate via
  `for p in /proc/[0-9]*; tr '\0' ' ' </proc/$p/cmdline | grep -q PATTERN`.
  Diagnose hung procs: `/proc/PID/stat` (utime), task states
  (`cut -d' ' -f3 /proc/PID/task/*/stat`), `/proc/PID/task/PID/wchan`;
  `faulthandler.dump_traceback_later()` captures python stacks without
  touching the target code.

## Threading / concurrency hazards (all hit live)
1. **Lazy importlib singletons deadlock on worker threads.** 32 workers
   froze in `importlib._bootstrap.acquire` (campaign_stats exec'd via
   `spec_from_file_location` inside pool threads; first run passed by race
   luck). Fix: `prewarm_imports()` — resolve every lazy module in the MAIN
   thread before `ThreadPoolExecutor`; workers read cached globals only.
2. **fd-level stderr redirection is process-global.** `os.dup2(wfd, 2)` for
   RDKit warning capture deadlocked a pool (foreign warnings fill an unread
   pipe). Fix: module-level lock around the whole dup2 dance; single writer
   then close-and-read.
3. **Shared `Bio.Align.PairwiseAligner` is not thread-safe** and newer
   Biopython alignments objects are streaming iterators — `[0]` indexing
   crashed 25/50 shards with `IndexError`. Fix: `threading.local()` aligner
   + `next(iter(align(...)))` (first == best; numerically identical).
4. **Biopython denominator differs across envs** (`counts().aligned` exists
   in pod builds, absent locally → identity denominator aligned vs maxlen).
   For env-parity metrics, assert within-env equality against the reference
   implementation (drift-guard tests), accept both semantics in portable
   unit tests, run production scorings in one env class (pods).

## NFS / data realities
- `find` over `/data/validation` (15k entry dirs, multi-MB JSONs) is too
  slow for interactive use; `os.scandir` + `stat` on the results filename
  is ~30-40 s. Reads of individual `results.json` are sub-second.
- Results filename is `results.json`; `results-vN.json` exists only for
  historical waves — v13/v14 refer to campaign *versions*, not filenames.
  Resolve scan pattern from the anchor's own `full.pattern`.
- Per-entry results docs carry `data.signatures`, `data.identifiers`,
  `data.verification`, `data.fragments`, `data.stage_errors` (INV-4 stable).

## Metric cache hazards
- `sim_cache/pairs.jsonl` is durable and append-only; resolution FAILURES
  were persisted as `0.0` (stale-negative poisoning — see case file F-7).
  Any consumer must treat pair zeros as suspect; heal tooling:
  `scripts/stats/sigstage_heal.py --purge --dry-run` first, backup +
  atomic `os.replace` rewrite, never in-place edits.
- Anchor/discipline: versioned `campaign_stats_vN.json` files are the
  frozen denominators. Narrowed runs (`--sample`/shards) cannot match
  full-set denominators — gate STRICT on full runs, recorded WARNINGs
  (`--anchor-lax`) on narrowed ones.
- **campaign_stats sim is SINGLE-THREADED** (engine calls sit in the
  `as_completed` consumption loop): unresolvable-pair recurrences must be
  pre-warmed (`sigstage_warmup.py`) and in-run negative memoization
  (engine A1.1) is load-bearing — without them a rerun freezes on ghost
  re-chaining (2026-10-07: 60 TIME_WAIT sockets, ~26h projection vs ~2h
  fixed). Diagnose with socket-state census + identifier-cache growth,
  NOT wall-time alone.

## Failure-mode lessons (2026-10-08 closeout wave)
1. **Container OOM can be page-cache-driven, not RSS.** `/sys/fs/cgroup/memory.stat`
   shows `anon` (app/working set) vs `file` (NFS page cache charged to the
   container) -- a pass died twice at ~24GB of file cache with 122MB anon.
   Mitigate: `os.posix_fadvise(fd, 0, 0, POSIX_FADV_DONTNEED)` after every bulk
   read; prefer a FRESH pod for giant read sweeps over a long-lived one
   (accumulated cache made the same pass 20x slower then fatal on the old pod).
2. **results.json can be huge (up to ~98MB).** Never `json.load` sweeps of the
   full doc from 16 threads against a 25GB cap; text-regex the needed fields
   with full-parse fallback for ambiguous shapes (merger gate pass pattern).
3. **`CAMPAIGN_STATS_SINCE` is part of every campaign denominator** (default
   `2026-09-10T11:00:00`). Any anchor-census replication that ignores it
   produces phantom drift (measured +508/+508 vs v14 before the fix fired
   STRICT correctly). STRICT misfires are usually replication bugs: suspect
   your own replay before suspecting campaign drift.
4. **Anything used twice belongs in `scripts/stats/` with tests.** The first
   merger was an ad-hoc `.tmp` script lost to a hygiene pass; rebuilt
   permanently as `sigstage_merge.py`. Same for the audit summarize mode.
5. **Dry-run checkpoints pay for themselves.** `sigstage_heal --purge
   --dry-run` caught a driver crash before any cache write; the real purge
   then matched the dry-run byte-deterministically. Keep
   measure->dry-run->real (+expected counts pre-stated) the default pattern
   for any cache-touching tool.

## Sharding pattern (hundreds of pods available)
- One shard per pod: `--shard i/N`, `--threads 16`, budget-capped web
  escalations; collect deterministic per-shard JSONL (sort rows before
  write); merge offline; verify: uniform tool checksum in shard scan
  metadata, 0 duplicate row keys, per-shard row counts match aggregate,
  byte-determinism via one independent shard rerun.
- Keep 1 pristine copy of pre-change artifacts (`run_v1/` convention)
  before any rerun that overwrites an output dir.

## Reference
- `../lookup/s0-signature-stage-case-file.md` — the campaign that produced
  these lessons (findings, artifacts, actions)
- `../../scripts/stats/README.md` — provenance + replay protocol
