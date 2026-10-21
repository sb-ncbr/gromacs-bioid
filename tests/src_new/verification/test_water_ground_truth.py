"""Water ground-truth rule tests (v3.140, V-36). No network.

Rule: for a segment typed WATER (fragments/segments record from analyze),
the skeleton fingerprint is degenerate in a specific way — every candidate
whose canonical smiles is water-equivalent yields skel == 1.0 (observed in
run b4813beb: 67 TIP3 hits "verified", all the same identity dressed in
different database records). The FIRST such hit is the water ground truth
(conf lift to 100, ground_truth_override="water_triatomic"); the rest are
duplicate records of the identity and become unverified with
rejection_reason="water_duplicate_identity". Non-water segments unchanged.
"""

from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from unittest.mock import MagicMock, patch

import pytest

from src_new.config.loader import RunConfig
from src_new.verification.manager import VerificationManager
from src_new.verification.models import VerificationScore


# --- helpers (mirrors test_element_ground_truth.py) --------------------------

def _mk_manager():
    cfg = MagicMock(spec=RunConfig)
    vc = MagicMock()
    vc.verify_top_n = 25
    vc.resolver_weight = 0.4
    vc.similarity_weight = 0.4
    vc.annotation_weight = 0.2
    vc.min_final_confidence = 30.0
    cfg.verification = vc
    reg = MagicMock()

    fetcher = MagicMock()
    fetcher.fetch.side_effect = lambda ident, ident_type: ident  # canonical == ident token
    reg.get_fetcher.return_value = fetcher

    worker = MagicMock()
    worker.verify.return_value = VerificationScore(
        kind="similarity", metric_name="idsm", raw_score=1.0, normalized_score=100.0
    )
    reg.get_applicable_workers.return_value = [worker]
    reg.get_scorer.return_value = None
    return VerificationManager(cfg, registry=reg)


def _mk_results(seg="seg_2_TIP3", seg_type="water"):
    results = MagicMock()

    def get_data(path, default=None):
        if path == "identifiers":
            return {seg: {}}
        if path == f"universe/segments/{seg}/properties":
            return {"atom_count_fragment": 3}
        if path == "fragments/segments":
            return [{"segment": seg, "type": seg_type, "copies": 12000, "atoms_per_copy": 3}]
        return default
    results.get_data.side_effect = get_data
    results.data_exists.side_effect = lambda p: p == f"identifiers/{seg}"
    return results


def _grp(atom_score=100.0):
    return {
        "signature": "O",
        "signature_type": "smiles",
        "consensus_score": 100.0,
        "source_resolvers": ["idsm_pubchem"],
        "hit_type": "identity",
    }


# canonical tokens -> skeleton sim for _chemical_corroboration patch
_SKEL = {"WATER_A": 1.0, "WATER_B": 1.0, "CID_A": 1.0, "NOT_WATER": 0.3}


def _chemical_stub(results, segment, canonical_signature):
    sim = _SKEL.get(canonical_signature)
    if sim is None:
        return None, "fingerprint_unavailable"
    return sim, "skelfp:v1"


def _verify(mgr, results, groups: dict):
    with patch("src_new.verification.manager.collect_hits", return_value=[MagicMock()]), \
         patch("src_new.verification.manager.deduplicate_and_score", return_value=groups), \
         patch("src_new.verification.manager._chemical_corroboration", side_effect=_chemical_stub):
        return mgr.verify_all(results)


def _hits(out, seg):
    return (out or {}).get(seg, [])


# --- tests -------------------------------------------------------------------

def test_water_segment_pins_first_identical_hit():
    mgr = _mk_manager()
    seg = "seg_2_TIP3"
    groups = {
        ("WATER_A", "PUBCHEM_CID"): _grp(),
        ("NOT_WATER", "CHEBI_ID"): _grp(),
        ("WATER_B", "CHEMBL_ID"): _grp(),
    }
    out = _verify(mgr, _mk_results(seg=seg, seg_type="water"), groups)
    hits = _hits(out, seg)
    by_id = {h.identifier: h for h in hits}

    pinned = by_id["WATER_A"]
    assert pinned.is_verified is True
    assert pinned.ground_truth_override == "water_triatomic"
    assert pinned.final_confidence == 100.0

    dupe = by_id["WATER_B"]
    assert dupe.is_verified is False
    assert dupe.rejection_reason == "water_duplicate_identity"

    other = by_id["NOT_WATER"]
    assert other.is_verified is False
    assert other.rejection_reason == "fingerprint_mismatch"


