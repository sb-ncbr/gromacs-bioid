# Context Update Workflow

## Core Concept
Keep context files synchronized with project state through lightweight, verification-focused updates.

## Key Points
- **Trigger**: Run `python -m validation.src.cli status` before updating status.md
- **Update frequency**: Refresh numbers after each major validation milestone
- **Line budget**: If a file exceeds 200 lines, split by function
- **Verification**: Always verify commands work before documenting

## Update Checklist

```bash
# 1. Get fresh status
python -m validation.src.cli status

# 2. Update lookup/status.md with new numbers

# 3. Verify line count
wc -l .opencode/context/bat3/lookup/status.md

# 4. Confirm <200 lines
```

## Reference
- `../standards/mvi.md` - File size limits
- `/home/tomsko/work/bat3/.opencode/context/bat3/lookup/status.md` - Current status
