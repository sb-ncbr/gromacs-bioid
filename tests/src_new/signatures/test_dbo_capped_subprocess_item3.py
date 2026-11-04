"""Item 3 (c13 corpus): the carboxylate-capped single-shot DBO must run
in the KILLABLE WORKER, never in-process.

Offline repro (entry 9227, .tmp/redteam/item3_repro): the capped
attempt's DetermineBondOrders call spun >3 h inside RDKit C++ with no
cooperative checkpoint — SIGALRM cannot interrupt a C++ call (the W3 A5
hazard the ladder's Fix C documented; Fix B never got the same
protection). Fleet evidence: 9227/9260 wall-killed at exactly 3 h with
zero stage-budget warnings.
"""

from __future__ import annotations

import os
import sys

import pytest

rdkit = pytest.importorskip("rdkit")

sys.path.insert(0, os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from rdkit import Chem
from rdkit.Chem import AllChem

from src_new.signatures.generators import _perceive_cache as pc


def _stripped(smi):
    """Embed + strip to the all-single pre-state (ladder-test idiom)."""
    mol = Chem.MolFromSmiles(smi)
    assert mol is not None
    mol = Chem.AddHs(mol)
    if not AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=7):
        AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=7)
    rw = Chem.RWMol(mol)
    for b in rw.GetBonds():
        b.SetBondType(Chem.BondType.SINGLE)
        b.SetIsAromatic(False)
    for a in rw.GetAtoms():
        a.SetFormalCharge(0)
        a.SetNoImplicit(True)
        a.SetIsAromatic(False)
    return rw.GetMol()


# the BH-049 explosive shape: 3 deprotonated carboxylates + 8 amides
_ASP = "C(CC(=O)[O-])C(=O)N"
_GLY = "CC(=O)N"
_M13_SHAPE_SMI = ("N" + _ASP + _GLY + _GLY + _ASP + _GLY + _GLY
                  + _ASP + _GLY + "CC(=O)O")


class TestCappedSingleShotInWorker:
    def test_capped_shot_uses_killable_worker(self, monkeypatch):
        """The capped attempt MUST round-trip through the persistent
        worker with mode='capped' (vehicle proof, TestFixCHardKill
        idiom) — and still solve the BH-049 shape with identical
        chemistry (charges on the carboxylate oxygens)."""
        calls = {}
        real_call = pc._DboWorkerProcess.call

        def spy_call(self, mol_binary, net_charge, budget, mode="ladder"):
            calls["mode"] = mode
            return real_call(self, mol_binary, net_charge, budget,
                             mode=mode)

        monkeypatch.setattr(pc._DboWorkerProcess, "call", spy_call)
        monkeypatch.setattr(pc, "_dbo_run_remaining_s", lambda: 1e9)

        mol = _stripped(_M13_SHAPE_SMI)
        ok = pc.determine_bond_orders_safely(mol, net_charge=-3)

        assert ok, "the capped single-shot must still solve the shape"
        assert calls.get("mode") == "capped", \
            "the capped attempt must run in the killable worker"
        assert sum(a.GetFormalCharge() for a in mol.GetAtoms()) == -3
        assert sum(1 for a in mol.GetAtoms()
                   if a.GetAtomicNum() == 8
                   and a.GetFormalCharge() == -1) >= 3

    def test_capped_timeout_falls_through_to_ladder(self, monkeypatch):
        """Item-3 follow-up (user ruling 11-03): worker timeout on the
        capped shot falls through to the subprocess-capped ladder with
        the run cap bypassed and the fallback budget floor — ga1's
        ladder SOLVED this class (~20 min) and skipping discarded
        recoverable chemistry (wrong InChIKey on 9227). The capped
        attempt's run-cap slice is refunded (it bought nothing)."""
        class _Dead:
            def call(self, *a, **k):
                return None

        ladder = []

        def fake_ladder(m, q, *, ignore_run_cap=False, min_budget_s=0.0):
            ladder.append((ignore_run_cap, min_budget_s))
            return True

        monkeypatch.setattr(pc, "_get_dbo_worker", lambda: _Dead())
        monkeypatch.setattr(pc, "_dbo_run_remaining_s", lambda: 1e9)
        monkeypatch.setattr(pc, "_dbo_ladder_subprocess", fake_ladder)

        mol = _stripped(_M13_SHAPE_SMI)
        ok = pc.determine_bond_orders_safely(mol, net_charge=-3)

        assert ok is True
        assert ladder, "timeout must fall through to the ladder"
        assert ladder[0][0] is True, \
            "the fall-through ladder must bypass the run cap"
        assert ladder[0][1] > 0, \
            "the fall-through ladder must get the fallback budget floor"

    def test_capped_na_falls_through_to_ladder(self, monkeypatch):
        """No odd-UA carboxylate component: the parent-side fast path
        returns na without a round trip, and the historical ladder
        still runs."""
        ladder = []
        monkeypatch.setattr(pc, "_dbo_ladder_subprocess",
                            lambda m, q: ladder.append(1) or True)

        mol = _stripped("CC(=O)N")  # acetamide: no carboxylate to cap
        ok = pc.determine_bond_orders_safely(mol, net_charge=0)

        assert ok is True
        assert ladder, "non-applicable cap must fall through to the ladder"
