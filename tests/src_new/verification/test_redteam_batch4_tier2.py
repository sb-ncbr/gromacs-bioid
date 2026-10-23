"""Red-team batch-4 (5.8) — D-05/B-06 tier-2 fingerprint.

Empirical basis (probe 2026-10-23, structures fetched live from PubChem and
recorded in fixtures/d05/structures.json; RDKit TanimotoSimilarity on
hashed count-Morgan r3/4096/chiral):

    tier-1 collapses everything:  DPPC/DMPC 1.0, glucose/galactose 1.0,
                                  L/D-alanine 1.0, benzene/cyclohexane 1.0
    tier-2 (chosen params) separates all of them while keeping
    same-entity at 1.0.

Pins below are a GOLDEN TABLE: the measured separation values themselves
are the regression guard — any FP-parameter drift breaks them.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src_new.signatures.skeletize import from_smiles, skeleton_fp, tanimoto
from src_new.signatures.tier2fp import tier2_fp, tier2_key, tier2_tanimoto

FIXTURE = Path(__file__).parent / "fixtures" / "d05" / "structures.json"
_STRUCTURES = json.loads(FIXTURE.read_text())


def _mol(name: str):
    return from_smiles(_STRUCTURES[name]["smiles"])


def _t2(a: str, b: str) -> float:
    return tier2_tanimoto(tier2_fp(_mol(a)), tier2_fp(_mol(b)))


class TestGoldenSeparationTable:
    def test_same_entity_is_one(self):
        for name in ("DPPC", "glucose", "ATP", "water"):
            assert _t2(name, name) == pytest.approx(1.0, abs=1e-9)

    @pytest.mark.parametrize("pair,expected", [
        (("DPPC", "DMPC"), 0.9106),
        (("DPPC", "POPC"), 0.8392),
        (("palmitic", "stearic"), 0.8889),
        (("stearic", "oleic"), 0.5652),
        (("cholesterol", "cholestanol"), 0.5714),
        (("glucose", "galactose"), 0.8049),
        (("L-ala", "D-ala"), 0.7333),
    ])
    def test_homologues_and_stereoisomers_separated(self, pair, expected):
        """Every pair tier-1 calls identical must sit materially below 1.0
        — and at the MEASURED value (parameter-drift guard)."""
        assert _t2(*pair) == pytest.approx(expected, abs=5e-4)
        # and tier-1 really was blind here (gate semantics documented)
        skel = tanimoto(skeleton_fp(_mol(pair[0])), skeleton_fp(_mol(pair[1])))
        assert skel == pytest.approx(1.0, abs=1e-9)

    @pytest.mark.parametrize("pair,expected", [
        (("ATP", "ADP"), 0.8476),
        (("ATP", "ITP"), 0.7025),
    ])
    def test_near_variants_below_tier1_not_above(self, pair, expected):
        """Phosphate/base variants differ in heavy skeleton already — tier-2
        must stay BELOW tier-1 for them, never above (sharper, not looser)."""
        assert _t2(*pair) == pytest.approx(expected, abs=5e-4)
        skel = tanimoto(skeleton_fp(_mol(pair[0])), skeleton_fp(_mol(pair[1])))
        assert _t2(*pair) < skel

    @pytest.mark.parametrize("pair", [
        ("water", "hydroxide"), ("water", "hydronium"), ("ammonia", "ammonium"),
        ("benzene", "cyclohexane"),
    ])
    def test_charge_and_ring_variants_fully_separated(self, pair):
        assert _t2(*pair) == pytest.approx(0.0, abs=1e-9)

    def test_tier2_key_discriminates_within_skeleton_family(self):
        assert tier2_key(_mol("DPPC")) != tier2_key(_mol("DMPC"))
        # stable across re-parse (content-derived, deterministic)
        assert tier2_key(_mol("DPPC")) == tier2_key(
            from_smiles(_STRUCTURES["DPPC"]["smiles"]))
        assert re.fullmatch(r"[0-9a-f]{8}", tier2_key(_mol("DPPC")))


class TestClassIdTier2Discriminator:
    def test_chemical_class_id_gains_t2_suffix(self):
        from src_new.verification.manager import _equivalence_class_id
        cid_dppc = _equivalence_class_id(
            "PUBCHEM_CID", "452110", "resname",
            _STRUCTURES["DPPC"]["smiles"], None)
        cid_dmpc = _equivalence_class_id(
            "PUBCHEM_CID", "5459377", "resname",
            _STRUCTURES["DMPC"]["smiles"], None)
        assert cid_dppc.startswith("skeleton:")
        assert "#t2:" in cid_dppc
        assert cid_dppc != cid_dmpc  # homologues must NOT share a class
        # deterministic for the same record
        assert cid_dppc == _equivalence_class_id(
            "PUBCHEM_CID", "452110", "resname",
            _STRUCTURES["DPPC"]["smiles"], None)


class TestChemicalCorroborationTier2:
    def test_corroboration_returns_tier2(self, tmp_path):
        from src_new.results.results_manager import ResultsManager
        from src_new.verification.manager import _chemical_corroboration
        from src_new.signatures.skeletize import fp_to_hex

        results = ResultsManager(tmp_path / "results.json")
        dmpc = _mol("DMPC")
        results.set_data("signatures/SEG1/generated/smiles",
                         _STRUCTURES["DMPC"]["smiles"])
        results.set_data("signatures/SEG1/generated/skeleton_fp",
                         f"skelfp:v1:{fp_to_hex(skeleton_fp(dmpc))}")
        sim, method, t2 = _chemical_corroboration(
            results, "SEG1", _STRUCTURES["DPPC"]["smiles"])
        assert sim == pytest.approx(1.0, abs=1e-9)   # tier-1 gate: same skeleton
        assert method == "skelfp:v1"
        assert t2 == pytest.approx(0.9106, abs=5e-4)  # tier-2: homologue, not same


class TestRerankTier2PreRank:
    def test_tier2_leads_within_skeleton_equal_family(self):
        from src_new.verification.manager import _structure_rerank_groups
        groups = [
            (("5459377", "PUBCHEM_CID"), {"consensus_score": 100.0}),  # DMPC
            (("452110", "PUBCHEM_CID"), {"consensus_score": 50.0}),   # DPPC
        ]
        skel = {("5459377", "PUBCHEM_CID"): 1.0, ("452110", "PUBCHEM_CID"): 1.0}
        t2 = {("5459377", "PUBCHEM_CID"): 0.9106, ("452110", "PUBCHEM_CID"): 1.0}
        out = _structure_rerank_groups(groups, skel, 0.7, t2)
        # exact-structure record wins the pre-rank despite lower consensus
        assert out[0][0] == ("452110", "PUBCHEM_CID")

    def test_raise_only_gate_still_tier1(self):
        from src_new.verification.manager import _structure_rerank_groups
        groups = [
            (("1", "PUBCHEM_CID"), {"consensus_score": 100.0}),
            (("2", "PUBCHEM_CID"), {"consensus_score": 50.0}),
        ]
        skel = {("1", "PUBCHEM_CID"): 0.3, ("2", "PUBCHEM_CID"): 0.2}
        t2 = {("1", "PUBCHEM_CID"): 0.0, ("2", "PUBCHEM_CID"): 1.0}
        out = _structure_rerank_groups(groups, skel, 0.7, t2)
        # below the tier-1 threshold tier-2 must NOT reorder anything
        assert [k for k, _m in out] == [("1", "PUBCHEM_CID"), ("2", "PUBCHEM_CID")]


class TestFidelityKeyTier2Slot:
    def test_t2_breaks_ties_after_identity(self):
        from src_new.verification.manager import _fidelity_order_key
        from src_new.verification.models import VerifiedHit

        def _h(iid, t2):
            return VerifiedHit(
                identifier=iid, ident_type="PUBCHEM_CID", database="pubchem",
                resolver_score=100.0, similarity_score=None,
                annotation_quality_score=None, final_confidence=70.0,
                supporting_evidence_count=2, is_verified=True,
                skeleton_sim=1.0, hit_type="similarity",
                skeleton_t2_sim=t2)
        hi, lo, none_ = _h("1", 1.0), _h("2", 0.91), _h("3", None)
        assert _fidelity_order_key(hi) < _fidelity_order_key(lo)
        assert _fidelity_order_key(lo) < _fidelity_order_key(none_)


class TestManagerStoresTier2:
    def test_stored_hit_carries_t2(self, tmp_path):
        """End-to-end: chemical identity with same-skeleton canonical ->
        verified, skeleton_sim 1.0, skeleton_t2_sim = measured homologue
        value."""
        import time
        from types import SimpleNamespace
        from src_new.results.results_manager import ResultsManager
        from src_new.verification.manager import VerificationManager
        from src_new.config.loader import RunConfig
        from src_new.signatures.skeletize import fp_to_hex

        class F:
            def supports(self, _it):
                return True
            def fetch(self, _nid, _it):
                return _STRUCTURES["DPPC"]["smiles"]

        mgr = VerificationManager.__new__(VerificationManager)
        mgr._registry = SimpleNamespace(
            get_fetcher=lambda ident_type, signature_type=None: F(),
            get_applicable_workers=lambda *a, **k: [],
            get_scorer=lambda *a, **k: None)
        mgr._verification_config = RunConfig().verification

        results = ResultsManager(tmp_path / "results.json")
        results.set_data("identifiers/SEG1/genA/res0", {
            "signature": "DMPC", "hit_type": "identity",
            "hits": ["5459377"], "ident_type": "PUBCHEM_CID",
            "signature_type": "resname"})
        results.set_data("signatures/SEG1/generated/smiles",
                         _STRUCTURES["DMPC"]["smiles"])
        results.set_data("signatures/SEG1/generated/skeleton_fp",
                         f"skelfp:v1:{fp_to_hex(skeleton_fp(_mol('DMPC')))}")
        mgr.verify_all(results, deadline_epoch=time.time() + 60)
        stored = results.get_data("verification/SEG1/verified_hits")[0]
        assert stored["is_verified"] is True
        assert stored["skeleton_sim"] == pytest.approx(1.0, abs=1e-9)
        assert stored["skeleton_t2_sim"] == pytest.approx(0.9106, abs=5e-4)
        assert "#t2:" in stored["equivalence_class_id"]
