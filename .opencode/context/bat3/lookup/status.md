# BAT3 Validation Status (2026-09-10, post-full-scale-GO)

## Core Concept
Current truth for the ceitec-biodata-ns validation deployment. Full-scale run is LIVE and healthy as of 2026-09-10 ~14:20 UTC.

## Key Points
- **Entries indexed**: 15,185 (14,066 with ground truth: 27,328 signatures = 14,787 UniProt + 12,541 PDB)
- **Full-scale run**: queue drain in progress — ~640 completed of 14.6k at checkpoint, ~10 completions/min peak, celery depth 0, dispatch ON
- **Validation metrics (pilot, hit@K vs GT)**: hit@1 = 0.348, hit@5 = 0.731, hit@10 = 0.811 overall (pdb 0.840); 456 rows in `validation_results`
- **Images live**: `bat3-worker:v2.14`, `bat3-validation-api:v3.86` (api + validation-worker), helm `bat3-ceitec` rev 6
- **Worker uids unified**: both consumer pools run as uid 1000 (validation-worker was 65534 → cross-uid EPERM source, unified 2026-09-10 PM)
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

- Intake throughput: download-cohort-bound (GB trajectories over MDposit bandwidth; runs-created ~5-6/15min in that segment). v3.91 adds parallel phase-2 intake (VALIDATION_INTAKE_WORKERS, 16) + Range-resume; further gains need a dedicated prefetch pipeline, not more threads
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
