# BAT3 Validation Status (2026-09-23 late, legacy wave in flight)

> ⚠️ **STALE for publication numbers** — this document predates the final v14 drain (metrics here are pilot/legacy-wave era). For paper-canonical numbers see `publication-v14-numbers.md`; for campaign history see `publication-journal.md`. Infra notes below (images, pools, downloader) may also be dated — verify against live cluster before acting.

## Core Concept
Current truth for the ceitec-biodata-ns validation deployment. **Metric verdict landed 2026-09-23** (S7 v6): inchikey att=58.0% validated@10=19.0% | pdb @10=99.6% | uniprot @10=98.4% | entry-any-validated@10=98.9%. Infra hardened: swallowed-crash cork (enabled_similarity) fixed, prefetch-stacking OOM cured, fleets 15x20Gi both pools, residue reverify 3,444/3,446 renovated.

## Key Points
- **Entries indexed**: 15,185 (14,066 with ground truth: 27,328 signatures = 14,787 UniProt + 12,541 PDB)
- **Full-scale run**: 1,691/14,622 completed (11.6%); throughput cohort-bound (on-disk wave ~20/min; GB-download wave ~5-8 runs/15min over MDposit bandwidth)
- **Validation metrics (pilot, hit@K vs GT)**: hit@1 = 0.348, hit@5 = 0.731, hit@10 = 0.811 overall (pdb 0.840); 456 rows in `validation_results`
- **Images live**: `bat3-worker:v2.33` (bat3-worker ×15 + bat3-ui-worker ×2), `bat3-validation-api:v3.114` (validation-api ×1, validation-worker ×15). Worker CLI pins `--pool=threads --concurrency=2 --prefetch-multiplier=1`; memory 12Gi/20Gi. **Offline-PUBCHEM stack**: inchikey_self + formula_chembl resolvers live (inchikey_self unconditional; formula_chembl gated ON in config_shared.ini). v3.95(no-suffix) crashes (HEAD Dockerfile poison, fixed). PUG blocks cluster IP since 2026-09-12 (laptop 200 / cluster 503); structure matrix: CID=cache->PUG->IDSM-SPARQL, IK=cactus->chembl->PUG, ChEMBL/CHEBI native; pubchem_struct+formula_pubchem disabled in config_shared.ini `validation-api:v3.95` (no-suffix) CRASHES: HEAD Dockerfile.api had `mv main.py` poison - use v3.95b / fixed snapshot at /tmp/opencode/Dockerfile.api.fixed (line removed in commit 0a3079a79). fsGroupChangePolicy=OnRootMismatch on worker deploys (rollout chown stall fix)
- **Worker pools**: uid 1000 everywhere; BOTH consume one default celery queue — ship pipeline-code fixes into BOTH images (v2.15 + v3.92); validation-worker mounts BLAST DBs (P2-17)
- **Downloader hardened**: taxonomy (terminal `project_not_found`/`no_simulation_files` vs transient `download_failed`), atomic `.part`, size verify, S3 fallback via `mdfind-s3-secret` (mddata bucket; legacy `mddbr_A0001_<file>` layout), `download_report.json` audit per entry

## Scheduler State (at checkpoint)
- validation_queue: ~13.9k queued, ~640 completed, 26 processing, 21 failed
- Failed tail (frozen since 13:57): 16 perm-wave (P2-15 attribution open) + 5 `No loading strategy succeeded` (data-reject candidates)
- Sweeper: 30s tick in validation-api; may re-attach stale Redis exceptions to healthy entries (P2-15 — verify live mtime before trusting "failed")
- Dispatch: `VALIDATION_DISPATCH_ENABLED=1` (gate in validation-api env; flip to 0 to pause intake)

## Similarity Validation (S7, 2026-09-10 evening)
- **Metric corrected**: hit@K is similarity vs MDDBR annotations, not exact-id join. Sequences: local-alignment identity (PairwiseAligner); structures mapped into sequence space; chemicals: PubChem fingerprint Tanimoto + InChIKey connectivity
- Engine: `scripts/validation_similarity.py`; durable NFS caches (`sim_cache/` + `mddbr_meta_cache/`); pair-cache jsonl
- **Pilot (results-v4, 456 entries)**: pdb mean@1=0.996 (validated 99.3%), uniprot 0.976 (95.1%); entry-any-validated@1=99.6% — bat3's top hits are near-identical to annotation
- GT now includes **9,626 inchikey rows** (INCHIKEYS harvested from MDDBR; `scripts/harvest_chemical_gt.py`)
- S5 exact-match kept as documented lower bound in campaign_stats (v3, `--sim`, `--pattern`)
- Scale-up: bat3-worker 40 + validation-worker 50 (uid 1000, DBs mounted on both) = ~360 slots; observed ~20/min with on-disk entries
- REQUEUE-ALL executed after validation-worker DB-mount fix (P2-17 resolved); scorch theory replaced by full reprocessing

