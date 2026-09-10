# Running BAT3 Validation

## Core Concept
Start a background validation loop to process pending BAT3 runs against MDDBR entries.

## Key Points
- **Workers**: Use 6 workers for parallel processing
- **Batch size**: 50 entries per batch
- **Timeouts**: 1800s per run, 3600s per batch
- **Background**: Use `setsid` to detach from terminal
- **Monitoring**: Check logs and status periodically

## Start Background Loop

```bash
setsid python validation/scripts/run_until_done.py \
  --workers 6 --batch-size 50 --timeout 1800 \
  --batch-timeout 3600 --sleep 10 \
  >> validation/output/run_loop_background.log 2>&1
```

## Check Status

```bash
# Validation status
python -m validation.src.cli status

# View live logs
tail -f validation/output/run_loop_background.log
```

## Reference
- `../lookup/status.md` - Current run numbers
- `../errors/common-issues.md` - Troubleshooting
