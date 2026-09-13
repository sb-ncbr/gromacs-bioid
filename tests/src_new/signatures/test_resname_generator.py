"""ResnameGenerator tests (name emitter for CCD resolution)."""

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from unittest.mock import MagicMock

import pytest

hy = pytest.importorskip("MDAnalysis")
import numpy as np
from MDAnalysis import Universe
from MDAnalysis.core.topologyattrs import Resnums, Resnames

from src_new.signatures.generators.resname import ResnameGenerator
from src_new.signatures.registry import get_default_generators
from src_new.config.loader import SignaturesConfig
from src_new.molecules.instances import MoleculeInstance, MoleculeType


def _frag(elements, resnames):
    n = len(elements)
    uniq = list(dict.fromkeys(resnames))
    resindex = [uniq.index(r) for r in resnames]
    u = Universe.empty(n, n_residues=len(uniq), n_segments=1, atom_resindex=resindex, trajectory=True)
    u.add_TopologyAttr("names", [f"{e}{i}" for i, e in enumerate(elements)])
    u.add_TopologyAttr(Resnames(uniq))
    u.add_TopologyAttr(Resnums(list(range(1, len(uniq) + 1))))
    u.add_TopologyAttr("elements", list(elements))
    u.load_new(np.zeros((n, 3), dtype=np.float32), format="memory")
    return u.atoms


def _inst(**kw):
    return MoleculeInstance(instance_id="m0", **kw)


def test_single_resname_emitted():
    g = ResnameGenerator(SignaturesConfig())
    inst = _inst(resnames=["CHL1"], molecule_type=MoleculeType.LIPID)
    frag = _frag(["C", "O"], ["CHL1", "CHL1"])
    assert g.is_applicable(inst, frag, MagicMock()) is True
    assert g.generate(inst, frag, MagicMock()) == "CHL1"


def test_multi_resname_returns_none():
    g = ResnameGenerator(SignaturesConfig())
    inst = _inst(resnames=["ALA", "CHL1"])
    frag = _frag(["C", "C"], ["ALA", "CHL1"])
    assert g.is_applicable(inst, frag, MagicMock()) is False
    assert g.generate(inst, frag, MagicMock()) is None


def test_registered():
    assert "resname" in [g.name for g in get_default_generators(SignaturesConfig())]


def test_fallback_to_fragment_resnames():
    g = ResnameGenerator(SignaturesConfig())
    inst = _inst(resnames=[])
    frag = _frag(["C", "O"], ["AZL", "AZL"])
    assert g.generate(inst, frag, MagicMock()) == "AZL"