- **Ops (2026-09-23 late, wave in flight)**: LEGACY reid wave (3,367 entries) running on v2.40/v3.118; strip+requeue mechanics in `scripts/strip_for_reidentify.py`; yield: 100% chem candidates on identify-done, verified chem accumulating; completions ~150-170/h; zombie-celery-client class closed (client-kill + rollout restart cookbook in common-issues). Next: audit_gap re-run + S7 v7 once the bulk lands (target: legacy no-chem 94% -> fresh-era ~19%; S7 v@10 toward fresh 77%).
- **Ops (2026-09-23 state, verdict sealed)**: queue completed=7,401 rising post-fix; processing ~72; celery=0; S7 v6 stats at `/data/validation/stats_s7_v6.log`; sim_cache GT structures 2,710 keys + 881k cached sim pairs; residue reverify COMPLETE (3,444/3,446); rank audit fresh2: rerank headroom=0 (evidence@1 wins all); docs: rerun playbook at `docs/VALIDATION_RERUN_PLAYBOOK.md`.
- **Ops (2026-09-21 state, wave-3.5 sealed)**: queue completed=7,389 (+119 new day-of), processing ~1,807, celery backlog **0** (melted 51k in hours), ns-truth+meta settle both firing. Current LIVE images: `bat3-worker:v2.31` (bat3-ee + bat3-ui), `bat3-validation-api:v3.112` (api + validation-worker). Spin-class dead via smiles kekulization-elimination; child-isolation fully reverted (data-loss wave resolved); pipeline contract restored (front stages 2-10s, chem verify flows at 73-300 verified/entry fresh).
- **Ops (2026-09-18 state)**: queue completed=7,128 flat; processing 7,438; celery backlog 19.6k growing; completed 30m/2h/6h = 0. v2.26/v3.107 (resume) deployed; completions not yet recovering - pattern not solved by resume alone. Active investigation: (a) heavy-task stall pre-export, (b) persistent intake>drain accumulating backlog.
- **Ops (2026-09-17)**: UI fast lane: `validation.api.celery`? no -- `validation.ui.celery` dedicated (2-replica bat3-ui-worker); manual runs via portal route to it (VALIDATION_UI_QUEUE env); skip shared backlog entirely. Rollback = env='' + delete bat3-ui-worker.
- **Ops (2026-09-16)**: mass reverify killed pre-completion by v3.105 rollout pod-restart (2,165/15,132 applied atomically; safe to rerun anytime); process-silo rule of thumb recorded: api rollouts kill in-pod nohup jobs. v3.105 = reranked chemistry verification; inchikey search-layer is open frontier (pool-presence probe overnight).
- **Metrics baseline (2026-09-15 truth)**: S7v4 full pop: entry-any @1 90.8%/@10 97.8% | pdb v@1 76.8%→95.4%@10 | uniprot v@1 78.8%→89.6%@10 | inchikey organic att 58.9% | signature-level true construction ≈47.3% (exact 11.3 + connectivity 15.6 + skel_high 20.6). Ions (M9) presence-scored 70% in smoke; cofactor unlock (M10b) in proof.
- Intake: dispatcher healthy 8/tick, STALE_HOURS=12. Ghost-fleet purge 2026-09-12 (23,705 ghost tasks) + NFS-truth settlement (5,181 completions recovered). Workers at 16+16 during PUG defense (upscale lever: 40). Completions now marked via MGET settle (api v3.98+) at production pace
- 2026-09-11 OOM incident: validation-worker resourced at web-tier (2CPU/4Gi) while running the BAT3 pipeline → wholesale OOMKilled churn overnight (~2,127 zombie runs accumulated, throughput collapsed). Fixed: resources → 4CPU/10Gi (same as bat3-worker); sweeper VALIDATION_STALE_HOURS=3 reclaimed ~1.8k zombies; post-fix 33 runs/15min + 18 completions/15min
## Known Remaining Items
- P2-15: sweeper batch fail-marks at :27/:57 need attribution audit before bulk-trusting "failed"
- 5 loading failures: genuine data rejects (loader tried all strategies) — inspect per entry
- ~63 heavy pilot stragglers may still land in `results-v4.json`
- Worker logs: MDAnalysis DEBUG flood hides tracebacks in tail windows — raise level for incidents
- `fasta_map_protein` generator returns None for ~86 entries (P1-12, open)
- Build policy: images from `git show HEAD:Dockerfile.*` (P2-16: working-tree Dockerfile.api had WIP `mv main.py`)

## Reference
- `../errors/common-issues.md` — failure signatures incl. session-2 classes (P2-11..P2-16)
- `bat3_validation/docs/INCIDENT_REGISTRY_2026-09.md` — full forensic log (external dir)
- `ceitec-deployment.md` — live deployment facts
- `../guides/full-scale-dispatch.md` — runbook (versions updated post-GO)

## 2026-09-26 — intermediate audit v6.5 confirms recovery; spin observability upgraded

- Campaign: 5,897/15,185 (38.8%); drain bursty (cheap flushes 262/h, heavy cohorts every
  <=3h); celery list ~20.8k (drain<feed is ordering, not illness). 4 failed (3 poison + 1
  download). Zero re-fences since spin fix.
- **S7 v6.5 (intermediate, all completed-so-far)**: inchikey att 58.0%->84.8%,
  validated@10 19.0%->44.2% (fresh-era anchor ~77%, trajectory on course for v7);
  pdb 99.6%@10 | uniprot 98.2%@10 hold; entry-any 99.0%; weak frontier = ion class
  (34.4%@10, att 51.4%). Artifacts: /data/validation/stats_s7_v6_5.{log,json}; 60,386
  new sim pairs on top of 901k cache; run = --full --sim --sim-budget 150000 (~2h).
- Spin observability: SPIN_DEBUG=1 enabled fleet-wide on validation-worker (pre-built
  instrumentation). KEY toolkit: per-generator [SPIN] START/DONE markers (eefeff9c5) in
  kubectl logs — a stall names itself as START-without-DONE. Caveat: faulthandler
  dump_traceback_later re-arms per task start; cheap churn suppresses dumps by design.
- Residual spin SIBLING (compute-side, annotation-free): entries 9189-class sat >15h
  CPU-hot/logless with virtual-minority->non-strict-sequence->mini3di tail. Post-restart
  fleet shows healthy generator-level churn; no localized frame yet (next 15h-silent pod:
  check its results.debug.log tail + unmatched [SPIN] START).
- signature_isolated_timeout x3,996 in S6 = eefeff9c5 120s child-isolation catching
  generator timeouts at scale (pre-existing insurance, quietly active).
- Mirror annotation score cap 70 (no IUPAC/synonyms) shifts absolute confidence slightly
  vs PUG era by design; hit@K metrics unaffected.

## 2026-09-25 late — wedge CLASS hardened + spin-class root-caused and FIXED

- Fleets: `bat3-worker:v2.42` (bat3-ceitec ×15, bat3-ui ×2), `bat3-validation-api:v3.120`
  (validation-api ×1, validation-worker ×15). Commits aeced4bfb (broker hardening) +
  7196cd45c (verify annotation offline).
- Campaign: 5,897/15,185 completed (38.8%); bursty drain (~262/h cheap cohort, ~15/h heavy,
  ~56/h sustained average); ~9.3k remaining ≈ week-scale at current rate. 4 failed (3 poison
  + 1 download). Zero new failure classes since v3.120.
- Broker wedge (consumer stuck in BRPOP after CERIT resets): closed architecturally. Shared
  redis_broker_transport_opts() on ALL celery apps; socket_timeout bounds reads only (big
  simulations never interrupted — user constraint); visibility_timeout=6h kills the
  same-entry duplicate-run channel for long tasks. Detection lesson: ping/inspect lies under
  saturation — trust per-pod log freshness + kubectl top CPU + redis drain.
- Spin class: entries spun 3-6h at 100% CPU with zero logs inside verify; root = per-candidate
  PUG annotation HTTP (2×timeout=10s × up to verify_top_n=100 × fragments) against banned
  egress — NOT RDKit fingerprint math. Proven: SPIN_DEBUG dumps at pubchem_scorer.py:78;
  isolated .apply() repro. Fix: annotation scorer reads local mirror first (70-cap score),
  PUG fallback 3s timeouts. Acid: 7277 done in 215s (was 5h+), 0 HTTP. 32 fenced entries
  cheap-failed then requeued post-deploy (0 re-fences; they drain via FIFO position ~2.6k-16k).
