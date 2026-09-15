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
