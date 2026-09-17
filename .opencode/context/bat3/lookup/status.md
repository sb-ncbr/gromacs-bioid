# BAT3 Validation Status (2026-09-11, post scale-up + chemistry fix)

## Core Concept
Current truth for the ceitec-biodata-ns validation deployment. Full-scale run is LIVE and healthy as of 2026-09-10 ~14:20 UTC.

## Key Points
- **Entries indexed**: 15,185 (14,066 with ground truth: 27,328 signatures = 14,787 UniProt + 12,541 PDB)
- **Full-scale run**: 1,691/14,622 completed (11.6%); throughput cohort-bound (on-disk wave ~20/min; GB-download wave ~5-8 runs/15min over MDposit bandwidth)
- **Validation metrics (pilot, hit@K vs GT)**: hit@1 = 0.348, hit@5 = 0.731, hit@10 = 0.811 overall (pdb 0.840); 456 rows in `validation_results`
- **Images live**: `bat3-worker:v2.25` ×16, `bat3-validation-api:v3.105` api ×1 + validation-worker ×16 (PUG-independent chemistry stack). v3.95(no-suffix) crashes (HEAD Dockerfile poison, fixed). PUG blocks cluster IP since 2026-09-12 (laptop 200 / cluster 503); structure matrix: CID=cache->PUG->IDSM-SPARQL, IK=cactus->chembl->PUG, ChEMBL/CHEBI native; pubchem_struct+formula_pubchem disabled in config_shared.ini `validation-api:v3.95` (no-suffix) CRASHES: HEAD Dockerfile.api had `mv main.py` poison - use v3.95b / fixed snapshot at /tmp/opencode/Dockerfile.api.fixed (line removed in commit 0a3079a79). fsGroupChangePolicy=OnRootMismatch on worker deploys (rollout chown stall fix)
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
