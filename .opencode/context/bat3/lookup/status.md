# BAT3 Validation Status (2026-09-23 late, legacy wave in flight)

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
- Open besides: 334 corrupt download triage; phase-2 audit_gap; FE bond-guess
  (deferred); zombie-PID exit-hang pattern (harmless, reap on pod touches);
  fence-watchdog revival (rides F17 wave — NFS-safe this time);
  7 master facade/store test failures (separate class, triage open);
  replay_identify_verify needs a WORKER pod (mirror at /app/databases;
  api pod lacks it).
