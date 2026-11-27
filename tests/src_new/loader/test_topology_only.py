"""dm1 audit (L2): a deposit with a topology but no coordinates (14 dm1
deposits: .itp, .psf, .prmtop only) loads from the topology alone; the
placeholder coordinates are marked so no stage uses them as geometry."""
import shutil
from pathlib import Path

import pytest

pytest.importorskip("MDAnalysis")

from tests.src_new.loader.test_chainless_topology_w31 import _run_results  # noqa: E402

PSF = Path(__file__).resolve().parents[2] / "data" / "charmm_psf_pdb" / "system.psf"
COORDINATE_SIGNATURES = {"pdb_protein", "pdb_backbone_protein", "topology_less_pdb", "ca_only_pdb",
                         "tdi", "mmcif"}


def test_psf_without_coordinates(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    shutil.copy(PSF, case / "system.psf")
    data = _run_results(case, tmp_path / "run")
    ok = [a for a in data["loading"]["attempts"] if a.get("status") == "success"]
    assert ok[-1]["strategy"] == "topology_only"
    assert data["loading"].get("coordinates_absent") is True
    sigs = data["signatures"]["PROA"]["generated"]
    assert "fasta_map_protein" in sigs and "smiles" in sigs
    assert not COORDINATE_SIGNATURES & set(sigs)
    assert "@" not in sigs["smiles"]  # no stereo from placeholder geometry


def test_coordinates_absent_mark():
    import MDAnalysis as mda
    from src_new.loader.coordinates import coordinates_absent, mark_coordinates_absent
    u = mda.Universe(str(PSF))
    assert not coordinates_absent(u)
    mark_coordinates_absent(u)
    assert coordinates_absent(u) and coordinates_absent(u.atoms[:3])
    assert u.atoms.positions.shape == (u.atoms.n_atoms, 3)
