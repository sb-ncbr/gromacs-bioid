"""W3.1 P24 follow-up: glycans skip bond-order determination; run-level
DBO ladder cap (~240 s) as a safety net.

Why the 1IGT glycans reached DBO at all: the SMILES generator has
skipped carbohydrates since wave-2 item 8d (the 1FC1 hang class), but
the inchi/selfies family build (build_once_family_mol) did not — so the
E/F glycan segments ran the full charge ladder through the InChI
generator, timed out at the budget, and their InChIKeys were computed
from the fallback (all-single) mol anyway. Live evidence: the E/F keys
are IDENTICAL between the W3 partial sweep (120 s cap) and the W3.1
sweep (300 s cap) — GRCWTHDYLSSDQD-UHFFFAOYSA-N — i.e. the DBO run
contributes nothing while burning 2 x 300 s and pushing the stage to
600.6 s (gate limit: 300 s).

Fix: (a) the family build takes skip_bond_orders and the InChI
generator passes it for CARBOHYDRATE instances (the glycan path —
glycan_composition — carries the identity); (b) selfies gets the same
carbohydrate guard smiles has (its attempt fails on the unsanitized
mol anyway); (c) a run-level DBO ladder cap (~240 s,
BAT3_BOND_ORDER_RUN_CAP_S) so no case can burn multiple full budgets —
charge-less NAD (~210 s, single ligand) still fits.
"""

from __future__ import annotations

import logging
import types
from unittest import mock

import pytest

rdkit = pytest.importorskip("rdkit")

P24 = ("/home/tomsko/work/bat3_article_reviews/bioid_bughunt/"
       "testcases/P24_1igt_antibody/input")


def _instance(mtype):
    return types.SimpleNamespace(instance_id="t", molecule_type=mtype)


def _fragment(resnames):
    return types.SimpleNamespace(
        residues=types.SimpleNamespace(resnames=resnames),
        segids=["C"],
    )


class TestSelfiesCarbohydrateGuard:
    def test_carbohydrate_instance_not_applicable(self):
        """Mirror of the smiles item-8d guard (selfies never got it)."""
        from src_new.molecules.instances import MoleculeType
        from src_new.signatures.generators.selfies import (
            SelfiesGenerator)
        from src_new.config.loader import SignaturesConfig
        gen = SelfiesGenerator(SignaturesConfig())
        assert gen._is_applicable(
            _instance(MoleculeType.CARBOHYDRATE), _fragment(["NAG"]),
            None) is False


class TestFamilyBuildSkipsDbo:
    def test_skip_bond_orders_never_calls_dbo(self, monkeypatch):
        """skip_bond_orders=True: the family build must not run the
        bond-order path at all (determine_bond_orders_safely untouched).
        RED at HEAD: no skip_bond_orders parameter existed."""
        from unittest import mock
        from src_new.signatures.generators import _perceive_cache as pc
        # a real 2-atom fragment is enough — the DBO call is what is
        # asserted, not the mol content
        frag = types.SimpleNamespace(
            atoms=types.SimpleNamespace(
                indices=[0, 1],
                elements=["C", "C"],
            ),
            bonds=types.SimpleNamespace(indices=[]),
        )
        monkeypatch.setattr(
            pc, "_external_cut_counts", lambda f: {}, raising=False)
        monkeypatch.setattr(
            pc, "_bonds_into", lambda *a, **k: None, raising=False)
        with mock.patch.object(
                pc, "determine_bond_orders_safely",
                side_effect=AssertionError("must not be called")) as spy:
            mol = pc.build_once_family_mol(frag, skip_bond_orders=True)
        assert spy.call_count == 0
        assert mol.GetNumAtoms() == 2

    def test_inchi_generator_skips_dbo_for_carbohydrates(self):
        """The InChI generator passes skip_bond_orders=True for
        CARBOHYDRATE instances — RED at HEAD: no skip, the glycan
        burned the full ladder budget through this generator."""
        from unittest import mock
        from src_new.molecules.instances import MoleculeType
        from src_new.signatures.generators import inchi as inchi_mod
        from src_new.signatures.generators import _perceive_cache as pc
        from src_new.config.loader import SignaturesConfig
        captured = {}
        real = pc.build_once_family_mol

        def spy(fragment, skip_bond_orders=False):
            captured["skip"] = skip_bond_orders
            return real(fragment, skip_bond_orders=True)

        def cached(frag, fam, builder, timeout_s=0):
            return builder()

        with mock.patch.object(inchi_mod, "build_once_family_mol", spy), \
                mock.patch.object(inchi_mod, "build_once_cached", cached), \
                mock.patch.object(
                    inchi_mod, "assign_stereo_from_3d",
                    lambda m, f: None):
            gen = inchi_mod.InchiKeyGenerator(SignaturesConfig())
            # minimal fragment for the family build (atoms only)
            frag = types.SimpleNamespace(
                atoms=types.SimpleNamespace(
                    indices=[0, 1], elements=["C", "C"]),
                bonds=types.SimpleNamespace(indices=[]))
            with mock.patch.object(
                    pc, "_external_cut_counts", lambda f: {}), \
                 mock.patch.object(
                    pc, "_bonds_into", lambda *a, **k: None):
                gen._generate(
                    _instance(MoleculeType.CARBOHYDRATE), frag, None)
        assert captured["skip"] is True, (
            "the InChI generator must skip bond orders for carbohydrates")


