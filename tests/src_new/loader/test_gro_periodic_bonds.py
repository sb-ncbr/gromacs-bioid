"""dm1 audit (L7): a topology-free .gro keeps molecules that cross a box
face whole (bonds guessed under the box, minimum image), the dm1 v5
coordinates tier done inside BioID."""
from pathlib import Path

import pytest

pytest.importorskip("MDAnalysis")

from tests.src_new.loader.test_chainless_topology_w31 import _run_results  # noqa: E402

# butane split across the x face of a 10 nm box (C-C 0.153 nm)
GRO = """butane across the box face
    4
    1BUT     C1    1   9.890   5.000   5.000
    1BUT     C2    2   9.990   5.110   5.000
    1BUT     C3    3   0.090   5.000   5.000
    1BUT     C4    4   0.190   5.110   5.000
  10.00000  10.00000  10.00000
"""


def test_molecule_across_box_face_stays_whole(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    (case / "butane.gro").write_text(GRO)
    data = _run_results(case, tmp_path / "run")
    segs = data["fragments"]["segments"]
    assert len(segs) == 1 and segs[0]["atoms_per_copy"] == 4, segs


def test_box_not_containing_atoms_is_not_used():
    import MDAnalysis as mda
    import numpy as np
    from src_new.loader.coordinates import mark_periodic_bond_guess, periodic_box
    u = mda.Universe.empty(2, trajectory=True)
    u.load_new(np.array([[0.0, 0, 0], [80.0, 0, 0]], dtype=np.float32), format="memory")
    u.dimensions = [10, 10, 10, 90, 90, 90]
    mark_periodic_bond_guess(u)
    assert periodic_box(u) is None
