"""The whole-system export keeps molecules in their input periodic image.

PbcRepair unwraps with reference="com", which moves every molecule's
centre into the primary cell. Identification does not care, but the 3D
view did: in 3PTB the benzamidine sits at x = -1.9 A, just outside the
cell, in the trypsin S1 pocket; the export put it at +53.0 A, one cell
length (54.89 A) away from the protein (live run f15d496a, 2026-11-08).
input_image_positions undoes the whole-lattice part of the unwrap per
molecule; molecules stay whole.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import MDAnalysis as mda
import pytest

from src_new.config.loader import RunConfig
from src_new.loader.export_mmcif import input_image_positions
from src_new.loader.unwrap import PbcRepair

P04 = Path(
    "/home/tomsko/work/bat3_article_reviews/bioid_bughunt/testcases/"
    "P04_3ptb_trypsin_benzamidine/input/3PTB.pdb")


def _two_molecules(ligand_x: float, split: bool = False) -> mda.Universe:
    """A 4-atom 'protein' inside a 20 A box and a bonded 2-atom 'ligand'.

    split=True instead cuts a 2-atom molecule across the x boundary."""
    u = mda.Universe.empty(6, n_residues=2, atom_resindex=[0, 0, 0, 0, 1, 1],
                           trajectory=True)
    u.add_TopologyAttr("names", ["C1", "C2", "C3", "C4", "L1", "L2"])
    u.add_TopologyAttr("resnames", ["PRO", "LIG"])
    u.add_TopologyAttr("resids", [1, 2])
    u.add_TopologyAttr("masses", [12.0] * 6)
    u.add_TopologyAttr("bonds", [(0, 1), (1, 2), (2, 3), (4, 5)])
    pos = np.array([[1, 5, 5], [2.5, 5, 5], [4, 5, 5], [5.5, 5, 5],
                    [ligand_x, 5, 5], [ligand_x + 1.0, 5, 5]], dtype=np.float32)
    if split:  # L1 at x = 19.5, L2 wrapped to x = 0.5: bonded across the box
        pos[4] = [19.5, 9, 9]
        pos[5] = [0.5, 9, 9]
    u.load_new(pos[np.newaxis], format="memory")
    u.dimensions = [20, 20, 20, 90, 90, 90]
    return u


def _unwrap(u: mda.Universe) -> np.ndarray:
    before = u.atoms.positions.copy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        u.atoms.unwrap(compound="fragments", reference="com", inplace=True)
    return u.atoms.positions - before


def test_molecule_outside_the_cell_returns_to_its_input_image():
    u = _two_molecules(ligand_x=-1.5)
    original = u.atoms.positions.copy()
    disp = _unwrap(u)
    assert u.atoms.positions[4, 0] == pytest.approx(18.5)  # moved by the unwrap
    pos = input_image_positions(u, disp)
    assert pos is not None
    np.testing.assert_allclose(pos, original, atol=1e-4)


def test_split_molecule_stays_whole():
    u = _two_molecules(ligand_x=0, split=True)
    disp = _unwrap(u)
    moved = input_image_positions(u, disp)
    pos = u.atoms.positions if moved is None else moved
    assert np.linalg.norm(pos[4] - pos[5]) == pytest.approx(1.0, abs=1e-3)


def test_nothing_to_do_returns_none():
    u = _two_molecules(ligand_x=8.0)
    disp = _unwrap(u)
    assert input_image_positions(u, disp) is None
    assert input_image_positions(u, None) is None
    assert input_image_positions(u, np.zeros((3, 3))) is None  # wrong shape


@pytest.mark.skipif(not P04.exists(), reason="bughunt testcase P04 not available")
def test_3ptb_benzamidine_stays_in_the_pocket():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        u = mda.Universe(str(P04))
    ben = u.select_atoms("resname BEN")
    protein = u.select_atoms("protein")
    original = ben.positions.copy()
    pbc = PbcRepair(u, RunConfig())
    pbc.run()
    assert pbc.unwrap_displacement is not None
    pos = input_image_positions(u, pbc.unwrap_displacement)
    assert pos is not None
    np.testing.assert_allclose(pos[ben.indices], original, atol=1e-3)
    d = np.linalg.norm(pos[ben.indices][:, None, :] - pos[protein.indices][None, :, :], axis=2)
    assert d.min() < 4.0
