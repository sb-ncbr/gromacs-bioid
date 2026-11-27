"""dm1 audit (L3/L4/L5): a topology with another engine's trajectory loads
natively (dm1 rewrote frame 0 outside BioID: plan v8), NAMD binary .coor
pairs with its .psf, and with several systems in one deposit the topology /
trajectory pair whose atom counts agree is used, not the alphabetically
first (BrafDimer.prmtop + BrafMonomer.nc, Cx46.psf + Cx50.dcd)."""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

mda = pytest.importorskip("MDAnalysis")

from tests.src_new.loader.test_chainless_topology_w31 import _run_results  # noqa: E402

DATA = Path(__file__).resolve().parents[2] / "data" / "charmm_psf_pdb"


def _strategy(data: dict) -> str | None:
    att = (data.get("loading") or {}).get("attempts") or []
    ok = [a for a in att if a.get("status") == "success"]
    return ok[-1]["strategy"] if ok else None


def _case(tmp_path: Path, suffix: str, fmt: str | None = None) -> Path:
    case = tmp_path / "case"
    case.mkdir()
    shutil.copy(DATA / "system.psf", case / "system.psf")
    u = mda.Universe(str(DATA / "system.psf"), str(DATA / "system.pdb"))
    with mda.Writer(str(case / f"system{suffix}"), u.atoms.n_atoms, **({"format": fmt} if fmt else {})) as w:
        w.write(u.atoms)
    return case


@pytest.mark.parametrize("suffix,fmt,strategy", [
    (".xtc", None, "charmm_psf_xtc"),
    (".trr", None, "charmm_psf_trr"),
    (".coor", "NAMDBIN", "charmm_psf_coor"),
])
def test_psf_with_other_engine_coordinates(tmp_path, suffix, fmt, strategy):
    data = _run_results(_case(tmp_path, suffix, fmt), tmp_path / "run")
    assert _strategy(data) == strategy
    assert (data.get("fragments") or {}).get("segments")


def _half_psf(case: Path, name: str) -> None:
    u = mda.Universe(str(DATA / "system.psf"), str(DATA / "system.pdb"))
    _write_psf(u.select_atoms(f"index 0:{u.atoms.n_atoms // 2}"), case / name)


def _used(data: dict) -> list:
    return [a for a in data["loading"]["attempts"] if a.get("status") == "success"][-1]["used_files"]


def test_closest_named_pair_first(tmp_path):
    case = _case(tmp_path, ".dcd")           # system.psf + system.dcd
    _half_psf(case, "a_other.psf")           # sorts first, other system
    data = _run_results(case, tmp_path / "run")
    assert _strategy(data) == "charmm_psf_dcd"
    assert any(p.endswith("system.psf") for p in _used(data))


def test_atom_counts_decide_when_names_tie(tmp_path):
    case = _case(tmp_path, ".dcd")
    (case / "system.psf").rename(case / "sys_b.psf")
    (case / "system.dcd").rename(case / "sys.dcd")
    _half_psf(case, "sys_a.psf")             # same stem affinity, wrong count
    data = _run_results(case, tmp_path / "run")
    assert _strategy(data) == "charmm_psf_dcd"
    assert any(p.endswith("sys_b.psf") for p in _used(data)), _used(data)


def _write_psf(atoms, path: Path) -> None:
    """Minimal X-PLOR PSF of an atom selection (no bonds), enough for a
    different atom count."""
    lines = ["PSF", "", "       1 !NTITLE", " REMARKS test", "", f"{atoms.n_atoms:8d} !NATOM"]
    for i, a in enumerate(atoms, 1):
        lines.append(f"{i:8d} {a.segid or 'A':<4s} {a.resid:<4d} {a.resname:<4s} {a.name:<4s} "
                     f"{a.type:<4s} {0.0:10.6f} {a.mass:13.4f}           0")
    lines += ["", "       0 !NBOND: bonds", ""]
    path.write_text("\n".join(lines) + "\n")
