"""Coordinate-source probing for the loading pipeline (mdpc 'probe' port).

Reads n_atoms of trajectory/coordinate sources with topology-free MDAnalysis
readers BEFORE attempting a Universe build, so atom-count mismatches become
structured `rejected_atoms` outcomes (with both counts recorded) instead of
opaque Universe() exceptions. Topology counts are parsed only when a pairing
needs them (probe is cheap; parse is not cached here — Universe construction
parses again, acceptable at bat3's one-simulation-per-run scale).

Topology-only scope (locked decision): trajectories are frame-0 coordinate
sources, never analyzed as trajectories.

Usage in strategies: match(topology_atoms, source_path) -> ProbeResult
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("base")


# topology-free readers for trajectory sources (mdpc table)
# NOTE: AMBER ascii .mdcrd is deliberately absent — its reader (TRJReader)
# REQUIRES the n_atoms kwarg, i.e. probing it needs the topology, which defeats
# the point; mdcrds fall back to the Universe build's own count check (they are
# vanishingly rare in deposit corpora anyway — 14 files in mdpc's 337k corpus).
_READER_BY_SUFFIX = {
    ".dcd": ("DCDReader", "MDAnalysis.coordinates.DCD"),
    ".xtc": ("XTCReader", "MDAnalysis.coordinates.XTC"),
    ".trr": ("TRRReader", "MDAnalysis.coordinates.TRR"),
    ".nc": ("NCDFReader", "MDAnalysis.coordinates.TRJ"),
}


@dataclass
class ProbeResult:
    ok: bool
    n_atoms_source: int | None = None
    n_atoms_topology: int | None = None
    error_code: str = ""       # rejected_atoms | probe_failed
    error_message: str = ""


def probe_source_n_atoms(path: Path) -> int | None:
    """n_atoms of a trajectory coordinate source via its topology-free reader.

    Returns None for non-trajectory sources (static text formats like
    .pdb/.gro/.crd/.rst7 are parsed by the Universe build anyway; probing
    them would need the full parser, defeating the point).
    """
    suffix = path.suffix.lower()
    spec = _READER_BY_SUFFIX.get(suffix)
    if spec is None:
        return None
    cls_name, module = spec
    try:
        import importlib

        mod = importlib.import_module(module)
        reader_cls = getattr(mod, cls_name)
        reader = reader_cls(str(path))
        return int(reader.n_atoms)
    except Exception as exc:
        logger.warning(f"probe of {path.name} failed: {exc}")
        return None


def match_atoms(topology_atoms: int, source: Path) -> ProbeResult:
    """Check a topology/trajectory atom-count pairing.

    - probe unreadable or source n_atoms missing -> probe_failed (fallback:
      let the Universe build decide, preserving old behavior)
    - mismatch -> rejected_atoms with both counts recorded
    - equal (or probe not applicable for the source type) -> ok
    """
    n_src = probe_source_n_atoms(source)
    if n_src is None:
        suffix = source.suffix.lower()
        if suffix in _READER_BY_SUFFIX:
            return ProbeResult(
                ok=True,  # defer to Universe build; do not hard-fail on a probe hiccup
                n_atoms_topology=topology_atoms,
                error_code="probe_failed",
                error_message=f"could not probe {source.name}; deferring to load attempt",
            )
        return ProbeResult(ok=True, n_atoms_topology=topology_atoms)
    if n_src != topology_atoms:
        return ProbeResult(
            ok=False,
            n_atoms_source=n_src,
            n_atoms_topology=topology_atoms,
            error_code="rejected_atoms",
            error_message=(
                f"atom count mismatch: topology has {topology_atoms} atoms, "
                f"{source.name} has {n_src}"
            ),
        )
    return ProbeResult(ok=True, n_atoms_source=n_src, n_atoms_topology=topology_atoms)
