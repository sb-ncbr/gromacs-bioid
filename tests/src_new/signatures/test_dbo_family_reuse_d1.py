"""c13 D1: the smiles-class and inchi/selfies families share ONE bond-order
determination per input graph within a run.

In-pod evidence (9227 re-run 2026-11-04): the smiles family solved the
cyclic peptide through the fall-through ladder (07:56 -> 08:08); the inchi
family then asked again for the same graph, found the run cap spent and
re-ran the 1800 s fall-through ladder until the stage budget expired
(08:08 -> 08:20). Before the fall-through existed, the second family got
no bond orders at all and its InChIKey was computed on the all-single graph.
"""

from __future__ import annotations

import pytest

pytest.importorskip("rdkit")
mda = pytest.importorskip("MDAnalysis")

from rdkit import Chem

from src_new.signatures.generators import _perceive_cache as pc
from src_new.signatures.generators.smiles import _build_smiles_mol

# zwitterionic dipeptide with two carboxylates: exercises the capped
# single-shot path that 9227's peptide takes
_SMI = "[NH3+]CC(=O)NC(CC(=O)[O-])C(=O)[O-]"


@pytest.fixture
def fragment():
    u = mda.Universe.from_smiles(_SMI, addHs=True, generate_coordinates=True)
    return u.atoms


@pytest.fixture
def run(monkeypatch):
    pc.set_dbo_run_id("d1-test-run")
    pc.dbo_run_budget_reset()
    yield
    pc.dbo_run_budget_reset()


@pytest.fixture
def worker_calls(monkeypatch):
    calls = []
    real_call = pc._DboWorkerProcess.call

    def spy(self, mol_binary, net_charge, budget, mode="ladder"):
        calls.append(mode)
        return real_call(self, mol_binary, net_charge, budget, mode=mode)

    monkeypatch.setattr(pc._DboWorkerProcess, "call", spy)
    return calls


def _key(mol):
    return Chem.MolToInchiKey(Chem.RemoveHs(mol, sanitize=False))


def test_second_family_reuses_solution_with_run_cap_spent(
        fragment, run, worker_calls, monkeypatch):
    smiles_mol = _build_smiles_mol(fragment)
    n_first = len(worker_calls)
    assert n_first >= 1
    # the run cap is spent before the inchi family asks (9227 timeline)
    monkeypatch.setattr(pc, "_dbo_run_remaining_s", lambda: -1.0)
    inchi_mol = pc.build_once_family_mol(fragment)
    assert len(worker_calls) == n_first, "the solved graph must not be re-solved"
    assert _key(inchi_mol) == _key(smiles_mol)
    assert [b.GetBondType() for b in inchi_mol.GetBonds()] == \
        [b.GetBondType() for b in smiles_mol.GetBonds()]
    assert [a.GetFormalCharge() for a in inchi_mol.GetAtoms()] == \
        [a.GetFormalCharge() for a in smiles_mol.GetAtoms()]


def test_reuse_matches_a_fresh_solve(fragment, run):
    _build_smiles_mol(fragment)
    reused = pc.build_once_family_mol(fragment)
    pc.dbo_run_budget_reset()
    fresh = pc.build_once_family_mol(fragment)
    assert Chem.MolToSmiles(reused) == Chem.MolToSmiles(fresh)
    assert _key(reused) == _key(fresh)


def test_failed_outcome_is_reused_too(fragment, run, monkeypatch):
    calls = []

    def failing(mol, q):
        calls.append(1)
        return False

    monkeypatch.setattr(pc, "_determine_bond_orders_uncached", failing)
    pc.build_once_family_mol(fragment)
    pc.build_once_family_mol(fragment)
    assert calls == [1]


def test_different_graph_is_solved_separately(fragment, run, monkeypatch):
    calls = []
    real = pc._determine_bond_orders_uncached

    def spy(mol, q):
        calls.append(mol.GetNumAtoms())
        return real(mol, q)

    monkeypatch.setattr(pc, "_determine_bond_orders_uncached", spy)
    pc.build_once_family_mol(fragment)
    other = mda.Universe.from_smiles("CC(=O)[O-]", addHs=True,
                                     generate_coordinates=True).atoms
    pc.build_once_family_mol(other)
    assert len(calls) == 2


def test_stage_reset_and_other_runs_do_not_share(fragment, run, monkeypatch):
    calls = []
    real = pc._determine_bond_orders_uncached

    def spy(mol, q):
        calls.append(1)
        return real(mol, q)

    monkeypatch.setattr(pc, "_determine_bond_orders_uncached", spy)
    pc.build_once_family_mol(fragment)
    pc.dbo_run_budget_reset()          # next generate_signatures stage
    pc.build_once_family_mol(fragment)
    pc.set_dbo_run_id("d1-other-run")  # a concurrent run (BH-053 keying)
    try:
        pc.build_once_family_mol(fragment)
    finally:
        pc.dbo_run_budget_reset()
        pc.set_dbo_run_id("d1-test-run")
    assert len(calls) == 3
