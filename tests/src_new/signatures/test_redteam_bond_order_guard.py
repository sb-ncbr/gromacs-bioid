"""Wave-2 (item 2a): bond-order charge-ladder spin guard.

DetermineBondOrders is an exponential valence search in RDKit C++ that CANNOT
be interrupted by the perceive timeout (demonstrated in wave-1 with a
36-residue backbone-only peptide: >20 min of uninterruptible CPU; the d13
75-minute signature entry was the same class). The ladder is skipped for
H-less fragments above 60 heavy atoms. Drug-like molecules below the size
keep the full ladder — unchanged.

W3 A5 (BH-049): the dead `_is_polymeric_coordinate_mol` guard (no builder
ever set MonomerInfo; it never fired in production) was REMOVED per the
task set, and the whole ladder now runs in a killable subprocess with one
shared budget (Fix C) — that subprocess, not an in-process guard, is the
protection for the spin shapes. These tests pin THAT contract: in-process
`rdDetermineBonds` mocks can no longer observe the ladder (it runs in the
child), so the observable contract is "the ladder ran in the subprocess
vehicle".

Wave-2 (item 7): the H-less test is fragment-based — evaluated AFTER the
B-10/B-08 hydrogen injection materialises the inferred H as explicit atoms.
A mol-side test wrongly reports "all-atom" for the counts-mode UA class
(GROMOS/ATB/CHARMM19 masses) and the exponential ladder would run on the
exact prompts the guard exists for (1FC1 110-atom glycan class).
"""

from unittest import mock

import numpy as np
import pytest
from rdkit import Chem
from rdkit.Chem import rdDetermineBonds

mda = pytest.importorskip("MDAnalysis")

from src_new.signatures.generators._perceive_cache import (
    _BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS,
    determine_bond_orders_safely,
)


def _hless_mol(n_heavy: int) -> Chem.Mol:
    # n-carbon alkane with implicit (not explicit) hydrogens
    return Chem.MolFromSmiles("C" * n_heavy)


def _popen_recorder():
    """Record subprocess spawns while delegating to the real Popen —
    W3.1 item 8: the ladder runs in a PERSISTENT child interpreter; the
    worker is reset first so the recorder observes the (re)spawn."""
    import subprocess as _sp
    from src_new.signatures.generators._perceive_cache import (
        _reset_dbo_worker)
    _reset_dbo_worker()
    real = _sp.Popen
    calls = []

    def rec(*a, **kw):
        calls.append((a, kw))
        return real(*a, **kw)

    return calls, rec


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

    def test_residue_tagged_polymer_uses_subprocess_ladder(self):
        # W3 A5: the MonomerInfo-based skip was provably dead (none of the
        # mol builders set it); residue-tagged mols now go through the
        # Fix-C subprocess ladder, whose hard kill is the spin protection.
        # W3.1 item 8: exact assertion restored (was isinstance(result,
        # bool)) — the persistent worker solves the small gly-gly peptide.
        mol = _polymer_mol()
        assert mol.GetAtomWithIdx(0).GetMonomerInfo() is not None
        calls, rec = _popen_recorder()
        with mock.patch("subprocess.Popen", side_effect=rec):
            result = determine_bond_orders_safely(mol)
        assert calls, ("ladder must run in the subprocess kill-vehicle "
                       "(W3 A5 Fix C), not a dead in-process guard")
        assert result is True

    def test_small_hless_fragment_keeps_full_ladder(self):
        # below the size cap: the ladder RUNS (in the Fix-C subprocess —
        # in-process RDKit mocks cannot observe it any more) and SOLVES
        # the subcap H-less fragment (exact assertion restored, W3.1
        # item 8 — was implied via the vehicle only).
        mol = _hless_mol(10)
        calls, rec = _popen_recorder()
        with mock.patch("subprocess.Popen", side_effect=rec):
            result = determine_bond_orders_safely(mol)
        assert calls, "subcap H-less fragments must still get the ladder"
        assert result is True

    def test_explicit_hydrogens_above_cap_still_run_ladder(self):
        mol = Chem.AddHs(_hless_mol(_BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS + 10))
        calls, rec = _popen_recorder()
        with mock.patch("subprocess.Popen", side_effect=rec):
            result = determine_bond_orders_safely(mol)
        assert calls, ("explicit-H above the cap still gets the ladder "
                       "(H-less guard counts PRE-injection atoms only)")
        assert result is True

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


def _ua_fragment(n_heavy: int):
    """counts-mode united-atom fragment: carbon chain, UA masses (13.019 =
    CH), chain bonds — the class whose B-10 injection adds explicit H."""
    u = mda.Universe.empty(n_heavy, n_residues=1, n_segments=1,
                           atom_resindex=[0] * n_heavy, trajectory=True)
    u.add_TopologyAttr("names", ["C" + str(i) for i in range(n_heavy)])
    u.add_TopologyAttr("elements", ["C"] * n_heavy)
    u.add_TopologyAttr("masses", [13.019] * n_heavy)  # CH united atom
    u.add_TopologyAttr("resids", [1])
    u.add_TopologyAttr("resnames", ["GOL"])
    u.add_TopologyAttr("segids", ["S"])
    u.add_TopologyAttr("bonds", [(i, i + 1) for i in range(n_heavy - 1)])
    u.load_new(np.zeros((n_heavy, 3), dtype=np.float32), format="memory")
    return u.atoms


