# BAT3 Validation Pipeline

## Core Concept
Validation compares BAT3 output against MDDBR (Molecular Dynamics Database Repository) ground truth to measure accuracy and coverage.

## Key Points
- **Purpose**: Verify BAT3 results match known MDDBR signatures
- **Scope**: 7,643 MDDBR entries indexed, 4,112 complete
- **Pending**: ~2,221 complete entries awaiting validation runs
- **Metrics**: hit@1/5/10, step success rates, completion rates
- **Storage**: Results in `validation/bat3_runs.db` SQLite database

## Pipeline Flow

```text
MDDBR Entry → Index → BAT3 Run → Compare Signatures → Report Metrics
     ↓           ↓          ↓            ↓              ↓
   7,643      Indexed   2,494 runs   Match check   hit@N scores
```

## Reference
- `../lookup/status.md` - Current validation numbers
- `/home/tomsko/work/bat3/validation/src/` - Validation source code
