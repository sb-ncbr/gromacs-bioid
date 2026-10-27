"""Wave-2 item 6a (GitHub #3): bond guessing must fire when bonds are
INSUFFICIENT, not only when absent, and must UNION with authored CONECT.

Pre-change: `_has_bonds()` gate meant a partial CONECT set (1XJR class)
received no coordinate guessing at all; and if guessing ever ran, the
MDAnalysis path would have replaced authored bonds.
"""

import numpy as np
from MDAnalysis import Universe
from MDAnalysis.core.topology import Topology
from MDAnalysis.core.topologyattrs import (
    Atomnames,
    Bonds,
    Masses,
    Resids,
    Resnames,
    Segids,
)

from src_new.config.loader import RunConfig
from src_new.loader.repair import TopologyRepair, bonds_insufficient


def _chain_universe(n_atoms: int, authored_bonds, spacing: float = 1.54):
    top = Topology(n_atoms, 1, 1, attrs=None)
    u = Universe(top)
    u.add_TopologyAttr(Atomnames(["C"] * n_atoms))
    u.add_TopologyAttr(Masses([12.011] * n_atoms))
    u.add_TopologyAttr(Resnames(["LIG"]))
    u.add_TopologyAttr(Resids([1]))
    u.add_TopologyAttr(Segids(["S"]))
    if authored_bonds:
        u.add_TopologyAttr(Bonds(authored_bonds))
    u.load_new(np.array([[[i * spacing, 0.0, 0.0] for i in range(n_atoms)]],
                        dtype=np.float32), format="memory")
    return u


class TestPartialConectUnion:
    def test_partial_conect_gets_union_guessed_bonds(self):
        # 8-atom chain, only bond (0,1) authored: 1 < 8*0.25 -> insufficient
        u = _chain_universe(8, [(0, 1)])
        repair = TopologyRepair(u, RunConfig())
        n = repair.guess_bonds()
        found = {tuple(sorted(b)) for b in u.atoms.bonds.indices}
        # authored bond preserved AND the guessed chain added (7 bonds total)
        assert (0, 1) in found
        assert (1, 2) in found
        assert n >= 7
        assert n == len(u.atoms.bonds)

    def test_full_conect_untouched(self):
        # 7 authored bonds in 8 atoms: sufficient -> no guessing, no change
        u = _chain_universe(8, [(i, i + 1) for i in range(7)])
        before = len(u.atoms.bonds)
        repair = TopologyRepair(u, RunConfig())
        n = repair.guess_bonds()
        assert n == 0
        assert len(u.atoms.bonds) == before

    def test_no_bonds_still_guessed(self):
        u = _chain_universe(8, None)
        repair = TopologyRepair(u, RunConfig())
        n = repair.guess_bonds()
        assert n >= 7

    def test_bonds_insufficient_predicate(self):
        assert bonds_insufficient(_chain_universe(8, None)) is True
        assert bonds_insufficient(_chain_universe(8, [(0, 1)])) is True
        assert bonds_insufficient(_chain_universe(8, [(i, i+1) for i in range(7)])) is False

    def test_union_never_drops_authored_bond(self):
        # 8 atoms with ONE authored bond that the coordinate guesser would
        # NOT find (4.5 A = way outside carbon vdw ranges): insufficient
        # coverage (1 < 8*0.25) triggers guessing; the authored bond must
        # survive the union.
        u = _chain_universe(8, [(0, 1)])
        pos = np.zeros((1, 8, 3), dtype=np.float32)
        pos[0, 0] = [0, 0, 0]
        pos[0, 1] = [4.5, 0, 0]
        for i in range(2, 8):
            pos[0, i] = [4.5 + (i - 1) * 1.54, 0.0, 0.0]
        u.atoms.positions = pos[0]
        repair = TopologyRepair(u, RunConfig())
        repair.guess_bonds()
        found = {tuple(sorted(b)) for b in u.atoms.bonds.indices}
        assert (0, 1) in found  # authored long bond survives
        assert (1, 2) in found  # and the real chain bonds got guessed
