"""W3.1 item 8 (A5): persistent bond-order worker, respawned after a
kill; 300 s / atom-scaled budget; start_new_session + killpg; PDEATHSIG.

Audit §2 A5 regressions (live evidence at HEAD):
- SUBPROCESS PER CALL: every ligand pays ~170 ms of interpreter+rdkit
  startup for the bond-order ladder (was 0.1-0.4 ms in-process);
- THE 120 S CAP IS TOO TIGHT: charge-less NAD (GRO/PDB with H) used to
  succeed in ~210 s and now loses its InChIKey;
- ORPHANS: the DBO grandchild keeps burning CPU after the run is
  terminated;
- WEAKENED TESTS: assertions rewritten to `isinstance(result, bool)`.

Fix contract (implemented in src_new after this file went RED):
1. one persistent worker interpreter per process (fork-safe: a forked
   child never reuses the parent's worker), respawned after a kill;
2. budget: BAT3_BOND_ORDER_TIMEOUT_S default 300 s, scaled up with atom
   count (never below the base, hard ceiling 1800 s);
3. the child runs start_new_session=True (own process group) and sets
   PR_SET_PDEATHSIG so it dies with the parent run; timeouts kill the
   whole group (killpg).
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path
from unittest import mock

import pytest

if importlib.util.find_spec("rdkit") is None:
    pytest.skip("rdkit required", allow_module_level=True)

from rdkit import Chem
from rdkit.Chem import AllChem

from src_new.signatures.generators._perceive_cache import (
    determine_bond_orders_safely)

REPO = Path(__file__).resolve().parents[3]


def _reset_worker():
    from src_new.signatures.generators import _perceive_cache as pc
    pc._reset_dbo_worker()


def _stripped(smi: str):
    mol = Chem.AddHs(Chem.MolFromSmiles(smi))
    if AllChem.EmbedMolecule(mol, randomSeed=7) != 0:
        AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=7)
    for b in mol.GetBonds():
        b.SetBondType(Chem.BondType.SINGLE)
    for a in mol.GetAtoms():
        a.SetFormalCharge(0)
        a.SetNoImplicit(True)
    return mol


@pytest.fixture(autouse=True)
def _fresh_worker():
    _reset_worker()
    yield
    _reset_worker()


class TestPersistentWorker:
    def test_worker_reused_across_calls(self, monkeypatch):
        """Two ligands, ONE interpreter: the second call must not pay a
        fresh interpreter+rdkit startup (~170 ms each at HEAD).
        RED at HEAD: one Popen per call."""
        monkeypatch.setenv("BAT3_DBO_NO_CAP", "1")
        monkeypatch.setenv("BAT3_BOND_ORDER_TIMEOUT_S", "60")
        real_popen = subprocess.Popen
        calls = []

        def rec(*a, **kw):
            calls.append((a, kw))
            return real_popen(*a, **kw)

        with mock.patch("subprocess.Popen", side_effect=rec):
            ok1 = determine_bond_orders_safely(_stripped("CC(=O)N"),
                                               net_charge=0)
            ok2 = determine_bond_orders_safely(_stripped("CCO"),
                                               net_charge=0)
        assert ok1 and ok2
        assert len(calls) == 1, (
            f"the bond-order worker must be PERSISTENT (one spawn for "
            f"the whole process), got {len(calls)} spawns")

    def test_worker_respawned_after_kill(self, monkeypatch):
        """A killed worker (timeout path) is respawned by the next
        call — one bad ligand must not poison the rest of the run."""
        monkeypatch.setenv("BAT3_DBO_NO_CAP", "1")
        monkeypatch.setenv("BAT3_BOND_ORDER_TIMEOUT_S", "60")
        from src_new.signatures.generators import _perceive_cache as pc
        worker = pc._get_dbo_worker()
        pid = worker.proc.pid
        assert worker.alive()
        os.killpg(os.getpgid(pid), 9)  # the timeout path's group kill
        worker.proc.wait(timeout=10)  # let the kernel reap it
        worker = pc._get_dbo_worker()  # same logical worker slot
        assert worker.proc.pid != pid, "dead worker must respawn"
        ok = determine_bond_orders_safely(_stripped("CCO"), net_charge=0)
        assert ok, "respawned worker must serve requests"

    def test_worker_child_in_own_session_with_pdeathsig(self, monkeypatch):
        """start_new_session=True (own process group — killpg can take
        out anything the ladder spawns) and PDEATHSIG (the worker dies
        with the parent run, no orphan CPU burn).
        RED at HEAD: no start_new_session in the spawn kwargs."""
        monkeypatch.setenv("BAT3_DBO_NO_CAP", "1")
        monkeypatch.setenv("BAT3_BOND_ORDER_TIMEOUT_S", "60")
        real_popen = subprocess.Popen
        kwargs_seen = []

        def rec(*a, **kw):
            kwargs_seen.append(kw)
            return real_popen(*a, **kw)

        with mock.patch("subprocess.Popen", side_effect=rec):
            determine_bond_orders_safely(_stripped("CC(=O)N"),
                                         net_charge=0)
        assert kwargs_seen, "no worker spawn observed"
        assert kwargs_seen[0].get("start_new_session") is True, (
            kwargs_seen[0])

    def test_worker_dies_with_parent_process(self, monkeypatch):
        """REAL orphan check: a driver process starts the worker, uses
        it, and exits; the worker interpreter must die with it
        (PR_SET_PDEATHSIG). RED at HEAD: no persistent worker to
        orphan."""
        monkeypatch.setenv("BAT3_DBO_NO_CAP", "1")
        driver = Path(REPO) / ".tmp" / "dbo_worker_driver.py"
        driver.parent.mkdir(exist_ok=True)
        driver.write_text(
            "import sys\n"
            f"sys.path.insert(0, {str(REPO)!r})\n"
            "from src_new.signatures.generators import _perceive_cache"
            " as pc\n"
            "w = pc._get_dbo_worker()\n"
            "print(w.proc.pid, flush=True)\n")
        proc = subprocess.run([sys.executable, str(driver)],
                               capture_output=True, text=True, timeout=120)
        assert proc.returncode == 0, proc.stderr[-400:]
        worker_pid = int(proc.stdout.strip().split()[-1])

        def _alive(pid):
            try:
                os.kill(pid, 0)
                return True
            except OSError:
                return False

        deadline = time.monotonic() + 10
        while _alive(worker_pid) and time.monotonic() < deadline:
            time.sleep(0.2)
        assert not _alive(worker_pid), (
            f"worker {worker_pid} survived its parent — orphaned DBO "
            f"interpreter keeps burning CPU after the run")


class TestBudget:
    def test_default_budget_300_and_atom_scaled(self, monkeypatch):
        """The 120 s cap starved charge-less NAD (~210 s); the budget
        is now 300 s by default and scales with atom count (hard
        ceiling 1800 s). RED at HEAD: fixed 120."""
        monkeypatch.delenv("BAT3_BOND_ORDER_TIMEOUT_S", raising=False)
        from src_new.signatures.generators import _perceive_cache as pc
        small = Chem.AddHs(Chem.MolFromSmiles("CCO"))
        assert pc._dbo_budget_s(small) == 300.0
        big = Chem.RWMol()
        for _ in range(400):
            big.AddAtom(Chem.Atom(6))
        big = big.GetMol()
        assert pc._dbo_budget_s(big) >= 400.0, "atom-scaled budget"
        huge = Chem.RWMol()
        for _ in range(5000):
            huge.AddAtom(Chem.Atom(6))
        assert pc._dbo_budget_s(huge.GetMol()) <= 1800.0, "hard ceiling"

    def test_env_override_kept(self, monkeypatch):
        monkeypatch.setenv("BAT3_BOND_ORDER_TIMEOUT_S", "17")
        from src_new.signatures.generators import _perceive_cache as pc
        assert pc._dbo_budget_s(Chem.MolFromSmiles("CC")) == 17.0
