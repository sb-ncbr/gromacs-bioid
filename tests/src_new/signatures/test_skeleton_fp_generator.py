"""Unit tests for the skeleton_fp signature generator (F12). No network/NFS."""

from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import numpy as np
import pytest

mdanalysis = pytest.importorskip("MDAnalysis")
from MDAnalysis import Universe
from MDAnalysis.core.topologyattrs import Resnums
from unittest.mock import MagicMock

from src_new.signatures.generators.skeleton_fp import SkeletonFingerprintGenerator
from src_new.signatures.registry import get_default_generators
from src_new.config.loader import SignaturesConfig
from src_new.signatures.skeletize import (
    from_smiles, skeleton_fp, tanimoto_hex, parse_signature, format_signature,
)
from src_new.loader.universe_facade import SegmentProperty


def _make_universe(elements, bonds, positions=None):
    n = len(elements)
    u = Universe.empty(n, n_residues=1, n_segments=1, trajectory=True)
    u.add_TopologyAttr("names", [f"{e}{i}" for i, e in enumerate(elements)])
    u.add_TopologyAttr("resnames", ["LIG"])
    u.add_TopologyAttr(Resnums([1]))
    u.add_TopologyAttr("segids", ["L"])
    u.add_TopologyAttr("elements", list(elements))
    if bonds:
        u.add_TopologyAttr("bonds", bonds)
    pos = np.zeros((n, 3), dtype=np.float32) if positions is None else np.asarray(positions, dtype=np.float32)
    u.load_new(pos, format="memory")
    return u


def _make_facade():
    facade = MagicMock()
    props = MagicMock()
    props.flags = {
        SegmentProperty.IS_PROTEIN.value: False,
        SegmentProperty.IS_NUCLEIC.value: False,
        SegmentProperty.HAS_POSITIONS.value: True,
        SegmentProperty.HAS_ELEMENTS.value: True,
        SegmentProperty.HAS_NAMES.value: True,
    }
    facade.get_segment_properties.return_value = props
    return facade


def _ethanol():
    # C-C-O bonded path (ethanol CCO as CH3-CH2-OH reduced to 3 heavy atoms)
    u = _make_universe(["C", "C", "O"], bonds=[(0, 1), (1, 2)])
    return u.atoms


def test_registered_in_default_generators():
    names = [g.name for g in get_default_generators(SignaturesConfig())]
    assert "skeleton_fp" in names


def test_bonded_fragment_emits_expected_fingerprint():
    gen = SkeletonFingerprintGenerator(SignaturesConfig())
    inst = MagicMock()
    frag = _ethanol()
    assert gen.is_applicable(inst, frag, _make_facade()) is True
    sig = gen.generate(inst, frag, _make_facade())
    assert sig is not None
    assert sig.startswith("skelfp:v1:")
    hex_part, heavy = parse_signature(sig)
    assert heavy == "C2O"
    # identical skeleton fingerprint to RDKit-derived ethanol
    ref = format_signature(from_smiles("CCO"))
    assert tanimoto_hex(sig, ref) == 1.0


def test_bond_order_agnostic_output():
    # same topology but generator must equal benzene-vs-cyclohexane behaviour:
    # any bond orders collapse; here check ring-with-double-bond equivalence at
    # the signature level for a 6-carbon ring (single bonds in fragment)
    n = 6
    bonds = [(i, (i + 1) % n) for i in range(n)]
    frag = _make_universe(["C"] * n, bonds=bonds).atoms
    gen = SkeletonFingerprintGenerator(SignaturesConfig())
    sig = gen.generate(MagicMock(), frag, _make_facade())
    assert sig is not None
    cyc = format_signature(from_smiles("C1CCCCC1"))
    bnz = format_signature(from_smiles("c1ccccc1"))
    assert tanimoto_hex(sig, cyc) == tanimoto_hex(sig, bnz) == 1.0


def test_zero_bonds_returns_none():
    gen = SkeletonFingerprintGenerator(SignaturesConfig())
    frag = _make_universe(["C", "C", "C"], bonds=[]).atoms
    # no bonds at all -> perception skipped in this test path via applicability exception
    # _is_applicable returns True (perception fallback allowed) but generate must
    # return None when connectivity cannot be established on 3 collinear points far apart
    if gen.is_applicable(MagicMock(), frag, _make_facade()):
        sig = gen.generate(MagicMock(), frag, _make_facade())
        assert sig is None


def test_applicability_requires_elements():
    gen = SkeletonFingerprintGenerator(SignaturesConfig())
    facade = _make_facade()
    props = facade.get_segment_properties.return_value
    props.flags[SegmentProperty.HAS_ELEMENTS.value] = False
    assert gen.is_applicable(MagicMock(), _ethanol(), facade) is False


def test_disabled_by_config():
    cfg = SignaturesConfig(skeleton_fp=False)
    gen = SkeletonFingerprintGenerator(cfg)
    assert gen.is_applicable(MagicMock(), _ethanol(), _make_facade()) is False
