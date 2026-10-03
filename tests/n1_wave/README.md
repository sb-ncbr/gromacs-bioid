# N1 wave gates
- `test_golden_parity.py` — pytest mirror (dev envs with full deps).
- `run_gates.py` — dependency-free in-pod runner (canonical executor):
  `python3 /data/validation/n1_run_gates.py [eid,...]` with N1_FIXTURES /
  N1_GOLDEN / N1_ALLOW_DELTA env; exit 0 = green.
- `allow_delta.json` — per-workstream allowlist for intended golden deltas
  (created as waves land; only diffs listed here may pass).
Baseline: G0 GREEN on v3.124, 2026-10-03 (10/10 fixtures).
