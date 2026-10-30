"""W3 BH-053: the persistent DBO ladder worker and the run-level ladder
budget must be isolated per calling thread / per run.

W3.1 item 8 introduced ONE persistent worker interpreter per PROCESS and
a module-global run budget. That is only sound for the serial
in-process path. Under --pool=threads (production) two runs share the
worker process:

  (a) both threads write frames to ONE stdin and spawn readers on ONE
      stdout — a reply can be applied to the WRONG molecule (silent
      wrong bond orders, wrong InChIKey stereo layer downstream);
  (b) one run's budget timeout kills the worker process GROUP — the
      other run's in-flight request dies with it (false
      bond_order_timeout, all-single pre-state);
  (c) run B's stage-start dbo_run_budget_reset() zeroes run A's
      accumulated budget (both runs drain one counter).

This module pins the three isolation contracts:
  (a) 2 threads, 20 synchronized rounds, different molecules — every
      call returns True AND every mol gets ITS OWN bond pattern;
  (b) thread A's forced timeout (kill_group) never fails thread B's
      in-flight request;
  (c) run B's budget reset does not change run A's remaining budget.

RED at e70dfa107 (.tmp/redteam/bh053.RED.txt), GREEN after the
per-thread worker + run-keyed budget fix.
"""

from __future__ import annotations

import importlib.util
import threading

import pytest

if importlib.util.find_spec("rdkit") is None:
    pytest.skip("rdkit required", allow_module_level=True)

from rdkit import Chem
from rdkit.Chem import AllChem

import src_new.signatures.generators._perceive_cache as pc
from src_new.signatures.generators._perceive_cache import (
    determine_bond_orders_safely)


def _stripped(smi: str):
    """Real molecule -> explicit H -> 3D -> all bonds SINGLE, charges 0
    (the exact state _atoms_into/_bonds_into present to DBO in prod)."""
    mol = Chem.AddHs(Chem.MolFromSmiles(smi))
    if AllChem.EmbedMolecule(mol, randomSeed=7) != 0:
        AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=7)
    for b in mol.GetBonds():
        b.SetBondType(Chem.BondType.SINGLE)
        b.SetIsAromatic(False)
    for a in mol.GetAtoms():
        a.SetFormalCharge(0)
        a.SetNoImplicit(True)
        a.SetNumExplicitHs(a.GetTotalNumHs())
    return mol


def _nonsingle(m) -> int:
    return sum(1 for b in m.GetBonds()
               if b.GetBondType() != Chem.BondType.SINGLE)


# benzene (stripped +H = 12 atoms) restores 3 non-single bonds;
# acetamide (stripped +H = 10 atoms) restores exactly 1 (the C=O).
BENZENE_ATOMS = 12


