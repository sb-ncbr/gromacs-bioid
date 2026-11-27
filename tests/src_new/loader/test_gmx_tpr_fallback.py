"""dm1 audit (L1): a .tpr MDAnalysis cannot read (16 dm1 deposits:
load_exception / unsupported version) is converted by GROMACS itself
(gmx editconf -conect) and loaded as PDB with its topology bonds."""
from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

pytest.importorskip("MDAnalysis")

from src_new.loader import strategies  # noqa: E402
from tests.src_new.loader.test_chainless_topology_w31 import _run_results  # noqa: E402

PDB = Path(__file__).resolve().parents[2] / "data" / "charmm_psf_pdb" / "system.pdb"


def _fake_gmx(tmp_path: Path, ok: bool = True) -> Path:
    """A stand-in `gmx` that writes the fixture PDB to the -o path."""
    script = tmp_path / "gmx"
    body = (f"import shutil, sys\nargs = sys.argv\nout = args[args.index('-o') + 1]\n"
            f"shutil.copy({str(PDB)!r}, out)\n") if ok else "import sys\nsys.stderr.write('Fatal error: cannot read tpr version 200')\nsys.exit(1)\n"
    script.write_text(f"#!{sys.executable}\n{body}")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def _case(tmp_path: Path) -> Path:
    case = tmp_path / "case"
    case.mkdir()
    (case / "topol.tpr").write_bytes(b"\x00\x00\x00\x0dnot a real tpr" * 64)
    return case


def _strategy(data: dict) -> str | None:
    ok = [a for a in (data.get("loading") or {}).get("attempts") or [] if a.get("status") == "success"]
    return ok[-1]["strategy"] if ok else None


def test_unreadable_tpr_loads_through_gmx(tmp_path, monkeypatch):
    monkeypatch.setattr(strategies, "_GMX", str(_fake_gmx(tmp_path)))
    data = _run_results(_case(tmp_path), tmp_path / "run", input_kind="gromacs")
    assert _strategy(data) == "gromacs_tpr_gmx"
    assert (data.get("fragments") or {}).get("segments")


def test_gmx_failure_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(strategies, "_GMX", str(_fake_gmx(tmp_path, ok=False)))
    with pytest.raises(strategies._GateFailure, match="cannot read tpr version"):
        strategies._tpr_to_pdb_with_gmx(_case(tmp_path) / "topol.tpr")
