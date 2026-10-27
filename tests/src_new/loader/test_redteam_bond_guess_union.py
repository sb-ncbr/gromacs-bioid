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
    Elements,
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


class TestHydrogenPruning:
    """wave-2 item 6b: at most one bond per guessed hydrogen (shortest)."""

    def _nho_universe(self, h_o_dist: float):
        # cetirizine N-H...O geometry: N-(1.02)-H-(h_o_dist)-O collinear
        top = Topology(3, 1, 1, attrs=None)
        u = Universe(top)
        u.add_TopologyAttr(Atomnames(["N1", "H1", "O1"]))
        u.add_TopologyAttr(Elements(["N", "H", "O"]))
        u.add_TopologyAttr(Masses([14.007, 1.008, 15.999]))
        u.add_TopologyAttr(Resnames(["LIG"]))
        u.add_TopologyAttr(Resids([1]))
        u.add_TopologyAttr(Segids(["S"]))
        pos = np.array([[[0.0, 0, 0], [1.02, 0, 0], [1.02 + h_o_dist, 0, 0]]],
                       dtype=np.float32)
        u.load_new(pos, format="memory")
        return u

    def test_multi_bonded_hydrogen_keeps_only_shortest(self):
        # H-O = 1.40 A: within fudge of both N and O -> guesser bonds H to
        # BOTH donors; prune must keep only N-H (1.02 < 1.40).
        u = self._nho_universe(1.40)
        repair = TopologyRepair(u, RunConfig())
        repair.guess_bonds()
        found = {tuple(sorted(b)) for b in u.atoms.bonds.indices}
        assert (0, 1) in found      # N-H survives (shortest)
        assert (1, 2) not in found  # H...O contact pruned
        h_bonds = [b for b in found if 1 in b]
        assert len(h_bonds) == 1

    def test_single_bonded_hydrogen_untouched(self):
        # H-O = 2.20 A: outside fudge -> H bonds only to N; prune is a no-op
        u = self._nho_universe(2.20)
        repair = TopologyRepair(u, RunConfig())
        repair.guess_bonds()
        found = {tuple(sorted(b)) for b in u.atoms.bonds.indices}
        assert found == {(0, 1)}


def _water_pair_universe(o_o_dist: float):
    """bughunt BH-020: two HOH residues whose O atoms sit o_o_dist apart."""
    import MDAnalysis as mda
    u = mda.Universe.empty(4, n_residues=2, n_segments=1,
                           atom_resindex=[0, 0, 1, 1], trajectory=True)
    u.add_TopologyAttr("names", ["O", "H", "O", "H"])
    u.add_TopologyAttr("elements", ["O", "H", "O", "H"])
    u.add_TopologyAttr("masses", [15.999, 1.008, 15.999, 1.008])
    u.add_TopologyAttr("resnames", ["HOH", "HOH"])
    u.add_TopologyAttr("resids", [1, 2])
    u.add_TopologyAttr("segids", ["S"])
    pos = np.array([[[0, 0, 0], [0.9, 0, 0],
                     [o_o_dist, 0, 0], [o_o_dist + 0.9, 0, 0]]],
                   dtype=np.float32)
    u.load_new(pos, format="memory")
    return u


class TestWaterSolventIsolation:
    """bughunt BH-020: guessed solvent-solvent bonds make O2 (PubChem 977
    at 84 in P06/S31). Guessed bonds between different water residues are
    dropped; intra-water O-H bonds survive."""

    def test_close_crystal_waters_stay_separate(self):
        u = _water_pair_universe(1.4)
        repair = TopologyRepair(u, RunConfig())
        repair.guess_bonds()
        found = {tuple(sorted(b)) for b in u.atoms.bonds.indices}
        assert (0, 2) not in found        # no inter-water O-O bond
        assert (0, 1) in found           # intra-water O-H kept
        assert (2, 3) in found

    def test_far_waters_unchanged(self):
        u = _water_pair_universe(4.0)
        repair = TopologyRepair(u, RunConfig())
        repair.guess_bonds()
        found = {tuple(sorted(b)) for b in u.atoms.bonds.indices}
        assert found == {(0, 1), (2, 3)}
