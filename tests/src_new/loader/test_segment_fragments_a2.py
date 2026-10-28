"""W3 A2 (BH-037): per-segment components (F1) + broken-chain union (F2).

Production evidence (re-test g0a2091-1028): authored CONECT bonds cross
deduplicated segids (4HHB HIS-FE(HEM), 1AON ASP-MG, 6M0J ASN-NAG /
inter-chain SG-SG). MDAnalysis fragments spill across the shared bond
into the OTHER segid, so the whole cross-segid piece got dropped from
both segments; leftovers (a stray atom, a lone P of PO4) became the
"representative" and the real species vanished from picks, CSVs and
identification. F1 computes connected components using ONLY intra-segment
bonds; F2 merges polymer pieces of ONE broken chain (no (resid, icode)
repeats) into a union with molecule_count 1.

Prototypes: bioid_bughunt/logs/retest_g0a2091/frag_scripts/uf_patched2.py
"""

from __future__ import annotations

import numpy as np
import pytest
from unittest.mock import MagicMock

pytestmark = pytest.mark.skipif(
    __import__("importlib").util.find_spec("MDAnalysis") is None,
    reason="needs MDAnalysis",
)


def _mk_universe(atom_resindex, residue_segindex, names, resids, resnames,
                 segids, bonds):
    from MDAnalysis import Universe
    u = Universe.empty(
        len(atom_resindex),
        n_residues=len(resids),
        n_segments=len(segids),
        atom_resindex=atom_resindex,
        residue_segindex=residue_segindex,
        trajectory=True,
    )
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resids", resids)
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("segids", segids)
    u.add_TopologyAttr("elements", ["C"] * len(atom_resindex))
    if bonds:
        u.add_TopologyAttr("bonds", list(bonds))
    u.load_new(np.zeros((len(atom_resindex), 3), dtype=np.float32), format="memory")
    return u


def _facade(u):
    from src_new.loader.universe_facade import LoadedUniverse
    rep = MagicMock()
    rep.to_dict.return_value = {}
    return LoadedUniverse(
        universe=u, decision=MagicMock(), repair_report=rep,
        results=None, enhanced_nucleic_recognition=False)


def _uni_chain_ligand():
    """chain P: ALA(1)-ALA(2)-ALA(3) atoms 0-2 + stray atom 3; ligand L
    atoms 4-5; cross bond 0-4 (the LINK/metal-bond class)."""
    return _mk_universe(
        atom_resindex=[0, 1, 2, 3, 4, 4],
        residue_segindex=[0, 0, 0, 0, 1],
        names=[f"CA{i}" for i in range(6)],
        resids=[1, 2, 3, 99, 500],
        resnames=["ALA", "ALA", "ALA", "UNK", "LIG"],
        segids=["P", "L"],
        bonds=[(0, 1), (1, 2), (4, 5), (0, 4)],
    )


class TestCrossSegmentBonds:
    def test_cross_bond_does_not_drop_fragments(self):
        """P chain + stray unbonded atom + ligand L with a P-L bond:
        representative(P) = the whole chain; representative(L) = the
        ligand. Pre-F1 the mixed fragment is dropped from both segments
        and the 1-atom stray becomes the representative."""
        f = _facade(_uni_chain_ligand())
        rep_p = f.get_fragment("P")
        rep_l = f.get_fragment("L")
        assert sorted(rep_p.indices.tolist()) == [0, 1, 2], rep_p.indices
        assert sorted(rep_l.indices.tolist()) == [4, 5], rep_l.indices
        props = f.get_segment_properties("P")
        assert props.atom_count_fragment == 3

    def test_hem_plus_single_atom_po4_virtual_segment(self):
        """seg H = HEM (3 atoms) + PO4 1-atom piece; HEM cross-bonded to
        chain P. Representative(H) = HEM; PO4 becomes a virtual segment."""
        u = _mk_universe(
            atom_resindex=[0, 1, 2, 2, 2, 3],
            residue_segindex=[0, 0, 1, 1],
            names=["CA0", "CA1", "FE2", "C3", "C4", "P5"],
            resids=[1, 2, 300, 301],
            resnames=["ALA", "ALA", "HEM", "PO4"],
            segids=["P", "H"],
            bonds=[(0, 1), (2, 3), (3, 4), (4, 2), (0, 2)],
        )
        f = _facade(u)
        rep_h = f.get_fragment("H")
        assert sorted(rep_h.indices.tolist()) == [2, 3, 4], rep_h.indices
        virtuals = {k: v for k, v in f.get_virtual_segments().items()} \
            if hasattr(f, "get_virtual_segments") else dict(getattr(f, "_virtual_fragments", {}))
        po4_virtuals = [k for k, v in virtuals.items()
                        if k.startswith("H__v") and 5 in set(map(int, v.indices))]
        assert po4_virtuals, f"PO4 must surface as a virtual segment, got {sorted(virtuals)}"

    def test_nag_zn_cl_virtual_and_copy_counts(self):
        """seg H = 4 NAG (2 atoms each) + ZN + CL, every NAG cross-bonded
        to the chain. ZN and CL become virtual segments; NAG copies = 4."""
        atom_resindex = [0, 1, 1, 2, 2, 3, 3, 4, 4, 5, 6]
        residue_segindex = [0, 1, 1, 1, 1, 1, 1]
        resnames = ["ALA", "NAG", "NAG", "NAG", "NAG", "ZN", "CL"]
        resids = [1, 10, 11, 12, 13, 20, 21]
        bonds = [(0,)]
        # chain atom 0 bonded to every NAG's first atom
        bonds = [(0, 1), (0, 3), (0, 5), (0, 7), (1, 2), (3, 4), (5, 6), (7, 8)]
        u = _mk_universe(atom_resindex, residue_segindex,
                         names=[f"A{i}" for i in range(11)],
                         resids=resids, resnames=resnames, segids=["P", "H"],
                         bonds=bonds)
        f = _facade(u)
        rep_h = f.get_fragment("H")
        assert sorted(set(rep_h.resnames.tolist())) == ["NAG"], rep_h.resnames
        props = f.get_segment_properties("H")
        assert props.molecule_count == 4, props.molecule_count
        virtuals = dict(getattr(f, "_virtual_fragments", {}))
        v_resnames = {tuple(sorted(set(v.resnames.tolist()))) for k, v in virtuals.items()
                      if k.startswith("H__v")}
        assert ("ZN",) in v_resnames and ("CL",) in v_resnames, v_resnames

    def test_interchain_disulfide_keeps_full_chains(self):
        """Chains P and Q joined by an S-S bond; each has a stray atom.
        Both representatives must be the FULL chain, not the stray."""
        u = _mk_universe(
            atom_resindex=[0, 1, 2, 3, 4, 5, 6, 7],
            residue_segindex=[0, 0, 0, 0, 1, 1, 1, 1],
            names=["CA0", "CA1", "SG2", "U3", "CA4", "CA5", "SG6", "U7"],
            resids=[1, 2, 3, 99, 11, 12, 13, 98],
            resnames=["ALA", "ALA", "CYS", "UNK", "ALA", "ALA", "CYS", "UNK"],
            segids=["P", "Q"],
            bonds=[(0, 1), (1, 2), (4, 5), (5, 6), (2, 6)],
        )
        f = _facade(u)
        assert sorted(f.get_fragment("P").indices.tolist()) == [0, 1, 2]
        assert sorted(f.get_fragment("Q").indices.tolist()) == [4, 5, 6]


