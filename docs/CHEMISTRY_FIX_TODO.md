# Chemistry Identification Fix Plan (deep-dive 2026-09-11, probe-validated)

## Evidence base (why this plan)
- Entry 2207: azilsartan ACID correctly extracted (mol_L, 52 atoms) then corrupted: garbage SMILES (M1), formula -2H (protonation frame), InChIKey of nonexistent compound, formula-identity ~100 junk CIDs auto-verified @40 (verification bug, `src_new/verification/manager.py` hit_type=="identity" free pass).
- Population: 241/250 chem-GT entries best_sim<0.3; S7v2 att=84% / mean@10=0.004; proteins >=95% via similarity path.
- Probe (live PUG + RDKit, recorded in registry session 6):
  - skeleton-FP Tanimoto: neutral vs -2H dianion = 0.889 (protonation-tolerant); true vs formula-mate junk = 0.19 (junk rejected); acid vs medoxomil = 0.578 (correctly distinct)
  - skeleton-SMILES unusable as PUG query vehicle (fastsim returns neither true form) -> skeleton-FP is for RESCORING, candidates come from fastformula H-family
  - GT mismatch class: MDDBR annotates azilsartan MEDOXOMIL (prodrug) but sim contains azilsartan ACID -> ~real mismatches exist; must be flagged, not blamed.

## Design (keystone): `skeleton_fp` signature
RemoveHs -> collapse all bonds to SINGLE -> uncharge -> Morgan r2/2048 bits + heavy-atom formula.
Signature value format: `skelfp:v1:<hex>|<heavyFormula>` e.g. `skelfp:v1:0a1f...|C25H18N4`.
Same currency everywhere: identification rescore, verification gate, S7 validation.

- Candidates: fastformula H-family (H+-4) union + InChIKey connectivity-layer (when trustworthy structure exists) + CCD templates when resname known.
- Verify: candidate CID fingerprint fetched from PUG -> skeleton-Tanimoto >= 0.7 (tune on 2207/1532) -> is_verified.
- Validate (S7): skeleton-Tanimoto vs GT-CID skeletonized reference; report both 0.7 and 0.85 columns during migration.

## Phase 1 — Signature + verification honesty (ship together, avoids blind window)

- [x] **F12 — `skeleton_fp` signature generator + shared util** (DONE 2026-09-12: `skeletize.py` + generator + config + registry; 13 tests; H-scrub invariants)
  - Goal: new signature type generated per small molecule; shared skeletonization util used by generator, verifier, S7 mirror.
  - Files: new `src_new/signatures/generators/skeleton_fp.py`; new `src_new/signatures/skeletize.py` (collapse/uncharge/FP/heavy-formula util); register in signatures registry + config (`SignaturesConfig`)
  - Validation: in-pod dry-run on /data/validation/2207: mol_L -> skelfp present, heavy formula `C25H18N4`, FP hex; azilsartan-acid CID skeleton-Tanimoto ~0.89.
  - DoD: results.json contains skeleton_fp signature for mol_L; unit test collapses aromatic mol without exception and is deterministic.

- [x] **F7 — Skeleton-FP-gated chemical verification** (DONE 2026-09-12: gate in `verification/manager.py`; threshold 0.7; offline 2207 replay: junk 0.14-0.28 rejected, acid 1.0, prodrug 0.73)
  - Goal: chemical ident_types (PUBCHEM_CID/CHEMBL/CHEBI/INCHIKEY/SMILES) NEVER verify on hit_type=="identity" alone; require skeleton-Tanimoto(candidate, molecule.skeleton_fp) >= threshold; record `self_sim` + `sim_method=skelfp` on VerifiedHit. `hit_type=="identity"` free pass remains ONLY for accession-level protein/nucleotide types.
  - Files: `src_new/verification/manager.py` (evidence rule), `src_new/verification/models.py` (fields), fingerprint fetch via existing PUG helpers + NFS fp cache
  - Validation: rerun verifier offline on stored 2207 signatures -> ~0 verified chem hits (honest), unverified reasons = `fingerprint_mismatch`.
  - DoD: no formula-list CID verified without corroborating fingerprint evidence; unit test with synthetic formula-mate list.

- [x] **F7b — Formula-resolver hits are candidates, not identity** (DONE via F7 gate: chemical identity cannot self-verify regardless of hit_type tagging)
  - Goal: `formula_pubchem` results tagged hit_type non-identity (candidate class); verification dedup no longer promotes formula groups to identity.
  - Files: `src_new/identification/resolvers/formula.py`, `src_new/verification/dedup.py`
  - Validation: identifiers sections show non-identity hit_type for formula hits.
  - DoD: grep of results.json shows no identity-tagged formula hits in new runs.

## Phase 2 — Tolerant candidate generation (identification)

- [x] **F9 — fastformula H-family resolver (candidate generation)** (DONE 2026-09-12: `resolvers/hfamily.py` H±4 union, strict parse, ≤3 rps; rescoring stays in F7 gate)
  - Goal: given molecule formula C25H18N4O5, query fastformula for H in {H-4..H+4} (element profile fixed), union candidates, dedupe; each candidate fingerprint-fetched and skeleton-rescored; hits emitted with skeleton-Tanimoto as resolver score (identity-like quality, similarity-tolerant).
  - Files: `src_new/identification/resolvers/formula.py` (family expansion), PUG wrappers, per-candidate FP fetch + sim scoring hook (shared with F7)
  - Validation: on 2207 mol_L, candidate set contains azilsartan-acid CID and skeleton-Tanimoto ranks it #1.
  - DoD: azilsartan case end-to-end produces ranked list with true CID top; rate-limit respected (see Ops guardrail).

- [ ] **F8 — CCD template lookup (authoritative channel where available)**
  - Goal: resname -> CCD/PDB component dict -> InChIKey (connectivity-layer query) -> candidate CID, skeleton-rescored like all others. Fallback order: CCD -> H-family formula -> connectivity inchikey (if structure trustworthy).
  - Files: new `src_new/identification/resolvers/ccd_template.py`; registry wiring
  - Validation: known-resname ligand (e.g., arginine-class entry 1532) resolves true compound via CCD path.
  - DoD: entries with CCD-known resnames show resolver source `ccd_template` and skeleton-Tanimoto >= threshold.

- [ ] **F12b — Prodrug/GT-delta flag (GT-artifact class, reporting only)**
  - Goal: when best skeleton-Tanimoto lands in 0.5-0.75 band and heavy-formula delta matches known prodrug/adduct groups (e.g., medoxomil C5H4O3), tag `gt_delta_class=prodrug_like` on entry-level report; excluded from quality blame in S7 reporting (reported separately).
  - Files: `scripts/campaign_stats.py` (S7 annotation), small delta-table in `scripts/validation_similarity.py`
  - Validation: entry 2207 flagged prodrug_like with acid/medoxomil pair.
  - DoD: S7 output shows separate counter for gt_delta_class entries.

## Phase 3 — Extraction + legacy-quality (separate dives)

- [ ] **F11 — Lipid fragment reconstruction**
  - Goal: membrane molecules (cholesterol-class) reconstructed whole instead of ~14-atom junk clusters; virtual segments require intact-residue species.
  - Files: `src_new/loader/universe_facade.py`, fragment clustering
  - Validation: cholesterol-bearing entry yields intact 74-atom molecule + sensible SMILES.
  - DoD: no junk ~14-atom species clusters become signatures.

- [ ] **F10 — Legacy SMILES quality (deprioritized)**
  - Goal: topology-bonds path passes conformer to DetermineBondOrders; garbage-SMILES fallback labeled on signature (`trust: perceived|topology|ccd`).
  - Files: `src_new/signatures/generators/smiles.py`
  - Validation: `insufficient_bonds` warning rate drops on sample.
  - DoD: SMILES output labeled; metric no longer depends on this path (skeleton_fp is primary).

## Phase 4 — Ops guardrails + rebaseline

- [ ] **M7 — Rate-limit discipline + caches**
  - Goal: all PUG callers respect <=3 rps with 429/503 backoff jitter (self-inflicted outages observed); candidate-FP fetch uses durable NFS cache (`/data/validation/sim_cache/`) like S7.
  - Files: `validation_similarity.py` fetchers + resolver HTTP sessions (`_create_retry_session`)
  - Validation: zero 503 during probe-scale scoring; cache hit ratio visible in logs.
  - DoD: no ServerBusy bursts during F9 resolver runs.

- [ ] **M7b — Rollout: images + selective requeue**
  - Goal: deploy skeleton_fp+gate+resolvers in BOTH consumer images (worker v2.16, api v3.95, both consume celery queue); then selectively requeue inchikey-GT entries (SQL UPDATE ... status='queued' where entry in inchikey GT) for rebaseline, NOT global requeue.
  - Files: Docker build from `git show HEAD:Dockerfile.*`; rollout plan
  - Validation: both deployments on new images; requeue count = inchikey-GT count.
  - DoD: first requeued entries show skelfp signatures + gated verification in results.json.

- [ ] **M7c — Rebaseline metrics**
  - Goal: S7v2 (FT skeleton) on post-fix window + full population, before/after table; inchikey att should stay high but now mean-sim > 0.6 targets; prodrug_like class counted separately.
  - Files: scripts/campaign_stats.py runs
  - Validation: numbers recorded in registry session 6 + status.md.
  - DoD: final chemistry quality statement published in context.

- [ ] **M8 — Context harvest**
  - Goal: registry session 6 (deep-dive + probe + this plan), common-issues signatures (garbage-SMILES class, formula-identity flood, GT prodrug class), CHEMISTRY_FIX_TODO committed.
  - DoD: commit landed, context consistent.

## Parked / open
- No structure-consuming lipid resolver (lipids need F11 + own design later).
- `PUBCHEM_CID "0"` junk filter (falsy ids) — batch with F7.
- S7 family-depth cap (50) vs per-molecule ranking — revisit if best-sim ranks beyond 50 after F7 (evaluate on rebaseline data).
- Sweeper dwell vs celery backlog (STALE_HOURS=12) — recheck near campaign end.

---

## LANDED post-plan (2026-09-12/13 execution record)

### Phase 1-2 status
- [x] F12 skeleton_fp (`7863b56..` in `3d9a6a87f`) — generator+util+registry, live v2.16+
- [x] F7 verification gate (skeleton Tanimoto>=0.7) — live; 2207 replay junk 0.14-0.28 rejected, acid 1.0, prodrug 0.73
- [x] F7b via gate semantics (chemical identity cannot self-verify)
- [x] F9 hfamily candidate union (candidates-only; rescoring unified in gate)
- [x] Fetch hardening (v3.96 fetcher: polite retry, batch CSV prefetch 50/call, NFS smiles cache)
- [x] PubChem circuit breaker (skip PUG-dependent resolvers during outage; worker v2.18)
- [x] MGET settle batch fix (completion job no longer self-throttles; api v3.98)
- [x] IPv4-first transport fix (IPv6 PUG endpoint blackhole; images v2.19/v3.99)
- [x] Per-IP PUG block confirmed (laptop 200 / cluster 503); **PUG-independence stack shipped**:
      CID: cache -> PUG -> IDSM SPARQL mirror | inchikey: cactus -> chembl -> PUG
      ChEMBL/ChEBI native. images v3.101/v2.21, workers 16+16, pubchem_struct+formula_pubchem disabled in config
- [x] Celery ghost-fleet purge + NFS-truth settlement (23,705 ghosts purged; 5,181 settled completed)

### Metrics stack
- [x] S7 skeleton-FP currency (skel-cid/skel-inchikey re-versioned; validates>=0.7 chem / 0.9 seq), gate-verified counters

### Remaining (carry to next phase)
- [ ] F8 CCD-template bond assignment (authoritative channel for known resnames)
- [ ] F11 lipid fragment reconstruction (separate loader dive; A__v2 ~14-atom junk clusters)
- [ ] F10 legacy SMILES quality (deprioritized; skeleton_fp is primary)
- [ ] F12b prodrug/GT-delta reporting tag (band confirmed ~0.73; reporting-only)
- [ ] ChemSpider integration (key available, 1000 tokens; add as CID fallback chain member)
- [ ] Re-scale workers when PUG stabilizes + config re-enable of disabled resolvers decision
- [ ] Final full-population skeleton S7 rebaseline (v3 run in flight)

---

## LANDED wave 2 (2026-09-14/15)

- [x] **M9 ion-GT class split** (scripts/gt_rules.py + S7 ion row): ions presence-scored via fragments.unique element summaries (~45% of no_molecule was GT ions; smoke(120): att=70% validated=70%; entry-any @1 96.3->97.2)
- [x] **F13 average-frame fix** (LoadStrategy.PDB trajectory frame-0; LOADER_STRUCTURE_SOURCE=average rollback; v2.24/v3.104): avg-frame proof entry 3392 sim 0.014 -> instantaneous 1.0; skel_low artifact class
- [x] **M10b cofactor unblacklist** (ccd.json: ATP/ADP/AMP whitelisted, matches GT keys ZKHQWZAMYRWXGA etc.; proof requeue 5 exemplars in flight)
- [x] **GT hardening stack complete**: ChEMBL standard_inchi_key poison removed (identical bogus SMILES for unrelated queries!); charged-species keys try -N form; GT harvest 3984/4311 (92%) cached durably; structure matrix fully PUG-independent
- [x] **True chemistry baseline measured** (signature-level): exact 11.3% / connectivity 15.6% / skel_high 20.6% / no_mol 25.5% / skel_low 23.7% (pre-F13; expect shrinking rework) / unresolved 2.9%

## Remaining (next wave candidates)
- [ ] **M10a peptide channel**: peptide GTs scored via protein sequence alignment (molecule exists as chain; chemical hash unfit). Design: organic/peptide-class split in metric + sequence-bridge scoring.
- [ ] Re-run signature-level measurement post-F13 (skel_low expectation: collapse).
- [ ] Sim v4 final population run with ion-aware + F13 + full alternates (current v4 numbers are pre-M9 era; rerun fresh population when tail completes).
- [ ] Worker upscale 16 -> 40 (queue tail complete).
- [ ] ChemSpider token top-up; optional second-tier CID fallback dedicated.
- [ ] Fold F11 note: classifier-suspect cohorts documented as classification, not bug.

---

## WAVE 3 — Chemical verification postmortem (investigation 2026-09-18, funnel-measured)

Funnel over 250 sampled inchikey-GT entries (of 7,342, all with results.json):
S1 skeleton_fp 204/250, own inchi_key 193/250, key==GT exact 43, same-connectivity 44,
diff-connectivity 106, no-structure 44. Candidates: pools exist 133/250 but similarity-
neighbor-only; pool_hit(>=0.7 cached-evidence) 11/250; verified chem **2/250**.
Rejections 8,948: 98% `fingerprint_unavailable`. Wire-fix proofs: 3023C 27 honest
mismatches, 3139C verified skel=1.0 through production gate.

### Defects + fixes (landed = working tree, uncommitted)
- [x] **D1 (CRITICAL) — verification wire bug**: `workers.py::_verify_results_worker` built
      temp ResultsManager with ONLY `identifiers/{seg}`; F7 gate molecule skeleton_fp always
      None -> 100% fingerprint_unavailable for chemicals since F7 shipped. FIXED: 4-tuple
      work items carry `signatures/{seg}`; worker sets it on the temp manager
      (`pipeline_steps/__init__.py` +7/-3, `workers.py` +9/-4; tests 7/7 + 33/33 green).
