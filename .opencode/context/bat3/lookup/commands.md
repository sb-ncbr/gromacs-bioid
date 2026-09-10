# BAT3 CLI Commands

## Core Concept
Quick reference for all BAT3 validation CLI commands.

## Key Points
- **Status**: Check run and entry counts
- **Index**: Manage MDDBR entry indexing
- **Run**: Execute BAT3 validation runs
- **Compare**: Generate comparison reports

## Status Commands

```bash
# Full status report
python -m validation.src.cli status
```

## Index Commands

```bash
python -m validation.src.cli index --all
python -m validation.src.cli index --backfill-failing
python -m validation.src.cli index --retry-unreachable
```

## Run Commands

```bash
# Single bounded batch
python -m validation.src.cli run --batch-size 50 --timeout 1800

# Background loop (see guides/running-validation.md)
setsid python validation/scripts/run_until_done.py --workers 6 ...
```

## Compare/Report Commands

### Campaign statistics (2026-09-10)
```bash
P=$(kubectl get pods -n ceitec-biodata-ns -o jsonpath='{.items[0].metadata.name}' -l app=validation-api)
kubectl exec $P -n ceitec-biodata-ns -- python3 /data/validation/campaign_stats.py                 # quick (SQL, ~5s)
kubectl exec $P -n ceitec-biodata-ns -- python3 /data/validation/campaign_stats.py --full         # + NFS scan (~10s)
kubectl exec $P -n ceitec-biodata-ns -- python3 /data/validation/campaign_stats.py --entry 2944   # one entry digest
kubectl exec $P -n ceitec-biodata-ns -- python3 /data/validation/campaign_stats.py --full --json-out /data/validation/stats-$(date +%F).json
```
Sections S1-S6: coverage/ETA, failure taxonomy, per-stage, per-molecule, hit@K per GT type, health extras.
--since ISO filters results.json by mtime (default 2026-09-10T11:00 — excludes incident-era files; empty string includes all).
Repo source: `validation/scripts/campaign_stats.py` (deployed copy on NFS at /data/validation/).

```bash
# Generate comparison report
python -m validation.src.cli compare
python -m validation.src.cli report
```

## Reference
- `status.md` - Current status numbers
- `../guides/running-validation.md` - Background loop setup