class TestConcurrentLadders:
    def test_two_threads_20_rounds_own_results(self, monkeypatch):
        """(a) 2 threads run the ladder concurrently on different
        molecules, 20 synchronized rounds: each thread gets its own
        worker (distinct child pid) and every mol gets ITS OWN bond
        pattern (benzene 3, acetamide 1). With one shared worker the
        write frames interleave and the reply readers cross."""
        monkeypatch.setenv("BAT3_DBO_NO_CAP", "1")  # force the ladder
        monkeypatch.setenv("BAT3_BOND_ORDER_TIMEOUT_S", "60")
        pc._reset_dbo_worker()
        n_rounds = 20
        res: dict = {}
        workers: dict = {}

        def run(smi: str, tag: str):
            workers[tag] = pc._get_dbo_worker().proc.pid
            mols = [_stripped(smi) for _ in range(n_rounds)]
            for i, m in enumerate(mols):
                barrier.wait()
                ok = determine_bond_orders_safely(m, net_charge=0)
                res[(tag, i)] = (ok, _nonsingle(m))

        barrier = threading.Barrier(2)
        ta = threading.Thread(target=run, args=("c1ccccc1", "benzene"))
        tb = threading.Thread(target=run, args=("CC(=O)N", "acetamide"))
        ta.start()
        tb.start()
        ta.join()
        tb.join()

        # structural: one worker per calling thread
        assert workers["benzene"] != workers["acetamide"], (
            f"both threads share ONE worker process: {workers}")
        # behavioral: no call failed (frame desync shows up as ok=False)
        failed = {k: v for k, v in res.items() if not v[0]}
        assert not failed, f"ladder calls failed (frame cross-talk): {failed}"
        # behavioral: every mol got its OWN bond pattern (a crossed reply
        # would overlay the other molecule's solved bond orders)
        wrong = {k: v for k, v in res.items()
                 if v[1] != (3 if k[0] == "benzene" else 1)}
        assert not wrong, f"wrong bond orders applied (replies crossed): {wrong}"
        pc._reset_dbo_worker()

    def test_forced_timeout_does_not_kill_other_thread(self, monkeypatch):
        """(b) thread A's forced budget timeout (TimeoutExpired ->
        kill_group) must not fail thread B's in-flight request: each
        thread owns its worker process, and each worker runs in its own
        session, so the kill cannot reach the other thread's worker."""
        monkeypatch.setenv("BAT3_DBO_NO_CAP", "1")  # force the ladder
        pc._reset_dbo_worker()
        # benzene (12 atoms): budget below any possible round trip ->
        # guaranteed TimeoutExpired -> the real kill_group timeout path.
        # acetamide (10 atoms): 10 s, far above a normal round trip.
        monkeypatch.setattr(
            pc, "_dbo_budget_s",
            lambda mol: 1e-5 if mol.GetNumAtoms() == BENZENE_ATOMS else 10.0)
        n_rounds = 5
        res: dict = {}

        def storm():
            mols = [_stripped("c1ccccc1") for _ in range(n_rounds)]
            for i, m in enumerate(mols):
                barrier.wait()
                res[("a", i)] = determine_bond_orders_safely(m, net_charge=0)

        def victim():
            mols = [_stripped("CC(=O)N") for _ in range(n_rounds)]
            for i, m in enumerate(mols):
                barrier.wait()
                res[("b", i)] = determine_bond_orders_safely(m, net_charge=0)

        barrier = threading.Barrier(2)
        ta = threading.Thread(target=storm)
        tb = threading.Thread(target=victim)
        ta.start()
        tb.start()
        ta.join()
        tb.join()

        assert all(v is False for k, v in res.items() if k[0] == "a"), (
            f"thread A should hit the forced timeout every round: {res}")
        b_failures = {k: v for k, v in res.items() if k[0] == "b" and v is not True}
        assert not b_failures, (
            "thread B's requests died with thread A's kill "
            f"(shared worker process group): {b_failures}")
        pc._reset_dbo_worker()


class TestRunScopedBudget:
    def test_budget_reset_is_run_scoped(self):
        """(c) run B's stage-start budget reset must not change run A's
        remaining budget: the accumulator is keyed by run id, not one
        module-global counter both runs drain."""
        cap = pc._dbo_run_cap_s()
        pc.set_dbo_run_id("runA")
        try:
            pc.dbo_run_budget_reset()
            with pc._dbo_run_lock:
                pc._dbo_run_elapsed["runA"] = 100.0
            # run B starts its generate_signatures stage mid-run-A
            pc.set_dbo_run_id("runB")
            pc.dbo_run_budget_reset()
            # back in run A's scope: A's budget is untouched
            pc.set_dbo_run_id("runA")
            remaining = pc._dbo_run_remaining_s()
            assert remaining == pytest.approx(cap - 100.0), (
                f"run A's budget was clobbered by run B's reset: {remaining}")
            # and run B starts fresh
            pc.set_dbo_run_id("runB")
            assert pc._dbo_run_remaining_s() == pytest.approx(cap)
        finally:
            pc.set_dbo_run_id(None)
