# BAT3 Validation Status (2026-09-10)

## Core Concept
Current truth for the ceitec-biodata-ns validation deployment after the Sept-2026 incident remediation.

## Key Points
- **Entries indexed**: 15,185 (14,066 with ground truth: 27,328 signatures = 14,787 UniProt + 12,541 PDB)
- **Entries processed (reproc campaign)**: 456/GT-covered subset of 570 ever-run
- **Entries with verified identifications**: 444/456 (97%)
- **Validation metrics (hit@K vs GT)**: hit@1 = 0.348, hit@5 = 0.731, hit@10 = 0.811 overall (pdb hit@10 0.840)
- **Metrics persisted**: 456 rows in Postgres `validation_results` (414 passed / 42 failed)
- **Images live**: `bat3-worker:v2.13`, `bat3-validation-api:v3.83`, helm `bat3-ceitec` rev 6

## Scheduler State
- bat3_runs: 1,379 completed, 1,394 failed (zombies swept)
- validation_queue: 14,583 queued (incl. 180 requeued zombies), 39 failed
- Dispatch: OFF by default (`VALIDATION_DISPATCH_ENABLED=0` in validation-api env)
- Sweeper: active on 30s tick in validation-api

## Remaining Gaps
- ~63 heavy stragglers finishing; 51 no-input entries (ids ~1-20) need re-download
- 51 low-id entries missing input dirs on NFS
- `fasta_map_protein` generator returns None for ~86 entries (P1-12, open)
- hit@1 quality + fragment-vs-GT strictness = accuracy iteration, not infra

## Reference
- `../errors/common-issues.md` — incident failure signatures
- `.opencode/../validation/docs -> ../../bat3_validation/docs/INCIDENT_REGISTRY_2026-09.md` — full forensic log (external dir)
- `ceitec-deployment.md` — live deployment facts