class TestBrokenChainUnion:
    def test_broken_chain_unique_resids_union_mol1(self):
        """One chain whose guessed bonds miss two long links -> pieces
        {0-1}, {2-3}, {4-5} with UNIQUE resids: F2 union, molecule_count 1
        (pre-F2: largest piece is 2 atoms < 80%, mol = 3)."""
        u = _mk_universe(
            atom_resindex=[0, 1, 2, 3, 4, 5],
            residue_segindex=[0, 0, 0, 0, 0, 0],
            names=[f"CA{i}" for i in range(6)],
            resids=[1, 2, 3, 4, 5, 6],
            resnames=["ALA"] * 6,
            segids=["A"],
            bonds=[(0, 1), (2, 3), (4, 5)],
        )
        f = _facade(u)
        rep = f.get_fragment("A")
        props = f.get_segment_properties("A")
        assert sorted(rep.indices.tolist()) == [0, 1, 2, 3, 4, 5], rep.indices
        assert props.molecule_count == 1, props.molecule_count
        assert props.atom_count_fragment == props.atom_count_total == 6

    def test_two_copies_repeated_resids_mol2(self):
        """Two identical chains in one segid (repeated resids) are NOT a
        broken single chain: the _chain_union marker must NOT be set, and
        molecule_count stays 2 (the representative itself is the A-09
        polymer union, which is cosmetic - copies are counted on the
        intra-segment component species)."""
        u = _mk_universe(
            atom_resindex=[0, 1, 2, 3, 4, 5],
            residue_segindex=[0, 0, 0, 0, 0, 0],
            names=[f"CA{i}" for i in range(6)],
            resids=[1, 2, 3, 1, 2, 3],
            resnames=["ALA"] * 6,
            segids=["A"],
            bonds=[(0, 1), (1, 2), (3, 4), (4, 5)],
        )
        f = _facade(u)
        rep = f.get_fragment("A")
        props = f.get_segment_properties("A")
        assert "A" not in getattr(f, "_chain_union", set()), (
            "repeated resids = two copies, never a broken single chain")
        assert props.molecule_count == 2, props.molecule_count

    def test_intact_chain_small_stray_piece_union(self):
        """A chain with one small unbonded polymer piece and all-unique
        resids is ONE chain: F2 merges it (whole-segment representative,
        molecule_count 1 via the chain-union marker)."""
        u = _mk_universe(
            atom_resindex=[0, 1, 2, 3, 4, 5, 6],
            residue_segindex=[0] * 7,
            names=[f"CA{i}" for i in range(7)],
            resids=[1, 2, 3, 4, 5, 6, 7],
            resnames=["ALA"] * 7,
            segids=["A"],
            bonds=[(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)],
        )
        f = _facade(u)
        rep = f.get_fragment("A")
        props = f.get_segment_properties("A")
        assert sorted(rep.indices.tolist()) == [0, 1, 2, 3, 4, 5, 6]
        assert props.molecule_count == 1
        assert props.atom_count_fragment == props.atom_count_total == 7
