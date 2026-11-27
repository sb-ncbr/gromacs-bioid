"""dm1 audit (L9): an AMBER topology MDAnalysis refuses (CHARMM-to-AMBER
"chamber" step5_input.parm7, figshare/27176445) is read by ParmEd and loaded
with the deposit's own coordinates. Checked here on a regular prmtop, where
the ParmEd route must reproduce MDAnalysis' own load."""
from pathlib import Path

import pytest

pytest.importorskip("parmed")
pytest.importorskip("MDAnalysis")

from src_new.input.discovery import inspect_directory, select_best_file_combination
from src_new.loader.strategies import LoadStrategy, validate_for_strategy, get_fallback_strategies

CASE = Path(__file__).resolve().parents[2] / "data" / "amber_prmtop_rst7"


REAL_PRMTOP = Path(__file__).resolve().parents[2] / "fixtures" / "n1" / "1920" / "input" / "topology.prmtop"


def test_parmed_psf_matches_mdanalysis_topology():
    import MDAnalysis as mda
    from src_new.loader.strategies import _amber_topology_as_psf
    psf = mda.Universe(str(_amber_topology_as_psf(REAL_PRMTOP)))
    ref = mda.Universe(str(REAL_PRMTOP), topology_format="PRMTOP")
    assert psf.atoms.n_atoms == ref.atoms.n_atoms
    assert list(psf.atoms.names) == list(ref.atoms.names)
    assert list(psf.residues.resnames) == list(ref.residues.resnames)
    assert len(psf.bonds) == len(ref.bonds)


def test_parmed_validation_pairs_coordinates():
    bundle = inspect_directory(CASE)
    val = validate_for_strategy(bundle, LoadStrategy.AMBER_PARMED)
    assert val.ok, val.errors
    assert val.selected_files["coordinates"].suffix in (".rst7", ".inpcrd", ".restrt")


def test_parmed_is_in_the_amber_ladder():
    bundle = inspect_directory(CASE)
    ladder = get_fallback_strategies(select_best_file_combination(bundle), bundle)
    assert LoadStrategy.AMBER_PARMED in ladder
    assert ladder.index(LoadStrategy.AMBER_PARMED) > ladder.index(LoadStrategy.AMBER_PRMTOP_RST7)
