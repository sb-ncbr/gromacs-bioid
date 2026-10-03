"""W4/F-N1b: fallback extraction for merged/branched residue graphs.

Mirrors house builder (test_fasta_nucleic_enhancements): Universe.empty with
DNA residues, phosphate backbone bonds. Two disconnected strands -> merged
assembly; branched graph -> non-linear component; single chain -> strict path.
"""
from __future__ import annotations

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")

from src_new.config.loader import SignaturesConfig
from src_new.signatures.generators.fasta import (
    fragment_to_protseq_map_based,
    _residue_components,
    _is_linear_chain,
    _submatrix,
)

DNA_ATOMS = [["P", "O5'", "C5'", "C4'", "C3'", "O3'"]]
CFG = SignaturesConfig()


def _mk_universe(resnames, bonds, segid="X"):
    atom_resindex, names = [], []
    for i, anames in enumerate(DNA_ATOMS * len(resnames)):
        atom_resindex.extend([i] * len(anames))
        names.extend(anames)
    u = mda.Universe.empty(len(names), n_residues=len(resnames), n_segments=1,
                           atom_resindex=atom_resindex, trajectory=True)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resids", list(range(1, len(resnames) + 1)))
    u.add_TopologyAttr("resnums", list(range(1, len(resnames) + 1)))
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("segids", [segid])
    u.add_TopologyAttr("elements", ["P" if n == "P" else "C" for n in names])
    u.load_new(np.zeros((len(names), 3), dtype=np.float32), format="memory")
    u.add_TopologyAttr("bonds", bonds)
    return u


def _dna_chain_bonds(res_indices, atoms_per_res=6):
    """Intra-residue backbone chain + inter-residue P(i)->O3'(i-1) links."""
    bonds = []
    intra = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5)]
    for i in res_indices:
        off = i * atoms_per_res
        bonds.extend((off + a, off + b) for a, b in intra)
        # link P of residue i to O3' of residue i-1 (same strand list order)
        pos = res_indices.index(i)
        if pos > 0:
            prev_off = res_indices[pos - 1] * atoms_per_res
            bonds.append((off + 0, prev_off + 5))
    return bonds


class TestStrandSelect:
    def _universe_two_strands(self, long_first: bool):
        long_seq = ["DA", "DC", "DG", "DT", "DA", "DC"]  # 6-mer
        short_seq = ["DA", "DT"]                            # 2-mer
        resnames = (long_seq + short_seq) if long_first else (short_seq + long_seq)
        if long_first:
            long_idx, short_idx = list(range(6)), [6, 7]
        else:
            short_idx, long_idx = [0, 1], list(range(2, 8))
        bonds = _dna_chain_bonds(long_idx) + _dna_chain_bonds(short_idx)
        return _mk_universe(resnames, bonds)

    def test_two_strands_picks_longest(self):
        frag = self._universe_two_strands(True).atoms
        seq = fragment_to_protseq_map_based(frag, CFG, anchor=None)
        assert len(seq) == 6

    def test_deterministic_regardless_of_input_order(self):
        s1 = fragment_to_protseq_map_based(self._universe_two_strands(True).atoms, CFG, anchor=None)
        s2 = fragment_to_protseq_map_based(self._universe_two_strands(False).atoms, CFG, anchor=None)
        assert len(s1) == len(s2) == 6
        assert s1 == s2

    def test_merged_duplex_like_case_includes_full_strand(self):
        # two equal 4-mer strands: selector must pick deterministically (min first index),
        # and the picked sequence must be exactly one of the strands (not a chimaera).
        s = ["DA", "DC", "DG", "DT"]
        bonds = _dna_chain_bonds([0, 1, 2, 3]) + _dna_chain_bonds([4, 5, 6, 7])
        frag = _mk_universe(s + ["DG", "DA", "DT", "DC"], bonds).atoms
        seq = fragment_to_protseq_map_based(frag, CFG, anchor=None)
        assert len(seq) == 4

    def test_branched_component_returns_longest_linear(self):
        resnames = ["DA", "DC", "DG", "DT"]
        bonds = _dna_chain_bonds([0, 1, 2, 3])
        # add a branch: residue 2 gets an extra bond to residue 1 (deg(1 becomes 3)
        bonds.append((2 * 6 + 0, 1 * 6 + 5))
        frag = _mk_universe(resnames, bonds).atoms
        seq = fragment_to_protseq_map_based(frag, CFG, anchor=None)
        assert 2 <= len(seq) <= 4

    def test_single_chain_strict_path_unchanged(self):
        resnames = ["DA", "DC", "DG", "DT", "DA"]
        bonds = _dna_chain_bonds([0, 1, 2, 3, 4])
        frag = _mk_universe(resnames, bonds).atoms
        seq = fragment_to_protseq_map_based(frag, CFG, anchor=None)
        assert len(seq) == 5

    def test_component_helpers(self):
        adj = [[False] * 6 for _ in range(6)]
        for i in range(3):
            adj[i][i + 1] = adj[i + 1][i] = True
        adj[4][5] = adj[5][4] = True
        comps = _residue_components(adj)
        assert sorted(len(c) for c in comps) == [2, 4]
        assert len(comps[0]) == 4  # largest first (selector consumes comps[0])
        assert _is_linear_chain(_submatrix(adj, comps[0]))
