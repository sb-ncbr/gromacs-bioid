"""Red-team Batch 1.6 (sequence/format) regression tests.

  B-02: map-based FASTA builds the residue graph from ALL inter-residue
        bonds — disulfides/isopeptides add degree-3 residues, sequentiality
        verification fails, and the fallback returns truncated/reversed/
        chimeric sequences (fixture 4725: 160-aa protein -> 62-aa reversed
        fragment).
  B-03: without an N-terminal Met anchor, path direction is decided by set
        iteration order over resindices — whole chains come out reversed
        depending on residue offset in the universe.
  B-04: hand-written PDB formatters pad-but-don't-truncate: 4-char residue
        names (LYSH/CYS2/HISE/NALA) and resSeq >= 10000 shift every column
        and produce unparseable/mis-parsed Foldseek/AlphaFind/RCSB inputs.
"""
from __future__ import annotations

import MDAnalysis as mda
import pytest

from src_new.config.loader import RunConfig


_RESSEQ = ["ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "CYS", "ILE"]
_EXPECTED = "ARNDCQEGCI"


def _protein_universe(resnames, disulfide=None, offset_residues=0):
    """Bonded peptide chain N-CA-C-O per residue (+SG on CYS), optionally
    offset by leading WAT residues and one SG-SG disulfide."""
    atoms_per = []
    names = []
    resname_list = []
    for _ in range(offset_residues):
        atoms_per.append(3)
        names += ["O", "H1", "H2"]
        resname_list.append("WAT")
    for rn in resnames:
        n = 5 if rn == "CYS" else 4
        atoms_per.append(n)
        names += ["N", "CA", "C", "O"] + (["SG"] if rn == "CYS" else [])
        resname_list.append(rn)
    resindex = []
    for ri, cnt in enumerate(atoms_per):
        resindex += [ri] * cnt
    n = len(names)
    u = mda.Universe.empty(n, n_residues=len(atoms_per), n_segments=1,
                           atom_resindex=resindex, trajectory=True)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resids", list(range(1, len(atoms_per) + 1)))
    u.add_TopologyAttr("resnames", resname_list)
    u.add_TopologyAttr("segids", ["S"])
    bonds = []
    base = offset_residues * 3
    prev_c = None
    for i, rn in enumerate(resnames):
        n_i, ca_i, c_i, o_i = base, base + 1, base + 2, base + 3
        bonds += [(n_i, ca_i), (ca_i, c_i), (c_i, o_i)]
        if prev_c is not None:
            bonds.append((prev_c, n_i))  # peptide bond C(i-1)-N(i)
        prev_c = c_i
        base += 5 if rn == "CYS" else 4
    if disulfide is not None:
        # SG atom indices at the two RESIDUE POSITIONS (must be CYS there)
        sg = {}
        base = offset_residues * 3
        for i, rn in enumerate(resnames):
            if i in disulfide:
                assert rn == "CYS", "disulfide endpoints must be CYS"
                sg[i] = base + 4
            base += 5 if rn == "CYS" else 4
        bonds.append((sg[disulfide[0]], sg[disulfide[1]]))
    u.add_bonds(bonds)
    return u


def _map_seq(u):
    from src_new.signatures.generators.fasta import fragment_to_protseq_map_based

    return fragment_to_protseq_map_based(u.atoms, RunConfig().signatures)


class TestB02BackboneOnlyGraph:
    def test_disulfide_does_not_truncate_sequence(self):
        """Fixture-4725 shape (one chain, CYX bridges 4-111 / 38-159):
        map FASTA must be the full sequence, not a partial BFS path."""
        u = _protein_universe(_RESSEQ, disulfide=(4, 8))
        assert _map_seq(u) == _EXPECTED

    def test_disulfide_kept_out_of_graph_keeps_all_residues(self):
        resnames = _RESSEQ + _RESSEQ[::-1]
        # CYS sit at positions 4, 8 and (mirrored) 11, 15
        u = _protein_universe(resnames, disulfide=(4, 15))
        assert _map_seq(u) == "ARNDCQEGCI" + "ICGEQCDNRA"


class TestB03DeterministicDirection:
    def test_direction_is_n_to_c_regardless_of_resindex_offset(self):
        """Same chemical chain at resindex offset 50: direction must still be
        N->C (old code picked direction by set-iteration order)."""
        u = _protein_universe(_RESSEQ, offset_residues=50)
        assert _map_seq(u) == _EXPECTED
        assert _map_seq(u)[0] == "A" and _map_seq(u)[-1] == "I"


class TestB04PdbFixedWidth:
    def test_four_char_resnames_and_big_resseq_roundtrip(self, tmp_path):
        """LYSH/CYS2/NALA + resids 9998-10002: written PDB must map names to
        standard 3-letter codes, renumber 1..n, and PARSE BACK cleanly."""
        from src_new.signatures.generators.topology_less_pdb import (
            fragment_to_pdb_ca_only)

        resnames = ["NALA", "LYSH", "CYS2", "HISE"]
        atoms_per, names, resids, positions = [], [], [], []
        for i, rn in enumerate(resnames):
            atoms_per.append(1)
            names.append("CA")
            resids.append(9998 + i)
            positions.append((float(i * 3.8), 0.0, 0.0))
        resindex = []
        for ri, cnt in enumerate(atoms_per):
            resindex += [ri] * cnt
        u = mda.Universe.empty(len(names), n_residues=len(resnames), n_segments=1,
                               atom_resindex=resindex, trajectory=True)
        u.add_TopologyAttr("names", names)
        u.add_TopologyAttr("resids", resids)
        u.add_TopologyAttr("resnums", resids)
        u.add_TopologyAttr("resnames", resnames)
        u.add_TopologyAttr("segids", ["S"])
        u.atoms.positions = positions

        pdb_text = fragment_to_pdb_ca_only(u.atoms)
        lines = [ln for ln in pdb_text.splitlines() if ln.startswith("ATOM")]
        assert len(lines) == 4
        for i, ln in enumerate(lines):
            resname_field = ln[17:20]
            resseq_field = ln[22:26]
            assert resname_field.strip() in {"ALA", "LYS", "CYS", "HIS"}, (
                f"4-char residue name leaked into fixed-width field: {ln!r}"
            )
            assert resseq_field.strip().isdigit() and int(resseq_field) <= 9999
        # round-trip: the emitted file must be parseable as a PDB
        fn = tmp_path / "q.pdb"
        fn.write_text(pdb_text)
        u2 = mda.Universe(str(fn))
        assert [str(r) for r in u2.atoms.resnames] == ["ALA", "LYS", "CYS", "HIS"]
        assert [int(r) for r in u2.atoms.resids] == [1, 2, 3, 4]
