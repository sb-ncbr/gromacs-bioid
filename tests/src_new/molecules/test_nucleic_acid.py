"""Unit tests for src_new.molecules.nucleic_acid (Phase 1, ENAR).

Covers the tier-1 resname normalizer case matrix, atom-name normalization
('*' vs "'" spellings), the sugar-phosphate fingerprint, and the mandatory
cross-residue phosphodiester guard (cofactor protection).
"""
from __future__ import annotations

import numpy as np
import pytest

mda = pytest.importorskip("MDAnalysis")

from src_new.molecules.nucleic_acid import (
    has_cross_residue_phosphodiester,
    normalize_atom_name,
    normalize_nucleic_resname,
    residue_has_sugar_phosphate,
)


class TestNormalizeNucleicResname:
    """Tier-1 resname normalization matrix."""

    @pytest.mark.parametrize("resn,expected", [
        # canonical one-letter codes (legacy parity)
        ("A", "A"), ("C", "C"), ("G", "G"), ("T", "T"), ("U", "U"),
        # deoxy two-letter codes (legacy parity)
        ("DA", "A"), ("DC", "C"), ("DG", "G"), ("DT", "T"), ("DU", "U"),
        # legacy R-aliases (legacy parity)
        ("RA", "A"), ("RC", "C"), ("RG", "G"), ("RU", "U"), ("RT", "T"),
        # DNA terminal codes (user's D[ACGT][35] pattern)
        ("DA3", "A"), ("DA5", "A"), ("DC3", "C"), ("DC5", "C"),
        ("DG3", "G"), ("DG5", "G"), ("DT3", "T"), ("DT5", "T"),
        # RNA terminal codes (user's [ACGU][35] pattern)
        ("A3", "A"), ("A5", "A"), ("C3", "C"), ("C5", "C"),
        ("G3", "G"), ("G5", "G"), ("U3", "U"), ("U5", "U"),
        # odd-but-harmless cross combos still normalize
        ("DU5", "U"), ("DT3", "T"),
        # case/whitespace robustness
        (" da3 ", "A"), (" dg5", "G"),
    ])
    def test_accepts(self, resn, expected):
        assert normalize_nucleic_resname(resn) == expected

    @pytest.mark.parametrize("resn", [
        # modified bases must NOT normalize by name (tier-2 handles them structurally)
        "PSU", "H2U", "OMC", "OMG", "5MC", "1MA", "2MG", "7MG",
        # ligands / cofactors
        "ATP", "ADP", "GTP", "NAD", "FAD", "COA", "SAM", "HEM",
        # protein residues
        "ALA", "GLY", "LYS", "HIS",
        # lipids & other 3-char D-prefixed names that must not collapse
        "DPPC", "DHA",
        # inosine deliberately excluded (iodide collision risk, see module docstring)
        "I", "DI",
        # CHARMM full base names are out of scope (documented follow-up)
        "ADE", "CYT", "GUA", "THY", "URA",
        # empty / degenerate
        "", " ", "D", "5",
    ])
    def test_rejects(self, resn):
        assert normalize_nucleic_resname(resn) is None


class TestNormalizeAtomName:
    @pytest.mark.parametrize("raw,expected", [
        ("C4'", "C4'"),
        ("C4*", "C4'"),
        (" c3' ", "C3'"),
        ("O3*", "O3'"),
        ("P", "P"),
        ("o5'", "O5'"),
    ])
    def test_spellings(self, raw, expected):
        assert normalize_atom_name(raw) == expected