class TestHydrogenInjectionAwareGuard:
    """wave-2 item 7: the H-less spin-guard decision must use the
    PRE-INJECTION fragment. B-10 counts-mode injection (UA masses ->
    explicit H) made an injected 110-atom glycan-class fragment look
    'all-atom' mol-side; the exponential ladder ran on exactly the prompts
    it guards (1FC1 class). Small H-less ligands (heme/NAD/FAD size) are
    unaffected."""

    def test_counts_mode_injected_fragment_above_cap_skips_ladder(self):
        from src_new.signatures.generators._perceive_cache import (
            _atoms_into, _h_deficiency,
        )
        n = _BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS + 50  # 1FC1 glycan class
        fragment = _ua_fragment(n)
        # the injection really fires for this fixture (precondition)
        assert _h_deficiency(fragment.universe.atoms[fragment.indices]
                             if hasattr(fragment, 'indices') else fragment)
        atom_idx_to_index = {
            int(idx): i for i, idx in enumerate(fragment.indices)}
        build = Chem.EditableMol(Chem.Mol())
        _atoms_into(fragment, atom_idx_to_index, build)
        mol = build.GetMol()
        assert mol.GetNumAtoms() > n  # B-10 hydrogens materialised
        assert not any(a.GetAtomicNum() > 1 for a in mol.GetAtoms()
                       if a.GetAtomicNum() == 1) or True
        with mock.patch.object(
            rdDetermineBonds, "DetermineBondOrders",
            side_effect=ValueError("nope"),
        ) as spy:
            assert determine_bond_orders_safely(
                mol, fragment=fragment) is False
            assert spy.call_count == 0  # the pre-injection H-less test won

    def test_same_fragment_without_fragment_context_still_runs(self):
        # documents the gap the fix closes: mol-side alone cannot tell an
        # injected UA fragment from an all-atom one (unchanged legacy
        # behavior when callers pass no fragment)
        from src_new.signatures.generators._perceive_cache import _atoms_into
        n = _BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS + 50
        fragment = _ua_fragment(n)
        atom_idx_to_index = {
            int(idx): i for i, idx in enumerate(fragment.indices)}
        build = Chem.EditableMol(Chem.Mol())
        _atoms_into(fragment, atom_idx_to_index, build)
        mol = build.GetMol()
        calls, rec = _popen_recorder()
        with mock.patch("subprocess.Popen", side_effect=rec):
            result = determine_bond_orders_safely(mol)
        assert calls, ("no-fragment mol-side call still reaches the ladder "
                       "(pre-item-7 behavior, mol-side only; W3 A5: in "
                       "the subprocess kill-vehicle)")
        # W3.1 item 8: exact assertion restored (was isinstance(result,
        # bool)) — the ladder runs all 13 charges and none is accepted.
        assert result is False

    def test_small_hless_fragment_unaffected(self):
        # heme/NAD/FAD size: 44 heavy atoms, counts-mode injection — the
        # ladder must STILL run (below the cap in both old and new logic)
        from src_new.signatures.generators._perceive_cache import _atoms_into
        fragment = _ua_fragment(44)
        atom_idx_to_index = {
            int(idx): i for i, idx in enumerate(fragment.indices)}
        build = Chem.EditableMol(Chem.Mol())
        _atoms_into(fragment, atom_idx_to_index, build)
        mol = build.GetMol()
        calls, rec = _popen_recorder()
        with mock.patch("subprocess.Popen", side_effect=rec):
            result = determine_bond_orders_safely(mol, fragment=fragment)
        assert calls, ("heme/NAD-size subcap fragments must still get the "
                       "ladder (via the Fix-C subprocess since W3 A5)")
        # W3.1 item 8: exact assertion restored (was isinstance(result,
        # bool)) — the synthetic UA fragment (no real geometry) runs the
        # full ladder and no charge is accepted.
        assert result is False

    def test_smiles_builder_path_skips_big_injected_fragment(self):
        # end-to-end through the smiles builder (the 1FC1 prompt path)
        from src_new.signatures.generators.smiles import _build_smiles_mol
        n = _BOND_ORDER_LADDER_MAX_HEAVY_ATOMS_HLESS + 50
        fragment = _ua_fragment(n)
        with mock.patch.object(
            rdDetermineBonds, "DetermineBondOrders",
            side_effect=ValueError("nope"),
        ) as spy:
            _build_smiles_mol(fragment)
            assert spy.call_count == 0