- [x] **D2a (HIGH) — inchikey resolver PUG-only + breaker-muted**: exact-identity channel
      dead (3606: extracted key == GT, pool top 0.692, inchikey section never attempted).
      FIXED: `fetch_cids_from_inchikey` PUG-first with -N variant, IDSM SPARQL reverse
      fallback (URI -> CID), soft-fail []; `inchikey_pubchem` removed from
      `_PUBCHEM_RESOLVERS` breaker set (+breaker test updated).
- [x] **D3a-c fetcher hazards**: poisoned ChEMBL standard_inchi_key step DELETED from
      `_fetch_inchikey` (live-proven 2026-09-18); cactus multi-line -> first valid line;
      `_fetch_inchikey` now cached via `_cache_*_ns('ikey', ...)`; `prefetch_pubchem`
      digit-only filter (tests 17/17 green).
- [x] **D4p — silent cache loss root**: `_cached_json()` wrote without makedirs and swallowed
      OSError; `inchikey_smiles` never in DIRS -> every GT structure re-fetched per run for
      weeks (NFS parent-mtime proof). FIXED: makedirs + DIRS entry.
- [x] **D4 — GT structure rebuild**: 2,710/4,311 unique GT keys durably cached in
      `sim_cache/inchikey_smiles/` (pass1 cactus 1,687; pass2 IDSM mirror +920/cactus +103;
      remaining 1,593 = ions/obscure/no-registry class, ChemSpider optional ~1k tokens).
      Persistence now permanent (D4p fix).
- [ ] **D5 — extraction residue classes**: lipid_shorthand (F11); skel-present-but-sanitization
      -failed; died-before-signatures. 42% diff-connectivity is the extraction frontier.
- [ ] **D6 — production boot-loop (S0 blocker)**: 12h sweeper vs >12h tasks (13 runs/entry,
      fail marks exactly 12h00m apart); celery metas expire in-flight (settle blind; 8,435
      unlinked settlements overnight); queue completed flat 7,128 >29h; celery ~19.7k;
      ~6,900/7,438 'processing' entries disk-silent >12h. Priced drivers: RCSB scorer flood
      (336k fetches/entry over 5 days -> FIXED by S1 below), PairwiseAligner pathology
      (S2 pending), 12h sweep re-marks + no NFS-truth settle (S3 pending).
- [x] **S1 — RCSB fetch flood**: new `fetchers/rcsb_cache.py` (sha1-keyed NFS cache,
      polite transport, `_CachedResponse` shim with `.text`), wired into `pdb_scorer.py`
      (+ instance memo), `sequence_fetcher.py`, `structure_fetcher.py`. Tests migrated to
      mock rcsb_cache; scorers 14/14 green.
- [x] **S1 regression tail**: root cause was NOT the mock targets — S1 had dropped the
      module's `import requests` while uniprot/ncbi paths still call it -> NameError ->
      silent None. Fixed by restoring the import; fetchers+scorers 31/31 green.
- [x] **S2 — aligner guard**: DP-matrix cell cap (25M) + `next(iter(alignments))` in
      `_compute_alignment_score` (no len/bool materialization -> count-overflow class
      eliminated); 2 new unit tests; workers 18/18 green.
- [x] **S3 — NFS-truth settle job**: `settle_by_results_truth` in `queue_processor.py`
      (head-slice tasks parser, stale-artifact guard via started_at-vs-mtime, warning-as-
      terminal, env kill-switches; per-item settle preserves batch counters + activity log),
      wired into `periodic_completion_check` in `main.py`; 9/9 unit tests green.

### Post-fix path — STATUS (finalized 2026-09-21)
- [x] **RW250 replay**: fixed gate over 250 persisted entries: 0.8% -> 48.4% entries
      verified; fetch-fail 98% -> 3.4% (proofs archived at
      `/data/validation/_ops_archive/session-13-14_2026-09-21/`).
- [x] **Deployment**: v3.111/v2.30+v2.31/v3.112 rolled on api+3 worker pools;
      consumers stable 247+ nodes, drain = ~100s/day, celery backlog melted 51k -> 0.
- [x] **Commit wave**: aea60ae5a (chem wave-3 fixes), 5c361e730 (stage budgets),
      11080a6e3 (resolver interior deadlines), eefeff9c5 (spin-class root kill),
      1de6860e0 (isolation revert).
- [ ] Full inchikey-gt replay (7,342) + S7 recompute (next big measurement).
- [ ] Requeue scope for isolation-window empty-content entries (decision pending).

## WAVE 3.5/4 — the freeze whodunit + mis-fortune (documented 2026-09-21, accept in full)
- [x] **Freeze root** (: +100% CPU 15h+, zero IO, generate_signatures): virtual-class
      fragment hit RDKit kekulization inside `smiles.py::Chem.SanitizeMol`. Proven
      live under SPIN_DEBUG instrumentation (`SYSTEM__v4/smiles START`, never DONE).
- [x] **kef-fix (eefeff9c5)**: kekulization eliminated from smiles (partial sanitize
      minus KEKULIZE, MolToSmiles kekuleSmiles=False); healthy molecules output
      identical; frozen class proven completing via terminal-verify.
- [x] **Isolation misfortune + revert (1de6860e0)**: child-process isolation by risky
      class timed out ~always -> silent signature vaporization en masse (entries
      completed empty). FULL REVERT authorized + shipped; outcomes on v2.31/v3.112
      confirm content restored (sigs 28-47, idents 120-41k, verified 73-300 fresh).
- [x] **Stage budgets** (outer+manager+resolver-interior identity+similarity phases+hfamily+verify):
      cooperative early-exit with honest stage_time_budget warnings; inert except in
      actual long-tail stalls (0 firings observed).
- [x] **Pipeline contract restored**: 2-10s per front stage, verify flows, completions
      sustained (queue settled ~119 first day, per-minute cadence after fixes).
- [x] **Residue reverify COMPLETE** (2026-09-22/23, waves A→B2→A3/B4): 3,444/3,446
      conf=0.0/fingerprint_unavailable-residue entries renovated in place via
      `scripts/replay_verification.py` (post-loop write-block bug fixed, --threads/--entries-file).
      Two final entries lost to hung network reads (statistical noise).
- [x] **Storm era sealed (2026-09-22)**: poison entries 2290/2291/2299 (76.5k-bond
      non-linear fasta_map class) failed permanently; 84x3 stale claims reclaimed via
      repo sweep semantics; celery `worker_prefetch_multiplier=1` durable + CLI pins
      `--concurrency=2 --prefetch-multiplier=1` on both worker pools; fleets
      redistributed 30×10Gi → 15×20Gi (same budget) under user authorization.
- [x] **The invisible cork (2026-09-23, commit 2dfd5fdcb)**: `IdentifierResolver.__init__`
      dead-code-after-return orphan (`enabled_similarity` unset) crashed EVERY
      `_identify_molecules` step since Sep 20 — swallowed by executor → crash-resume
      loops: 2,325 results.json touched/12h, 0/400 all-stages-done, completions ~0.
      Fixed, images v2.32/v3.113, completions resumed immediately.
- [x] **METRIC VERDICT (2026-09-23, /data/validation/stats_s7_v6.log)**: 15,185 entries:
      inchikey n=5,914 att=58.0% validated@10=19.0%; ion att=51.4% v=34.0% flat;
      pdb validated@10=99.6%; uniprot @10=98.4%; entry-any@10=98.9%; exact ≥1 hit 87.6%.
      Rank audit (n=500 fresh): evidence@1 in ALL covering cases → rerank headroom=0.
- [x] **Inchikey low-numbers audit RESOLVED (2026-09-23)**: the 19% aggregate is an
      era artifact driven by the PubChem (PUG) cluster block since 09-12.
      Producer channel map: `L-seg molecular_formula -> formula_pubchem` was the
      ONLY ligand-CID enumeration route -> everything first-processed post-block has
      0 stored hits (3,370 legacy census: 100% attempted-stubs). Rich fresh entries
      ride pre-block candidate stores; verify chain unaffected (cactus/IDSM live).
- [x] **Offline-PUBCHEM fallbacks shipped (758d8f22e, images v2.33/v3.114)**:
      InchiKeySelfResolver (InChIKey signature = identity candidate, no network) +
      FormulaChEMBLResolver (EBI REST exact-formula; gate identifiers.formula_chembl
      or VALIDATION_SKIP_PUG=1). 20 tests green. config_shared.ini: formula_chembl:yes
      + [names] abs NFS paths (ccd.json copied to /data/validation/databases/).
- [x] **PROOF GATE green 3/3**: 1532 -> 26 verified chem; 1602 -> CID 138805674
      conf=93 skel=1.0 string-identical to GT; 1682 -> 6 verified chem.
- [ ] **LEGACY WAVE IN FLIGHT (3,367 entries)**: strip_for_reidentify.py
      (tasks.{identify,verify,export}.status->'failed') + natural dispatcher requeue;
      production does identify+verify with new fallbacks. Mid-wave state:
      identify-done entries carry chem candidates at 100%; verified chem landing;
      completions ~150-170/h. ETA to full pass: ~14-20h. Then: audit_gap.py re-run +
      S7 v7 recompute for the public verdict delta.
- [ ] Follow-up captured (priority order):
      * inchikey audit aftermath: recompute after wave; maps/manual DB sources
        (never existed; only ccd.json shipped; consider generating or retire paths).
      * loading-fail class on wave (~6 entries 'No loading strategy' = input-GC).
      * damage-window rows scoping/requeue (signature_isolated_timeout-marked).
      * name_ccd/glycan/lite channels sizzling metrics (reporting gate only).
      * ion/peptide classes in metric routing (M10a design, nothing implemented).
      * monster-class OOM nibbling at 20Gi (rare; watch-class, cheap-fail topology guard open).


## NEXT (post-mirror, opened 2026-09-24 evening)

NEXT (2026-09-26, post v6.5 intermediate audit)

Intermediate audit CONFIRMED recovery trajectory (inchikey validated@10 19.0% -> 44.2%
mid-drain; att 84.8%; pdb/uniprot hold ~99/98). Spin observability upgraded (SPIN_DEBUG
fleet-wide + [SPIN] generator markers). One open spin-sibling case noted (9189-class;
not yet localized).

Spin class RESOLVED (root: per-candidate PUG annotation HTTP stall; fix 7196cd45c,
mirror-first annotation on v2.42/v3.120; acid test 7277: 5h+ -> 215s). Broker wedge class
hardened (aeced4bfb; no recurrence since v2.41/v3.119). Campaign draining at ~56/h bursty
average (cheap cohorts flush; protein entries now finish ~2-3h instead of never).
Mechanics reference: playbook §7 + common-issues.md spin resolution entries.

In order:

1. **Drain monitor**: completion bursts every <=3h + zero stuck_cpu_spin re-fences +
   zero new failure classes. The 32-entry fence cohort drains via FIFO (queue position
   was 2.6k-16k); no surgery needed. Optional capacity lever: more validation-worker
   replicas (config-only) once a full heavy-day rate is known.
2. **S7 v7**: campaign_stats.py --full --sim once bulk lands (inchikey validated@10
   expect toward/above fresh-era ~77%; entry completes already at 38.8%+).
3. **Phase 2 scoping**: audit_gap.py on post-mirror completions; requeue only entries
   whose NEW chemistry still shows zero/weak candidates (most fallback-era was flushed
   by phase-1 + failed-mass requeues on 2026-09-24/25: 978 + 4,040 + 32 cohort).
4. **Ops persistence**: redis `timeout 60` -> deployment args (dispatcher-paused
   maintenance); Layer-2 watchdog CronJob (detection multi-signal per common-issues:
   ping lies under saturation); TZ align bat3/ui worker pods to UTC; cleanup
   /app/databases/pubchem-sample + old build jobs.
5. **Mirror lifecycle (Phase 5)**: weekly sync CronJob (md5-driven), rollback runbook,
   docs/PUBCHEM_DATABASE.md; watch SERVER_CLOSED_CONNECTION_ERROR churn (benign so far).
6. **Stretch**: maps/manual name DBs source-or-retire; cheap-fail non-linear topology
   guard (poison trio); signatures_timeout_s config field unimplemented; verify-side
   remaining cost = RDKit fingerprints only (bounded; top_n=100 left as-is on purpose).


## WAVE 5 — gt_absent anatomy + candidate-window fixes (audit 2026-09-26)

### Audit findings (evidence-based, liveness-filtered)

**A. The v6.5 headline was measurement noise, not chemistry.** S7 scanners counted
annotations from *stale* results.json of claimed-but-unfinished entries
(5,347 of 7,342 GT-inch entries are `processing`; their files are legacy
failed/partial contents, e.g. load_failed from the Sep-10 era). Liveness filter
(`load_simulation==success && verify_results==success`) reconciles exactly
(4,866 deepest=analyze_universe etc. ≈ DB counts). On LIVE completions:
inchikey organic att=99.3%, validated@1=65.1%, @10=75.2% (n=1,732);
ion validated=72.1% (n=840). v6.5 said 44.2%/34.4% — systematically depressed.
Fix in protocol: any future S7 scan must require verify_results success.

**B. gt_absent is candidate plumbing, not compound absence.** Of 341 live
organic annotations with best candidate sim <0.5 (only ~14/341 = true absence):
- 261 (77%) = GT compound present in sim (segment skeleton-FP vs GT = 1.0
  verified on 2451/2447/2164), in mirror, formula resolvers ran — yet no
  structurally-correct candidate reached the window. Split:
  - **C2 protonation frame: 163 (62%)** — fragment formula = sim protonation
    state (e.g. C15H13ClN3O), GT lives under another frame (C15H12ClN3O);
    exact-formula families structurally cannot intersect. H±4 bridge
    (`formula_hfamily`) EXISTS with a local-mirror backend but is SKIPPED: it
    sits in     `_PUBCHEM_RESOLVERS` (resolution_manager) and the PUG breaker has
    been open since the 2026-09-24 NCBI blacklist. (Confirmed: formula_hfamily
    absent from attempted resolvers on the matched segments of C2 entries.)
  - **C1 structure-blind window: 92 (35%)** — GT connectivity IS in the
    fragment's exact formula family, but `verify_top_n=100` is cut on
    consensus_score (identity-typed formula candidates ALL at 100). GT's first
    CID rank: median 3,097, p90 11,694, max 25,395. Only 1/92 within 100.
- 53 GT-unresolvable InChIKeys (MDDBR-side metadata gap; report-only),
  12 pair-cache zero poison (PUG-era LookupError cached as sim=0.0),
  6 heavy-formula extraction artifacts.
- Ion residual: presence evidence is incidental (segment element listings);
  structural metals (Zn-class, n=847 GT ions) under-detected; atom signature
  fired 2x in 14.6k entries. (Defer: separate dive.)

Artifacts: /data/validation/audit_chem_ion.json, audit_gt_absent.json,
audit_gt_absent_rows.jsonl (scripts in-repo .tmp/, pipeline untouched).

### Fix entries

- [x] **F13 — Ungate local H-family from the PUG breaker**
  (DONE 2026-09-26, commit 5af0ef4f6, v2.43/v3.121 fleet-wide. Breaker honors
  `offline_capable()`; local caps 5000/25000 (config). Acid 2447: GT-block CID
  rank1/skel 1.0 through the protonation frame.)
  - Follow-up queued: hfamily local-db handle is init-once-per-process; if the
    mirror is briefly unreachable at worker start that instance silently
    degrades to the PUG path. Lazy-retry like fetchers' _local_db().
  - `resolution_manager._PUBCHEM_RESOLVERS`: `formula_hfamily` must not be
    skipped when its local backend is active (offline path; the PUG fallback
    inside the resolver stays breaker-gated). Declare offline capability on
    the resolver (e.g. `offline_capable_when_local_db()`), breaker consults it.
  - Local-mode caps rise to rescue-sized: per-variant 200→5,000 and total
    500→25,000 (config `pubchem.hfamily_local_max_per_query/_max_total`;
    PUG path keeps legacy 200/500). Families are index lookups; cost is the
    F14 reranker's, bounded there.

