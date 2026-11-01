"""W3.3 item 3: PBC unwrapping without a box.

Production evidence (re-eval acceptance): M05-class runs recorded
`pbc_unwrap_failed` for amber inputs whose coordinate frame carries no
box, while the topology does (`%FLAG BOX_DIMENSIONS`) — unrecoverable
only because this MDAnalysis build drops `.box` in both ParmEd parsers.
And a genuinely boxless structure is not a failure: wholeness is
decided by the (box-independent) bond/backbone scans.

Rules (user directive):
1. Universe without dimensions + amber topology file -> recover the box
   from `%FLAG BOX_DIMENSIONS` (format: beta, a, b, c) before unwrapping.
2. Still boxless -> skip unwrapping, keep the absolute-threshold
   wholeness scan (bond > 4 A, backbone gap > configured 4.2-class);
   whole = INFO (no warning), broken = still loud.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import numpy as np
import pytest

mdanalysis = pytest.importorskip("MDAnalysis")
from MDAnalysis import Universe

from src_new.config.loader import RunConfig
from src_new.loader.unwrap import PbcRepair, _read_prmtop_box

_PRMTOP = """\
%VERSION  VERSION_STAMP = V0001.000  DATE = 10/31/26  12:00:00
%FLAG BOX_DIMENSIONS
%FORMAT(5E16.8)
  1.09471000E+02  3.00000000E+01  3.00000000E+01  3.00000000E+01
%FLAG ATOM_NAME
%FORMAT(20a4)
CA
"""

_PDB_WHOLE = """\
ATOM      1  CA  ALA A   1       1.000   1.000   1.000  1.00  1.00           C
ATOM      2  CB  ALA A   1       2.500   1.000   1.000  1.00  1.00           C
TER
END
"""

_PDB_BROKEN = """\
ATOM      1  CA  ALA A   1       1.000   1.000   1.000  1.00  1.00           C
ATOM      2  CB  ALA A   1       9.500   1.000   1.000  1.00  1.00           C
TER
END
"""


def _universe(tmp: Path, pdb: str, name: str):
    p = tmp / name
    p.write_text(pdb)
    u = Universe(str(p))
    u.add_bonds([[0, 1]])
    return u


def _config() -> RunConfig:
    cfg = RunConfig()
    cfg.loader.unwrap_periodic_boundaries = True
    cfg.loader.unwrap_guess_bonds_if_missing = False
    return cfg


class TestPrmtopBoxParsing:
    def test_reads_box_dimensions_flag(self, tmp_path):
        p = tmp_path / "system.prmtop"
        p.write_text(_PRMTOP)
        dims = _read_prmtop_box(str(p))
        assert dims is not None
        assert dims[:3] == pytest.approx([30.0, 30.0, 30.0])
        assert dims[3] == pytest.approx(90.0)
        assert dims[4] == pytest.approx(109.471)
        assert dims[5] == pytest.approx(90.0)

    def test_missing_flag_returns_none(self, tmp_path):
        p = tmp_path / "system.prmtop"
        p.write_text("%VERSION x\n%FLAG ATOM_NAME\n%FORMAT(1a4)\nCA\n")
        assert _read_prmtop_box(str(p)) is None

    def test_non_prmtop_suffix_returns_none(self, tmp_path):
        p = tmp_path / "system.pdb"
        p.write_text(_PRMTOP)  # right content, wrong file kind
        assert _read_prmtop_box(str(p)) is None


class TestPrmtopBoxRecovery:
    def test_boxless_universe_recovers_box_and_unwraps(self, tmp_path):
        u = _universe(tmp_path, _PDB_WHOLE, "coords.pdb")
        assert u.dimensions is None
        prmtop = tmp_path / "coords.prmtop"
        prmtop.write_text(_PRMTOP)
        object.__setattr__(u, "filename", str(prmtop))
        report = PbcRepair(u, _config()).run()
        assert report.box_dimensions is not None
        assert report.box_dimensions[0] == pytest.approx(30.0)
        assert report.unwrapped is True
        assert not report.warnings


class TestBoxlessWholeness:
    def test_boxless_whole_is_info_not_warning(self, tmp_path):
        u = _universe(tmp_path, _PDB_WHOLE, "mol.pdb")
        report = PbcRepair(u, _config()).run()
        assert report.box_dimensions is None
        assert report.unwrapped is False
        assert report.unwrap_method == "none (no periodic box)"
        assert report.max_bond_length == pytest.approx(1.5)
        assert report.bond_jumps == 0
        assert report.warnings == []
        assert report.error is None

    def test_boxless_broken_stays_loud(self, tmp_path):
        u = _universe(tmp_path, _PDB_BROKEN, "mol.pdb")
        report = PbcRepair(u, _config()).run()
        assert report.box_dimensions is None
        assert report.unwrapped is False
        assert report.bond_jumps >= 1
        assert report.error is not None
        assert any("PBC unwrapping failed" in w for w in report.warnings)
