"""LoadStrategy.PDB: trajectory-frame sourcing + safe average fallback."""

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from pathlib import Path

import pytest
mda = pytest.importorskip("MDAnalysis")

from src_new.loader.strategies import LoadStrategy, load_with_strategy, validate_for_strategy
from src_new.input.discovery import discover_input_kind, inspect_directory
from src_new.input.models import InputKind
from src_new.config.loader import RunConfig


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _mini_pdb(p: Path) -> None:
    lines = [
        "ATOM      1  C1  LIG A   1      10.000  10.000  10.000  1.00  0.00           C\n",
        "ATOM      2  C2  LIG A   1      11.500  10.000  10.000  1.00  0.00           C\n",
        "ATOM      3  O1  LIG A   1      12.500  10.500  10.000  1.00  0.00           O\n",
        "TER\nEND\n",
    ]
    p.write_text("".join(lines))


def _mini_xtc(p: Path, pdb: Path) -> None:
    # write a tiny 2-frame xtc from the same universe
    import MDAnalysis as mda
    import numpy as np
    u = mda.Universe(str(pdb))
    with mda.Writer(str(p), u.atoms.n_atoms) as w:
        for dx in (0.0, 5.0):
            u.atoms.positions = np.array([[10.0 + dx, 10.0, 10.0],
                                          [11.5 + dx, 10.0, 10.0],
                                          [12.5 + dx, 10.5, 10.0]], dtype="float32")
            w.write(u.atoms)


def test_pdb_strategy_loads_trajectory_frame0(tmp_path, monkeypatch):
    pdb = tmp_path / "average.pdb"; _mini_pdb(pdb)
    xtc = tmp_path / "trajectory.xtc"; _mini_xtc(xtc, pdb)
    bundle = inspect_directory(tmp_path)
    dec = type("D", (), {})()
    v = validate_for_strategy(bundle, LoadStrategy.PDB)
    assert "pdb" in v.selected_files and "xtc" in v.selected_files
    monkeypatch.setenv("LOADER_STRUCTURE_SOURCE", "trajectory")
    cfg = RunConfig()
    u = load_with_strategy(LoadStrategy.PDB, v.selected_files, cfg)
    # instantaneous frame (dx=0): coordinate x of first atom == 10.0, not averaged (12.5)
    import numpy as np
    assert abs(float(u.atoms.positions[0][0]) - 10.0) < 0.5
    assert len(u.trajectory) == 2


def test_average_only_still_works(tmp_path):
    pdb = tmp_path / "average.pdb"; _mini_pdb(pdb)
    bundle = inspect_directory(tmp_path)
    v = validate_for_strategy(bundle, LoadStrategy.PDB)
    assert "xtc" not in v.selected_files
    cfg = RunConfig()
    u = load_with_strategy(LoadStrategy.PDB, v.selected_files, cfg)
    assert u.atoms.n_atoms == 3


def test_env_override_returns_average_behavior(tmp_path, monkeypatch):
    pdb = tmp_path / "average.pdb"; _mini_pdb(pdb)
    xtc = tmp_path / "trajectory.xtc"; _mini_xtc(xtc, pdb)
    bundle = inspect_directory(tmp_path)
    v = validate_for_strategy(bundle, LoadStrategy.PDB)
    monkeypatch.setenv("LOADER_STRUCTURE_SOURCE", "average")
    cfg = RunConfig()
    u = load_with_strategy(LoadStrategy.PDB, v.selected_files, cfg)
    # in_memory of pdb only: no trajectory frames present
    assert len(u.trajectory) == 1