- [x] **F14 — Skeleton-aware rerank before the `verify_top_n` window**
  (DONE 2026-09-26, commit 5af0ef4f6, v2.43/v3.121. Raise-only ordering with
  byte-identical legacy fallback; non-chem positions preserved;
  cap 25k->60k via config_shared.ini (2026-09-27). Acid 2451: GT CID rank1
  verified skel 1.0 (was absent from a 4,855-family). Cohort audit 2026-09-27,
  890 post-v3.121 completions: validated@10 75.2% -> 87.1%, @1 65.1 -> 68.9,
  gt_absent 19.6% -> 7.3% (=within ~3pts of the ~4% true-absence floor).)
  - Follow-up queued: precomputed skeleton FPs in the mirror build cycle
    (rerank becomes ~10x cheaper: 32k-pool 16min -> ~2min).
  - `manager.verify_all`: after dedup+consensus sort, before `[:verify_top_n]`,
    if the segment has a molecule skeleton_fp and #chemical groups > top_n:
    compute skeleton Tanimoto (skelfp:v1 vs segment signature) for chemical
    candidates from mirror-local structures (CID: fetchers' local path;
    INCHIKEY: mirror exact→block-range fetch, see F15), then re-order:
    if ANY chemical skel ≥ SKELF_VERIFY_THRESHOLD (0.7), chem groups sort by
    (skel desc, consensus desc); else legacy consensus order EXACTLY
    (raise-only: uninformative/corrupt molecule skeleton changes nothing;
    random-junk skel on 2048-bit Morgan r2 ~0.1-0.4, arch-anchors:
    formula-mate 0.19, prodrug 0.58).
  - Non-chemical groups keep legacy ordering; final merged order preserves
    them relative-positionally (protein hits untouched; window mix changes
    only among chemical groups).
  - Budget guardrails: config `verification.verify_rerank_max_candidates`
    (default 25,000; beyond → legacy order + warning), honors `_over_budget`;
    per-CID skeleton sims memoized per segment; log rerank size + duration.
  - No change to verdict logic/thresholds: F7 gate semantics unchanged; the
    window just stops being a lottery.

- [x] **F15 — Mirror block-range structure fetch for INCHIKEY candidates**
  (DONE 2026-09-26, commit 5af0ef4f6. by_inchikey_block indexed range +
  fetcher fallback. Acid 2164: hfamily 176 candidates; both GT-block CIDs
  verified skel 1.0. fingerprint_unavailable class collapsed
  (21 vs 486 pre-fix in failing top10 rejections).)

- [ ] **F16 (open) — Persistent pair-cache zero-poison purge**: sim_cache
  pairs.jsonl rows written as sim=0.0 from LookupError during the PUG-ban era
  (v6.5 counted 9,763 unmapped). Drop/recompute those rows before S7 v7 so
  stale zeros stop zeroing pairs whose structures now resolve offline.

- [ ] **Ion channel deep-dive (open)**: post-fix cohort ion validated 61.7%
  (was 72.1% pre-fix live; likely cohort composition, evidence path untouched).
  Presence channel is incidental (segment element listings; structural metals
  like Zn-class under-detected; atom signatures fired 2x/14.6k). Options:
  metrics-only GT-delta reporting, or a real presence channel (signatures for
  metal residues; attribute ions in/lost from segment clusters). Audit when
  the general cohort drains.
  - `compound_fetcher`: INCHIKEY exact-miss → block-range local lookup
    (first 27-char block prefix via indexed range scan), fixes self-inchi
    variant dead ends (2164-class: fragment IK is a stereo/H variant absent
    from mirror exact index but present under block).

### Acceptance + validation plan
- Unit tests: rerank ordering properties (GT-block rises in 4855-family mock;
  raise-only no-skel-≥0.7 → byte-identical legacy order; non-chem untouched;
  cap → legacy+log); hfamily local caps + breaker exclusion; F15 block fetch.
- Offline replays (pod, no PUG): 2451 (C1) → verified hit with skeleton
  sim≥0.7 and GT-block CID top-ranked; 2447 (C2: hfamily union feeds, F14
  ranks) expect the C15H12ClN3O/GT-block CID verified; 2164 (F15) expect
  self-inchi structure fetched and gate evaluated (verified or honest
  fingerprint_mismatch with skeleton present — not fingerprint_unavailable).
- Staged: bump v2.43/v3.121, roll validation-worker; acid-test 2-3 sandboxed
  entries via run_pipeline_task.apply() first (copy dirs to /tmp first).
- Metric watch: post-fix cohort audit re-run (same liveness-filtered scripts);
  expectation: gt_absent C1+C2 mass (~255 ann ≈ 24% of live organic failure
  mass) collapses toward ~0; inchikey live @10 75.2% → toward 90% on the
  fixed cohort; pdb/uniprot metrics unchanged (rerank does not touch them).
- Watch: rerank worst-case latency (25k × ~0.5ms ≈ 15s/segment worst),
  no new wedge/spin signatures (runbooks in playbook §7/§8).

## WAVE 6 — generator-budget isolation + external HTTP timeouts (OPEN, designed 2026-09-29)

Context: WAVE 5 (F13/14/15) landed and reclaimed the chemistry path; the campaign's
remaining ~2% are hostage to compute-side spins of a NEW class, fully localized this
week. Fence-watchdog currently holds them out of the fleet (ops-only mitigation);
~420 entries preserved as the regression corpus
(`/data/validation/quarantine_smiles_spin_2026-09-27.txt`).

### F17 — subprocess-isolated generator budget (DESIGN, unimplemented)
- **Root**: `MolToSmiles` canonicalization spins unboundedly on small dense cage/ring
  junk clusters from virtual `SYSTEM__vN` fragments (both `smiles` and
  `smiles_not_sanitized`; same fragments also stall `selfies` / `inchi_key`). The
  2026-09-20 policy excluded KEKULIZE only. NOT size-predictable: 4,247-atom systems
  hit it — size-based skipping is provably wrong.
- **Design constraint (explicit user ruling)**: NO per-generator/thread timeouts or
  signal tricks — that class of patch broke production before. The safe primitive is
  a **subprocess**: run the RDKit-derive stage for a fragment in a spawned child with
  a wall-clock budget; on overrun the parent KILLS the child (no threads, no signals,
  no shared state), records `smiles_timeout`/`generator_timeout` as an honest failure
  signature, and the pipeline continues with the remaining generators. Deterministic,
  testable, bounded blast radius.
- **Secondary hardening**: cheap pre-check (atom/ring size) may SKIP the obviously
  hopeless fragments to save child-spawn cost, but the child budget is the guarantee,
  the pre-check is an optimization only.
- **Test corpus**: the ~420 quarantined entries (thus the fence list is a FEATURE —
  replay set, not grime). Each must end with `*_timeout` signatures instead of a
  frozen thread.
- **Watch out**: faulthandler path is broken in celery workers (LoggingProxy lacks
  fileno) — the isolation child must do its own logging; do not rely on SPIN_DEBUG
  dumps for child debugging.

### F18 — external HTTP hard timeouts (unimplemented)
- Paths still calling out without any timeout: cactus.nci.nih.gov resolution,
  uniprot FASTA fetch, PUG fastsimilarity fallback remnants. Observed hangs up to
  10.4h holding worker slots. Fix = explicit connect+read timeouts + fail-soft on ALL
  external HTTP in identification/verification; mirror/local sources are never touched.

### Replay plan (after F17/F18 ship)
1. Requeue the ~420 quarantined entries (last_error LIKE 'quarantined%').
2. Watchdog stays armed (already generator-generic).
3. Expect: no `[SPIN] ... START` older than its budget anywhere in the fleet.

## WAVE 7 — Enhanced Nucleic Acid Recognition (ENAR) (DONE 2026-09-30)

Motivation: DNA/RNA-focused analysis showed fragile NA recognition (hard 80%
gate on an enumerated resname table) and missing NA sequence/structure
signature coverage in several input shapes. PyMOL research (Selector.cpp)
gave the model: pattern-based resname folding + structure-based
sugar-phosphate fingerprint fallback, C4' guide atom (C3' fallback, PNA).

**Commits**: 0920eebaa, eb88b0302, b0afcc035, f32b907a3, cc93741c6, bfc077fdb
(+deploy fix 9f98d8e45). **Images**: bat3-worker:v2.44, bat3-validation-api:v3.122
(fleet-wide 2026-09-30), bat3-frontend:latest rebuilt.