- Ops facts: container names worker/ui-worker/api per deployment; psql heredoc needs
  `kubectl exec -i`; pod /tmp wiped per rollout (repro dirs die with pods); ephemeral debug
  containers RBAC-blocked; redis timeout 60 still runtime-only (persist TODO); celery list
  position lookup: `redis-cli lrange celery 0 -1 | grep <task_uuid>`.
- Next: drain at ~56/h → S7 v7 stats when bulk lands; audit_gap phase-2 (post-mirror weak
  chem requeue); leftovers: watchdog CronJob (Layer-2), TZ skew (bat3/ui pods log +02:00 vs
  validation UTC), redis args persistence, strip/replay ops scripts now committed.

## 2026-09-24 evening — PubChem mirror LIVE, chemistry re-run phase 1 in flight

- Images: bat3-worker v2.40 / validation-api v3.118 (+ celery keepalive/gossip fixes from v2.34).
- Local PubChem mirror production: /app/databases/pubchem/current (124.67M CIDs, golden
  parity 80/81 vs PUG). Identities + verification fetches offline; proof on entry 2188
  ligand: formula class 5.4ms, GT CID #1, verify fetches 2-6ms.
- Wave phase 1 re-run launched: 978 requeued (28 failed + 950 completed-in-fallback-era),
  2,389 processing continue; identify+verify+export refreshing with full mirror coverage.
- Opera status: redis CONFIG timeout=60 runtime (persist at next maintenance); plan
  docs/PLAN_PUBCHEM_MIRROR.md Phases 1-4 complete, Phase 5 (cron sync + final docs) open.

## 2026-09-26 late — inchikey-gap audit: numbers were noise, plumbing was the gap

- **Metric correction**: v6.5 S7 (44.2%/34.4%) was polluted by stale results.json of
  5,347 processing entries (legacy failed/partial contents counted). Liveness-filtered
  audit on completed runs: **inchikey organic att=99.3%, validated@10=75.2%, @1=65.1%;
  ion validated 72.1%** (matches fresh-era anchor). Any S7 must liveness-filter
  (load_simulation+verify_results success). See common-issues "Metrics trap".
- **gt_absent anatomy** (341 live annotations): 77% present-in-sim-but-windowed-out
  (163 protonation-frame family miss + 92 consensus-blind top-100 cut, median CID rank
  3,097, formula candidates identity-typed at consensus 100), 53 GT keys unresolvable,
  12 pair-cache zero poison, ~14 true absence. Proofs: entries 2451/2447/2164.
- **Root bugs found**: `formula_hfamily` local backend exists but is skipped by the PUG
  circuit breaker (listed in _PUBCHEM_RESOLVERS); verify_top_n cut is structure-blind
  for chem candidates. Fixes designed: F13/F14/F15 in docs/CHEMISTRY_FIX_TODO.md WAVE 5 —
  awaiting user approval to implement.
- Audit artifacts: /data/validation/audit_chem_ion.json, audit_gt_absent{.json,_rows.jsonl};
  scripts .tmp/audit_*.py (reusable for post-fix cohort).
- Campaign: drain continues on v2.42/v3.120 (~40% complete); no new failure classes.

## 2026-09-27 — WAVE 5 landed: cohort re-audit confirms chemistry fixed

- Fleet: v2.43/v3.121 (F13+F14+F15, commit 5af0ef4f6). verify_rerank_max_candidates
  25000 -> 60000 in config_shared.ini (config-only; cap skips were pre-config instances).
- Post-v3.121 cohort audit (890 completions, 765 organic ann, liveness clean):
  **inchikey validated@10 75.2% -> 87.1%, @1 65.1% -> 68.9%; gt_absent 19.6% -> 7.3%
  (floor ~4%)**; no_family 0.3%; pair-cache poison over (322 unmapped / 24,098 fresh).
- Ion class 61.7% on this cohort (was 72.1% pre-fix live): likely cohort composition
  (chemistry-era backlog, metal-cofactor dense); untouched evidence path; watch on the
  general cohort, next audit target if persistent.
- Campaign: 10,003 completed (65.9%), rate ~18/h during heavy rerank cohorts (expected
  latency price), 0 new failures, 0 re-fences. Next: final drain -> S7 v7 (liveness-
  filtered) -> phase-2 audit_gap -> ops leftovers (watchdog, redis args, TZ, mirror
  Phase 5). Perf follow-up queued: precomputed skeleton FPs in mirror build.

## 2026-09-27/29 — smiles-canonicalization storm: fence-watchdog era + fleet redistribution

- **New freeze class (localized)**: RDKit `MolToSmiles` canonicalization spins forever on
  small dense cage/ring junk clusters produced for virtual `SYSTEM__vN` fragments.
  NOT size-correlated (4,247-atom systems poison same as 161k); hits `smiles` AND
  `smiles_not_sanitized`; siblings later surfaced at `selfies`/`inchi_key` stages;
  third variant = hung external HTTP (cactus.nci.nih.gov 10.4h, uniprot/PUG calls with
  no timeout). Signature: `[SPIN] <seg>/<gen> START`, zero DONE, pod ~1 core CPU-hot.
- **Mitigation shipped (ops-only, no app code)**: three manual waves (50/99/96 fenced)
  then the **fence-watchdog** (`/tmp/fence_watchdog_v2.py` on validation-api, 10-min
  cycles): any `[SPIN] START` tail >30 min or HTTP-connect tail >75 min among live
  `processing` entries → fence to `failed/quarantined`, append NFS file
  `/data/validation/quarantine_smiles_spin_2026-09-27.txt`, inline-LREM all listed
  entries' celery messages. Corpus ≈ 420 (2% of campaign) — PRESERVED as the regression
  suite for the future fix. Also reaped ~18 kombu-zombie pods (7-20h silent, heartbeat/
  sync tails, zero CPU) — classic dead broker flows (Sept-24 class, no restart).
