"""c13 S6: resolver temp files must never reach the input directory, and the
ones interrupted runs already left there must not become the loaded system.

Fleet evidence (b15, 2026-11-04): entry 2623's input dir held MDposit's
average.pdb + trajectory.xtc + a stray tmpiu6dt969.pdb (29-atom ligand query
written by a c13 run). _rank_pdb_candidates ranks any non-"average" stem
first, so the stray became the system (29 atoms instead of 4,675) and the
SARS-CoV-2 protein GT vanished; 8 of the 397 sample entries were affected.
"""

from __future__ import annotations

from pathlib import Path

from src_new.identification.base import safe_tmp_dir
from src_new.input.discovery import (
    discover_input_kind, inspect_directory, select_best_file_combination)
from src_new.loader.strategies import LoadStrategy, validate_for_strategy

_PDB = "ATOM      1  CA  ALA A   1       0.000   0.000   0.000  1.00  0.00           C\nEND\n"


def _mdposit_dir(tmp_path: Path, *strays: str) -> Path:
    d = tmp_path / "input"
    d.mkdir()
    (d / "average.pdb").write_text(_PDB)
    for name in strays:
        (d / name).write_text(_PDB)
    return d


def test_stray_temp_files_are_not_input(tmp_path):
    d = _mdposit_dir(tmp_path, "tmpiu6dt969.pdb", "tmphdj1ccfj.json", "tmp_18iu000.cif")
    bundle = inspect_directory(d)
    assert [f.path.name for f in bundle.files] == ["average.pdb"]
    decision = select_best_file_combination(bundle)
    assert [p.name for p in decision.topology_files] == ["average.pdb"]
    validation = validate_for_strategy(bundle, LoadStrategy.PDB)
    assert validation.selected_files["pdb"].name == "average.pdb"
    assert "multiple_pdb_files" not in validation.warnings


def test_only_mkstemp_names_are_ignored(tmp_path):
    """User files that merely start with 'tmp' stay input."""
    d = _mdposit_dir(tmp_path, "tmp_model.pdb", "tmpfile.pdb")
    names = sorted(f.path.name for f in inspect_directory(d).files)
    assert names == ["average.pdb", "tmp_model.pdb", "tmpfile.pdb"]


def test_stray_alone_is_not_an_input_kind(tmp_path):
    d = tmp_path / "input"
    d.mkdir()
    (d / "tmpabcdefgh.pdb").write_text(_PDB)
    assert discover_input_kind(d) is None


def test_resolver_temp_dir_is_never_the_input_dir(tmp_path):
    d = _mdposit_dir(tmp_path)
    out = safe_tmp_dir(str(d))
    assert Path(out) != d and d not in Path(out).parents
    assert Path(out).is_dir()
