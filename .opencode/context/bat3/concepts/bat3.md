# BAT3: MD Simulation Analysis Pipeline

## Core Concept
BAT3 is a pipeline for analyzing molecular dynamics (MD) simulations and identifying molecules. It processes simulation data through a binding site analysis workflow.

## Key Points
- **Purpose**: Analyze MD trajectories to identify binding sites and molecules
- **Active codebase**: `src_new/` contains current implementation
- **Deprecated**: `src/` is legacy code; do not use for new development
- **API endpoint**: `api_endpoint_new.py` handles HTTP requests
- **Validation**: `validation/` directory contains MDDBR comparison tools

## Project Structure

```
bat3/
├── src_new/           # Active implementation
├── src/               # DEPRECATED - legacy code
├── api_endpoint_new.py # Current API handler
├── validation/        # MDDBR validation toolkit
└── tests/             # Test suite
```

## Reference
- `/home/tomsko/work/bat3/src_new/` - Active source code
- `/home/tomsko/work/bat3/validation/` - Validation toolkit
