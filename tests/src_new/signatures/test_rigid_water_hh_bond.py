"""Rigid water models carry an H-H "bond" (AMBER TIP3P/SPC, CHARMM TIP3):
it must not reach chemistry perception (run 575c8fe7: water read as the
ring [H]1[H]O1, no database water matched)."""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

pytest.importorskip("MDAnalysis")
from MDAnalysis import Universe
from MDAnalysis.core.topologyattrs import Resnums

from src_new.config.loader import SignaturesConfig
from src_new.signatures.generators._perceive_cache import _intra_bond_pairs, clear_cache
from src_new.signatures.generators.inchi import InchiKeyGenerator
from src_new.signatures.generators.skeleton_fp import SkeletonFingerprintGenerator
from src_new.signatures.generators.smiles import SimpleSmilesGenerator
from tests.src_new.signatures.test_skeleton_fp_generator import _make_facade

WATER_XYZ = [[0.0, 0.0, 0.0], [0.9572, 0.0, 0.0], [-0.24, 0.927, 0.0]]


def _water(with_hh: bool):
    u = Universe.empty(3, n_residues=1, n_segments=1, trajectory=True)
    u.add_TopologyAttr("names", ["O", "H1", "H2"])
    u.add_TopologyAttr("resnames", ["WAT"])
    u.add_TopologyAttr(Resnums([1]))
    u.add_TopologyAttr("segids", ["W"])
    u.add_TopologyAttr("elements", ["O", "H", "H"])
    u.add_TopologyAttr("masses", [15.999, 1.008, 1.008])
    u.add_TopologyAttr("bonds", [(0, 1), (0, 2)] + ([(1, 2)] if with_hh else []))
    u.load_new(np.array(WATER_XYZ, dtype=np.float32), format="memory")
    return u.atoms


def _signatures(frag):
    clear_cache()
    cfg, inst, facade = SignaturesConfig(), MagicMock(), _make_facade()
    return {g.name: g.generate(inst, frag, facade)
            for g in (SimpleSmilesGenerator(cfg), InchiKeyGenerator(cfg), SkeletonFingerprintGenerator(cfg))}


def test_hh_bond_is_dropped_from_water():
    assert sorted(_intra_bond_pairs(_water(with_hh=True))) == [(0, 1), (0, 2)]


def test_rigid_water_is_perceived_as_water():
    rigid, flexible = _signatures(_water(True)), _signatures(_water(False))
    assert rigid == flexible
    assert rigid["inchi_key"] == "XLYOFNOQVPJJNP-UHFFFAOYSA-N"  # water
    assert "1" not in rigid["smiles"]  # no ring


def test_dihydrogen_keeps_its_bond():
    u = Universe.empty(2, n_residues=1, n_segments=1, trajectory=True)
    u.add_TopologyAttr("elements", ["H", "H"])
    u.add_TopologyAttr("bonds", [(0, 1)])
    assert _intra_bond_pairs(u.atoms) == [(0, 1)]
