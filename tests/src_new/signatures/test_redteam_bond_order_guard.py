"""Wave-2 (item 2a): bond-order charge-ladder spin guard.

DetermineBondOrders is an exponential valence search in RDKit C++ that CANNOT
be interrupted by the perceive timeout (demonstrated in wave-1 with a
36-residue backbone-only peptide: >20 min of uninterruptible CPU; the d13
75-minute signature entry was the same class). The ladder is skipped for
H-less fragments above 60 heavy atoms and for residue-tagged (polymer,
sequence-described) coordinate fragments. Drug-like molecules below the size
keep the full ladder — unchanged.
"""

from unittest import mock

from rdkit import Chem
from rdkit.Chem import rdDetermineBonds

from src_new.signatures.generators._perceive_cache import (
    _BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS,
    determine_bond_orders_safely,
)


def _hless_mol(n_heavy: int) -> Chem.Mol:
    # n-carbon alkane with implicit (not explicit) hydrogens
    return Chem.MolFromSmiles("C" * n_heavy)


def _polymer_mol() -> Chem.Mol:
    # 2-residue glycine peptide from a PDB block: atoms carry residue info
    pdb = (
        "ATOM      1  N   GLY A   1      10.000   0.000   0.000  1.00 20.00           N\n"
        "ATOM      2  CA  GLY A   1      11.450   0.000   0.000  1.00 20.00           C\n"
        "ATOM      3  C   GLY A   1      12.000   1.300   0.000  1.00 20.00           C\n"
        "ATOM      4  O   GLY A   1      12.000   2.300   0.000  1.00 20.00           O\n"
        "ATOM      5  N   GLY A   2      12.500  -0.500   1.200  1.00 20.00           N\n"
        "ATOM      6  CA  GLY A   2      13.950  -0.500   1.200  1.00 20.00           C\n"
        "ATOM      7  C   GLY A   2      14.500   0.800   1.200  1.00 20.00           C\n"
        "ATOM      8  O   GLY A   2      14.500   1.800   1.200  1.00 20.00           O\n"
        "END\n"
    )
    return Chem.MolFromPDBBlock(pdb, sanitize=False, removeHs=True)


class TestBondOrderLadderSpinGuard:
    def test_large_hless_fragment_skips_ladder(self):
        with mock.patch.object(
            rdDetermineBonds, "DetermineBondOrders",
            side_effect=ValueError("nope"),
        ) as spy:
            mol = _hless_mol(_BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS + 10)
            assert determine_bond_orders_safely(mol) is False
            assert spy.call_count == 0  # not even one exponential attempt

    def test_residue_tagged_polymer_skips_ladder(self):
        with mock.patch.object(
            rdDetermineBonds, "DetermineBondOrders",
            side_effect=ValueError("nope"),
        ) as spy:
            mol = _polymer_mol()
            assert mol.GetAtomWithIdx(0).GetMonomerInfo() is not None
            assert determine_bond_orders_safely(mol) is False
            assert spy.call_count == 0

    def test_small_hless_fragment_keeps_full_ladder(self):
        # below the size cap: ladder proceeds (all attempts fail -> False,
        # but it TRYING is the contract for drug-like fragments)
        with mock.patch.object(
            rdDetermineBonds, "DetermineBondOrders",
            side_effect=ValueError("nope"),
        ) as spy:
            mol = _hless_mol(10)
            assert determine_bond_orders_safely(mol) is False
            assert spy.call_count == 13

    def test_explicit_hydrogens_above_cap_still_run_ladder(self):
        with mock.patch.object(
            rdDetermineBonds, "DetermineBondOrders",
            side_effect=ValueError("nope"),
        ) as spy:
            mol = Chem.AddHs(_hless_mol(_BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS + 10))
            assert determine_bond_orders_safely(mol) is False
            assert spy.call_count == 13

    def test_accepted_solution_path_unchanged(self):
        with mock.patch.object(rdDetermineBonds, "DetermineBondOrders"):
            mol = Chem.MolFromSmiles("O=C(O)CN")
            assert determine_bond_orders_safely(mol) is True


class TestSmilesGeneratorIntegration:
    """The generator-level wiring: the spin guard must also fire through
    smiles._fix_bond_orders_rdkit (the only caller)."""

    def test_fix_bond_orders_skips_large_hless(self):
        from src_new.signatures.generators.smiles import _fix_bond_orders_rdkit
        with mock.patch.object(
            rdDetermineBonds, "DetermineBondOrders",
            side_effect=ValueError("nope"),
        ) as spy:
            _fix_bond_orders_rdkit(_hless_mol(_BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS + 10))
            assert spy.call_count == 0
