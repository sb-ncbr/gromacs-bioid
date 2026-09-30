"""Wave-7 Phase 4 (B4): real nucleic backbone trace PDB tests.

4.1: select_na_backbone_atom priority (C4' > C3' > P), '*'/'=' spellings.
4.2: fragment_to_pdb with backbone_selector emits REAL guide atoms at REAL
     coordinates; legacy selector=None path (protein) byte-preserved.
"""
from __future__ import annotations

from io import StringIO

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")
from Bio.PDB import PDBParser

from src_new.molecules.nucleic_acid import select_na_backbone_atom
from src_new.signatures.generators.pdb import fragment_to_pdb


def _mk_universe(resnames, atom_names_per_res, positions, resids=None):
    atom_resindex, names = [], []
    for i, anames in enumerate(atom_names_per_res):
        atom_resindex.extend([i] * len(anames))
        names.extend(anames)
    n_res = len(resnames)
    resids = resids or list(range(1, n_res + 1))
    u = mda.Universe.empty(len(names), n_residues=n_res, n_segments=1,
                           atom_resindex=atom_resindex, trajectory=True)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resids", resids)
    u.add_TopologyAttr("resnums", resids)
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("segids", ["X"])
    u.add_TopologyAttr("elements", [n.replace("'", "")[0] for n in names])
    u.load_new(np.array(positions, dtype=np.float32), format="memory")
    return u


def _lines(pdb_str):
    return [ln for ln in pdb_str.splitlines() if ln.startswith(("ATOM", "HETATM"))]


class TestSelectNaBackboneAtom:
    SUGAR = ["P", "O5'", "C5'", "C4'", "C3'", "O3'", "N9", "C8"]

    def _res(self, names):
        n = len(names)
        u = _mk_universe(["DA"], [names], [[0.0, 0.0, 0.0]] * n)
        return u.residues[0].atoms

    def test_prefers_c4prime(self):
        assert select_na_backbone_atom(self._res(self.SUGAR)).name == "C4'"

    def test_c3prime_fallback(self):
        names = [n for n in self.SUGAR if n != "C4'"]
        assert select_na_backbone_atom(self._res(names)).name == "C3'"

    def test_phosphorus_last_resort(self):
        assert select_na_backbone_atom(self._res(["P", "N9"])).name == "P"

    def test_star_spelling(self):
        names = [n.replace("'", "*") for n in self.SUGAR]
        assert select_na_backbone_atom(self._res(names)).name == "C4*"

    def test_none_when_no_backbone_atoms(self):
        assert select_na_backbone_atom(self._res(["N9", "C8", "N1"])) is None


class TestBackbonePdbWithSelector:
    NAMES = ["P", "O5'", "C5'", "C4'", "C3'", "O3'"]

    def _na_u(self):
        # distinct C4' positions per residue so we can verify real coords
        positions = [
            (i * 6.0 + off[0], off[1], off[2]) if j == 3 else (i * 6.0, j, 0.0)
            for i in range(2) for j, off in enumerate([(0, 0, 0)] * 3 + [(1.5, 2.5, 3.5)] + [(0, 0, 0)] * 2)
        ]
        positions = []
        for i in range(2):
            base = i * 6.0
            for j in range(len(self.NAMES)):
                positions.append((base + j + (100.0 if j == 3 else 0.0), j * 1.1, 2.0))
        return _mk_universe(["DA", "DC"], [self.NAMES] * 2, positions, resids=[1, 2])

    def test_real_atom_real_coords(self):
        u = self._na_u()
        pdb = fragment_to_pdb(u.atoms, True, backbone_selector=select_na_backbone_atom)
        lines = _lines(pdb)
        assert len(lines) == 2  # one per residue
        for line in lines:
            assert line[12:16].strip() == "C4'"
            assert line[76:78].strip() == "C"
        # coordinates must equal the source C4' positions (x = base + 3 + 100)
        x_vals = sorted(float(line[30:38]) for line in lines)
        src = sorted(u.atoms.positions[i][0] for i, n in enumerate(u.atoms.names) if n == "C4'")
        assert x_vals == pytest.approx(src, abs=1e-3)

    def test_parseable_by_biopython(self):
        u = self._na_u()
        pdb = fragment_to_pdb(u.atoms, True, backbone_selector=select_na_backbone_atom)
        structure = PDBParser(QUIET=True).get_structure("x", StringIO(pdb))
        residues = list(structure.get_residues())
        assert len(residues) == 2

    def test_p_fallback_element(self):
        u = _mk_universe(["DA"], [["P", "N9"]], [(5.0, 5.0, 5.0), (0.0, 0.0, 0.0)])
        pdb = fragment_to_pdb(u.atoms, True, backbone_selector=select_na_backbone_atom)
        lines = _lines(pdb)
        assert len(lines) == 1
        assert lines[0][12:16].strip() == "P"
        assert lines[0][76:78].strip() == "P"
        assert float(lines[0][30:38]) == pytest.approx(5.0, abs=1e-3)


class TestLegacyProteinBackbonePreserved:
    """selector=None must keep the legacy centroid pseudo-atom behavior."""

    def _prot_u(self):
        names = [["N", "CA", "C", "O"]] * 2
        positions = [(i * 3.8 + j, 0.0, 0.0) for i in range(2) for j in range(4)]
        return _mk_universe(["ALA", "GLY"], names, positions, resids=[1, 2])

    def test_centroid_ca_preserved(self):
        u = self._prot_u()
        pdb = fragment_to_pdb(u.atoms, True)  # no selector == legacy
        lines = _lines(pdb)
        assert len(lines) == 2
        for i, line in enumerate(lines):
            assert line[76:78].strip() == "C"
            # legacy: mean of the 4 atom x-positions of residue i
            expected_x = np.mean([i * 3.8 + j for j in range(4)])
            assert float(line[30:38]) == pytest.approx(expected_x, abs=1e-3)

    def test_deterministic_repeat_calls(self):
        u = self._prot_u()
        assert fragment_to_pdb(u.atoms, True) == fragment_to_pdb(u.atoms, True)
