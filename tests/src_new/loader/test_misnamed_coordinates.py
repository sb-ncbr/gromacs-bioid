"""dm1 audit (L10): coordinate files whose suffix hides their format, which
dm1 repaired outside BioID (prepare_inputs netcdf_mdcrd / rename), and the
AMBER NetCDF restart MDAnalysis refuses (figshare/29716145 min2.rst.nc)."""
import shutil
from pathlib import Path

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")
netcdf = pytest.importorskip("scipy.io").netcdf_file

from tests.src_new.loader.test_chainless_topology_w31 import _run_results  # noqa: E402

AMBER = Path(__file__).resolve().parents[2] / "data" / "amber_prmtop_rst7"
CHARMM = Path(__file__).resolve().parents[2] / "data" / "charmm_psf_pdb"


def _strategy(data):
    return [a for a in data["loading"]["attempts"] if a.get("status") == "success"][-1]["strategy"]


def _reference():
    return mda.Universe(str(AMBER / "system.prmtop"), str(AMBER / "coords.rst7"), format="RESTRT")


def _write_nc(path, xyz, convention, frames=True):
    with netcdf(str(path), "w", version=2) as f:
        f.Conventions = convention
        f.ConventionVersion = "1.0"
        if frames:
            f.createDimension("frame", None)  # the unlimited dimension comes first
        f.createDimension("atom", len(xyz))
        f.createDimension("spatial", 3)
        if frames:
            v = f.createVariable("coordinates", "f", ("frame", "atom", "spatial"))
            v.units = "angstrom"
            v[0] = xyz
        else:
            v = f.createVariable("coordinates", "d", ("atom", "spatial"))
            v.units = "angstrom"
            v[:] = xyz


def _amber_case(tmp_path, name):
    case = tmp_path / "case"
    case.mkdir()
    shutil.copy(AMBER / "system.prmtop", case / "system.prmtop")
    return case, case / name


def test_netcdf_restart(tmp_path):
    ref = _reference()
    case, nc = _amber_case(tmp_path, "min2.rst.nc")
    _write_nc(nc, ref.atoms.positions, "AMBERRESTART", frames=False)
    data = _run_results(case, tmp_path / "run")
    assert _strategy(data).endswith("_nc")


def test_netcdf_deposited_as_mdcrd(tmp_path):
    ref = _reference()
    case, nc = _amber_case(tmp_path, "prod.mdcrd")
    _write_nc(nc, ref.atoms.positions, "AMBER")
    data = _run_results(case, tmp_path / "run")
    assert _strategy(data).endswith("_mdcrd")


def test_coor_that_is_pdb_text(tmp_path):
    case = tmp_path / "case"
    case.mkdir()
    shutil.copy(CHARMM / "system.psf", case / "system.psf")
    shutil.copy(CHARMM / "system.pdb", case / "system.coor")
    data = _run_results(case, tmp_path / "run")
    assert _strategy(data) == "charmm_psf_coor"