def test_non_water_segment_keeps_two_identical_verified():
    mgr = _mk_manager()
    seg = "seg_9_LIG"
    results = _mk_results(seg=seg, seg_type="small_molecule")
    groups = {
        ("WATER_A", "PUBCHEM_CID"): _grp(),
        ("WATER_B", "PUBCHEM_CID"): _grp(),
    }
    out = _verify(mgr, results, groups)
    hits = _hits(out, seg)
    assert sum(h.is_verified for h in hits) == 2
    assert all(h.ground_truth_override is None for h in hits)


def test_water_pin_requires_exact_skeleton_match():
    mgr = _mk_manager()
    seg = "seg_2_TIP3"
    groups = {("NOT_WATER", "PUBCHEM_CID"): _grp()}  # skel 0.3 — nothing to pin
    out = _verify(mgr, _mk_results(seg=seg, seg_type="water"), groups)
    hits = _hits(out, seg)
    assert hits[0].is_verified is False
    assert hits[0].ground_truth_override is None


def test_element_rule_unchanged_on_monoatomic():
    # coexistence guard: water segment-typing never fires for SOD (type=ion)
    mgr = _mk_manager()
    results = _mk_results(seg="seg_3_SOD", seg_type="ion")
    results.get_data.side_effect = None

    def get_data2(path, default=None):
        if path == "identifiers":
            return {"seg_3_SOD": {}}
        if path == "universe/segments/seg_3_SOD/properties":
            return {"atom_count_fragment": 1}
        if path == "fragments/segments":
            return [{"segment": "seg_3_SOD", "type": "ion", "copies": 120, "atoms_per_copy": 1}]
        return default
    results.get_data.side_effect = get_data2

    grp = {
        "signature": "Na", "signature_type": "element", "consensus_score": 100.0,
        "source_resolvers": ["atom"], "hit_type": "identity",
    }
    out = _verify(mgr, results, {("Na", "ELEMENT"): grp})
    hits = _hits(out, "seg_3_SOD")
    assert hits[0].is_verified is True
    assert hits[0].ground_truth_override == "element_monoatomic"
    assert hits[0].final_confidence == 100.0


# --- plateau-honesty (v3.140): deterministic 94% => None ---------------------

def test_plateau_confidence_emitted_as_none():
    """skel==1.0 + resolver capped at 100 + no ground-truth override is the
    F-07 deterministic plateau (94.0 for every member of a family) — the
    composed number carries zero per-hit information and must be None."""
    mgr = _mk_manager()
    seg = "seg_9_TOCL2"
    results = _mk_results(seg=seg, seg_type="lipid")
    results.get_data.side_effect = None

    def gd(path, default=None):
        if path == "identifiers":
            return {seg: {}}
        if path == f"universe/segments/{seg}/properties":
            return {"atom_count_fragment": 248}
        if path == "fragments/segments":
            return [{"segment": seg, "type": "lipid", "copies": 60, "atoms_per_copy": 248}]
        return default
    results.get_data.side_effect = gd
    out = _verify(mgr, results, {("CID_A", "PUBCHEM_CID"): _grp()})
    hit = _hits(out, seg)[0]
    assert hit.is_verified is True
    assert hit.final_confidence is None
    assert hit.ground_truth_override is None  # plateau is not a verdict


def test_ground_truth_override_keeps_its_100():
    # covered indirectly by test_water_segment_pins_first_identical_hit;
    # explicit guard that plateau nulling never touches overrides:
    mgr = _mk_manager()
    seg = "seg_2_TIP3"
    out = _verify(mgr, _mk_results(seg=seg), {("WATER_A", "PUBCHEM_CID"): _grp()})
    hit = _hits(out, seg)[0]
    assert hit.final_confidence == 100.0
    assert hit.ground_truth_override == "water_triatomic"


def test_non_plateau_confidence_preserved():
    """skel below 1.0 (but >= verify threshold) keeps a real composed value."""
    mgr = _mk_manager()
    seg = "seg_7_LIG"
    results = _mk_results(seg=seg, seg_type="lipid")
    results.get_data.side_effect = lambda path, default=None: (
        {seg: {}} if path == "identifiers"
        else {"atom_count_fragment": 40} if path == f"universe/segments/{seg}/properties"
        else [{"segment": seg, "type": "lipid", "copies": 1, "atoms_per_copy": 40}] if path == "fragments/segments"
        else default
    )
    with patch("src_new.verification.manager.collect_hits", return_value=[MagicMock()]), \
         patch("src_new.verification.manager.deduplicate_and_score",
               return_value={("CID_X", "PUBCHEM_CID"): _grp()}), \
         patch("src_new.verification.manager._chemical_corroboration",
               return_value=(0.9, "skelfp:v1")):
        hit = _hits(mgr.verify_all(results), seg)[0]
    assert hit.is_verified is True
    assert hit.final_confidence == 80.0  # 0.4*100(resolver) + 0.4*100(sim worker) + 0
