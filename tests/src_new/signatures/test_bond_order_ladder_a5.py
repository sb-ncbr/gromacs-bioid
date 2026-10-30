"""W3 A5 (BH-049): RDKit DetermineBondOrders explosion on multi-carboxylate
peptides (M13 daptomycin: every stack dump over 20 min sat inside
rdDetermineBonds.DetermineBondOrders at ladder charge 0).

Two-part fix contract pinned here (logs/final_wo/m13/rootcause_m13.md,
scripts/m13_fix.py + hard_timeout_proto.py):

Fix B — carboxylate-capped single-shot DBO BEFORE the ladder: on a copy,
temporarily protonate one O of every odd unsaturated-atom {C,O,O}
carboxylate component, run DetermineBondOrders ONCE at charge
(q + n_capped), copy bond orders back, charge -1 on each capped O.
Every UA component even -> first matching is perfect -> ms, no
enumeration. Caller topology charge wins when nonzero; otherwise the
charge is graph-derived (+1 per 4-connected N, -1 per capped O). Failure
leaves the mol in the all-single pre-state (hardened vs the prototype).

Fix C — the whole ladder runs in a hard-killed subprocess with ONE
shared budget (BAT3_BOND_ORDER_TIMEOUT_S, default 120 s). SIGALRM cannot
interrupt RDKit C++; a killable child can. Timeout is recorded as a
`bond_order_timeout` warning and the caller continues without
bond orders (all-single pre-state preserved on the parent mol).
(test mocks Popen to prove the vehicle is really used.)
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
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

REPO = Path(__file__).resolve().parents[2]
M13_INPUT = Path(
    "/home/tomsko/work/bat3_article_reviews/bioid_bughunt/testcases/"
    "M13_daptomycin_amber/input")
M13_PDB = M13_INPUT / "structure.pdb"


def _stripped(smi: str):
    """Real molecule -> explicit H -> 3D -> all bonds SINGLE, charges 0
    (the exact state _atoms_into/_bonds_into present to DBO in prod)."""
    mol = Chem.AddHs(Chem.MolFromSmiles(smi))
    if AllChem.EmbedMolecule(mol, randomSeed=7) != 0:
        AllChem.EmbedMolecule(mol, useRandomCoords=True, randomSeed=7)
    ref = Chem.MolToSmiles(Chem.RemoveHs(mol))
    rw = Chem.RWMol(mol)
    for b in rw.GetBonds():
        b.SetBondType(Chem.BondType.SINGLE)
        b.SetIsAromatic(False)
    for a in rw.GetAtoms():
        a.SetFormalCharge(0)
        a.SetNoImplicit(True)
        a.SetIsAromatic(False)
    return rw.GetMol(), ref


# 3 deprotonated Asp side chains + 8 amides: the BH-049 explosive shape
# (UA odd {C,O,O} carboxylate components among many C=O pairs).
_ASP = "C(CC(=O)[O-])C(=O)N"
_GLY = "CC(=O)N"
_M13_SHAPE_SMI = ("N" + _ASP + _GLY + _GLY + _ASP + _GLY + _GLY
                  + _ASP + _GLY + "CC(=O)O")


def _all_single(mol) -> bool:
    return all(b.GetBondType() == Chem.BondType.SINGLE
               for b in mol.GetBonds())


class TestFixBCarboxylateCap:
    def test_three_carboxylates_eight_amides_fast(self):
        """BH-049 shape: HEAD runs the ladder at the correct charge and
        takes >120 s (bench: 8 amides); with Fix B this is the single
        capped attempt -> milliseconds."""
        mol, _ = _stripped(_M13_SHAPE_SMI)
        t0 = time.monotonic()
        ok = determine_bond_orders_safely(mol, net_charge=-3)
        dt = time.monotonic() - t0
        assert ok, "the correct charge must be accepted"
        assert dt < 30.0, f"bond-order determination took {dt:.1f}s (>120 s class on HEAD)"
        assert sum(a.GetFormalCharge() for a in mol.GetAtoms()) == -3
        assert any(b.GetBondType() != Chem.BondType.SINGLE
                   for b in mol.GetBonds()), "bond orders must be perceived"
        # deprotonation landed on the carboxylate oxygens
        assert sum(1 for a in mol.GetAtoms()
                   if a.GetAtomicNum() == 8 and a.GetFormalCharge() == -1) >= 3

    @pytest.mark.parametrize("smi,q", [
        ("C(CC(=O)[O-])(CC(=O)[O-])(C(=O)[O-])O", -3),   # citrate(3-)
        ("[NH3+]C(CCC(=O)[O-])C(=O)[O-]", -1),           # glutamate(-1)
        ("c1ccccc1C(=O)[O-]", -1),                       # benzoate
    ])
    def test_known_acids_unchanged(self, smi, q):
        """M10/M11-class acids: identical chemistry to the reference
        charged protonation graph (no regression from the cap path)."""
        mol, ref = _stripped(smi)
        t0 = time.monotonic()
        ok = determine_bond_orders_safely(mol, net_charge=q)
        assert ok
        assert time.monotonic() - t0 < 30.0
        assert sum(a.GetFormalCharge() for a in mol.GetAtoms()) == q
        assert Chem.MolToSmiles(Chem.RemoveHs(mol)) == ref


class TestFixCHardKill:
    def test_ladder_runs_in_subprocess(self, monkeypatch, tmp_path):
        """Vehicle proof: the ladder attempt MUST happen in a child
        process (in-process SIGALRM cannot interrupt RDKit C++)."""
        monkeypatch.setenv("BAT3_DBO_NO_CAP", "1")  # force the ladder
        monkeypatch.setenv("BAT3_BOND_ORDER_TIMEOUT_S", "60")
        mol, _ = _stripped("CC(=O)N")  # no odd comps: clean ladder case
        real_popen = subprocess.Popen
        calls = []
        with mock.patch("subprocess.Popen",
                        side_effect=lambda *a, **kw: (
                            calls.append(a) or real_popen(*a, **kw))):
            ok = determine_bond_orders_safely(mol, net_charge=0)
        assert ok
        assert calls, "ladder must run in a subprocess (hard-kill vehicle)"

    def test_ladder_core_exhausts_all_thirteen_charges(self):
        """W3 A5: the 13-charge exhaustion semantic now lives in
        _dbo_ladder_core (runs in the Fix-C child; mockable in-process).
        Preserves the wave-2 'ladder tries all 13, then False' coverage."""
        from unittest import mock as _mock
        from rdkit.Chem import rdDetermineBonds as _rdb
        from src_new.signatures.generators._perceive_cache import (
            _dbo_ladder_core)
        with _mock.patch.object(_rdb, "DetermineBondOrders",
                                side_effect=ValueError("nope")) as spy:
            mol = Chem.MolFromSmiles("CC")
            assert _dbo_ladder_core(mol, 0) is False
            assert spy.call_count == 13

    def test_timeout_kills_and_preserves_prestate(self, monkeypatch, caplog):
        """A hung ladder is killed at the shared budget; recorded as
        bond_order_timeout; parent mol still all-single (unchanged).
        W3.1 item 8: the worker is PERSISTENT and warm — a small ligand
        answers in milliseconds, so the hang is induced deterministically
        by SIGSTOPping the worker (the budget then expires on a reply
        that can never come; the whole group is killpg'd)."""
        import os as _os
        import signal as _signal
        monkeypatch.setenv("BAT3_DBO_NO_CAP", "1")
        # far below any possible ladder runtime -> deterministic timeout
        monkeypatch.setenv("BAT3_BOND_ORDER_TIMEOUT_S", "0.05")
        from src_new.signatures.generators import _perceive_cache as pc
        pc._reset_dbo_worker()
        worker = pc._get_dbo_worker()
        _os.kill(worker.proc.pid, _signal.SIGSTOP)  # deterministic hang
        mol, _ = _stripped("CC(=O)N")
        t0 = time.monotonic()
        import logging
        with caplog.at_level(logging.WARNING, logger="base"):
            ok = determine_bond_orders_safely(mol, net_charge=0)
        dt = time.monotonic() - t0
        assert not ok
        assert dt < 30.0, f"kill path took {dt:.1f}s"
        assert _all_single(mol), "killed ladder must leave the pre-state"
        assert any("bond_order_timeout" in r.getMessage()
                   for r in caplog.records), caplog.text


_M13_DRIVER = r"""
import json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])  # repo root
from src_new.pipeline_steps import build_load_and_export_tasks
from src_new.executor.executor import PipelineExecutor
from src_new.results.results_manager import ResultsManager
repo, wd, out_dir, results_path, pdb = sys.argv[1:6]
manager = ResultsManager(results_path, pipeline_name="m13-a5")
tasks = build_load_and_export_tasks()[:6]  # discover..generate_signatures
ex = PipelineExecutor(steps=tasks, results_manager=manager,
                      pipeline_name="m13-a5")
t0 = time.monotonic()
ex.run(working_directory=wd, output_directory=out_dir,
       input_kind="pdb", input_files={"structure": pdb})
print(json.dumps({"wall_s": time.monotonic() - t0}))
"""


@pytest.mark.skipif(not M13_PDB.exists(), reason="M13 fixture not present")
class TestM13Integration:
    def test_stages_1_to_6_under_60s(self, tmp_path):
        """Production failure: daptomycin hung >20 min inside
        DetermineBondOrders at ladder step 1. Contract: stages 1-6
        complete < 60 s; the LIG chemistry is daptomycin."""
        wd = tmp_path / "in"
        wd.mkdir()
        shutil.copy(M13_PDB, wd / "structure.pdb")
        results_path = tmp_path / "results.json"
        proc = subprocess.Popen(
            [sys.executable, "-c", _M13_DRIVER, str(REPO), str(wd),
             str(tmp_path / "out"), str(results_path), str(wd / "structure.pdb")],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            out, err = proc.communicate(timeout=60)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            pytest.fail("stages 1-6 did not finish within 60 s "
                        "(BH-049 spin class still present)")
        assert proc.returncode == 0, f"driver crashed:\n{err[-2000:]}"
        wall = json.loads(out.strip().splitlines()[-1])["wall_s"]
        assert wall < 60.0
        payload = json.loads(Path(results_path).read_text())
        assert payload["pipeline"]["status"] == "success", (
            payload.get("critical_errors"))
        data = payload.get("data", {})
        segs = data.get("universe", {}).get("segments", {})
        assert segs, "no segments in results"
        # daptomycin is the largest segment; check its chemistry
        big_name = max(
            segs, key=lambda n: (segs[n].get("properties", {}) or {})
            .get("atom_count_fragment", 0))
        sigs = (data.get("signatures", {}).get(big_name, {})
                .get("generated", {}))
        assert sigs, f"no signatures for segment {big_name!r}"
        mol = sigs.get("molecular_formula", {})
        formula = mol.get("formula") if isinstance(mol, dict) else mol
        assert formula == "C72H98N17O26", (big_name, mol)
        ik = sigs.get("inchi_key", {})
        key = ik.get("value") or ik.get("inchi_key") or ik if isinstance(
            ik, dict) else ik
        assert str(key).startswith("DOAKLVKFURWEDJ"), (big_name, ik)