class TestSugarPhosphateFingerprint:
    def test_full_prime_spelling(self):
        names = ["P", "O5'", "C5'", "C4'", "C3'", "O3'", "N9", "C8"]
        assert residue_has_sugar_phosphate(names)

    def test_full_star_spelling(self):
        names = ["P", "O5*", "C5*", "C4*", "C3*", "O3*", "N9"]
        assert residue_has_sugar_phosphate(names)

    @pytest.mark.parametrize("missing", ["O3'", "C3'", "C4'", "C5'", "O5'"])
    def test_incomplete_sugar_rejected(self, missing):
        names = ["P", "O5'", "C5'", "C4'", "C3'", "O3'", "N9"]
        names.remove(missing)
        assert not residue_has_sugar_phosphate(names)

    def test_protein_residue_rejected(self):
        assert not residue_has_sugar_phosphate(["N", "CA", "C", "O", "CB"])

    def test_heme_rejected(self):
        assert not residue_has_sugar_phosphate(["FE", "NA", "NB", "NC", "ND"])


def _mk_universe(names, resindex, resnames, bonds):
    """Build a synthetic universe with explicit names/residues/bonds."""
    n = len(names)
    u = mda.Universe.empty(n, n_residues=max(resindex) + 1, n_segments=1,
                           atom_resindex=resindex, trajectory=True)
    u.add_TopologyAttr("names", names)
    u.add_TopologyAttr("resids", list(range(1, max(resindex) + 2)))
    u.add_TopologyAttr("resnames", resnames)
    u.add_TopologyAttr("segids", ["X"])
    positions = np.zeros((n, 3), dtype=np.float32)
    u.load_new(positions, format="memory")
    if bonds:
        u.add_TopologyAttr("bonds", bonds)
    return u


class TestCrossResiduePhosphodiester:
    def test_real_linkage_detected(self):
        """res0: O3' bonded to res1: P  -> True (classic 3'->5' linkage)."""
        u = _mk_universe(
            names=["O3'", "O5'", "P", "O5'", "O3'"],
            resindex=[0, 0, 1, 1, 1],
            resnames=["DA", "DG"],
            bonds=[(2, 0)],  # P(res1) - O3'(res0), cross-residue
        )
        assert has_cross_residue_phosphodiester(u.atoms)

    def test_star_spelling_detected(self):
        u = _mk_universe(
            names=["O3*", "P"],
            resindex=[0, 1],
            resnames=["DA3", "RG5"],
            bonds=[(0, 1)],
        )
        assert has_cross_residue_phosphodiester(u.atoms)

    def test_intra_residue_p_o3_does_not_count(self):
        """CoA-style 3'-phosphate INSIDE one residue must not promote."""
        u = _mk_universe(
            names=["P", "O5'", "C5'", "C4'", "C3'", "O3'", "PA", "O3A"],
            resindex=[0, 0, 0, 0, 0, 0, 0, 0],
            resnames=["COA"],
            bonds=[(5, 6)],  # O3'(res0) - PA(res0): intra-residue only
        )
        assert not has_cross_residue_phosphodiester(u.atoms)

    def test_atp_ligand_rejected(self):
        """Free ATP: full sugar atoms + phosphates, bonds only intra-residue."""
        u = _mk_universe(
            names=["O5'", "C5'", "C4'", "C3'", "O3'", "PA", "PB", "PG"],
            resindex=[0] * 8,
            resnames=["ATP"],
            bonds=[(0, 5), (5, 6), (6, 7)],  # triphosphate tail, all intra-res
        )
        assert not has_cross_residue_phosphodiester(u.atoms)

    def test_bondless_fragment_returns_false(self):
        u = _mk_universe(
            names=["O3'", "P"],
            resindex=[0, 1],
            resnames=["DA3", "DG5"],
            bonds=None,  # no bonds topology at all
        )
        assert not has_cross_residue_phosphodiester(u.atoms)

    def test_unrelated_p_pairs_rejected(self):
        """P-O5' cross-residue is NOT the linkage signature we want."""
        u = _mk_universe(
            names=["O5'", "P"],
            resindex=[0, 1],
            resnames=["X1", "Y1"],
            bonds=[(0, 1)],
        )
        assert not has_cross_residue_phosphodiester(u.atoms)
