"""bughunt BH-001: single-atom fragments became ions with ELEMENT answers at 100.

Chain of causes (report b9-1027):
  1. universe_facade._classify_molecule_type checked atom_count == 1 -> ION
     BEFORE the water rule, so every crystallographic water without
     resolved hydrogens (HOH, O only) was typed ion — "ELEMENT O at 100"
     in every RCSB case; PO4 stripped to bare P answered "ELEMENT P".
  2. signatures/generators/atom.py emitted an element signature for ANY
     one-atom fragment.
  3. verification._element_ground_truth checked only ident type + atom
     count, so the ELEMENT identity was lifted to confidence 100.

Fix: water by residue (independent of bonds/atom count), ION only for
allowlisted single-atom elements (metals/halides/noble gases), the atom
signature gated on molecule type ION, the ground-truth rule gated on
segment type ion + the same allowlist, and heavy-only water typed WATER
gets the H2O formula.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

mda = pytest.importorskip("MDAnalysis")

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src_new.loader.universe_facade import LoadedUniverse
from src_new.molecules.instances import MoleculeInstance, MoleculeType


def _props(**kw):
    base = {"flags": {}, "atom_count_fragment": 10}
    base.update(kw)
    return types.SimpleNamespace(**base)


def _fragment(resnames, elements):
    return types.SimpleNamespace(
        residues=types.SimpleNamespace(resnames=resnames),
        atoms=types.SimpleNamespace(elements=elements),
    )


class TestClassifierBH001:
    def _cls(self, **kw):
        return LoadedUniverse._classify_molecule_type(kw["props"], kw["frag"])

    # --- water by residue, any atom count -----------------------------

    def test_crystal_water_without_h_is_water(self):
        # the headline case: HOH with only its O (H not resolved)
        assert self._cls(props=_props(atom_count_fragment=1),
                         frag=_fragment(["HOH"], ["O"])) == MoleculeType.WATER

    def test_h2o_and_dod_resnames_are_water(self):
        assert self._cls(props=_props(atom_count_fragment=1),
                         frag=_fragment(["H2O"], ["O"])) == MoleculeType.WATER
        assert self._cls(props=_props(atom_count_fragment=3),
                         frag=_fragment(["DOD"], ["O", "D", "D"])) == MoleculeType.WATER

    def test_tip3p_lone_hydrogen_is_not_water(self):
        # no CONECT: a stripped H fragment must not become WATER (O==1
        # required) nor ION — UNKNOWN, no ELEMENT identity
        assert self._cls(props=_props(atom_count_fragment=1),
                         frag=_fragment(["TIP3"], ["H"])) == MoleculeType.UNKNOWN

    def test_bare_oxygen_without_water_resname_is_not_water(self):
        # composition alone (no residue nomenclature) must not invent water
        assert self._cls(props=_props(atom_count_fragment=1),
                         frag=_fragment(["UNK"], ["O"])) == MoleculeType.UNKNOWN

    # --- ion allowlist -------------------------------------------------

    def test_metal_and_halide_single_atoms_are_ion(self):
        assert self._cls(props=_props(atom_count_fragment=1),
                         frag=_fragment(["ZN"], ["Zn"])) == MoleculeType.ION
        assert self._cls(props=_props(atom_count_fragment=1),
                         frag=_fragment(["CLA"], ["Cl"])) == MoleculeType.ION
        assert self._cls(props=_props(atom_count_fragment=1),
                         frag=_fragment(["SOD"], ["Na"])) == MoleculeType.ION

    def test_lone_organic_atom_is_unknown(self):
        # the PO4-less phosphorus / broken carbon cases
        for el in ("C", "N", "O", "P", "S"):
            assert self._cls(props=_props(atom_count_fragment=1),
                             frag=_fragment(["LIG"], [el])) == MoleculeType.UNKNOWN, el

    def test_noble_gas_single_atom_is_ion(self):
        assert self._cls(props=_props(atom_count_fragment=1),
                         frag=_fragment(["XE"], ["Xe"])) == MoleculeType.ION


class TestAtomSignatureGate:
    """The element signature exists only for ION-typed fragments now."""

    def _gen(self):
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators.atom import AtomGenerator
        return AtomGenerator(SignaturesConfig())

    def _facade(self):
        return types.SimpleNamespace(
            get_segment_properties=lambda s: types.SimpleNamespace(
                flags={"has_elements": True}))

    def test_ion_fragment_emits_element_signature(self):
        gen = self._gen()
        inst = MoleculeInstance(instance_id="t", molecule_type=MoleculeType.ION)
        frag = types.SimpleNamespace(segids=["X"], n_atoms=1)
        assert gen._is_applicable(inst, frag, self._facade()) is True

    def test_unknown_typed_lone_atom_no_element_signature(self):
        gen = self._gen()
        inst = MoleculeInstance(instance_id="t", molecule_type=MoleculeType.UNKNOWN)
        frag = types.SimpleNamespace(segids=["X"], n_atoms=1)
        assert gen._is_applicable(inst, frag, self._facade()) is False

    def test_water_typed_lone_oxygen_no_element_signature(self):
        gen = self._gen()
        inst = MoleculeInstance(instance_id="t", molecule_type=MoleculeType.WATER)
        frag = types.SimpleNamespace(segids=["X"], n_atoms=1)
        assert gen._is_applicable(inst, frag, self._facade()) is False


class TestElementGroundTruthGate:
    """_element_ground_truth now requires segment type ion + allowlist."""

    def _results(self, seg_type):
        data = {
            "fragments/segments": [{"segment": "A", "type": seg_type}],
            "universe/segments/A/properties": {"atom_count_fragment": 1},
        }
        return types.SimpleNamespace(
            get_data=lambda key, _d=data: _d.get(key))

    def test_zn_in_ion_segment_is_ground_truth(self):
        from src_new.verification.manager import _element_ground_truth
        assert _element_ground_truth(
            self._results("ion"), "A", "ELEMENT", "identity", element="Zn") is True

    def test_water_segment_not_ground_truth(self):
        from src_new.verification.manager import _element_ground_truth
        assert _element_ground_truth(
            self._results("water"), "A", "ELEMENT", "identity", element="O") is False

    def test_organic_element_in_ion_segment_refused(self):
        from src_new.verification.manager import _element_ground_truth
        assert _element_ground_truth(
            self._results("ion"), "A", "ELEMENT", "identity", element="C") is False

    def test_allowlisted_element_in_unknown_segment_refused(self):
        from src_new.verification.manager import _element_ground_truth
        # signature exists but the loader never typed the segment ion
        assert _element_ground_truth(
            self._results("unknown"), "A", "ELEMENT", "identity", element="Zn") is False


class TestHeavyOnlyWaterFormula:
    """A crystallographic water typed WATER with only O resolved -> H2O."""

    def _gen(self):
        from src_new.config.loader import SignaturesConfig
        from src_new.signatures.generators.formula import MolecularFormulaGenerator
        return MolecularFormulaGenerator(SignaturesConfig())

    def _frag(self, elements):
        return mda.Universe.empty(
            len(elements), n_residues=1, n_segments=1,
            atom_resindex=[0] * len(elements), trajectory=True,
        ) or None

    def test_heavy_only_water_formula_is_h2o(self):
        gen = self._gen()
        inst = MoleculeInstance(
            instance_id="t", molecule_type=MoleculeType.WATER,
            element_composition={"O": 1})
        frag = types.SimpleNamespace(atoms=types.SimpleNamespace(elements=[]))
        assert gen._generate(inst, frag, None) == "H2O"

    def test_full_water_formula_unchanged(self):
        gen = self._gen()
        inst = MoleculeInstance(
            instance_id="t", molecule_type=MoleculeType.WATER,
            element_composition={"O": 1, "H": 2})
        frag = types.SimpleNamespace(atoms=types.SimpleNamespace(elements=[]))
        assert gen._generate(inst, frag, None) == "H2O"

    def test_lone_oxygen_not_typed_water_stays_o(self):
        gen = self._gen()
        inst = MoleculeInstance(
            instance_id="t", molecule_type=MoleculeType.UNKNOWN,
            element_composition={"O": 1})
        frag = types.SimpleNamespace(atoms=types.SimpleNamespace(elements=[]))
        assert gen._generate(inst, frag, None) == "O"
