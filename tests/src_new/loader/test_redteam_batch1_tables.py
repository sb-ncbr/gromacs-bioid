"""Red-team Batch 1.7 (tables/sites) regression tests.

  B-09/A-19: KNOWN_RESIDUE_CODES misses common FF variants (CYX->X!), HYP
             maps to 'O' (pyrrolysine), and ACE/NME caps are INSERTED as 'X'
             into sequences.
  A-08:      KNOWN_NUCLEIC_ACIDS_CODES contains ligand codes (DTX -> 'T'):
             the digitoxigenin in fixture 4725 types as NUCLEIC. Single
             residues can never be nucleic acids.
  A-11/B-13: TIP4P virtual site MW is mapped to element O -> water becomes
             H2O2 (hydrogen peroxide), and any LP/EPW site kills chemistry.
  B-16:      formula string is alphabetical, not Hill (ChEMBL exact-match
             lookups miss anything with B/Br/Cl/F).
  A-14:      export_mmcif caches residues by (resid, resname) across chains
             -> multi-chain exports crash ("Atom N defined twice").
"""
from __future__ import annotations

import MDAnalysis as mda
import pytest
from types import SimpleNamespace

from src_new.config.loader import RunConfig
from src_new.constants import KNOWN_NUCLEIC_ACIDS_CODES, KNOWN_RESIDUE_CODES


def _u(residues, segid="S", with_masses=None, with_elements=None, bonds=()):
    """residues: list of (resname, [atom_names])."""
    atoms_per = [len(names) for _, names in residues]
    n = sum(atoms_per)
    resindex = []
    for ri, cnt in enumerate(atoms_per):
        resindex += [ri] * cnt
    u = mda.Universe.empty(n, n_residues=len(residues), n_segments=1,
                           atom_resindex=resindex, trajectory=True)
    u.add_TopologyAttr("names", [a for _, names in residues for a in names])
    u.add_TopologyAttr("resids", list(range(1, len(residues) + 1)))
    u.add_TopologyAttr("resnames", [rn for rn, _ in residues])
    u.add_TopologyAttr("segids", [segid])
    if with_masses is not None:
        u.add_TopologyAttr("masses", with_masses)
    if with_elements is not None:
        u.add_TopologyAttr("elements", with_elements)
    if bonds:
        u.add_bonds(bonds)
    return u


class TestB09ResidueTable:
    @pytest.mark.parametrize("name,letter", [
        ("CYX", "C"), ("CYM", "C"), ("CYSH", "C"),
        ("LYN", "K"), ("LSN", "K"),
        ("HISD", "H"), ("HISE", "H"), ("HISH", "H"),
        ("MSE", "M"), ("SEP", "S"), ("TPO", "T"), ("PTR", "Y"), ("NLE", "L"),
        ("HYP", "P"),          # hydroxyproline is NOT pyrrolysine 'O'
        ("DAL", "A"), ("DCY", "C"), ("DPN", "P"),
        ("NALA", "A"), ("CGLY", "G"), ("NMET", "M"), ("NSER", "S"),
    ])
    def test_ff_variants_map_to_parent(self, name, letter):
        from src_new.signatures.generators.fasta import resname_to_one_letter
        assert resname_to_one_letter(name) == letter

    def test_caps_are_not_inserted_into_sequences(self):
        """ACE-ALA-NME capped peptide: caps must vanish, seq must be 'A'."""
        from src_new.signatures.generators.fasta import _fragment_extract_residues
        u = _u([("ACE", ["CH3"]), ("ALA", ["N", "CA", "C", "O"]), ("NME", ["N"])])
        code_map, _ = _fragment_extract_residues(u.atoms)
        assert list(code_map.values()) == ["A"], (
            "ACE/NME caps leak X into BLAST query sequences (B-09)"
        )


class TestA08NucleicTable:
    def test_dtx_is_not_a_nucleic_code(self):
        assert "DTX" not in KNOWN_NUCLEIC_ACIDS_CODES
        assert "DAX" not in KNOWN_NUCLEIC_ACIDS_CODES

    def test_single_residue_is_never_nucleic(self):
        """A lone DA/A residue (free nucleoside, or the DTX steroid in fixture
        4725) must not type as NUCLEIC."""
        u = _u([("A", [f"AT{i}" for i in range(15)])],
               with_elements=["C"] * 8 + ["N"] * 5 + ["O"] * 2)
        from src_new.loader.universe_facade import LoadedUniverse, SegmentProperty
        facade = LoadedUniverse(universe=u, decision=SimpleNamespace(),
                                repair_report=SimpleNamespace(), results=None)
        props = facade.get_segment_properties("S")
        assert props.flags[SegmentProperty.IS_NUCLEIC.value] is False

    def test_two_residues_can_still_be_nucleic(self):
        from src_new.loader.universe_facade import LoadedUniverse, SegmentProperty
        u = _u([("A", ["P", "O3'", "C1'"]), ("U", ["P", "O3'", "C1'"])],
               with_elements=["P", "O", "C", "P", "O", "C"],
               bonds=[(1, 3)])  # O3'(i)-P(i+1) phosphodiester
        facade = LoadedUniverse(universe=u, decision=SimpleNamespace(),
                                repair_report=SimpleNamespace(), results=None)
        props = facade.get_segment_properties("S")
        assert props.flags[SegmentProperty.IS_NUCLEIC.value] is True


