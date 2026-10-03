# N1 wave gates
- `test_golden_parity.py` — pytest mirror (dev envs with full deps).
- `run_gates.py` — dependency-free in-pod runner (canonical executor):
  `python3 /data/validation/n1_run_gates.py [eid,...]` with N1_FIXTURES /
  N1_GOLDEN / N1_ALLOW_DELTA env; exit 0 = green.
- `allow_delta.json` — per-workstream allowlist for intended golden deltas
  (created as waves land; only diffs listed here may pass).
Baseline: G0 GREEN on v3.124, 2026-10-03 (10/10 fixtures).

## Running gates (worker pod, pre-image overlay pattern)
```
# sync local code to pod overlay, then:
tar cz src src_new tests | kubectl exec -i -n ceitec-biodata-ns POD -c worker -- sh -lc 'tar xz -C /tmp/gate_src'
# golden gates (dep-free runner):
PYTHONPATH=/tmp/gate_src python3 /data/validation/n1_run_gates.py
# unit tests (pytest via user-site; pypi reachable):
PYTHONUSERBASE=/tmp/pylibs PYTHONPATH=/tmp/pylibs/lib/python3.11/site-packages:/tmp/gate_src \
  python3 -m pytest tests/src_new -q
```
Overlay note: include legacy `src/` (generators import src.constants) or registry
tests fail on import. BAT3_SRC env on helper scripts forces overlay-first import.

## W1 gate evidence (2026-10-03)
- Unit: tests/src_new/pipeline_steps/test_stage_error_persistence.py (8/8).
- E2E on fixture 1682 (full serial pipeline, scratch): stage_errors.signatures
  .SYSTEM contains 'fasta_map_nucleic: Found 4 disjoint residue components'
  verbatim; all pipeline tasks success/warning; verify stage green (INV-4).
  Artifact: /data/validation/logs/n1_e2e_1682_results.json.
- Golden gates: GREEN 10/10; @errors field allowed per allow_delta.json
  (worker now surfaces generation failure reasons, previously silent).
- Suite: tests/src_new/signatures + new = 89 passed.
