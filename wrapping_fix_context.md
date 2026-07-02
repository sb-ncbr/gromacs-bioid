# Wrapping Fix Context

## Bug / Feature
Input simulations can be broken across periodic boundaries: parts of molecules "teleport" to the other side of the simulation box. This makes structural search/visualization impossible.

## Affected Run
- `run_id`: `2c405b11-a52a-4e1c-9649-9c7d16660538`
- Input: `md_TonB_10mM_deprot_ca2+_nowater.gro` + `.tpr` (GROMACS)
- 4615 atoms, protein + 192 Cl⁻ ions
- Observed: residues 9, 12, 16, etc., jump ~70–180 Å across the box; protein chain visually split.
- Exported `system.mmcif` and segment mmCIF lack `_cell.*` box records.

## Debugger Summary
- Pipeline status: `success` with warnings.
- Tasks completed: discover_input, load_simulation, repair_topology, analyze_universe, generate_signatures, identify_molecules, verify_results, export_results.
- Identification confidence was low (`final_confidence: 0.0`) partly due to BLAST timeouts / RCSB API issues, but the structural root cause is PBC wrapping.
- No unwrapping or box-preservation step is currently applied.

## Relevant Code Locations
- `src_new/loader/strategies.py` — loads GROMACS TPR+GRO via MDAnalysis `Universe(..., in_memory=True, tpr_resid_from_one=True)`.
- `src_new/loader/repair.py` — `TopologyRepair` fixes elements/masses/names/bonds but does not touch coordinates.
- `src_new/loader/universe_facade.py` — `LoadedUniverse` analyzes segments and fragments; uses raw positions.
- `src_new/pipeline_steps/__init__.py` — pipeline steps; current order:
  `discover_input → load_simulation → repair_topology → analyze_universe → generate_signatures → identify_molecules → verify_results → export_results`.
- `src_new/loader/export_mmcif.py` — exports whole-system and segment mmCIF using Biopython `MMCIFIO`; does not write `_cell` records.
- `src_new/signatures/generators/pdb.py` / `mmcif.py` — generate signatures from raw fragment positions.
- `src_new/config/loader.py` / `config.ini` — loader configuration.
- Tests: `tests/src_new/loader/test_export_mmcif.py`.

## Proposed Fix
Add a periodic-boundary unwrapping repair step after topology repair and before universe analysis, and preserve the simulation box in exports/signatures.

### High-level Plan
1. **Configuration**: add loader options (e.g., `unwrap_periodic_boundaries`, `unwrap_compound`, `unwrap_reference`, `unwrap_on_missing_bonds`).
2. **New module**: `src_new/loader/unwrap.py` with a `PbcRepair` class.
   - Read box from `universe.dimensions`.
   - Ensure bonds exist (use existing bond guesser as fallback).
   - Call MDAnalysis `AtomGroup.unwrap(compound='fragments', reference='com', inplace=True)` for single-frame inputs.
   - For multi-frame trajectories, add `MDAnalysis.transformations.unwrap(...)` to the trajectory.
   - Record a report.
3. **Pipeline integration**: insert `_unwrap_periodic_boundaries` between `_repair_topology` and `_analyze_universe`.
4. **Box export**: inject `_cell.length_*` / `_cell.angle_*` and `_symmetry.space_group_name_H-M 'P 1'` into mmCIF exports; optionally add `CRYST1` to PDB signatures.
5. **Tests**: add tests verifying unwrapped protein continuity and presence of `_cell` records.

### Implementation TODO
- [ ] Add unwrap settings to `LoaderConfig` and `config.ini`
- [ ] Create `src_new/loader/unwrap.py` (`PbcRepair`)
- [ ] Insert unwrap step into pipeline between repair and analysis
- [ ] Write simulation box (`_cell`) into exported mmCIF files
- [ ] Optionally propagate box header to PDB/mmCIF signatures
- [ ] Add unit tests for wrapped structure unwrapping and box export
- [ ] Document edge cases and fallback strategies

## Research Agent Notes
- The research agent was invoked multiple times (including with explicit instructions to use `webfetch` and avoid jina.ai/textise proxies) but returned empty/aborted results each time.
- The plan above is therefore based on local code inspection and standard MDAnalysis 2.x API knowledge.
- When the research agent is fixed, it should verify: exact `AtomGroup.unwrap()` signature/defaults, bond requirements, multi-frame `transformations.unwrap` usage, and whether Biopython `MMCIFIO` can write `_cell` records directly.

## Next Steps
1. Fix the research agent.
2. Re-run research to confirm MDAnalysis API details.
3. Implement the fix following the plan above (delegate to programmer).
