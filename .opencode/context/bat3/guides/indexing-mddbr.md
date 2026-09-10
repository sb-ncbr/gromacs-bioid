# Indexing MDDBR Entries

## Core Concept
Index MDDBR entries into the local database before running BAT3 validation.

## Key Points
- **Full index**: Indexes all 7,643 MDDBR entries
- **Backfill**: Re-index entries with missing data
- **Retry**: Re-attempt unreachable nodes (cin/inr DNS issues)
- **Incremental**: Skips already-indexed entries
- **Cache**: Uses `validation/cache/` for fetched data

## Index Commands

```bash
# Index all MDDBR entries
python -m validation.src.cli index --all

# Backfill entries with missing data
python -m validation.src.cli index --backfill-failing

# Retry unreachable nodes (DNS failures)
python -m validation.src.cli index --retry-unreachable
```

## Reference
- `../lookup/status.md` - Entry counts
- `../errors/common-issues.md` - Unreachable node handling