class TestVirtualSiteSentinel:
    def test_mw_is_not_guessed_as_oxygen(self):
        from src_new.loader.repair import TopologyRepair
        u = _u([("SOL", ["OW", "HW1", "HW2", "MW"])])
        r = TopologyRepair(u, RunConfig())
        for name in ("MW", "EPW", "LP1", "EP1"):
            assert r._guess_single_element("", name, None, None) in (None, ""), (
                f"virtual-site name {name} must not guess a real element (A-11)"
            )

    def test_tip4p_water_is_water_not_peroxide(self):
        """TIP4P: MW mass 0, no element. Composition must exclude the site:
        {O:1,H:2}, type WATER (not small_molecule H2O2), HAS_ELEMENTS True."""
        u = _u([("SOL", ["OW", "HW1", "HW2", "MW"])],
               with_masses=[16.0, 1.0, 1.0, 0.0],
               with_elements=["O", "H", "H", ""])
        from src_new.loader.universe_facade import LoadedUniverse, SegmentProperty
        facade = LoadedUniverse(universe=u, decision=SimpleNamespace(),
                                repair_report=SimpleNamespace(), results=None)
        props = facade.get_segment_properties("S")
        inst = facade.extract_molecule_instance("S")
        assert inst.element_composition == {"O": 1, "H": 2}, (
            f"virtual site leaked into composition: {inst.element_composition}"
        )
        assert str(inst.molecule_type).lower().endswith("water"), (
            f"TIP4P typed {inst.molecule_type}, not WATER (H2O2 peroxide class)"
        )
        assert props.flags[SegmentProperty.HAS_ELEMENTS.value] is True


class TestB16HillFormula:
    def test_formula_is_hill_order(self):
        from src_new.signatures.generators.formula import MolecularFormulaGenerator

        g = MolecularFormulaGenerator(RunConfig().signatures)
        instance = SimpleNamespace(
            element_composition={"C": 28, "F": 2, "H": 30, "N": 6, "O": 8, "S": 1})
        out = g._generate(instance, None, None)
        assert out == "C28H30F2N6O8S", f"alphabetical, not Hill: {out}"

    def test_formula_hill_without_carbon(self):
        """Deploy-gate bug (v3.143-b1 E2E): the no-carbon Hill branch did
        rest.remove("H") on a list that excludes H by construction — every
        carbon-free molecule (WATER!) crashed the generator with
        'list.remove(x): x not in list'."""
        from src_new.signatures.generators.formula import MolecularFormulaGenerator

        g = MolecularFormulaGenerator(RunConfig().signatures)
        for comp, want in (({"O": 1, "H": 2}, "H2O"),
                           ({"N": 2}, "N2"),
                           ({"Cl": 1, "H": 1}, "ClH"),  # no-C Hill: fully alphabetical
                           ({"Na": 1}, "Na")):
            instance = SimpleNamespace(element_composition=comp)
            assert g._generate(instance, None, None) == want


class TestA14ExportMmcifMultiChain:
    def test_homo_oligomer_export_does_not_crash(self):
        from src_new.loader.export_mmcif import _build_biopython_structure

        n = 8
        u = mda.Universe.empty(n, n_residues=2, n_segments=2,
                               atom_resindex=[0, 0, 0, 0, 1, 1, 1, 1],
                               residue_segindex=[0, 1], trajectory=True)
        u.add_TopologyAttr("names", ["N", "CA", "C", "O"] * 2)
        u.add_TopologyAttr("resids", [1, 1])
        u.add_TopologyAttr("resnames", ["MET", "MET"])
        u.add_TopologyAttr("segids", ["A", "B"])
        structure = _build_biopython_structure(u)
        atoms = list(structure.get_atoms())
        assert len(atoms) == 8, (
            "multichain exports crashed on (resid, resname) cache collisions (A-14)"
        )
