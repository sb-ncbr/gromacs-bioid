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

```bash
# Generate comparison report
python -m validation.src.cli compare
python -m validation.src.cli report
```

## Reference
- `status.md` - Current status numbers
- `../guides/running-validation.md` - Background loop setup
