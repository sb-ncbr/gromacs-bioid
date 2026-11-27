"""GitHub #12: a hydrogen that the structure file only NAMES differently
(prmtop 'H2' vs mdtoolbelt PDB 'H1', MD-A0017Y / 2OUE) must not discard the
whole topology — but a hydrogen whose coordinates sit on the wrong heavy
atom must still fail the per-index check."""
from __future__ import annotations

import pytest

pytest.importorskip("MDAnalysis")

from tests.src_new.loader.test_topology_structure_w31 import (  # noqa: E402
    _attempts, _run, _write_probe)


def _h_probe(tmp_path, pdb_h_name: str, h_xyz: str):
    """Probe with CM1 (atom 5) turned into hydrogen 'H1' bonded to NA only."""
    probe = _write_probe(tmp_path / "probe")
    itp = probe / "heme.itp"
    text = itp.read_text()
    text = text.replace("     5   CT      1    HEM     CM1    1    0.00  12.0110",
                        "     5   HA      1    HEM     H1     1    0.00   1.0080")
    text = text.replace("      2   5     1\n", "")
    itp.write_text(text)
    pdb = probe / "heme.pdb"
    lines = []
    for line in pdb.read_text().splitlines():
        if line.startswith("ATOM") and line[12:16] == "CM1 ":
            line = (line[:12] + f"{pdb_h_name:<4s}" + line[16:30] + h_xyz
                    + line[54:76] + " H" + line[78:])
        lines.append(line)
    pdb.write_text("\n".join(lines) + "\n")
    return probe


def _top_pdb(data):
    return [a for a in _attempts(data) if a.get("strategy") == "gromacs_top_pdb"]


def test_hydrogen_rename_at_bond_length_keeps_topology(tmp_path):
    # NA at (1,1,1); H at 1.0 A from it
    probe = _h_probe(tmp_path, "H2", f"{2.0:8.3f}{1.0:8.3f}{1.0:8.3f}")
    attempts = _top_pdb(_run(probe, tmp_path))
    assert attempts and attempts[0].get("status") == "success", attempts


def test_misplaced_renamed_hydrogen_still_rejected(tmp_path):
    # H 2.0 A from its topology partner: coordinates belong to another atom
    probe = _h_probe(tmp_path, "H2", f"{3.0:8.3f}{1.0:8.3f}{1.0:8.3f}")
    attempts = _top_pdb(_run(probe, tmp_path))
    assert attempts and attempts[0].get("status") == "failed", attempts
    assert attempts[0].get("error_code") == "structure_name_mismatch", attempts[0]
