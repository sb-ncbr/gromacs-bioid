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
