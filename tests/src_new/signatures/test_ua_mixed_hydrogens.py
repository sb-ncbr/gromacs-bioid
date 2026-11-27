"""dm1 audit (I1): united-atom molecules that keep their polar hydrogens
explicit (Berger/GROMOS/OPLS-UA lipids: NH3+, OH) get their CH2/CH3 hydrogens
from the mass residuals; all-atom molecules stay untouched."""
import types

import pytest

mda = pytest.importorskip("MDAnalysis")
from rdkit import Chem

from src_new.signatures.generators._perceive_cache import _h_deficiency
from src_new.signatures.generators.smiles import _build_smiles_mol


def _frag(elements, masses):
    return types.SimpleNamespace(atoms=types.SimpleNamespace(elements=elements, masses=masses))


def test_mixed_united_atom_counts():
    # UA ethanol with explicit hydroxyl H: CH3 15.035, CH2 14.027, O, H
    assert _h_deficiency(_frag(["C", "C", "O", "H"], [15.035, 14.027, 15.999, 1.008])) == {0: 3, 1: 2}


def test_all_atom_stays_untouched():
    assert _h_deficiency(_frag(["C", "H", "H", "H", "O", "H"],
                               [12.011, 1.008, 1.008, 1.008, 15.999, 1.008])) is None


def test_hmr_all_atom_stays_untouched():
    # hydrogen mass repartitioning: heavy atoms LIGHTER, H heavier
    assert _h_deficiency(_frag(["C", "H", "H", "H"], [5.963, 3.024, 3.024, 3.024])) is None


def _universe(elements, masses, bonds):
    u = mda.Universe.empty(len(elements), n_residues=1, n_segments=1,
                           atom_resindex=[0] * len(elements), trajectory=True)
    u.add_TopologyAttr("elements", elements)
    u.add_TopologyAttr("masses", masses)
    u.add_TopologyAttr("names", [f"{e}{i}" for i, e in enumerate(elements)])
    u.add_TopologyAttr("resnames", ["EOH"])
    u.add_TopologyAttr("bonds", bonds)
    import numpy as np
    u.load_new(np.array([[0, 0, 0], [1.5, 0, 0], [2.2, 1.2, 0], [3.1, 1.2, 0]], dtype=np.float32),
               format="memory")
    return u


def test_mixed_united_atom_smiles_is_real_chemistry():
    u = _universe(["C", "C", "O", "H"], [15.035, 14.027, 15.999, 1.008], [(0, 1), (1, 2), (2, 3)])
    mol = _build_smiles_mol(u.atoms)
    assert Chem.MolToSmiles(Chem.RemoveHs(mol)) == "CCO"
