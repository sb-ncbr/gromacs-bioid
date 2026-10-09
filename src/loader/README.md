# DEPRECATED — legacy loader (frozen, superseded)

**Status: frozen. Do not extend or fix.** Superseded by `src_new/loader/`
(strategies.py + input/discovery.py), which is the engine-matrix loader used by
the production pipeline (`celery -A tasks` → `src_new.api.tasks.run_pipeline_task`).

## Why it stays
- No live deployment entrypoint imports `src.loader` directly; it's used only
  internally by the legacy `src/` package chain (`src.executor`, imported by the
  also-legacy `api_endpoint.py` / `api_endpoint_new.py` surfaces).
- Repo rule: no deletions without explicit confirmation — hence a freeze marker,
  not a removal.

## What superseded it (2026-10 loading-strategy widening)
- Engine matrix: GROMACS (+ trr coords), AMBER (+ rst7/mdcrd coords), CHARMM/NAMD
  (.psf + .pdb/.crd/.dcd), LAMMPS (.data), PDB, mmCIF.
- `src_new/loader/probe.py` atom-count probing; post-build success gates.
- This module set retains a quirky `XTC`-as-topology-with-rdkit-bond-inference
  strategy that the new loader deliberately does NOT port (no engine topology =
  honest failure instead).

Adding new engine support? Add a `LoadStrategy` in `src_new/loader/strategies.py`,
a suffix in `src_new/input/discovery.py::_CANONICAL_SUFFIX_TABLE`, and fixture
coverage in `tests/data/` — never here.

See `.opencode/context/bat3/concepts/loading-strategy.md` for the design record.
