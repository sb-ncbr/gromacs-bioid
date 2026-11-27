"""dm1 audit (L2): a Universe loaded from a topology alone carries
placeholder (all-zero) coordinates so every stage runs, and this mark so no
stage takes them for geometry: no bond guessing, no PBC unwrap, no metal
coordination, no stereo from 3D, no structure signatures, no render."""
from __future__ import annotations

_MARK = "_bat3_coordinates_absent"


def mark_coordinates_absent(universe) -> None:
    import numpy as np
    universe.load_new(np.zeros((universe.atoms.n_atoms, 3), dtype=np.float32), format="memory")
    setattr(universe, _MARK, True)


_PERIODIC = "_bat3_periodic_bond_guess"


def mark_periodic_bond_guess(universe) -> None:
    """dm1 audit (L7): a topology-free GROMACS coordinate file (every atom
    wrapped into the box): bonds are guessed under the box (minimum image),
    so molecules crossing a face are not cut into pieces."""
    setattr(universe, _PERIODIC, True)


def periodic_box(u):
    """The box to guess bonds under, or None: only for a marked Universe
    with an orthorhombic box that actually contains every atom (a wrong or
    placeholder box would bond atoms across faces)."""
    import numpy as np
    if not getattr(u, _PERIODIC, False):
        return None
    dims = getattr(u, "dimensions", None)
    if dims is None or len(dims) < 6:
        return None
    dims = np.asarray(dims, dtype=float)
    if not (np.all(dims[:3] > 0) and np.allclose(dims[3:6], 90.0, atol=1e-3)):
        return None
    pos = u.atoms.positions
    if pos.min() < -1.0 or np.any(pos.max(axis=0) > dims[:3] + 1.0):
        return None
    return dims


def coordinates_absent(obj) -> bool:
    """True for a marked Universe, or an AtomGroup / fragment of one."""
    u = getattr(obj, "universe", obj)
    return bool(getattr(u, _MARK, False))