Shipped changes:
- **A1/A2 recognition tiers** behind `enhanced_nucleic_acid_recognition`
  (default on: code, config.ini `[signatures]`, config_shared.ini, UI defaults).
  Tier-1 = legacy 80-entry table UNION liberal normalizer (D- prefix, [3|5]
  terminal codes DA3/RG5-class); tier-2 = structural sugar-phosphate
  fingerprint (O3'/C3'/C4'/C5'/O5') in the 0.3-0.8 band REQUIRING a
  cross-residue phosphodiester bond, so cofactors (CoA 3'-phosphate, ATP,
  NAD, FAD, free nucleotides) can never promote. Audit fields
  `na_detection` / `na_structural_promotions` land in results.json.
- **B1** resname_to_one_letter consults the normalizer; modified bases keep
  the designed 'X' degradation (BLAST sanitizer -> N).
- **B2** fasta_resname_nucleic fires exactly when map-based cannot (bondless
  atomistic NA coverage hole closed; gates provably complementary, no
  double production).
- **B3** map-based sequence extraction anchor parameterization; NA passes
  anchor=None (methionine heuristic inapplicable); protein byte-identical.
- **B4** pdb_backbone_*_nucleic emits the real C4' guide atom per residue at
  real coordinates/element (was: centroid pseudo-atom mislabeled "CA").
  Protein path byte-preserved (selector=None).
- **Gate fix**: pdb_nucleic generators required NOT-multi-atom residues
  (CG-only) -> atomistic DNA/RNA never produced PDB signatures at all;
  restriction dropped for NA, CG preserved.
- **C1** nucleotide verification scores all four orientation senses
  {q, rev(q), comp(q), revcomp(q)} (+RNA pair when U present) and takes the
  max: provably never below forward-only scoring. Fixture-proven
  68.42 -> 100.00 on a real reversed BFS output. Protein untouched
  (gated by signature_type, plumbed through VerificationWorker.verify).
- **Molecule-type anti-stomp**: element-composition fallback (lipid/carbo/
  small-mol) now runs only for UNKNOWN. DNA (C/O ~2.4, inside lipid band)
  was stamped LIPID and even emitted lipid_shorthand signatures; water/ion
  were equally stompable. Found by E2E, fixed before rollout.

Empirical basis (before each merge): fixtures from tmp/Cyt_c-DNA.pdb
(tests/fixtures/nucleic/*; protein+HEM+DNA duplex with DA3/DG5/DC3/DT5
terminals). Both 16-nt strand sequences recovered verbatim via the real
loader path AND via raw bondless PDB; C4' coords == source atoms; ON/OFF
toggle parity on the canary; in-image ENAR gates passed post-build; old
image proven tolerant of the new config key.

Deployment notes: surge rollout (maxSurge=1, maxUnavailable=0) swept the
164-pod validation-worker in ~15 min; in-flight monsters recovered via
celery visibility + results.json resume as designed. fence-watchdogs live
in the API pod /tmp -> must be relaunched after every API roll (done).
config_shared.ini backup at .bak-20260930.

Open follow-ups: unwrap.py divergent NA classifier reconciliation; CHARMM
three-letter base names + PNA names in tier tables; blast.py embedded table
dedup; DNA-vs-RNA typing metadata (descoped, trivial add); parameterize
frontend nginx upstream per helm release (envsubst). FE/metal vdw poisoning
of global bond guessing: known story, deferred (see common-issues).

## WAVE 8 — fidelity-first hit ordering + statistics-led decomposition (2026-10-01)

### F16 — fidelity-first presentation ordering (DONE, commit 811ddb55e)
- **Root**: verified chemical hits were stored in candidate-processing order
  and ranked by `final_confidence` (provenance-weighted) — audit 2026-09-30
  showed 12.3% of organic GT annotations (499/4,053) with their identity/
  in-band hit at rank 11-50 (engine_miss_identity: sim=1.0 at rank 12-37!).
  Retrieval solved, chemistry 96.8%-present — the deficit lived in ORDER.
- **Fix (ordering-only)**: stable repartition of each segment's verified_hits:
  [verified CHEMICAL hits, sorted (-skeleton_sim, -final_confidence, identifier,
  ident_type)] + [everything else, legacy relative order]. No gate/threshold/
  score change. Deterministic tie-break chain per UI contract (backend owns
  ranking, UI displays verbatim; verified flag is a column, never a sort key).
- **Projection-first validation**: `rerank_projection.py` replayed A_conf
  == v7 to the decimal, then B_fidelity => @5 82.5/@10 88.5 (0.7) with flip
  accounting +226/-10. Landed only after projection matched design claim.
- **v8 official** (campaign_stats.py metric aligned to same key, .bak-pre-fidelity):
  inchikey @5/@10 **85.8/90.6** (0.7), @10 87.9 (0.9), entry-any 99.5%;
  pdb/uniprot bit-identical. Flip dissection (flip_dissection.json): delta vs
  projection = 147 tie_reposition + 23 window_membership = skeleton tie-cluster
  noise, NOT rule drift. Rank cutoffs carry ±1-2pp tie sensitivity; quote v8,
  and prefer depth-invariant frames (@15: 91.1 ge0.7; in-window ~94) in prose.

### Audit-derived residual anatomy (the "why not 95%+ with proteins" answer)
- Proteins: GT is self-referential (annotation FROM the structure in the box),
  ranked space tiny, sequence identity exact-ish => ~99% is the natural level.
- Inchikeys: GT is bibliographic. 479/5,784 still fail @10 post-F16:
  273 have the GT skeleton NOWHERE in the entry (63 boxes have no small-molecule
  chemistry at all), rest are variant-layer (salt/stereo/protonation changes
  first-block-ok/full-key-miss) and gate-band stragglers. Honest ceiling ~93-94;
  we are at 90.6 @10 — residual is content, not pipeline.
- **Authoritative recount (Task B, 2026-10-01 evening)**: the 479 came from the
  pre-v8 PROJECTION failing set (649) minus flips-to-pass (170); reconciling
  reverse flips against the official v8 metric gives **541 failing rows**
  (residual_failing_rows_v8.jsonl). Bucket anatomy below supersedes the 479
  framing wherever they disagree.

### Task B — coverability probe of the residual (DONE 2026-10-01, read-only)

- **Method**: regenerated the AUTHORITATIVE v8 failing set (official
  verified_hits/_fid_key + family window 50/fallback 25 + 0.7 gate replicated
  verbatim; HARD reconciliation gate vs campaign_stats_v8.json S7 anchors:
  annotations 5,784, attempted 5,768, 56.3/85.8/90.6 — all matched exactly),
  then resolved each of the 541 unique failing inchikeys against the local
  PubChem mirror via PubChemDB (by_inchikey / by_inchikey_block + variant
  counts, the pipeline's own access path), cross-checked gt_compound_map.json
  (0 mismatches) and box chemistry.
- **Buckets (541 rows, 341 unique iks)**:
  - **GT_NOT_IN_MIRROR 130** (24%) — uncoverable by construction; GT compounds
    the mirror doesn't register (62 in no-chem boxes). Disclosed, not fixable.
  - **FIRST_BLOCK_ONLY 25** (4.6%) — variant layer; only salt/stereo/protonation
    siblings exist (variant depth median 2, max 138); 15 already have a >=0.7
    analog in-window.
  - **IN_MIRROR__NOT_PROPOSED 264** (49%) — true pipeline gap: GT in mirror,
    never surfaced in results.json. 171 in chem-bearing boxes = requeue-candidate
    class; 129 have a >=0.7 skeleton analog buried at rank >10.
  - **IN_MIRROR__SURFACED_BUT_LOST 122** (23%) — full key appears in
    results.json but lost before window top-10; 81 with >=0.7 analog in-window.
- **Reporting frame (raw + normalized, always together)**: raw 90.6% @10
  (n=5,784) · excl NOT_IN_MIRROR 92.7% (n=5,654) · excl uncoverable+variant
  93.1% (n=5,629). Of the 9.4pp gap: ~2.2pp bibliographic, ~0.4pp variant-layer,
  **~6.7pp (386 rows) pipeline-recoverable** — 210 of them already have a
  >=0.7 candidate sitting in the window (ranking/verification work, not
  retrieval: feeds the F-residual follow-up wave).
- **Phantom lesson** (metric replication): official S7 counts annotations only
  for entries with NON-EMPTY verified hits (`if r["hits"]` guard). A shadow
  implementation missing that guard produces +1 annotation with zero validated
  delta (5,785 vs 5,784). Replicate ALL guards when shadowing the metric.
- **Artifact set** (/data/validation/): coverability_probe.json (aggregates +
  10 examples/bucket), coverability_rows.jsonl (541 enriched rows),
  residual_failing_rows_v8.jsonl (authoritative failing set),
  coverability_ik_cache.json (mirror resolutions), coverability_classes.json +
  coverability_class_drift.json (4,311 GT-key classifications; 186 mirror-vs-web
  disagreements — web-chain classification nondeterminism, see common-issues).

### F19 — coordinated-metal awareness (ion channel) (DONE 2026-10-02; v9 official)

- **Root (audit-proved, 30-entry stratified sample)**: single-atom metal
  residues carry no covalent bonds, so connectivity segmentation ORPHANS them
  — absent from every instance composition, no `elements:` token, blind ion
  channel. 27/27 sample metals invisible at the instance layer; 26/27
  coordinated to protein/nucleic within 3.0 A; metals are ALWAYS present in
  the exported structure (entry 4341 arithmetic: protein 4,051 + TRS 20 +
  Zn 1 = 4,072 atoms; the Zn is literally the last serial). Free ions were
  already ~100% only because system/lipid clusters swallow them by luck.
- **Fix (Option 3 — presence parity, not chemistry)**: metals pass in
  `FragmentStore._record_summary` -> `data.fragments.metals`. Presence =
  single-pass element scan of universe atoms (NO distance math; vocabulary =
  `_ion_elements_of.metals_like` VERBATIM, 31 symbols incl. halides —
  vocabulary-mismatch bug caught by the evidence battery). Context =
  per-atom coordination for transition metals only, capped (200 atoms),
  one lazy cKDTree (O(n log n)); degrades to presence-only with recorded
  reasons (no_elements/no_positions/no_scipy/cap_exceeded/scan_crash).
  Metric: `_ion_elements_of` ADD-ONLY union with
  `fragments.metals.present_elements` (no-op on pre-F19 results).
  bound/free/associated is payload for future waves, NOT S7 gating.
- **Evidence (f19_evidence2.json; old channel reproduces v8 anchors bit-exact
  on the official frame)**: projection att 52.2 -> **97.3%**, val 35.1 ->
  **95.6%**; +1,057 validated-positive flips, 0 negative, 0 attempted-lost;
  Zn 26.2 -> 92.3 (n=736), Mg/Ca/Fe/Co/Cd -> 100, Ni 16.4 -> 92.7,
  controls K/Cu flat. Residual gap explained: 50 entries w/o system.mmcif,
  4 element-unresolved, Na genuinely absent in some boxes.
- **Perf gate (worker image, real code)**: 83 ms @350k salt; 378 ms @348k
  mixed + 12Zn (KDTree build dominates); cap-degrade 30 ms; presence at
  15-16 ms/300k atoms.
- **Commits**: dfea2a4d7 (scan + 15/15 tests incl. FragmentStore
  integration), c72688e7e (metric union + source-of-truth sync
  scripts/campaign_stats.py canonical, 23/23). NFS metric `.bak-pre-metals`.
  **No-move check**: ion/pdb/uniprot/entry-any BIT-IDENTICAL; organic
  inchikey +0.2pp @10 traced to POSITIVE-resolution cache growth between
  runs (web nondeterminism class; v8 90.6 remains official — see
  common-issues cache-state sensitivity).
- **Phase 3 (rollout + replay, 2026-10-02)**: image bat3-validation-api:v3.124
  live on validation-api (v3.123 superseded same-day by the facade fix);
  fleet rollout DEFERRED to the F17 wave (surgical replay needs no fleet).
  Offline replay spliced fragments/metals into the 857-entry ion-blind
  cohort: **852 replayed + 5 idempotent, 0 errors/timeouts/mismatches**
  (replay_fragments_metals.py, subprocess-per-entry 420s cap, EXPECTED-map
  verified per entry; dry-run 10/10, live sample 5/5 first).
- **Found+fixed en route (f7baeb734)**: WAVE-7 refactor missed the tuple
  unpack in the virtual-segment branch (`props.flags = ...` on a tuple) ->
  AttributeError in extract_molecule_instance on any __vN box (replay
  blocker, 8/10 dry-run failures). 1-line fix + 3 regression tests.
  The 7 pre-existing master test failures are a DIFFERENT class and persist
  (A/B-verified before and after) — separate triage, owner pending.
- **v9 OFFICIAL (campaign_stats_v9.json)**:
  ion attempted 52.2 -> **97.3%**, validated 35.1 -> **95.6%** — projection
  matched to the decimal; pdb 99.6 / uniprot 98.2 unchanged;
  inchikey 90.6 -> 91.3 (cache-growth class, disclosed, token-channels are
  the regression control); entry-any 99.5 -> 99.6.
  Audit cohort (4,641/1,737): validated 841 -> **1,684 (96.9%)**,
  no_metals 647 -> 33; per-element: Ca/Mg/Fe/Co/Mn/Cd/Cs/Li -> 100,
  Ni 18.8 -> 91.7, **Zn 27.1 -> 93.6% (n=591)**; free-ion controls flat
  (Cl 100, K 99.3, Na 83.3); floors disclosed (I 0->0, Na absent-class,
  residual 53 = degraded/stripped/unresolved). New channel attribution:
  fragments.metals:Zn 509 / Mg 247 / Ca 219 / Mn 46 / Ni 41.
- **Ops notes folded into common-issues.md**: kubectl strategic-merge matches
  containers BY NAME (phantom-container trap: patch targeted 'validation-api'
  but the container is 'api'); ephemeral /tmp ops scripts must live on NFS
  (fence watchdog lost on api-pod roll — revival rides the F17 wave);
  worker fleet still v3.122 until that wave.

### F-residual ranking wave (DONE 2026-10-02; S7 v10 OFFICIAL)

- **Basis**: Task B evidence (541-row v8 residual, bucketted). Included:
  411 mirror-present failing rows (NOT_PROPOSED 264 + SURFACED_BUT_LOST 122
  + FIRST_BLOCK_ONLY 25) = **406 distinct entries + 116 nochem riders**;
  excluded: GT_NOT_IN_MIRROR 130 rows (permanent disclosed floor).
  Pre-replay snapshot: backups/results_cohort406_pre_fresidual_2026-10-02.tgz.
- **Mechanism**: replay_identify_verify.py (rebuild identifiers with current
  resolvers incl. local-mirror hfamily/formula caps + verification with
  F16-era manager; atomic-on-diff). Rationale: entries computed under
  older-code resolvers; retrieval gap is a code-era artifact, not content.
- **Execution**: initial 3-chunk run lost to a fleet rollout mid-wave
  (15:16-15:24 UTC; /tmp logs died with pods — NFS logging rule); recovered
  same day as a **41-pod x 10-entry fan-out, 0 errors, 406/406 processed in
  ~35 min** (logs on NFS: logs/riv2/). Snapshot diff ground truth:
  118/406 entries moved (+112/-6), net **+1,520 chem-verified hits**; the
  few negatives are same-cluster redistributions/cap effects, zero bucket
  regressions measured downstream.
- **S7 v10 official (campaign_stats_v10.json, 2026-10-02 17:27Z)**:
  **inchikey @10 raw 90.6 -> 91.3* -> 92.9** (@5 88.2, @1 59.2);
  ion validated 95.6 FLAT (F19 channel unchanged — regression control);
  pdb 99.6 / uniprot 98.2 FLAT. (*v9 organic move = cache-growth
  provenance, disclosed.)
- **Coverable-normalized frame (gate-verified: probe regen identical to
  v10 anchors, delta +0 / 92.9 == 92.9)**:
  raw **92.9** | excl. not-in-mirror **95.0** | excl. not-in-mirror +
  variant layer **95.4** (Task B frame was 90.6 / 92.7 / 93.1).
- **Flip accounting (541 -> 410 residual, probe rerun with
  PROBE_ANCHOR_JSON=campaign_stats_v10.json; baselines pinned as
  *.taskB-baseline)**: **131 rows FIXED, 0 regressions, 0 bucket
  transitions.** NOT_PROPOSED 264->182 (82 fixed, 31%);
  SURFACED_BUT_LOST 122->77 (45 fixed, 37%); FIRST_BLOCK_ONLY 25->21 (4);
  GT_NOT_IN_MIRROR 130->130 (floor untouched, by design).
  131/5784 = +2.26pp — independently reproduces the raw 90.6->92.9 move.
- **Residual residue (410 rows)**: 182 NOT_PROPOSED (114 boxchem = requeue
  class), 77 SURFACED_BUT_LOST, 21 FIRST_BLOCK_ONLY, 130 not-in-mirror
  floor; probe flags 148 content-unattainable rows. Audit (v10-era,
  post-v3.121 frame, 4053 organic annotations): @10 hit-rate 84.5%;
  top residual classes engine_miss_identity 273, band_buried 222,
  gt_absent_best<0.3 91, prodrug_band 27.
- **Ops events this wave (all in common-issues)**: (a) never co-schedule
  campaign_stats + audit on the api pod — OOMKilled 16:28Z, serialize
  instead; (b) long-run scripts must live on NFS, not /tmp (audit script
  lost in the same OOM restart; fence-watchdog lesson generalized);
  (c) results.json pipeline payload is double-nested
  (results["data"]["verification"] / ["data"]["identifiers"]).
- **Do-not (still binding)**: no gate/threshold edits; no GT-aware logic;
  the 130-row floor and tie-cluster noise stay in every table.

### F-boxchem requeue wave (DONE 2026-10-03; S7 v11 OFFICIAL — falsification)

- **Basis**: the largest recoverable-looking residue of the F-residual wave —
  the 114-row boxchem subset of IN_MIRROR__NOT_PROPOSED (182-left bucket),
  112 distinct entries; full-pipeline requeue (load->analyze->signatures->
  identify->verify), not an offline replay. Snapshot: backups/
  results.json_boxchem112_pre_requeue_2026-10-02.tar (+9.8GB full-dir tgz).
- **Ops events**: 19/112 tasks stolen by the stale 64d-old bat3-ceitec-bat3-
  worker pool (shared celery broker!): 15 crashed on the pre-f7baeb734 tuple
  bug, 4 "completed" with old code. Ruling (user): upgrade-not-pause — the
  foreign pool now runs v3.124 (whole namespace unified); 19 requeued, all
  completed. One celery meta loss (node clock skew) settled manually after
  worker-log + results.json verification. Result: **112/112 completed, 0
  final failures**.
- **VERDICT — clean negative result**: coverable probe rerun anchored to
  campaign_stats_v11.json (GATE OK, regen delta +0): residual **410 -> 410,
  0 fixed, 0 regressions, 0 bucket transitions**; inchikey @10 exact regen
  5374 == v10 (92.9 raw unpinned). Spot-diff (5 entries): identifiers
  rebuilt 5/5, verification 2/5, molecules/signatures byte-identical.
- **Conclusion**: Task B's "requeue class" hypothesis falsified — upstream
  (universe->molecules->signatures) is deterministic on these inputs; chem-
  candidate churn does not reach the GT compounds. The 114 (+ wider 410
  residue) is engine-bound: organic ceiling for this code era =
  **92.9 raw / 95.0 excl-mirror / 95.4 excl-floor+variant**. Residue
  decomposition (audit v11-era): engine_miss_identity 277, band_buried 231,
  gt_absent 108+23, prodrug 31, variant-layer 21, floor 130.
- **S7 v11 OFFICIAL (campaign_stats_v11.json)**: inchikey 92.9 (5374 exact),
  ion 95.8 (+0.2 requeue noise), pdb 99.6, uniprot 98.2, entry-any 99.6;
  all controls flat. Frame frozen gate-verified across v8-v11 (ann=5784,
  att ~5768, delta +0 every anchored rerun).

### Bag-of-molecules funnel (v11; user S-metric; artifact bag_funnel_v11.json)
- Frame: 13,917 live+analyzable entries -> **25,451 molecule-units**
  (segment-level, the pipeline's own molecule unit).
- >=1 searchable-structural signature (A): **100.0%**; >=1 names signature
  (B): 100.0%; fingerprint-class: 0 by construction.
- >=1 identifier hit: **89.5%**; >=1 verified result: **87.7%**.
- Per class: protein 17,636 -> verified 93.6%; chem_other 6,118 -> 94.6%;
  **nucleic 1,697 -> hit 1.9% / verified 1.9% (NEW HOLE; task N1)**.

### NEXT proposed tasks (specced, awaiting scheduling; full specs in
### .tmp/TASKS_next_wave.md 2026-10-01; promote into this doc when scheduled)
- **N1 — nucleic resolution audit: SPEC READY at
  .tmp/TASK_N1_nucleic_resolution_audit.md (2026-10-03).** Hypotheses ranked:
  signature-format mismatch -> resolver coverage/config -> type misrouting ->
  true content gap. Audit-only phases P0/P1/P2; no fixes without approval.
- **A — F19: PHASES 0-2 DONE (see above); phase 3 rollout scheduled.**
- **B — coverability probe: DONE (2026-10-01)** — see "Task B" section above.
  Follow-up unlocked: 386-row pipeline-recoverable class (210 with >=0.7
  in-window candidate) becomes the F-residual ranking-wave input;
  IN_MIRROR__NOT_PROPOSED 171 boxchem rows = requeue candidates.
- **C — F17 generator-budget subprocess isolation + 437 replay** — **DEFERRED
  by user ruling (2026-10-02): the 437 stay quarantined for now.** Spec stands
  unchanged for a later session (signature_isolated_timeout x3,320 step-0
  audit; spawn-not-fork; subprocess per segment; F18 HTTP timeouts folded in;
  replay only after fixed image fleet-wide).

## TASK N1 — Nucleic resolution audit — AUDIT COMPLETE (2026-10-03, measurement-only)
Trigger: bag funnel v11 showed nucleic at 32/1,697 hits (1.89%) vs protein 93.6% / chem_other 94.6%.
Full deliverable: `/data/validation/n1_nucleic_audit.json`; spec+outcome: `.tmp/TASK_N1_nucleic_resolution_audit.md`.

Attribution of 1,665 hitless (wire-verified, 100% covered):
- **Layer A — RCSB structure-search dead campaign-wide (all classes)**: mmcif_struct 0/25k, pdb_struct_* 0/31k attempts with hits. File-URL 404 -> RCSB 404 passthrough (worker-pod probe); request schema also rejected (400) vs current API. Proteins masked by blast+alphafind; nucleic had no fallback. **This was the intended primary channel for nucleic structural ID.**
- **Layer B — no sequence for 50.4% (839)**: merged duplex/multi-strand segments can't produce fasta (linear-path limit, live-error "Found 4 disjoint residue components"); >=31-residue molecules: 731/736 sequence-less. Era + algorithm limit.
- **Layer C — gate physics for 49.5% (824)**: all <=30 nt; BLAST returns only below-gate partials (best 0.77-1.2 evalue vs 0.1); even perfect full-length short match (~0.2-0.4) fails. User hypothesis CONFIRMED + strengthened: even PDB-deposited designed duplexes cannot pass sequence gates at this length.
- **Layer D — names dead**: 1,662/1,665 name_molecule='lipid' (input convention).

Bug ledger additions: pdb_backbone_nucleic still broken on atomistic NA (v3.124, "Unable to generate PDB signature"); sig/resolution errors never persisted in results.json (dead-channel classes invisible postmortem); [identifiers] toggles ineffective; pdb_nucleic absent from stored content purely era (pre-wave-7 code), generates correctly live.

Fix menu (report-only, awaiting user pick): F-N1a RCSB channel revival (serve files + schema refresh; all-class lever) · F-N1b strand-aware splitting/per-component sequences · F-N1c <=25nt exact-identity override (content-gated; N2 pre-measure first) · F-N1d backbone_nucleic fix · F-N1e error persistence · F-N1f toggle hygiene.

## N1 FIX WAVE (F-N1a..e) — IN PROGRESS
Plan: `.tmp/PLAN_N1_FIX_WAVE.md` · Cohort for requeue: 797 nucleic entries (eids 1532–9990).

### Done & committed (master)
- W0 foundations `1f1523f25` (+`405292a09`): 10 real campaign fixtures (tests/fixtures/n1, 11MB,
  frame-0 trimmed with SHA-256 trim-parity vs campaign inputs), v3.124 goldens (sig+ident),
  dependency-free gate runner + pytest mirror, allow_delta ledger. G0 GREEN 10/10.
- W1 F-N1e `f230fbbf0`: stage_errors/{signatures,identifiers}/{seg} persisted (bounded 20/300 chars),
  separate branch (verify iterates those dicts); Generator.generate re-raises real reasons.
- W2 F-N1a `b6a9fbf35`: DEPLOYMENT_FILE_URL env override (ini fallback intact);
  GET /files/validation-<eid>-<ts>/... route → VALIDATION_FILES_ROOT (guarded, 404-durable).
  A2: NO schema change needed (existing client works for proteins, verified live);
  RCSB structure-similarity backend = PROTEIN-ONLY (NA entry_id→404 / NA file_url→400; 1UBQ→200).
- W3 F-N1d `e227cea48`: mock/parallel-path completeness (resnums/resindex); NA PDB+backbone
  now generate on real fixtures. (Serial path was never broken; era content explains storage.)
- W4 F-N1b `94be929c5`: largest-component strand selection when sequentiality fails;
  deterministic (-len, seq); strict path byte-identical. Empirical: 1682 SYSTEM emits 147nt
  == campaign v1 BYTE-EXACT; blastn 42==42 control; all 4 merged SYSTEMs gain strand-size
  fasta; pre-existing payloads IDENTICAL (incl. protein fixture 1089).
- W5 F-N1c `fae6b00f5`: pre-measure 824-cohort (55 perfect-full, 53 both-dir, all ≤12mers;
  744 20-mers ZERO content → user content-gap confirmed for dominant cohort); identity-pass
  override: pident=100% & cov=100% & slen==qlen & q≤25 → accept regardless of evalue/bits,
  tagged exact_short_identity. Empirical: 1880/1881 12mers → 1FZX_A/B; fixtures exact-negative.

### In flight (W6)
- Image `cerit.io/tomsko/bat3-validation-api:v3.125-N1` built (7612591f41f4) + pushed.
- Probe pod `n1-w6-probe` (v3.125-N1, worker PVCs + PDBCHARGES SEC ctx) up.
- RESOLVED 2026-10-03 (commit 03d30e13b): 4725 gate "divergence" was overlay-methodology
  failure, not code. `n1_run_gates.py` inserts `sys.path.insert(0, BAT3_SRC or "/app")` →
  overlay runs without `BAT3_SRC=/tmp/gate_src` tested the pod's baked v3.124 code
  (PYTHONPATH/cd/pycache-purge cannot defeat it; V-18 extended w/ mechanism (c)).
  Image behavior verified honest + deterministic (3 runs, hash seeds 0/1 byte-identical;
  module-spy parity: identical residue graphs 2479at/160res deg {2:2,3:154,4:4}, fallbacks
  len 62/1 on both pods). SYSTEM fasta_map_protein (62-res component→35+-aa seq incl 1 X) +
  SYSTEM__v1 fasta_map_nucleic ('T') = disclosed W4 protein-broadening → allow_delta, no
  code change. FULL gates 10/10 GREEN on image pod AND overlay (BAT3_SRC set).
  Correct overlay invocation recorded in .tmp/PICKUP_N1_FIX_WAVE.md.

### W6 rest — DONE 2026-10-03 (probes on n1-w6-probe, image code)
- RCSB round-trip: route 200+md5 (44,533B golden 1089 payload, sha256 parity), guards
  404 (dir-list/traversal/unknown-eid); public plane 200+md5; RCSB POST resolver-shape:
  1UBQ→200/10 hits (self 100.0), synthetic→204 (fetch ok, honest zero), validation-uuid
  pre-rollout→404 w/ exact 'invalid entry_id' wrapper == campaign silent-failure mode.
- e2e: 1682 SYSTEM strand-select byte-exact == v1 (147nt); real stage_errors persisted
  (RCSB 404s from frozen fixture config, ChEMBL egress, morgan RingInfo); 4653 green.
  Harness 1682 assertion modernized to W4-era (backup in NFS logs).
- Units: wave suites 36/36; full tests/src_new red sets IDENTICAL (22==22) image vs
  v3.124 baseline → zero wave regressions; reds all env/pre-existing (DB/egress/blastdb).

### W6b rollout — DONE 2026-10-03
ceitec api ui-rework-b1→v3.125-N1 (+VALIDATION_FILES_ROOT, validation PVC ro mount;
route-table parity 70+1 pre-verified, zero UI-visible change); validation-api/worker +
ceitec worker all v3.125-N1 w/ DEPLOYMENT_FILE_URL=bioid-ceitec (canary→fleet; ini
[pdb] deployment_file_url set+recorded, backup taken). Public smoke: validation-uuid
GET 200 md5-exact, RCSB POST 204 fetched-ok (was 404 'invalid entry_id' pre-rollout).
bat3-ui-worker x2 (v2.44, queue validation.ui.celery) untouched by design (no theft
path, foreign UI lineage) — gap reported. Post-rollout fleet gates 10/10 GREEN.

### W7 replay — DONE 2026-10-03 (approval-gated measurement before requeue)
553-entry identify+verify replay on stored sigs (3 pods, shadow roots, zero mutation):
0 errors, 53 changed, **0 lost identifiers globally**. W5 override measured == design:
52 nuc segs gained (premeasure: 53 both-dir; 8/8 sample exact, e.g. snipped 1880 1FZX
A/B both strands). nuc100 static (expected pre-requeue); prot20 +12 entry gains all
external-drift, none lost. RCSB 404 in replay = shadow artifact only; wire proven W6b.
### W8 requeue 797 — DONE 2026-10-03 (batch nucleic-fix-wave-1)
786/797 completed; 11 still processing = pre-existing pathological signature-timeout
cohort (12h stale_timeout history pre-wave, unrelated to N1 changes; they complete
naturally over hours). 3884 transient ENOENT -> V-17 requeue -> completed.
Deep production proofs: 1881 -> 1FZX verified 100.0/conf 92 all 3 segs; merged cohort
100.0-identity hits (1HLV/1ZGW/3AN2). Wave-mechanism validations live (W4 fastas on
merged SYSTEMs, W5 exact-short-identity, W2 RCSB channel firing real requests).

### W9 statistics — DONE 2026-10-03 (v12 official, raw+normalized)
- campaign_stats_v12.json (full NFS scan + sim): inchikey FROZEN window 5784/5768
  exact; @1/5/10 = 59.2/88.3/92.9 (unchanged); ion ann 1747->1811 (+64), pdb ann
  11079->11186 (+107) — denominators are run-window dependent (S7 block counts
  annotations of entries-with-hits; +200 newly-verified nucleic entries entered);
  pdb @10 99.6->99.5 pct / abs-validated@10 est 11035->11130.
- Coverage probe refreshed, GATE OK anchored at v11 (new_pairs=0, metric stable;
  v8-anchor abort was its protective design, PROBE_ANCHOR_JSON env-swap is the
  sanctioned era advancement). Chem residual failing rows: 410->410, zero fixed,
  zero regressions (wave untouched chemistry).
- NUCLEIC CLASS (audit metric verbatim): 32/1697 = 1.89% -> 413/2091 = 19.75% hit;
  verified 32 -> 412. New nucleic segments surfaced +394 (1697->2091: W4 mixed-system
  segmentation). Strata: <=12mers 12.8->82.1%, 13-30 2.2->18.0%, 31-100 0.4->35.4%,
  big 0.4->1.7% (the remaining hole = verifiable-content absence, as audited).
- W8 flip (snapshot tgz vs live, 783 compared): seg-level verified gains on 201
  entries (392 segs); 4 entries lost UniProt ids, rotated to MORE PDB ids (3JA4/
  3JA5/6EHL/2JLF — candidate-set rotation on mixed prot-NA systems from W4 protein
  strand-select; entry-level verification UP in all 4; deterministic across siblings).
- bag_funnel_v12 + stats_package_v12.{json,md} assembled (figures data paths below).

### Figure-data files (post-v12)
- /data/validation/stats_package_v12.json / .md — master assembled package
- /data/validation/campaign_stats_v12.json (+ logs/campaign_stats_v12.log)
- /data/validation/bag_funnel_v12.json
- /data/validation/coverability_probe.json + coverability_rows.jsonl (+ .v11-baseline)
- /data/validation/residual_failing_rows_v8.jsonl (410) (+ baselines)
- /data/validation/n1_postwave_rate.json (nucleic 1.89->19.75 raw table)
- /data/validation/n1_w8_flip.json (per-entry pre/post verified deltas)
- /data/validation/n1_nucleic_rows.jsonl (pre) / rescan merged in n1_postwave_rate
- /data/validation/n1_w7_*.txt cohort lists; logs/n1_w7_{a,b,c}.{jsonl,log}

### Remaining: 11 pathological stragglers conclude naturally; registry closeout.
Pending user decisions: NA-mode RCSB containment (with W9 data), W10 all-class
RCSB-benefit requeue for proteins/chem (now that channel fires).
(identification-only deltas + protein parity sweep) → W8 requeue 797 (snapshots + queue,
V-16/V-17) → W9 closeout (anchors, flips, funnel v12, stats package v12).
### Pending user decisions
- NA-mode RCSB short-circuit (dead-by-design): keep wasted calls vs explicit short-circuit
  message. Recommendation: report-only this wave; decide with W9 closeout data.
- Requeue confirmation (W7 report first per plan).

## FINAL AUDIT (READ-ONLY) — findings register (opened 2026-10-04)

Post-campaign whole-codebase audit. Read-only mandate: findings reported, user decides
per item. Master register: `.tmp/final_findings.md` (scratch); this section = pinned ledger.

### A. Execution / queue / control plane (report 1, 2026-10-04)
- **F-03 (bug/med)** Restart-resume INERT: `ResultsManager.start_run` resets every task to
  "pending" (results_manager.py:211-218) BEFORE executor's resume-skip reads persisted state
  (executor.py:124-134) → restarts redo ALL stages; 2026-09-18 boot-loop fix silently dead.
  Fix sketch: task-entry `setdefault` instead of unconditional reset.
- **F-05 (methodology/med-high)** 12h stale sweeper requeues FOREVER (queue_processor.py:755-833):
  retry_count untouched, no cap/quarantine (dispatch path caps at 3). Mechanistic explanation
  of pathological-straggler class (12h slot burn per cycle). Fix sketch: stale-cycle counter →
  quarantine status after K cycles.
- **F-09 (risk/med, urgent-cheap)** bat3-ui-worker `PYTHONPATH=/data/validation/patched_src`;
  stale PRE-W4 src_new tree exists there (Sep 20, no W4/W5 markers). Inert only because CWD
  precedes PYTHONPATH (verified live). Fix: delete NFS tree + drop env.
- **F-01 (bug/med)** Duplicate POST routes in src_new/api/main.py (start-processing :509/:663,
  stop-processing :710/:727) — first wins, second defs are dead stubs that look live.
- **F-02 (consistency/low)** Worker entrypoint truth split: Dockerfile.worker CMD
  (-A src_new.celery_app --concurrency=4) is dead default; live = -A tasks --concurrency=2.
- **F-04 (fragility/med)** Prod worker task registration survives via bottom-of-file import
  side-effect (tasks.py:146); deleting it = fleet-wide silent dispatch outage.
- **F-07 (methodology/low-med)** pubchem.py returns threshold as hit "score" (TODO ×3,
  Tanimoto never computed) — synthetic ordinals for that resolver family.
- **F-08 (config/low)** CELERY_BROKER_TRANSPORT_OPTIONS env on 3 deploys: nobody reads it
  (code sets opts; VALUES DIFFER: env KEEPINTVL=30 vs code 20). Dead config.
- **F-06 (security/low)** Placeholder DB password as code default (api/main.py:23, loader.py:576).
- **F-10 (hygiene/low)** SPIN_DEBUG=1 armed fleet-wide (120s faulthandler dumps).
- **F-11 (architecture/info)** Control plane = repo-ROOT main.py (md5-verified live) + root
  queue_processor.py/models.py/tasks.py; bat3_validation/api v2.5 lineage has NO live
  deployment (divergent twin queue_processor, 500 vs 833 LOC).
- **F-12 (ok)** settle_by_results_truth well-guarded (mtime≥start−600s, ≥15min age, 400/tick).
- **F-13 (obs)** bat3-ceitec-bat3-redis 0/0 dormant; single broker everywhere.
- **F-14 (record-pin)** Fleet = 181 workers (164+15+2).

### B. Deferred from N1 fix menu (verify in audit; not executed in wave)
- **F-N1d** pdb_backbone_nucleic / pdb_backbone_not_sanitized_nucleic fail on atomistic NA
  ("Unable to generate PDB signature", v3.124 probe) — STILL OPEN, verify vs current code.
- **F-N1f (V-20)** [identifiers] "no" toggles ineffective in campaign inis — verify registry
  gating coverage (formula_chembl gate exists; others?).
- Mis-flagged segments: 21 nucleic-frame molecules carried protein signatures (pre-wave);
  post-W4 segmentation recount pending.
- topology_less_pdb mock/parallel-path failure ("SimpleNamespace has no attribute resnums")
  — serial campaign path fine; verify current state.

### C. Pending user decisions (carried)
- NA-mode RCSB containment (xclass: mmcif/pdb_struct families attempt ALL classes post-W2 —
  6,110 chem + 1,691 nucleic attempts that can only waste/400).
- W10 all-class RCSB-benefit requeue (proteins/chem) — needs replay-based estimate first.
- Audit decisions queue: F-01..F-14 dispositions.

### D. Identify/verify + wire + legacy (audit reports 2-3, 2026-10-04)
- **F-17 (methodology/med)** min_final_confidence=0.0 everywhere → confidence gate vacuous;
  non-chemical identity hits verify on resolver self-assertion w/o corroboration record.
- **F-21 (config/med, V-20 CONFIRMED)** [identifiers] ini toggles dead except 3 keys
  (overwrite_existing, formula_local, formula_chembl).
- **F-23 (med, decision)** NA-mode RCSB attempts design-dead (protein-centric structure node);
  NEW: protein mode's composition filter excludes mixed entries (F-24); query has NO
  request_options → silent 10-row truncation (F-25).
- **F-15 (drift/low-med)** parallel identify worker = fork of manager.resolve missing PUG
  breaker + overwrite-skip (armed only if identifiers_parallel=on).
- **F-16 (low)** resolve_all production-dead/test-only. **F-18 (low)** canonical signature
  map ×3 copies. **F-19 CLOSED** chain-collapse dedup safe (all-entity fetch + best-match).
  **F-22 CLOSED** F-N1d fixed by wave-7 B4.
- **F-20 (ops/low-med)** rcsb_cache: per-process limiter (fleet ceiling ≈ procs×3rps),
  hardcoded NFS cache path, no TTL.
- **F-26 (armed-divergence)** legacy start_processing endpoint → tasks.schedule_validation:
  ts-less run_ids (W2 serving 404s) + re-downloads into unserved /entries/ layout.
- **F-27 (packaging/low)** src/ PARTIALLY live (src_new imports src.constants ×2);
  CODE_HEALTH_REPORT findings 1-2 persist (no packaging; pytest not in requirements).
- **F-28 (methodology/med)** official figure generators + wave tooling: NFS-only, NO git —
  unversioned mutable single copies (v12 reproducibility hole); campaign_stats.py is the
  lone dual-homed/md5-synced exception.
- Evidence cross-checks: serving logs all-200 in W8 window (RCSB fetch healthy on campaign
  path); live 400s = genuine NA "could not process"; W4 strand-select deterministic (BFS
  atom-0 → deterministic sibling parity).

## FINAL AUDIT — SECTION E · Fix verification & deployment (2026-10-04)

**Rulings:** F-09 fixed (shadow tree deleted, ui-worker PYTHONPATH dropped, in-place) ·
F-10 wontfix · F-08 later · F-13 deferred-to-migration · F-26 → dedicated workstream
(widened: 6 main.py call sites + src_new endpoint) · F-04 armored (b65ea8845) ·
F-02 documented fallback CMD (372dec800).

**Code fixes (all image-baked, deployed as v3.126-audit2, fleet-wide):**
- F-01 ed4322254 duplicate stub routes removed (single defs; verified in-pod route table).
- F-03 ef1bc0ec1 start_run setdefault (status persistence) → REVISED 4b374e306 after
  live regression (below): skip only generate_signatures/identify_molecules/verify_results,
  only on persisted 'success'; loader/repair/unwrap/analyze/export always re-run.
- F-05 022240db2 sweeper consumes retry budget, quarantines at MAX_RETRIES, entry failed too.

**INCIDENT 2026-10-04 (audit1):** activating the never-fired 2026-09-18 skip path via
start_run-fix exposed latent missing context-rehydration: requeue of entry 1612
(unwrap='warning') skipped loader → unwrap critically failed (missing_universe),
pipeline failed. Caught by mandatory live requeue test before methodology work;
workers rolled back to N1 within ~25 min; semantics revised + verified. LESSON:
fixes that activate dead code paths REQUIRE live end-to-end verification, not only
synthetic tests. (synthetic unit tests passed while the integration semantics were wrong)

**Live verification evidence (v3.126-audit2, entry 1612, snapshot-backed):**
- Baseline (old code) requeue: 45s, completed, semantics identical to snapshot.
- Post-fix full run: 44.9s, completed, statuses+hits+segments+signatures identical.
- Resume run: 15.0s (3× faster), IDENTICAL semantics; run log shows exactly
  "Resume: skipping {generate_signatures,identify_molecules,verify_results}
  (persisted success)".
- F-05 live: synth straggler (retry=3, stale 25h) quarantined in one 30s sweeper
  tick: queue failed (cycle 4/3 note), entry failed; synth rows cleaned after.
- F-04: all workers register src_new.api.tasks.run_pipeline_task (fleet probe 181 hits).
- F-01: ceitec api route table single-def per route.
- Rollback yamls: .tmp/rollback/v3.126/*.pre-v3.126.yaml.

**Straggler implication:** 11 pathological stragglers now die within ≤3 stale cycles
(~36h) under deployed F-05 instead of looping forever.

**Empirical test artifacts (scratch):** .tmp/f03_repro.py, .tmp/f03b_executor_skip.py
(12/12 scenarios incl. exact 1612 production replay), .tmp/f05_stale_test.py (12/12;
9/12 fail pre-fix).

## FINAL AUDIT — SECTION F · Methodology fixes (ruled + implemented, 2026-10-04)

Rulings + plan: `.tmp/METHODOLOGY_DECISIONS.md` · `.tmp/IMPLEMENTATION_PLAN.md`.

**Wave A (repo hygiene, behavior-neutral):**
- F-18 canonical map ×3→1 `ae397f064` (byte-identity proven pre-edit; shared object post).
- F-16 resolve_all marked test/harness-only `2292d79aa`.
- F-07 pubchem constant-score semantics annotated `c9821a9f9`.
- F-06 neutral localhost DB default `46b59a0ff` (env-override verified both directions).

**Wave B (runtime semantics; deployed IMAGE v3.127.1 all-5):**
- F-21 `ef4ac367d` — CORRECTED scope (audit half-wrong, getattr blindspot):
  dual `<name>`/`<name>_similarity` pair mechanism was live for class-attr
  resolvers; fixed (i) 8 resolvers lacking declared IdentifiersConfig fields
  (ini keys silently dropped) and (ii) 5 classes / 7 instances assigning
  `self.name` AFTER `super().__init__()` (enablement keyed on "" = dead) —
  now property-based reads. Drift note: name_ccd/maps/manual similarity now
  honors its declared `no` default. SIDE-REPORT (unfixed, needs ruling):
  formula_chembl env-only construction → inert unless ini says `yes`.
- F-25 `c26810250` — RCSB paginate rows=10000; live-proven (464 total: 10→464
  returned rows, protein control from worker pod).
- F-17 `e562eee12` — verified_without_corroboration flag, telemetry-only per
  ruling (identity stays identity; zero metric shift); backfill default False.
- F-23 `65ae1c536` + refinement `fad7892d7` — NA-RCSB containment: nucleotide
  mode short-circuit + two-stage NA classifier (entity_poly types; residue-name
  scan for trimmed signatures — the gate caught stage-1 under-firing on REAL
  generated signature entry 1533, hence v3.127.1). Declared verdict
  `na_mode_unsupported` flows to stage_errors (countable non-failure class);
  pod-side contrast: same payload class → HTTP 400 as before.

**Deployment:** all 5 deployments `cerit.io/tomsko/bat3-validation-api:v3.127.1`
(era clean); rollback yamls: `.tmp/rollback/v3.127/` and `.tmp/rollback/v3.127.1/`.

**Live gate evidence (v3.127.1, in-pod + queue):**
- Resume-regression: 1612 requeue (row 165263, batch b-wave-live-gate) completed
  30s; verify-counts identical to snapshot; zero new errors at run time.
- F-23 real signature: containment fires in 0.2 ms, zero network round-trip.
- F-25: protein control query (464 total) returned all 464 rows from pod.
- F-21: toggle honored at applicable-resolvers layer; similarity untouched.
- F-17: gate→flag→persist chain in shipped image.
- DATA NOTE (report, not fixed): failed-run `critical_errors` records persist
  in results.json across successful recomputes (1612 still carries the
  11:03 audit1-incident pair). Likely needs an explicit clear-on-recompute
  policy decision.

## SECTION F2 · Wave C — F-15 parallel identify parity (2026-10-05, DEPLOYED v3.128)

- C1 `1ff4e76b3` — parallel identify worker DELETED its inline phase-loop fork;
  delegates to `manager.resolve()` per generator/signature against a temp
  ResultsManager (verify-worker pattern). Driver items extended: 5th tuple
  element = fragment's persisted identifiers blob (seeded so overwrite skip
  has serial parity); flat output at serial blob granularity.
  Fork deficits closed: PubChem circuit breaker, overwrite_existing skip,
  third canonical-map copy (already unified in F-18).
- V-24 offline gate (.tmp/f15_parallel_parity.py 10/10):
  T1-T3 parallel==serial deep-equality (real inchikey chain);
  T4-T5b breaker honored in BOTH paths (fork lacked it), both breaker states equal;
  T6-T9 overwrite skip fires in parallel (seed byte-identical; fresh compute
  preserved beside kept seed). Executor suite: 2 failures PROVEN pre-existing
  env at baseline via stash-bisect.
- C-close live (v3.128 all-5, rollback .tmp/rollback/v3.128/):
  isolated identifiers_parallel=1 proof in worker pod with REAL 1612-derived
  fragments (name_ccd + formula-mirror classes, thread pool 2): parallel ==
  serial deep-equal; zero worker errors. Regression row 165264: 15s resume
  pattern, completed.
- SIGNIFICANCE ADDITION (found during C3): src_new/api/routes/runs.py
  `/config/parallel-default` sets identifiers_parallel=True -> UI parallel
  default config already ARMS the identify parallel path in production. The
  fork was live-armed, not just latent; parity now makes that path safe.
  Remaining UI surface work (a toggle in the separate bat3-validation-ui
  repo) recorded as optional future item.
- NOTES: formula_chembl appears in similarity-phase `attempted` lists with
  <name>_similarity defaulting True even while identity is field-gated off --
  harmless no-op class; understanding pinned. Regression note: 1612 keeps the
  11:03 audit1-critical_errors pair (persistence question -> OQ-2, ruled in
  §G0). Straggler batch TERMINAL 2026-10-05: 788 completed + 9 completed,
  0 remaining, zero failures (F-05 quarantine horizon never tripped) --
  OQ-6 closed.

## OPEN QUESTIONS (living register, est. 2026-10-05; rulings batch §G0 2026-10-05)

Ruled items live in §E/§F/§F2/§G0; this list tracks unresolved, deferred, or
requires-user-ruling questions with anchors. Format: OQ-N · status · question
· evidence · disposition.

- OQ-1 · **RESOLVED §G0a — contained** · Empirical campaign (live-pod probes,
  2026-10-05): resolver is NOT inert -- it is live-enabled (worker SKIP_PUG=1
  registers it; live ini formula_chembl: yes) AND silently dead: coded filter
  `molecule_structures__full_molformula__exact` returns HTTP 400 upstream,
  swallowed by the designed 400->[] soft-fail => attempts counted, zero hits,
  zero errors, forever. Upstream truth: EBI ChEMBL removed formula fields
  from payloads (CHEMBL113/25 both None) and filters (exact variants either
  invalid [400] or silently ignored [full-DB results]); fuzzy search works
  but exact re-rank impossible (no per-candidate formula available). No api/2.
  RULING: contain. live ini flipped yes->no (single-line diff; backup
  /data/validation/backups/config_shared.ini.pre-oq1-2026-10-05 md5 6515685c);
  no-break proof chain: flag consumed ONLY by registry gate + enablement
  property; get_applicable_resolvers excludes it; similarity flag unpaired
  (True) but _resolve_similarity designed [] no-op; unit test
  test_chembl_flag_off_is_output_equivalent_containment locks contract
  (offline_fallbacks 28/28 green); live e2e post-flip: enabled_identity=False,
  formula identity selection = [formula_pubchem_local (working mirror),
  formula_pubchem, formula_hfamily]. Formula channel = local mirror + hfamily.
  Code kept dormant for revival via local ChEMBL mirror => OQ-11.
- OQ-2 · **RESOLVED §G1 — no code change, semantics proven** · Chain:
  api/tasks.py:75 ResultsManager loads existing payload -> requeue KEEPS
  errors; results_manager.py:36-50 fresh-init after results.json delete ->
  clean re-run CLEARS them. Unit pins (81309634c, 13/13): resume-reopen
  keeps; delete+fresh clears. LIVE PROOF entry 1612: snapshot
  /data/validation/backups/oq2-clean-1612-2026-10-05/results.json
  (md5 955374bc, errors=2 [11:03 audit1 pair] + 13 warning spam) -> rm
  results.json -> queue sim row 165266 -> run 177320 full recompute
  (~8 s end-to-end, input cached) -> NEW results.json md5 313753d1:
  critical_errors=[],
  verification payload BYTE-EQUAL vs snapshot (ts-normalized), 2 fresh
  warnings (pbc_unwrap + F-23 na_mode_unsupported -- containment verdict
  resurfacing by design), pipeline success, 9 tasks. History kept: old
  errors archived in snapshot + bat3_runs 177319 + this ledger.
- OQ-3 · **RESOLVED §G0** (commit 39e8599b7): 2 stale tracked .bak deleted;
  grep-clean; suite green-modulo-blast-env.
- OQ-4 · **DEFERRED (backlog)** · UI toggle identifiers_parallel in separate
  UI image; "parallel is a goal, but it's tricky" -- runs.py default already
  arms it safely post-F-15 parity.
- OQ-5 · **DEFERRED (research backlog)** · real NA structure-similarity
  upstream.
- OQ-6 · **RESOLVED §G0** · straggler batch terminal: 788+9 completed,
  zero failures, quarantine never tripped.
- OQ-7 · **RESOLVED §F5/F7/F8** · F-24 additive SHIPPED (default OFF,
  gold-fixture-proven); W10 full-family (ruled scope-(b)) drained 99.65%
  with zero-defect verification (both misflag metrics 0).
- OQ-8 · **RULED: leave** · formula_pubchem_local double-attempted list is
  known-cosmetic; churn not worth a deploy.
- OQ-11 · **SCHEDULED (between Wave F and Wave G)** · **local ChEMBL
  hosting/mirror** to revive formula_chembl offline (pattern: pubchem
  local_db, docs/PLAN_PUBCHEM_MIRROR.md). User: "before we get to G, we will
  resolve this local chembl hosting." Scope sketch: ChEMBL SQLite (or derived
  formula->CHEMBL table) on PVC, resolver switched to local lookup under a
  flag, empirical gates (caffeine->CHEMBL113 exact), ini flip back to yes
  only after proof.
- OQ-9 · **RESOLVED §F5–F8** · Serial-loop props-routing bug
  (_PinnedPropsFacade, `8dee3b89e`); blast radius measured at 4332/4324
  (not 21); W10 full-family requeue healed ALL -> official metric 0 and
  family metric 0/0/0 (recounts archived). Flat-cohort invariance proven
  unit + live (1612/2346).
- OQ-10 · **RESOLVED §G0** (commit 72763155d) · latent v3-era contract break:
  base.resolve() re-raised IdentifierResolutionError vs documented None.
  Ruling: drop raise, keep record (log + get_last_error -> manager error list
  -> UI). Evidence: identification suite 169p/5f -> 196p/4f, all remaining
  failures = blast-DB env class; telemetry contract locked by new test.

## SECTION F3 · Wave D — F-28 stats→repo + N1 leftovers (2026-10-05, repo-side)

- D2 `6f419b486` + tag `v12-stats-generators`: 34 NFS single-copy *.py captured
  byte-identical (md5-verified 0/34 mismatch), py_compile 34/34, into
  scripts/stats/ with MANIFEST.csv + README. Dual-home drift at copy time:
  6 identical; validation_similarity.py reverse-drift (REPO newer); rest
  NFS-only. NFS originals untouched; method = repo-edit-first from now on.
- D2b: adopted repo-native audit tools into scripts/stats/ (audit_gt_absent.py,
  audit_interm.py — previously .tmp-only lineage while their OUTPUTS lived
  on NFS) + new versioned tool n1_misflag_recount_postw4.py.
- D3 GOLD E2E (live): /tmp-redirected run of REPO-copy
  assemble_stats_package_v12.py regenerated stats_package_v12.json AND .md
  IDENTICAL (timestamp-normalized) to the frozen official artifacts
  (2026-10-03). Provable: the versioned code IS the code behind official v12.
- D4 N1 leftovers:
  * F-N1d CLOSED by live evidence: post-W4 entries carry pdb_nucleic +
    pdb_backbone_nucleic + not-sanitized variants (entry 1533 generated set).
  * gt_absent anatomy re-run (redirected, no official mutation): STABLE vs
    frozen — 194 rows, classes identical (A_gt_unresolvable 118, B1a 47,
    D_unrelated 28, B2 1; mirror-missing 76; sim_new_pairs 22).
  * mis-flag recount post-W4 (scripts/stats/n1_misflag_recount_postw4.py,
    same frozen-frame conditions as the original audit): count = 21
    UNCHANGED — BUT all 21 are recent-reprocessed virtual minority segments
    (SYSTEM__vN, 2026-09-26..10-03, incl. ENAR-on). Anatomy of 2346/SYSTEM__v4:
    is_nucleic=True name-tier fragment whose fasta_map_protein contains
    'CUAAUUCAAUUAUU' (RNA letters labeled as protein fasta) + full pdb_protein
    blobs. => NOT a pre-wave artifact: generator-class gating in the
    virtual-minority exposure path assigns protein-family generator names to
    nucleic fragments (content-wise wrong: RNA letters as protein sequence ->
    wasted protein attempts + noise). REPORTED as OQ-9; no fix without ruling.
- OQ-9 (REPORT 2026-10-05): minority-exposure virtual segments (SYSTEM__vN)
  emit protein-class generators for nucleic-framed fragments (21 segments,
  ~1% of nucleic frame, era-spanning incl. post-ENAR 2026-10-03). Evidence:
  entry 2346 SYSTEM__v4 fasta_map_protein='CUAAUUCAAUUAUU'. Suggested
  direction (needs ruling): gate generator class by segment properties
  (is_nucleic) for virtual segments; fix scope = signatures worker routing,
  not facade classification (which is correct).

## SECTION F4 · Wave E — F-27 constants promotion + packaging (2026-10-05, DEPLOYED v3.129)

- E1 `0bbe57de5`: src_new/constants.py generated from src.constants source
  of truth — 3 tables (masses 118 / residues 54 / nucleic 80) byte-VALUE
  identical, md5-verified vs snapshot; checkpoint tag pre-f27-checkpoint +
  .tmp backup. THREE import sites switched (plan had 2; 3rd = blast.py:19).
- ALARM-class find per user rule+ruling (a): universe_facade.py + blast.py
  carried try/except "isolated execution" fallbacks with SUBSET copies
  (20/54, 15/80 = silent degraded classification; dead in prod). Deleted;
  single canonical object proven shared across all 4 consumers (id-equal).
- E3 `0bbe57de5`: minimal pyproject.toml (metadata + dev=pytest + paths;
  requirements.txt remains image dep truth. pip -e install smoke OK).
- E4 tests: signatures 87, molecules 124, pipeline_steps 25, top-level 73,
  verification 143 pass; identification 169(+5 env), executor 10(+2 env),
  api 66+2, input 21+1 — api/input failures STASH-PROVEN pre-existing;
  loader NFS-backed stall class documented. f03b/f05/f15 harnesses green.
- E-close live gate (v3.129 all-5, rollback .tmp/rollback/v3.129/):
  in-image import smoke (shared canonical object); 1612 requeue
  (row 165265) 15s resume pattern, verify counts identical to snapshot,
  zero new critical errors. legacy src/ untouched (still importable).

## SECTION G0 · OQ rulings batch + hygiene (2026-10-05, repo-side)

- User ruled full OQ register (rulings embedded above). Executed items:
  * OQ-6 closed: straggler batch terminal (788+9, zero failures).
  * OQ-3 `39e8599b7`: 2 stale tracked .bak snapshots deleted (grep-clean).
  * OQ-10 NEW + RESOLVED same-session `72763155d`: alarm-first discovery --
    identification suite carried a latent contract break since
    'sequential final' (init-era test expected None; BASE-8 era tests
    expected raise).     Ruled contract = None + record kept. Suite
    169p/5f -> 196p/4f (remaining 4 = blast-DB env class, stash-proven
    identical pre/post). New telemetry-lock test added; BASE-8 pair updated.
- No deploy impact: behavior byte-equivalent in prod (manager absorbs both
  paths identically; identity+similarity loops symmetric) -- proof recorded
  in commit 72763155d. G0 items ride no image; Wave F image will carry
  nothing from G0 (contract change is test-visible only... note: base.py
  code DID change -> next image bump bundles it harmlessly; flagged in §F5
  when Wave F image is cut).
- Remaining queue: OQ-1 (empirical campaign, phase next), OQ-2 (verify
  recompute-reset semantics; fix if needed; ships with Wave F image),
  OQ-7 -> Wave F plan, OQ-9 fix inside Wave F, OQ-4/OQ-5 backlog,
  OQ-8 left-cosmetic.

## SECTION G0a · OQ-1 empirical campaign + containment (2026-10-05, no image)

- Empirics (live worker pod validation-worker-787bc84df7-22j9f @ v3.129):
  live ini had formula_chembl: yes (line 73, SKIP_PUG=1 era) => resolver
  ACTIVE on every chemical entry; 4-probe Lydia tests along with raw-API
  variants proved coded filter HTTP-400-swallowed => silent no-op (caffeine
  -> 0 hits / 0.14 s; malformed/system-scale too; full_molformula exact
  variant silently unfiltered 2.9 M rows; payloads carry no formula fields;
  api/2 404). Verdict: dead upstream, contained by ini flip yes->no.
  Snapshot: /data/validation/backups/config_shared.ini.pre-oq1-2026-10-05
  (md5 6515685cddf9b960defa5faab6d373dd); new md5 8b60d62a...; single-line
  diff (73c73). Running runs keep their already-loaded config; flip affects
  only NEW runs -- no mid-run interference possible (ini read at run start).
- No-break guarantee (code-level): the only consumers of the flag are the
  registry construction gate and the per-call enablement property
  (registry.py:118, base.py enabled_identity + get_applicable_resolvers).
  Verified live post-flip: registered (no import breakage), identity
  selection excludes it; formula sigs now served by working local mirror
  (formula_pubchem_local) + hfamily. Test lock:
  tests/src_new/identification/test_offline_fallbacks.py::
  TestRegistryGating::test_chembl_flag_off_is_output_equivalent_containment
  (offline_fallbacks 28/28).
- Lesson candidate (pinned into V-26 on next errors-sync): 400->[]
  "bad formula" soft-fail masks "invalid filter" bugs -- mechanism family
  sibling of V-25 getattr blindspot ("mechanism exists, empirically dead").
- OQ-11 scheduled between Wave F and Wave G: local ChEMBL hosting to
  revive this resolver offline (pubchem local_db pattern).

## SECTION G1 · OQ-2 closure — critical_errors lifecycle semantics proven (2026-10-05, no image)

- Operator semantics (documented contract, zero code change):
  * **requeue (resume)** -> ResultsManager loads existing results.json
    (api/tasks.py:75) -> critical_errors + warnings KEPT (the audit-history
    side the user wants preserved).
  * **clean re-run = snapshot results.json -> delete -> requeue** ->
    fresh payload (results_manager.py:36-50) -> errors CLEARED.
- Unit pins `81309634c`: tests/src_new/test_results_manager.py +
  test_oq2_resume_reopen_keeps_critical_errors + _clean_rerun_resets_
  (13/13 module).
- Live e2e (entry 1612, queue row 165266/batch oq2-clean-gate, run 177320):
  pre-delete snapshot oq2-clean-1612-2026-10-05 (md5 955374bc; errors=2
  from the 11:03 audit1 epoch; warnings 13-across-resume-cycles) -> rm ->
  full recompute ~8 s (input cached; resume-skip correctly NOT firing) ->
  new results.json md5 313753d1: critical_errors [], verification payload
  byte-equal (ts-normalized), pipeline success/9 tasks, fresh warnings = 2
  (pbc_unwrap + mmcif_struct na_mode_unsupported => F-23 containment
  verdict resurfacing as designed). 1612 is now a permanently de-noised
  gate entry; old noise archived in snapshot + bat3_runs 177319.

## SECTION F5a · OQ-9 fix landed (Wave F part 1, 2026-10-05, pre-deploy)

- `8dee3b89e` + test file tests/src_new/pipeline_steps/test_oq9_virtual_routing.py.
- Mechanics (verified reading facade/discovery/worker/snapshot chain):
  facade classification CORRECT all along (virtual props computed via
  _compute_flags(frag0)); parallel worker mock-facade routes correctly;
  SERIAL path bug: generators' get_segment_properties(fragment.segids[0])
  resolves PARENT segid props -> protein gens on NA virtual fragments.
  Live 21 rows therefore came from serial-processed entries.
- Fix: _PinnedPropsFacade + _pinned_props_facade in serial loop only.
  Flat-cohort byte-invariance guaranteed structurally (same props object)
  + locked by unit test; OQ-8/OQ-10 unchanged. Rides v3.130 with F-24.
- NEXT in Wave F: F1-B F-24 code (rcsb_include_mixed_complexes, default
  OFF, addon Protein/NA query appended) + gold fixtures; F2 additive +
  flat replay (3 anchors incl. the 21-row evidence via stats tooling);
  F3 W10 sweep; F4 v3.130 staged roll + 1612 gate + production W10.

## SECTION F5 · Wave F landed + deployed v3.130 (2026-10-05)

- Code: OQ-9 fix `8dee3b89e` (_PinnedPropsFacade serial routing; flat cohort
  byte-invariant by construction+unit lock); F-24 additive `33932ebe2`
  (rcsb_include_mixed_complexes default OFF; base list untouched; identity
  phase inherits merge); F-24 replay `ce5285163` (live-frozen gold fixture
  1UBQ base 464 + Protein/NA addon 2 {7P0V, 8ID2} + 1HLV 2 + 1S72 upstream
  400 datapoint; additive-invariant + identity-neutrality on real data).
  OQ-10/OQ-2 ride the image from G-era commits.
- BLAST-RADIUS ESCALATION (report-first): official N1 metric = 21 misflagged
  virtual NA segments; premeasure across 15,134 entries shows the family is
  4,332 segments / 4,324 unique entries (21 NA-class + 4311 neither-class
  ligand/lipid virtuals wearing protein signatures; 2261 SYSTEM__v2 spot-
  validated, era 2026-09). Ruling: FULL-FAMILY cleanup (4324-entry W10
  requeue) AND local-ChEMBL revival (OQ-11) BEFORE the requeue, so the
  one-time requeue runs in the final era. Pre-measure + cohort archived:
  /data/validation/backups/oq9-w10-2026-10-05/ (md5 c0679f.../3fd24f...).
- Pre-deploy replay-first PROOF (cohort entry 2346 real universe, overlay
  probe, restored byte-exact): baseline vs patched routing diff isolates
  ONLY virtual segments (flat segments identical); NA v4/v5 protein-gens
  removed + nucleic-gens added; neither-class v6 protein-gens removed.
- DEPLOY v3.130 (image 50895bceb10b, pushed; rollback yamls
  .tmp/rollback/v3.130/): staged worker-first 164/164, in-image smoke
  (OQ-9 helper present; F-24 flag default False; OQ-10 contract in base).
  Gates: 1612 clean re-run row 165267/run 177321 FLAT-INVARIANT live
  (0 signature-set diffs, verification byte-equal, 0 errors);
  2346 clean re-run row 165268/run 177322 HEALED live: v4/v5 protein
  6->0 nucleic 1->5 (fasta_map_nucleic='CUAAUUCAAUUAUU' -- the same RNA,
  correctly channeled); v6 protein 6->0/none added; flat SYSTEM keys
  byte-identical; 0 critical errors. Remaining 4 deployments rolled;
  era-check 5/5 v3.130.
- NEXT PHASES (ruled): Phase OQ-11 local ChEMBL mirror build -> v3.131
  + ini re-enable -> empirical gate; THEN W10 full-family requeue (4324
  entries, chunked batches, batch prefix w10-heal); post-sweep recounts
  (official 21-metric AND family metric) -> 0; then Wave G docs.

## SECTION F6 · OQ-11 local ChEMBL mirror landed + revived (v3.131, 2026-10-05)

- CODE `9a18c6677`: ChEMBLDB (molecules/chembl_db.py; pubchem_db idiom:
  immutable ro sqlite, exists() degrade hook), ChemblConfig.local_db_path
  = /app/databases/chembl/current/chembl.sqlite, FormulaChEMBLResolver
  local-first + one construction warning on REST fallback (REST preserved
  as unreachable-dead-but-intact fallback). Tests x5 (+26 fallback suite
  green); identification 188 pass / 4 known blast-env fails.
- BUILDER `bf0a69935`: scripts/build_chembl_local_mirror.py (resume-safe,
  schema sniff + RDKit fallback, caffeine self-check, atomic symlink).
  BUILD 2026-10-05 (worker pod): chembl_37_sqlite.tar.gz (5.76 GB) EBI ->
  distilled 2,901,464-row chembl.sqlite (224 MB; direct
  compound_properties.full_molformula column present in v37 -- no RDKit
  fallback needed), layout /app/databases/chembl/{v37,current->v37} +
  build_metadata.json, raw tarball kept. Self-check caffeine -> CHEMBL113
  first (48 exact hits).
- DEPLOY v3.131 (4cfc52ff..., rollback .tmp/rollback/v3.131/): staged
  worker-first, in-pod empirical gate (REAL live ini + mirror + resolver):
  caffeine C8H10N4O2 48 hits / 16 ms [CHEMBL113 first], aspirin C9H8O4 41
  hits / 166 ms [CHEMBL25], water H2O 4 hits / 7 ms, junk 0/1 ms, zero
  errors (vs dead-REST era: everything 0/silent). Rolled all 5 deployments,
  era-check 5/5 v3.131.
- RE-ENABLE: live ini flipped back no->yes (single-line diff; backup
  config_shared.ini.pre-oq11-reenable-2026-10-05; md5 symmetric reversal
  to 6515685c). Selection set now [formula_pubchem_local, formula_pubchem,
  formula_chembl (working offline), formula_hfamily].
- E2E gate 165269/run 177323 (1612 full clean re-run on v3.131): pipeline
  success, 0 errors, verification byte-equal, 0 unexpected diffs;
  formula_chembl ATTEMPTED in-pipeline on SYSTEM molecular_formula
  (whole-segment C310H362N122O188P30 -> 0 hits = correct system-scale
  class). OQ-8 cosmetic double-attempted-listing visible again in the
  payload -- ruled leave, noted.
- Formula ecosystem current truth: pubchem local (offline, primary) +
  chembl local (offline, revived) + PUG REST (503-dead soft) + hfamily.

## SECTION F7 · W10 full-family heal requeue FIRED (2026-10-05, in-flight)

- Capacity: validation-worker scaled 164 -> 450 (requests 250m CPU / 16Gi
  RAM as-is, limits unchanged 4cpu/24Gi; ns quota ceiling ~476 by request
  memory; ramping 244+ at fire time, rolling to 450).
- Requeue orchestration (in-pod psycopg2, CHUNK=500): FIRE COMPLETE
  18:41 — 4324/4324 snapshotted to backups/oq9-w10-2026-10-05/raw/ +
  deleted + queued (batch_id='w10-heal', priority 5). One false-start
  incident (host-side edit error in fire script; crashed pre-insert after
  chunk-0 file ops; rerun-safe retry completed with zero double-effect).
- Early drain evidence (t+~15 min): completed 128 / processing 108 /
  queued 4088 / FAILED 0. Heal verified on first completions
  (2261/2304/2306/2307): virtual protein misflags 5|6 -> 0, nucleic
  channels correct, zero errors, snapshot-backed flat checks.
  Explained delta class (NOT a bug): genuine-protein SYSTEM segments gain
  fasta_map_protein vs 2026-09-era outputs because map-fasta requires
  bond data (input-repair era difference; 2261 sample = clean 301-aa
  sequence). Family semantics stable since 1612/2346 gates.
- NEXT: tail monitor until drained (~hours); then double recount
  (official 21-metric + family 4332-metric) -> target 0; formula_chembl
  spot-hits on small-molecule cohort entries; Wave G docs after.

## SECTION F8 · W10 drain (99.65%) + heal verified to ZERO + v13 statistics delivered (2026-10-06)

- DRAIN: batch w10-heal 4305/4324 completed at stats-freeze time (199 frac.
  tail = scheduler/prefetch-class zombie claims from wave-wide OOMKilled
  (137) restarts; three dead-man reclaim rounds applied with audits on PVC;
  ~19 in-flight draining). User decision: tail keeps draining; quarantined
  sims get re-queued later, stats snapshot now.
- HEAL VERIFICATION (post-drain recounts, frame 15134):
  * official N1 21-metric: misflag = **0** (was 21), frame 13899,
    /data/validation/stats_v13/oq9_postw10_recount.json
  * full-family 4332-metric (own rescan, same family keys): **0/0/0 total**
    (na 0, other 0) -> /data/validation/stats_v13/oq9_virtual_misflag_postw10.json
  5501 (NFS stale-handle failure) cured via reclaim.
- v13 STATISTICS ARTIFACTS (canonical /data/validation home):
  * campaign_stats_v13.json (S1-S7 producer @ 08:24; 6674 B)
  * stats_package_v13.json/.md (assembler v13 `7cb2fade8`; frozen v12 untouched)
  * per_molecule_stats_v13.csv (26,354 rows; signature family composition,
    generator attempts, identifier resolver attempts + distinct hits,
    verified hits chem/seq split w/ real scores; script `78858cfd5`+fix)
  * stats_v13/ dir mirrors all four + heal-verification jsons.
- HEADLINE (post-heal era, validated%_of_annotations):
  inchikey @1 59.2->60.2 @5 88.3->89.4 @10 92.9->93.0 (ann 5784->5988)
  ion @1=@5=@10 95.9->96.1 (ann 1811->1876)
  pdb @1 97.3->96.9 @5 98.9->98.7 @10 99.5->99.5 (ann 11186->11392)
  uniprot @1 94.2->94.0 @5 97.2->97.0 @10 98.2->98.1 (ann 12575->12790)
  Deltas: chemistry up across inchikey/ion; pdb/uniprot down 0.1-0.4 pts =
  denominator growth from healed+new entries (honest note for figures).
- Links for figures (NFS): /data/validation/stats_package_v13{.json,.md},
  /data/validation/per_molecule_stats_v13.csv, mirrored under
  /data/validation/stats_v13/; verification jsons same dir.

## SECTION F8b · Per-species molecule statistics (v13, 2026-10-06)

- per_molecule_by_species_v13.csv + _summary.json (canonical root +
  stats_v13/ mirror; script `3f9202856`): 26,354 (entry,segment) rows
  aggregated into 15,987 UNIQUE species (key priority inchikey ->
  smiles-md5 -> prot-seq-md5 -> nuc-seq-md5 -> seg fallback, 544 'other').
  Class mix: protein 10,545 | chemical 3,901 | nucleic 997 | other 544;
  species bearing >=1 verified hit: protein 9,897, chemical 3,792,
  nucleic 163, other 2. Columns incl. n_entries/n_segments, families,
  id_distinct_hits, verified_hits (chem/seq split), top_verified_id+score,
  representative entry/segment.

## SECTION F9 · Epoch closure-hygiene state (2026-10-06)

- HEAL VERIFIED to ZERO: official N1 21-metric = 0; family 4332/4324
  metric = 0/0/0. v13 stats (package + both rollups + funnel) published on
  NFS canonical root + stats_v13/ bundle; per-molecule species coverage:
  protein 93.8% / chemical 97.2% / nucleic 16.3% (structural floor by
  design) / other 0.4%; entry-any 97.9/99.3/99.5.
- REMAINING TAIL (user decision: drain naturally, quarantine requeue later):
  batch 'w10-heal' 4305/4324 at freeze; ~19 rows = prefetch/zombie claim
  class (wave-wide OOMKilled bursts; 3 dead-man reclaim rounds applied
  w/ audits; NOT code defects; runs fail instantly at claim, zero-IO).
  Watchdog horizon 12h ultimately flips them; targeted requeue when
  convenient. 5501 (NFS stale handle) cured in reclaim wave 1.
- INFRA NOTES (for ops): validation-worker replicas ceilinged at 244 by
  namespace limits.cpu quota (1061600/1064900m; ~3300m free); scale-up
  attempt to 450 met FailedCreate; scaled back cleanly (carve-out:
  worker mem limits are 24Gi; OOM kills during the mass heal = collective
  peaks; current fleet steady at 244 x 4cpu/24Gi).
- NEW REGISTER ITEM: OQ-12 · open (ops hardening idea) · zombie/prefetch
  claim detection should be a ~1h DB-side dead-man probe (log-IO idle vs
  claim age per queue worker) instead of passive 12h stale_timeout;
  implemented as 3 manual reclaim scripts during W10 -- candidate for
  codifying as a sweeper route. Evidence: reclaim audits on PVC.
- Ledger commits for the era (context for harvest): 8dee3b89e OQ-9 fix,
  33932ebe2 F-24 code, ce5285163 F-24 replay, d67b6d336 §F5,
  9a18c6677+bf0a69935 OQ-11 code+builder, e51c70823 §F6, 6f8b6ae56 §F7,
  7cb2fade8/78858cfd5/3f9202856 stats tooling, 18c438d37/4bb23cf5e §F8(+b).
- Era truth at close: 5/5 deployments v3.131; live ini formula_chembl=yes
  (mirror-first), pdb.rcsb_include_mixed_complexes default no (shipped);
  queues: w10-heal 4305 done; stragglers-era completed earlier.

## SECTION G · Wave G closeout + F-26 design lane (2026-10-06)

### G3 · F-05 straggler auto-close datapoints (TERMINAL, 2026-10-06)
- Batch `nucleic-fix-wave-1` final state: **788 completed / 9 failed**,
  zero processing; batch window 2026-08-12 -> terminal 2026-10-05T18:38Z.
- All 9 failures carry `stale_timeout: no completion for >12h (stale
  cycle 3/3)` with retry_count=3 -- F-05 sweeper working exactly as
  designed (post-fix: <=3 stale cycles -> quarantine, entry failed,
  no silent resurrection). The September pathology (infinite 12h requeue
  of consistently-hanging entries) is dead. Horizon rule "re-check at
  >=12/24/36h; close when terminal" satisfied by DB state.
- User ruling 2026-10-06: quarantined entries will be requeued *later*
  intentionally (with the w10-heal tail or a dedicated wave); keep
  parked until then. Stats generation for that cohort deferred per
  OQ-era ruling.

### F-26 · Lane C design delivered (.tmp/F26_DESIGN.md, read-only lane)
- Empirical census (bat3_validation, 2026-10-06): canonical 14-ts run_id
  shape = 173,144 bat3_runs (active through today); uuid8 legacy = 66
  rows, last 2026-08-06; ts-less `validation-<eid>` = 0 rows (legacy
  schedule_validation never writes Bat3Run at all); queue FK linkage
  19,068 linked vs 3 NULL ever. => legacy dispatch = armed but disused
  since 2026-08-06; hazard is LATENT (UI/curl reactivation), not active.
- Failure chains pinned: both legacy run_id shapes fail serving regex
  `_UUID_PATH_RE` (ts \d{10,16}) -> /files/validation-... 404 -> RCSB
  deployment-file evidence absent; main.py:2078 + src_new/api/main.py:541
  start-processing endpoints create NO Bat3Run + NULL FK (settle blind,
  sweeper-only lifecycle; 541 doesn't even set started_at and uses an
  unserved split-brain layout /data/validation/results/<eid>/).
- Recommendation (user decision pending, Q1-Q4 in the design doc):
  **C-now + B-lite-post-campaign** -- freeze legacy dispatch (env guard,
  default frozen) + deprecation notes NOW (zero behavior change);
  reroute the two start-processing endpoints through
  process_validation_queue post-campaign; retire old validate/retry
  endpoints. F-04 registration import (tasks.py:146-152) stays untouched.
- Line-drift note: brief refs verified; tasks.py schedule_validation body
  = :33-112 (run_id :93); registration comment = :146-152.

### G1 · Legacy doc banners (2026-10-06)
- Era-stamped (blockquote banners, non-destructive):
  docs/ARCHITECTURE.md (pre-audit `src/` map -- historical intent),
  docs/src_new_backbone.md (structure ok; behavior superseded by F-03
  resume / campaign machinery / OQ-series), docs/CODE_HEALTH_REPORT.md
  (SUPERSEDED by the 28-finding final audit; serves as historical record
  only). Each banner points to this ledger + site + F26_DESIGN.md.

### G2 · k8s mkdocs hosting — probe state + ruling (2026-10-06)
- Probe: ingress class `nginx` in use (bat3-ceitec-bat3-ingress,
  validation-ui-v2); hosts under *.dyn.cloud.e-infra.cz. Namespace quota:
  limits.cpu 1061600/1064900m (3300m headroom) -- a docs pod at
  10m/32Mi requests + 100m/64Mi limits fits.
- docs/site: mkdocs material, 9 pages, docs_dir "." (self-contained);
  mkdocs absent from .venv -> built in image builder stage instead.
- User ruling: **docs image approach (builder stage + nginx), served
  under the existing UI host** (no new hostname). Implementation +
  port-forward verification + ledger entry follow in-session.

### Tail status at G-open (2026-10-06 ~10:00Z)
- w10-heal: 4306/4324 completed, 18 'processing' = diagnosed this morning
  as OOM-claim stragglers (pods OOMKilled 137 at 07:21-07:22 mid-run;
  entries cycle watchdog->claim->OOM; NOT the OQ-9 fix -- 8879 hung
  pre-fix since 09-12, distinct pathological class). User ruling: leave
  computing organically; quarantine requeue later (G3 note).

### G4a · F-24 mixed-complex channel ENABLED live (2026-10-06, user ruling)
- Config flip (additive, no image): live ini `/data/validation/config_shared.ini`
  `[pdb] rcsb_include_mixed_complexes = yes` appended with provenance
  comment. md5 6515685c -> 889730df; rollback snapshot
  `config_shared.ini.pre-f24-enable-2026-10-06` on PVC (md5-symmetric
  restore = flip back; also ini-flag-only, no code/image dependency).
- Effective per-run (queue dispatch resolves shared ini when per-entry
  config.ini absent -- queue_processor.py:131); in-flight claimed runs
  keep their task-start config (safe: additive flag).
- LIVE PROOF (v3.131 worker pod, production-shaped): scratch served uuid
  on the real W6b route (bioid-ceitec.../files/validation-999999999-<ts>/
  input/1ubq.pdb, scratch entry id chosen outside DB space, dirs deleted
  after): 1UBQ -> MERGED 466 hits = 464 base channel (fixture gold)
  + {7P0V, 8ID2} Protein/NA addon appended at tail; self 1UBQ present.
  Flag parsed True from live ini; resolver path =
  `_pdb_fetch_similar_structures` additive branch (code unchanged since
  33932ebe2). mmCIF-format note: RCSB payload hardcodes format="pdb" --
  structure files must be PDB-format (a .cif input yields upstream 500;
  production always feeds PDB; incident-class only, no code change).
- OQ-7 register thread: F-24 shipped default-OFF (F5) -> now LIVE.
  Expect: mixed-complex segment structures gain Protein/NA neighbors in
  new runs only (forward-only, frozen-v12/v13 untouched).

### G2 · k8s mkdocs hosting LANDED (2026-10-06)
- Docs image `cerit.io/tomsko/bat3-docs:v3.131-g2.2` (Dockerfile.docs:
  mkdocs-material:9 strict build -> nginxinc/nginx-unprivileged:1.27 on
  8080; worker_processes capped 2 -- auto=host-cores OOMed the 64Mi
  limit; PSA-restricted ns forced non-root; learnings recorded).
- Site restructure: pages moved docs/site/*.md -> docs/site/docs/*.md
  (git mv; mkdocs 1.6 rejects docs_dir "."). Build context = docs/site
  (root .dockerignore excludes docs/ for api image -- documented in
  Dockerfile.docs).
- Deployment validation-docs (1 repl, 10m/32Mi req / 100m/64Mi lim --
  fits 3300m ns cpu headroom) + svc; manifest deploy/validation-docs.yaml.
- Ingress: /docs Prefix on EXISTING UI host (user ruling "under ui"):
  https://bat3-validation.dyn.cloud.e-infra.cz/docs/ LIVE (200; UI at /
  verified 200 immediately after; TLS unchanged via existing secret).
  INCIDENT-NOTE: first strategic patch REPLACED ingress path list (~10s
  UI route gap); fixed within one step by full-desired-state patch;
  rollback snapshot .tmp/rollback/g2-docs/validation-ui-v2-ingress-
  pre-docs.yaml. Lesson: kubectl strategic patch on ingress paths list
  replaces -- always supply complete paths array.
- Verified: port-forward curls (index/identifiers/configuration/search
  index 200) + public URL curls post-patch.

### NEW REGISTER ITEM · OQ-13 (2026-10-06, user-added)
- **OQ-13 · queued · UI-worker sqlite mirror corruption class** --
  "file is not a database" errors in identification on UI-queued runs:
  corrupted local DB cache on UI workers ( known failure mode from
  earlier ops). Remedy per ruling: copy the known-good mirror DB from
  the validation worker deployment over to the UI workers and wire UI
  lane config to it (fresh integrity_check + immutable-copy pattern).
  To be implemented TOGETHER WITH the F-26 dispatch-lane unification
  (the UI queue lane is the same surface; single maintenance window,
  single era bump). Evidence to collect at fix time: which DB file
  (pubchem/current vs chembl/current), corrupt mtime/size, integrity
  probe output; keep failing example run id for before/after proof.

### G4b · External incident-registry note POSTED (2026-10-06)
- `/home/tomsko/work/bat3_validation/docs/INCIDENT_REGISTRY_2026-09.md`
  appended "Session 36" entry: September zero-results class -> resolved;
  pointer to this ledger + v13 stats + heal chain (W4->N1->W10) + open
  tails (F-26/OQ-13 window). NOTE: bat3_validation is NOT a git repo --
  file-level write only (no commit possible; user informed).
- Wave G status: G1 banners OK (fc3d5f6df), G2 hosting OK (cfe766b89),
  G3 datapoints OK, G4a F-24 live OK (f59d1b19a), G4b registry note OK.
  **Wave G COMPLETE.** Open: F-26 Q1-Q5 decision + OQ-13 window
  scheduling; w10-heal 18 rows computing organically per ruling.
