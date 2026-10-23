"""Batch-3 4.1 — B-14: perceive chemistry ONCE per fragment (cached Mol),
identical outputs, fail-fast family errors, soft timeout."""
from __future__ import annotations

import os
import time

import numpy as np
import MDAnalysis as mda
import pytest
from rdkit.Chem import rdDetermineBonds


def _acetate_fragment():
    """CH3COO- -like bonded fragment: 8 atoms, 6 bonds, one segid."""
    n = 8
    u = mda.Universe.empty(n, n_residues=1, n_segments=1,
                           atom_resindex=[0] * n, trajectory=True)
    # C C O O H H H H
    u.add_TopologyAttr("elements", ["C", "C", "O", "O", "H", "H", "H", "H"])
    u.add_TopologyAttr("names", [f"A{i}" for i in range(n)])
    u.add_TopologyAttr("resnames", ["ACT"])
    u.add_TopologyAttr("resids", [1])
    u.add_TopologyAttr("segids", ["SEG"])
    u.add_bonds([(0, 1), (1, 2), (1, 3), (0, 4), (0, 5), (0, 6)])
    u.atoms.positions = np.array([
        [0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [2.1, 0.9, 0.0], [2.1, -0.9, 0.0],
        [-0.5, 0.9, 0.0], [-0.5, -0.9, 0.0], [-0.5, 0.0, 0.9],
    ] + [[0.0, 0.0, 0.0]], dtype=np.float32)[:n]
    return u.atoms


def _instance(fragment):
    from src_new.molecules.instances import MoleculeInstance
    return MoleculeInstance(instance_id="inst0", atom_indices=list(fragment.indices))


def _chem_generators():
    from src_new.config.loader import SignaturesConfig
    from src_new.signatures.generators.smiles import (
        SimpleSmilesGenerator, SimpleSmilesGeneratorNoSanitize)
    from src_new.signatures.generators.inchi import InchiKeyGenerator
    from src_new.signatures.generators.selfies import SelfiesGenerator
    cfg = SignaturesConfig()
    return [SimpleSmilesGenerator(cfg), SimpleSmilesGeneratorNoSanitize(cfg),
            InchiKeyGenerator(cfg), SelfiesGenerator(cfg)]


@pytest.fixture(autouse=True)
def _clear_cache():
    from src_new.signatures.generators import _perceive_cache as pc
    pc.clear_cache()
    yield
    pc.clear_cache()


class TestB14PerceiveOnce:
    def test_determine_bond_orders_called_once_per_family(self, monkeypatch):
        """B-14: families (smiles-class; inchi/selfies) each perceive at most
        once per fragment — today every generator pays its own build."""
        calls = {"dbo": 0}
        real_dbo = rdDetermineBonds.DetermineBondOrders

        def spy(*a, **k):
            calls["dbo"] += 1
            return real_dbo(*a, **k)

        monkeypatch.setattr(rdDetermineBonds, "DetermineBondOrders", spy)
        frag = _acetate_fragment()
        inst = _instance(frag)
        results = {}
        for gen in _chem_generators():
            results[gen.name] = gen._generate(inst, frag, None)
        assert any(results.values()), results
        assert calls["dbo"] <= 2, (
            f"B-14: {calls['dbo']} perceptions for one fragment — the mol cache "
            "is not effective (families: smiles-class, inchi/selfies)")

    def test_cache_off_matches_cache_on(self, monkeypatch):
        """Behavior-identical: with caching disabled every generator must
        produce the exact same strings as with caching enabled."""
        outs = {}
        for mode in ("off", "on"):
            monkeypatch.setenv("BAT3_PERCEIVE_CACHE_OFF", "1" if mode == "off" else "0")
            from src_new.signatures.generators import _perceive_cache as pc
            pc.clear_cache()
            frag = _acetate_fragment()
            inst = _instance(frag)
            outs[mode] = {g.name: g._generate(inst, frag, None)
                          for g in _chem_generators()}
        assert outs["off"] == outs["on"], (
            {k: (outs["off"][k], outs["on"][k]) for k in outs["off"]
             if outs["off"][k] != outs["on"][k]})

    def test_build_error_is_cached_and_fail_fast(self, monkeypatch):
        """First family member pays the (timed-out) build; every later member
        re-raises the SAME cached error without rebuilding."""
        from src_new.signatures.generators import _perceive_cache as pc

        frag = _acetate_fragment()
        called = {"n": 0}

        def sleepy_builder():
            called["n"] += 1
            time.sleep(2)
            raise AssertionError("must not complete")

        with pytest.raises(pc.PerceiveTimeoutError):
            pc.build_once_cached(frag, "fam", sleepy_builder, timeout_s=1)
        with pytest.raises(pc.PerceiveTimeoutError):
            pc.build_once_cached(frag, "fam", sleepy_builder, timeout_s=1)
        assert called["n"] == 1, "family error was not cached/fail-fast"