class TestRunLevelCap:
    def test_cap_default_and_env(self, monkeypatch):
        from src_new.signatures.generators import _perceive_cache as pc
        monkeypatch.delenv("BAT3_BOND_ORDER_RUN_CAP_S", raising=False)
        assert pc._dbo_run_cap_s() == 240.0
        monkeypatch.setenv("BAT3_BOND_ORDER_RUN_CAP_S", "37")
        assert pc._dbo_run_cap_s() == 37.0

    def test_exhausted_budget_skips_ladder(self, monkeypatch, caplog):
        """With the run-level cap spent, the ladder is skipped outright
        (no worker round-trip, no budget burn) and the caller continues
        without bond orders. RED at HEAD: no run-level cap existed."""
        from src_new.signatures.generators import _perceive_cache as pc
        from rdkit import Chem
        monkeypatch.setenv("BAT3_DBO_NO_CAP", "1")
        monkeypatch.delenv("BAT3_BOND_ORDER_RUN_CAP_S", raising=False)
        pc.dbo_run_budget_reset()
        # spend the whole run-level budget up front
        with pc._dbo_run_lock:
            pc._dbo_run_elapsed_s = 1e6
        try:
            with mock.patch.object(
                    pc, "_get_dbo_worker",
                    side_effect=AssertionError("must not spawn")) as spawn:
                with caplog.at_level(logging.WARNING, logger="base"):
                    ok = pc.determine_bond_orders_safely(
                        Chem.MolFromSmiles("CC"))
        finally:
            pc.dbo_run_budget_reset()
        assert ok is False
        assert spawn.call_count == 0
        assert any("bond_order_run_budget_exhausted" in r.getMessage()
                   for r in caplog.records), caplog.text

    def test_reset_restores_budget(self, monkeypatch):
        from src_new.signatures.generators import _perceive_cache as pc
        monkeypatch.delenv("BAT3_BOND_ORDER_RUN_CAP_S", raising=False)
        pc.dbo_run_budget_reset()
        assert pc._dbo_run_remaining_s() == 240.0
        with pc._dbo_run_lock:
            pc._dbo_run_elapsed_s = 239.0
        assert pc._dbo_run_remaining_s() == 1.0
        pc.dbo_run_budget_reset()
        assert pc._dbo_run_remaining_s() == 240.0


class TestP24EndToEnd:
    def test_p24_identifiers_unchanged_and_fast(self, tmp_path):
        """REAL 1IGT corpus case through stages 0-5: the glycan segments
        keep their identifiers (InChIKey + glycan_composition, pinned
        to the pre-fix values) and generate_signatures no longer burns
        2 x 300 s of ladder budget. RED at HEAD: 600.6 s stage time."""
        import importlib
        import shutil
        from pathlib import Path
        w31 = importlib.import_module(
            "tests.src_new.loader.test_chainless_topology_w31")
        src = tmp_path / "src"
        src.mkdir()
        for f in Path(P24).iterdir():
            shutil.copy(f, src / f.name)
        data = w31._run_results(src, tmp_path, input_kind="pdb")
        segs = data.get("signatures") or {}
        glycan = None
        for s, p in segs.items():
            gen = (p or {}).get("generated") or {}
            if gen.get("glycan_composition"):
                glycan = gen
                break
        assert glycan is not None, "glycan segment missing"
        assert glycan.get("inchi_key") == "GRCWTHDYLSSDQD-UHFFFAOYSA-N", (
            "the glycan InChIKey must stay identical to the "
            "timeout-computed value")
        assert glycan.get("glycan_composition") == "Hex(4)HexNAc(4)X(1)"
        # the gate's own metric: generate_signatures stage wall time
        # (user acceptance: < 300 s; was 600.6 s)
        import json as _json
        from datetime import datetime
        payload = _json.loads(
            (tmp_path / "results.json").read_text())
        starts, stage_s = {}, 0.0
        for e in (payload.get("events") or []):
            if e.get("kind") == "step_start" and e.get(
                    "task_id") == "generate_signatures":
                starts[1] = e["timestamp"]
            elif (e.get("kind") == "step_finish"
                  and e.get("task_id") == "generate_signatures"
                  and 1 in starts):
                stage_s = (
                    datetime.fromisoformat(e["timestamp"])
                    - datetime.fromisoformat(starts[1])).total_seconds()
        assert stage_s < 300.0, (
            f"generate_signatures took {stage_s:.0f}s (gate limit 300 s; "
            f"was 600.6 s with 2 x 300 s glycan ladder burn)")