- **Duplicates-as-refresh insight (user-confirmed by repro)**: the ~31k redis backlog is
  NOT parasitic. Re-runs re-execute the FULL stage chain and rewrite results.json with
  post-F13/F14/F15 code (proof: entry 6533, first completed 09-27, full re-computation
  09-28). Purge proposal rejected; true campaign finish = backlog llen → 0, not rows =
  100%. rows max(completed_at) freezes once all rows touched (re-runs don't move rows).
  results.json is PARTIAL while rewritten mid-flight → S7 v7 must liveness-filter.
- **Fleet redistribution (user-directed)**: 15 → 48 → 96 (24/48 Gi) → 192 pods
  (1c/16-32Gi, CPU res held 192) → 492 → final **164 pods × (3c req/4c lim, 16 Gi req/
  24 Gi lim)** = **492 cores reserved** (+300 user-ordered). Observed: pods ≈ 1 compute
  thread each (max ~1 core despite 2-thread config) — per-pod single-core reality drove
  the sizing. RAM live ≈ 6-7% of reservation (reservation = monster OOM insurance only).
- **Campaign (2026-09-29 10:00 UTC)**: rows 13,854/14,624 (94.7%), 354 first-time
  monsters grinding (~few/h); **backlog 10.6k and draining ~600-1000/h → ETA tonight –
  Oct 1 early**. Zero data corruption; every terminated job resumes via celery
  visibility + results.json resume.
- **Next**: drain → S7 v7 (liveness-filtered, mandatory) → phase-2 audit_gap → fix design
  (F17 subprocess-isolated generator budget; corpus ready) → fence replay of ~420 →
  ion deep-dive → ops leftovers. See common-issues: "smiles canonicalization spin",
  "RS quota coexistence trap", "duplicates-as-refresh".

## 2026-09-30 — WAVE 7 (ENAR) shipped fleet-wide; campaign fully terminal

- Nucleic-acid recognition hardened end-to-end behind
  `enhanced_nucleic_acid_recognition` (default on: code, config.ini,
  config_shared.ini, UI defaults). See CHEMISTRY_FIX_TODO WAVE 7 for the full
  change list (A1/A2 tiered recognition w/ cross-residue phosphodiester
  guard, B1-B4 sequences+backbone, C1 orientation-aware verification,
  molecule-type anti-stomp). Commits 0920eebaa..bfc077fdb + 9f98d8e45.
- Images live: bat3-worker:v2.44 (×15 ceitec +×2 ui), bat3-validation-api:v3.122
  (validation-worker ×164 + validation-api), frontend rebuilt (nginx landmine
  defused, see common-issues). Watchdogs relaunched on new API pod (v2+v1).
- Campaign (14,624): **ALL terminal** — 13,857 completed + 767 failed.
  Refresh backlog drained naturally pre-rollout (~22h tail). Failed anatomy:
  334 corrupt inputs ("No loading strategy", e.g. entry 9754: topology 11.5k
  atoms vs trajectory 30 atoms = truncated download), ~420 smiles-spin
  quarantined (F17 corpus, q=437 current), poison/others ~13.
- Next: (a) triage 334 corrupt entries (re-download feasibility), (b) S7 v7
  liveness-filtered on the completed set + phase-2 audit_gap, (c) F17
  subprocess generator budget -> replay ~420, (d) ops leftovers (FE bond-guess
  known, frontend nginx param per release, unwrap classifier reconciliation).

## 2026-10-01 — campaign statistics arc complete: S7 v7/v8, audits, F16 shipped

- **S7 v7** (liveness-filtered per playbook §9; patch `.tmp/patch_stats_liveness.py`
  on NFS `campaign_stats.py`, bak-pre-v7): 13,324 live entries, 1,299 not-live
  skipped, 119,666 new pairs. S7: pdb 97.2/99.0/**99.6** · uniprot 94.2/97.2/**98.2**
  · inchikey 53.4/75.6/**84.8** · ion 35.1@all (att 52.2% only) · entry-any 99.4%@10.
- **Audits** (`.tmp/audit_chem_ion.py`, POST_F14=1, 4,641-entry cohort): organic
  misses are RANKING losses (engine_miss_identity 275 sim=1.0 at rank 12-37 +
  band_buried 224), not retrieval — window has gate-verified candidate for 96.8%.
  Ion misses are DETECTION losses: protein-coordinated metals invisible
  (no_metals frag type: protein x642; Zn n=591 validated 27.1% vs Cl/K/Na ~100%).
- **F16 fidelity-first ordering** (commit 811ddb55e, this repo:
  `src_new/verification/manager.py` + 6 tests, 16/16 green): verified chem hits
  sorted skeleton-fidelity-first in stored order; deterministic tie-break chain
  per UI relay (skel desc -> conf desc -> identifier asc -> type asc; UI displays
  verbatim). Projection-validated BEFORE landing (rerank_projection.json).
- **S7 v8 official** (`campaign_stats_v8.json`): inchikey @5/@10 **85.8/90.6** (0.7),
  entry-any 99.5%@10; pdb/uniprot bit-identical expected, tie-break noise only.
  Flip dissection vs projection (flip_dissection.json): 170/649 projected-fail
  rows pass under v8 — 147 tie_reposition + 23 window_membership = within
  tie-cluster noise, NOT a rule change. **@10 is tie-sensitive ±1-2pp; quote v8.**
- **Residual truth**: 479 organic annotations still fail @10 (residual_failing_rows.jsonl);
  273 have the GT skeleton nowhere in the entry (63 pure-protein boxes) = content
  floor; rest = variant-layer (salt/stereo/protonation) + gate-band stragglers.
- **Inchikey-vs-proteins explained** (user Q): proteins self-referential GT in
  the box + tiny ranked space; inchikey GT is bibliographic — presence empirical,
  candidates self-discovered among hundreds, Tanimoto analog continuum, and
  confidence-order loss = the residual. Ceiling ~=93-94% window coverage; we sit at
  90.6 @10 / ~94 in-window of the honest frame.
- **Next-wave specs** (`.tmp/TASKS_next_wave.md`, to be promoted into
  CHEMISTRY_FIX_TODO WAVE 8): (A) F19 coordinated-metal awareness in
  analyze_universe (ion fix); (B) pubchem_db coverability probe of the 479
  (buckets: not-in-mirror / first-block-only / not-proposed); (C) F17 subprocess
  generator budget + replay of 437 (fleet-wide image first, watchdog-quiet gate).
- **Task B coverability probe DONE** (`.tmp/coverability_probe.py`, in-worker
  run; hard-gated metric regen matched v8 anchors EXACTLY: 5,784/5,768,
  56.3/85.8/90.6). Authoritative v8 failing set = **541 rows / 341 unique iks**
  (supersedes the 479 projection-era number). Buckets: GT_NOT_IN_MIRROR 130 ·
  FIRST_BLOCK_ONLY 25 · IN_MIRROR__NOT_PROPOSED 264 (171 boxchem = requeue
  class; 129 with >=0.7 analog in-window) · IN_MIRROR__SURFACED_BUT_LOST 122
  (81 with >=0.7 in-window). Frame: raw **90.6** (5,784) · excl-uncoverable
  92.7 (5,654) · excl-uncoverable+variant 93.1 (5,629) — ~6.7pp of the gap is
  pipeline-recoverable (386 rows; 210 already have a >=0.7 candidate in-window,
  i.e. ranking/verification work not retrieval). Phantom hunt: +1 annotation
  was MY replication bug (official S7 `if r["hits"]` empty-hits guard); v8
  numbers stand unrevised. Artifacts: coverability_probe.json,
  coverability_rows.jsonl, residual_failing_rows_v8.jsonl,
  coverability_ik_cache.json, coverability_classes.json (+drift) on NFS.
- **F19 coordinated-metal awareness (ion channel) — PHASES 0-2 DONE**:
  audit proved the mechanism (single-atom metal residues orphaned from
  connectivity segmentation; 27/27 invisible at instance layer, 26/27
  protein/nucleic-coordinated <=3.0 A; entry 4341 arithmetic). Fix = presence
  parity (Option 3): metal_scan pass -> fragments/metals (vocabulary =
  metals_like verbatim incl. halides; transition-only capped context via
  lazy cKDTree; clean degrades) + _ion_elements_of add-only union. Commits
  dfea2a4d7 (15/15 tests) + c72688e7e (23/23; scripts/campaign_stats.py now
  canonical synced source). Official-frame projection (old==v8 anchors
  bit-exact): ion att 52.2->97.3%, val 35.1->95.6%, +1,057 flips 0 negative;
  Zn 26.2->92.3. Perf 83ms@350k salt / 378ms@348k mixed. NFS metric
  .bak-pre-metals; no-move check: ion/pdb/uniprot/entry-any BIT-IDENTICAL.
  Organic inchikey +0.2pp @10 in same-cohort rerun = positive-resolution
  cache growth (web nondeterminism; v8 90.6 stays official — see
  common-issues cache-state sensitivity).
- **Task C / F17 ruling (user, 2026-10-02): 437 stay quarantined; no F17 work
  this wave.** F18 folded into the same standing spec for later.
- 7 PRE-EXISTING master test failures (test_fragment_store/
  test_universe_facade, e.g. KeyError: Segment 'SOL' not found) A/B-verified
  NOT from F19 — suspected WAVE-7/UI-side fallout; awaiting triage owner.
- **F19 COMPLETE — v9 OFFICIAL (2026-10-02)**: ion att 52.2->97.3%, val
  35.1->95.6% (projection exact to the decimal); pdb/uniprot unchanged;
  inchikey 90.6->91.3 (cache-growth, disclosed); entry-any 99.6. Audit cohort
  (4,641): validated 841->1,684 (96.9%); Zn 27.1->93.6%; no_metals 647->33.
  Rollout: bat3-validation-api:v3.124 on validation-api; fleet roll deferred
  to F17 wave. Replay: 857-cohort spliced (852+5 idempotent, 0 errors/
  timeouts/mismatches) via replay_fragments_metals.py. En-route fixes:
  (a) f7baeb734 WAVE-7 tuple-unpack in virtual-segment branch (was the
  replay blocker; 3 regression tests); (b) kubectl container-name phantom
  trap + ephemeral-watchdog-loss lessons in common-issues; (c) PodSecurity
  restricted admission now requires per-container securityContext (worker
  deploy already compliant; api deploy patched). The 7 pre-existing master
  test failures are a DIFFERENT class, still open for triage.
- **F-residual ranking wave DONE (2026-10-02; S7 v10 OFFICIAL)**: 406-entry
  cohort replayed via 41-pod fan-out (0 errors; 3-chunk v1 lost to a fleet
  rollout — /tmp logs lesson, recovered same-day). Snapshot diff ground
  truth: 118 movers (+112/-6), net +1,520 chem-verified hits.
  **inchikey @10 raw 90.6 -> 91.3* -> 92.9; ion 95.6 / pdb 99.6 / uniprot
  98.2 all FLAT (controls).** Coverable-normalized frame (gate-verified
  regen==anchors): raw 92.9 / excl-not-in-mirror 95.0 / excl-floor+variant
  95.4. **Flip accounting: 541 -> 410 residual; 131 FIXED, 0 regressions,
  0 bucket transitions** (NOT_PROPOSED 264->182, SURFACED 122->77,
  FIRST_BLOCK 25->21, not-in-mirror floor 130->130 by design); 131/5784
  = +2.26pp, reproduces the raw move. Residue: 114 boxchem requeue class,
  77 surfaced-lost, 148 content-unattainable; audit top classes
  engine_miss_identity 273 / band_buried 222. Ops lessons added: no
  stats+audit co-scheduling on api pod (OOMKill); long-run scripts on NFS
  not /tmp; results.json double-nesting. Worker requests now cpu=250m
  (limits unchanged), 164/164 rolled.
- **F-boxchem requeue wave DONE (2026-10-03; S7 v11 OFFICIAL — negative
  result)**: 112-entry full-pipeline requeue of the 114-row boxchem class ->
  probe rerun (v11 anchors, GATE OK): residual 410->410, ZERO flips/
  regressions/transitions; inchikey @10 5374==v10. Falsification: upstream
  deterministic, residue engine-bound; organic ceiling this code era 92.9
  raw / 95.4 normalized. v11: ion 95.8 / pdb 99.6 / uniprot 98.2 / entry-any
  99.6 (controls flat). Ops: stale-worker theft wave (19/112 stolen by 64d
  v2.44 pool over shared broker) resolved by upgrading bat3-ceitec-bat3-wor-
  ker to v3.124 (user ruling: one project, stale=upgrade); whole namespace
  now v3.124 workers x179 + web w12 + api ui-rework-b1. 1 celery-meta-loss
  settle (clock-skew node) manual w/ verification.
- **Bag-of-molecules funnel v11 (user S-metric, NEW)**: 13,917 entries ->
  25,451 molecule-units; searchable-signature coverage 100% (A=100/B=100,
  fingerprint-class empty); >=1 identifier hit 89.5%; >=1 verified 87.7%.
  Per class: protein 93.6% verified, chem_other 94.6%, **nucleic 1.9% hit/
  verified — NEW HOLE => task N1 specced (.tmp/TASK_N1_nucleic_resolution_
  audit.md), awaiting scheduling.**
- Open besides: 334 corrupt download triage; phase-2 audit_gap; FE bond-guess
  (deferred); zombie-PID exit-hang pattern (harmless, reap on pod touches);
  fence-watchdog revival (rides F17 wave — NFS-safe this time);
  7 master facade/store test failures (separate class, triage open);
  replay_identify_verify needs a WORKER pod (mirror at /app/databases;
  api pod lacks it).

UPDATE 2026-10-03 (N1 audit COMPLETE): Nucleic hole root-caused at L0 evidence: dead RCSB structure channel campaign-wide (0/40k, URL-404 -> RCSB-404 passthrough; schema confirmed for proteins, backend = protein-only by design); 50.4% of hitless = no sequence (merged-multistrand linear-path limit); 49.5% = short-oligo blast gate physics (user hypothesis confirmed, 744/824 are 20-mers with zero deposited content). Artifacts /data/validation/n1_*.json.

UPDATE 2026-10-03-2 (N1 FIX WAVE in flight): W0-W5 all fixed and committed - W0 foundations (1f1523f25: fixtures/goldens/gates), W1 F-N1e (f230fbbf0 stage_errors persist), W2 F-N1a (b6a9fbf35 DEPLOYMENT_FILE_URL env + validation route), W3 F-N1d (e227cea48 mock parity), W4 F-N1b (94be929c5 strand-select; 1682 SYSTEM == campaign v1 byte-exact), W5 F-N1c (fae6b00f5 exact-short-identity). Image v3.125-N1 built+pushed. 4725 divergence RESOLVED (03d30e13b; overlay-harness BAT3_SRC shadowing, not code; deterministic W4 protein-broadening allow-listed). W6 probes + W6b ROLLOUT DONE (ab3035c65): ceitec api (route-verified 70+1), validation api/worker x164, ceitec worker x15 all v3.125-N1; config_shared.ini [pdb] deployment_file_url -> bioid-ceitec; public smoke 200/md5 + RCSB 204 fetched-ok (was 404 pre-rollout); fleet gates 10/10. bat3-ui-worker x2 upgraded to v3.125-N1 same day per user ruling (workers are workers; queue partitioning is api-level) -> ALL 183 worker pods one lineage. W7+W8+W9 ALL DONE 2026-10-03: nucleic 1.89%->19.75% verified-hit (32->412), frozen windows exact (5784/5768, @10 92.9), chem residual 410->410 zero flips, package v12 official (stats_package_v12.* + campaign_stats_v12.json + n1_postwave_rate.json + n1_w8_flip.json). Remaining: 11 pathological signature-timeout stragglers (pre-existing, finish naturally). Decisions pending: NA-RCSB containment, W10 all-class requeue. Full status + pickup: .tmp/PICKUP_N1_FIX_WAVE.md; CHEMISTRY_FIX_TODO wave section.

UPDATE 2026-10-04 (FINAL AUDIT + ONLINE DOCS): Read-only whole-codebase audit executed (no code touched; findings reported for user disposition). Wave 1 corrected agent memory to ground truth: pipeline lives in src_new/ (115 py, 21.5k LOC, baked as /app); production validation-api = repo-ROOT main.py (md5-verified in pod) + root queue_processor.py/models.py/tasks.py; ceitec api = src_new.api.main (image CMD); bat3_validation/api v2.5 lineage has NO live deployment; fleet = 181 workers all v3.125-N1 (kubectl context = kuba-cluster, not cerit). 28 findings pinned to ledger (commits e1c1c0ac0 + f54ebb962; master register .tmp/final_findings.md): headline F-03 restart-resume inert (start_run resets persisted statuses before skip-check), F-05 12h sweeper requeues forever (straggler factory, no cap/quarantine), F-09 dormant pre-W4 shadow tree on ui-worker PYTHONPATH (/data/validation/patched_src, inert by CWD precedence), F-17 confidence gate vacuous (min_final_confidence=0; identity verify = resolver self-assertion), F-21 [identifiers] toggles dead except 3 (V-20 confirmed), F-23/24/25 RCSB channel issues (NA design-dead + composition filter excludes mixed entries + silent 10-row truncation), F-26 armed legacy dispatch (ts-less run_ids), F-28 official stats tooling NFS-only/unversioned. Verified healthy: celery hardening, settle guards, stage budgets/errors wiring, chain-collapse dedup, F-N1d fixed by wave-7 B4, RCSB fetch all-200 W8 window, canonical maps identical. Wave 3: online docs built at docs/site/ (mkdocs-material, 9 pages, commit 6477f31fe) documenting audited behavior incl. dead-key/F-17 honesty notes; legacy docs flagged stale (ARCHITECTURE.md old tree) not overwritten. Decision queue with user: F-dispositions (top ROI: F-03/F-05/F-09), NA-RCSB containment (now informed: protein-only channel), W10 scoping, site hosting, legacy-doc supersede marks. Pickup: .tmp/PICKUP_FINAL_AUDIT.md (decision-oriented, supersedes PICKUP_N1_FIX_WAVE.md for current state).

UPDATE 2026-10-04-2 (FIX VERIFICATION + PROD DEPLOYMENT v3.126-audit2): Decision queue rulings executed - A-block: F-09 fixed live (pre-W4 NFS shadow tree /data/validation/patched_src deleted 1.5MB + PYTHONPATH dropped from ui-worker), F-10 wontfix, F-08 later (env actually present only on validation-worker), F-13 deferred-to-migration. B-block: F-01 fixed (ed4322254 stub routes), F-04 armored (b65ea8845 truthful DO-NOT-DELETE comment), F-02 documented (372dec800 fallback CMD), F-26 deferred to dedicated workstream (scope widened: 6 main.py call sites + src_new endpoint share ts-less schedule_validation path; recon brief .tmp/LANE_C_BRIEF.md), F-03+F-05 fixed AND deployed. INCIDENT: first F-03 (ef1bc0ec1 start_run-setdefault) activated the never-fired 2026-09-18 skip path whose latent missing-context bug exploded live on 1612 requeue (unwrap 'warning' re-ran after skipped loader; missing_universe; 14.8s fail) - caught by user-mandated live sim-requeue verification; workers N1-rolled-back within 25min; semantics revised per user ruling (4b374e306): skip ONLY generate_signatures/identify_molecules/verify_results, ONLY on persisted 'success'; context chain + export always re-run. VERIFIED LIVE on v3.126-audit2 (ALL 5 deployments, era-coherent; rollback yamls .tmp/rollback/v3.126/): baseline 45s -> recovery full-run 44.9s identical semantics -> resume run 15.0s (3x) identical semantics with "Resume: skipping ... (persisted success)" log lines; F-05 synth straggler quarantined in one 30s tick (queue+entry failed, cycle 4/3); F-04 fleet registration 181/181; F-01 single routes. Straggler implication: 11 pathological stragglers now terminate within <=3 stale cycles (~36h). Ledger CHEMISTRY_FIX_TODO.md Section E pinned (27f647f59); ops lesson V-24 added (dead-code activation requires live proof). Docs site polished to deployed semantics (resume/quarantine/PYTHONPATH/patched_src). Empirical artifacts: .tmp/f03_repro.py, .tmp/f03b_executor_skip.py (12/12), .tmp/f05_stale_test.py (12/12). NEXT: methodology dossier via Lane B (.tmp/LANE_B_BRIEF.md -> .tmp/METHODOLOGY_DECISIONS.md) then user walks C/D queue items 11-25.

UPDATE 2026-10-05 (AUDIT WAVES A-E ALL COMPLETE, fleet v3.129 era-clean): All 28-finding methodology queue items ruled by user and executed in five waves with per-step empirical tests + commits + checkpoint tags. Wave A hygiene (F-18 map unification ae397f064, F-16 2292d79aa, F-07 c9821a9f9, F-06 46b59a0ff). Wave B runtime semantics, one image: F-21 CORRECTED (ef4ac367d - audit half-wrong, getattr blindspot; dual <name>/<name>_similarity mechanism existed; fixed 8 undeclared config fields + 5 classes/7 instances assigning name after super().__init__ making toggles keyed on ''), F-25 (c26810250 RCSB paginate rows=10000; proven 464 tot/10->464), F-17 (e562eee12 verified_without_corroboration flag, telemetry-only zero metric shift), F-23 (65ae1c536+F-23-ref fad7892d7 NA containment verdict na_mode_unsupported; stage-2 residue classifier added after live gate caught trimmed-signature gap -> v3.127->v3.127.1). Wave C F-15 (1ff4e76b3): parallel identify fork DELETED, delegates manager.resolve against seeded temp ResultsManager; offline 10/10 equivalence+breaker+overwrite proofs; runs.py parallel-default route was live-arming the fork; deployed v3.128. Wave D repo-only (6f419b486+3f323b2ec + tag v12-stats-generators): 34 NFS stats scripts -> scripts/stats/ byte-identical md5-verified; GOLD E2E = repo-copy assemble_v12 regenerates official v12 artifacts IDENTICAL (ts-normalized); gt_absent anatomy STABLE; F-N1d closed; mis-flag recount=21 -> REPORT-first OQ-9 (virtual-minority segments carry protein-name generators; RNA letters as protein fasta entry 2346 SYSTEM__v4). Wave E F-27 (0bbe57de5, v3.129): constants promoted src->src_new (value+md5 equality; pre-f27-checkpoint tag; subset-fallback divergence fallbacks deleted per ruling; 3 import sites not 2); minimal pyproject (requirements.txt remains image truth). Live gates every wave (1612 requeues 165263/165264/165265 -> 15-30s resume pattern; counts identical; in-pod component proofs). OPEN QUESTIONS register OQ-1..OQ-9 documented ledger-bottom (formula_chembl inert-by-design, critical_errors persistence, 2 tracked .bak deletes, UI toggle, NA research, stragglers 788/9 horizon 10-06 ~04:00, W10 bundle, attempted-dup, OQ-9 misroute). NEXT: Wave F (F-24 additive-or-nofix + W10 replay-sweep-first) and Wave G (docs banners + k8s docs hosting + straggler closeout). Pickup: .tmp/PICKUP_AUDIT_WAVES.md.

## 2026-10-06 — audit-heal epoch COMPLETE (v13 era); stats published

- Epoch result: 28-finding audit queue ruled+executed (Waves A-E, F); fleet
  v3.131 all-5 deployments; OQ register closed except deferred lanes
  (OQ-4/5 backlog, OQ-8 cosmetic, OQ-12 new ops-idea).
- OQ-9 healed at family scale: official 21-row metric -> 0; full-family
  4332/4324 virtual misflags -> 0/0/0 (W10 one-time requeue, 4305/4324 at
  freeze; tail drains naturally; overcame wave-wide OOM kills via 3 audited
  dead-man reclaim rounds).
- formula channel offline-correct: pubchem local mirror (primary) +
  ChEMBL local mirror REVIVED v37 (2.9M rows; caffeine -> CHEMBL113 live);
  EBI REST formula API dead upstream (contained + documented).
- F-24 mixed complexes: additive `Protein/NA` channel shipped DEFAULT OFF
  (gold-fixture replays); can be enabled via ini [pdb]
  rcsb_include_mixed_complexes when the user decides to accept it live.
- Headline v13: entry-any 97.9/99.3/99.5 @1/@5/@10; channels S7
  inchikey 60.2@1 93.0@10 | ion 96.1 | pdb 96.9@1 99.5@10 | uniprot
  94.0@1 98.1@10 (annotations grew; pdb/uniprot -0.1..-0.4 = denominator
  effect of healed+new entries, not regression).
- Stats artifacts (NFS canonical + stats_v13/ bundle): stats_package_v13
  (json/md), campaign_stats_v13, per_molecule_stats_v13.csv (26354),
  per_molecule_by_species_v13.csv (15987 species; protein 10545 / chemical
  3901 / nucleic 997 / other 544), funnel_v13.json, heal recounts (=0).
- Ops notes: worker replicas ceiling 244 by ns limits.cpu quota; worker
  mem 24Gi limits caused OOM bursts during mass heal (at current 244
  steady); zombie/prefetch claim class = infra, handled by reclaim
  pattern (12h watchdog backstop + 1h dead-man ideal -> OQ-12).
- Ground truth ledger: docs/CHEMISTRY_FIX_TODO.md sections through F9;
  pickup `.tmp/PICKUP_AUDIT_WAVES.md`; next: audit tail close + Wave G
  (docs banners, k8s docs hosting, external incident registry note).

## 2026-10-06 (late) — F-26/OQ-13 implemented + v3.132 era deployed all-5

- Wave G COMPLETE: G1 banners / G2 docs hosting LIVE at
  bat3-validation.dyn.cloud.e-infra.cz/docs/ (image
  cerit.io/tomsko/bat3-docs, currently v3.132-g2.3), G3 F-05 terminal
  datapoints, G4a F-24 ENABLED live (proof 466=464+{7P0V,8ID2}; ini
  md5 889730df; rollback snapshot on PVC), G4b external incident
  registry Session-36 note (bat3_validation is NOT a git repo).
- F-26 dispatch unification (code census: legacy dead since 2026-08-06;
  UI Start -> main.py:2054, bioid UI -> src_new:541; API split-brain
  validation-api=main:app vs bat3-ceitec=src_new): legacy endpoints
  FROZEN by default (VALIDATION_LEGACY_DISPATCH=allow unfreezes; 410s),
  both start-processing endpoints rerouted to canonical
  process_validation_queue (commit 5c262f85e). Remaining: post-article
  hard-delete of 4 legacy endpoints.
- OQ-13 CLOSED: corrupt-cache class recurring (NFS relics quarantined
  /app/runs/_quarantine_cache/2026-10-06/); current era = ephemeral
  per-pod caches; code self-heal (quick_check -> rename-aside +
  recreate) + base.resolve sqlite guards (commit 06f72b110).
- v3.132 on all 5 image deployments; gates: external reroute 200
  {path: canonical}, legacy 410, F-04 intact (0 unregistered), +1
  organic completion on new image. Rollback .tmp/rollback/v3.132/.
- Lessons V-26 (quota-ceiling rolls: maxSurge 0 / maxUnavailable 25%,
  scale-dance nudge; stale 'perm-sweep' pod deleted per ruling) + V-27
  (ingress strategic patch replaces path lists) in common-issues.md.
- New register: OQ-14 (live validation-ui nginx lacks /api rewrite;
  bundle mixes prefixes -> /api/* 404 pre-existing; fix at UI wave).
- Ground truth ledger through SECTION H4; pickup file refreshed;
  w10-heal 4310/4324, tail 14 organic per ruling.

## 2026-10-10 — loading-strategy widening DEPLOYED 4/4 (v3.133 + w13); OQ-15 opened
Design/record: .opencode/context/bat3/concepts/loading-strategy.md (Deploy State = FINAL).
- Fleet: bat3-ui-worker(2) + bat3-ceitec-bat3-worker(15) + bat3-ceitec-bat3-api(1) on
  v3.133; bat3-ceitec-bat3-web on w13 (dropzone accept incl .psf/.dcd/.data/.rst7/.mdcrd/.cif,
  verified in served bundle). validation-worker=0 + dispatch=0 remain intentional (MDDBR off).
- Gates: replay 5/5 byte-identical pre-deploy; live E2E via POST /api/v1/runs:
  charmm_psf_pdb SUCCESS (input_kind=charmm/strategy=charmm_psf_pdb), solvent-pdb baseline
  SUCCESS. api healthy (pinned src_new entrypoint, 4 workers).
- INCIDENT during deploy: first api bump crashlooped — TWO stacked faults: DATABASE_URL
  env absent (F-06 default localhost:5432) AND v3.133 image CMD = main:app (wrong app for
  ceitec api; probes 404). Both fixed at ops level (env + pinned command/args); V-28 filed;
  chart command-pinning = permanent-fix candidate.
- NEW: OQ-15 open — amber prmtop+mdcrd AND prmtop+rst7 fixtures (synthetic, unnamed
  residues) wedge generate_signatures (1-core spin >=20min) live; runs cancelled, pods
  restarted. Not a prod regression (amber-coords input is new in v3.133). Follow-up:
  local py-spy profile + enumeration guard -> v3.134.
- Infra noise: Rancher control-plane API flapped 2x mid-deploy (self-healed; workloads
  unaffected). Port-forward used for API smoke (`svc/bat3-ceitec-bat3-api` 18000:8000).

## 2026-10-12 · Ion ground-truth rule landed live (v3.134/v3.135)
- Prod failure forensics (run fa3b942d, 2026-10-11): v3.133 image had lost `ncbi-blast+` (unversioned Dockerfile copy in ../bat3_validation lacked it) → all protein BLAST channels ENOENT; proteins verified nameless at conf 40; ions capped at 80 by construction (annotation weight unprovable for bare elements).
- User ruling (2026-10-11): ions are ground truth. Implemented element ground-truth override (monoatomic ELEMENT identity → conf 100, `ground_truth_override="element_monoatomic"`, hard scope guards; chemistry untouched). Repo `Dockerfile.full` canonicalized with blast restore; chart pins api command/args (V-28 closed).
- v3.134 live A/B (rerun 9d90d777): BLAST restored (65 named proteins, 5HVX/6SXG sim 95.3). A/B exposed a second bug: verify workers' minimal temp managers never saw universe segment properties (override stayed 80) → fix shipped in v3.135 (worker tuple now carries `universe/segments/<seg>/properties`; 5 e2e tests incl. real worker + real step).
- Live: worker×15 + ui-worker×2 = v3.135, api = v3.134, web = w13. In-pod E2E on A/B data: SOD/CLA/PORE_ION ions at conf 100 with override flag. Lessons: V-29 (image package-content gate), V-30 (minimal-payload worker stages). OQ-15 (amber signature wedge) still open.

## 2026-10-13 · Queue "stuck" incident resolved — SIGBUS task-loss (OQ-16 filed)
ui-worker hard-crashed exit 135 (SIGBUS) 07:17Z; 3 in-flight run tasks acked+lost (celery task_acks_late default false). 2 runs phantom-"running" 4.7h over idle fleet; 1 queued run's message culled (no celery lists in Redis; dangling unacked_index member timed at its enqueue). Remedied: POST cancel ×2; cancel+rerun of the queued run → new run efc63ac2 dispatched instantly and progressing. Registered OQ-16 (acks-late/idempotency, state reaper, SIGBUS source on ui fleet) + lesson V-31.

## 2026-10-19 · OQ-16 CLOSED — deadlock class eliminated (v3.136 live)
Rolled: api+worker+ui-worker v3.136 (acks-late/reject-on-lost + faulthandler),
state reaper live in api (redis leader lock verified), BLASTDB_MEM_MAP=0 on
both worker fleets (NFS-mmap SIGBUS defused). 6-day stable soak since last
SIGBUS. 3 residual zombies from 10-13 cancelled. Reaper live-smoke PASS.

## 2026-10-19b · v3.137 wave live — static PNG renders, Mol* gate, landing examples
Workers(15)+ui(2)+api -> v3.137 (pymol headless); web -> w14. render_png task
produces render/{system,segments}.png (Mol*-style transparent), 1M-atom UI gate
defaults big systems to static + opt-in override; landing page examples from
/runs/examples (auto newestsuccess+png or BAT3_EXAMPLE_RUNS env). E2E: 3 example
reruns queued (4ef9a8cc POPC, 22c4fade R2, 32066449 R0).
