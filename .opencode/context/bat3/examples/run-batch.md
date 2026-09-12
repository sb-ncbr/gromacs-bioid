# BAT3 Batch Run Example

## Core Concept
Example of running a bounded BAT3 validation batch and checking results.

## Key Points
- **Bounded run**: Process a fixed batch size
- **Status check**: Verify runs completed
- **Logs**: Check output for errors
- **Resume**: Loop handles retries automatically

## Example Batch Command

```bash
# Run bounded batch (50 entries, 30min timeout)
python -m validation.src.cli run \
  --batch-size 50 --timeout 1800
```

## Example Status Output

```
BAT3 Run Status
============================================================
  cancelled: 5
  completed: 2227
  failed: 262
------------------------------------------------------------
  Total runs: 2494

Entries:
  Total entries in DB: 7643
  Entries with runs: 1891
```

## Reference
- `../guides/running-validation.md` - Background loop setup
- `../lookup/commands.md` - All CLI commands
