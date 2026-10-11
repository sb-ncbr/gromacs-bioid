"""Element ground-truth rule tests (user ruling 2026-10-11). No network.

Rule: for a segment whose molecule is a SINGLE atom, an ELEMENT identity hit
is ground truth -> final_confidence is lifted to 100 and the hit carries
ground_truth_override="element_monoatomic". Scope guards: only ELEMENT
identity hits on monoatomic molecules; chemistry gates (F7) untouched.
"""

from __future__ import annotations

import os, sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from unittest.mock import MagicMock, patch

import pytest

from src_new.config.loader import RunConfig
from src_new.verification.manager import (
    VerificationManager,
    _element_ground_truth,
    _monoatomic_atom_count,
)
from src_new.verification.models import VerificationScore


# --- helpers ---------------------------------------------------------------

def _mk_manager():
    """Manager with production confidence weights (0.4/0.4/0.2)."""
    cfg = MagicMock(spec=RunConfig)
    vc = MagicMock()
    vc.verify_top_n = 25
    vc.resolver_weight = 0.4
    vc.similarity_weight = 0.4
    vc.annotation_weight = 0.2
    vc.min_final_confidence = 30.0
    cfg.verification = vc
    reg = MagicMock()
    reg.get_fetcher.return_value = MagicMock()
    # Element similarity worker: bare elements corroborate themselves at 100
    # (mirrors prod behaviour of the atom path).
    worker = MagicMock()
    worker.verify.return_value = VerificationScore(
        kind="similarity", metric_name="element_self", raw_score=1.0, normalized_score=100.0
    )
    reg.get_applicable_workers.return_value = [worker]
    reg.get_scorer.return_value = None  # no annotation evidence for elements (prod truth)
    return VerificationManager(cfg, registry=reg)


def _mk_results(seg="seg_6_SOD", atom_count_fragment=1):
    results = MagicMock()

    def get_data(path, default=None):
        if path == "identifiers":
            return {seg: {}}
        if path == f"universe/segments/{seg}/properties":
            if atom_count_fragment is None:
                return default
            return {"atom_count_fragment": atom_count_fragment}
        return default
    results.get_data.side_effect = get_data
    results.data_exists.side_effect = lambda p: p == f"identifiers/{seg}"
    return results


def _mk_group(hit_type="identity", consensus=100.0):
    return {
        "signature": "Na",
        "signature_type": "element",
        "consensus_score": consensus,
        "source_resolvers": ["atom"],
        "hit_type": hit_type,
    }


def _verify(mgr, results, identifier, ident_type, group):
    with patch("src_new.verification.manager.collect_hits", return_value=[MagicMock()]), \
         patch("src_new.verification.manager.deduplicate_and_score",
               return_value={(identifier, ident_type): group}):
        return mgr.verify_all(results)


# --- manager-level behaviour ------------------------------------------------

def test_monoatomic_element_identity_lifts_to_100():
    """Na+ monoatomic ELEMENT identity -> confidence 100 + override flag."""
    mgr = _mk_manager()
    per = _verify(mgr, _mk_results(atom_count_fragment=1), "NA", "ELEMENT", _mk_group())
    hit = per["seg_6_SOD"][0]
    assert hit.is_verified is True
    assert hit.final_confidence == 100.0
    assert hit.ground_truth_override == "element_monoatomic"


def test_polyatomic_same_element_stays_on_weighted_path():
    """S8-like mono-element fragment (8 atoms) must NOT get the override."""
    mgr = _mk_manager()
    per = _verify(mgr, _mk_results(atom_count_fragment=8), "S", "ELEMENT", _mk_group())
    hit = per["seg_6_SOD"][0]
    assert hit.is_verified is True
    assert hit.final_confidence == 80.0   # 0.4*100 + 0.4*100, annotation unscored
    assert hit.ground_truth_override is None


def test_missing_universe_props_stays_conservative():
    """No atom-count information -> no override (conservative default)."""
    mgr = _mk_manager()
    per = _verify(mgr, _mk_results(atom_count_fragment=None), "NA", "ELEMENT", _mk_group())
    hit = per["seg_6_SOD"][0]
    assert hit.final_confidence == 80.0
    assert hit.ground_truth_override is None


def test_similarity_hit_type_excluded():
    """ELEMENT similarity listing on a monoatomic segment is not an assertion."""
    mgr = _mk_manager()
    per = _verify(mgr, _mk_results(atom_count_fragment=1), "NA", "ELEMENT",
                  _mk_group(hit_type="similarity", consensus=55.0))
    hit = per["seg_6_SOD"][0]
    assert hit.ground_truth_override is None


def test_chemical_ident_type_still_fingerprint_gated():
    """Chemistry is untouched: a CID on a monoatomic segment still needs the F7 gate."""
    mgr = _mk_manager()
    chem_group = {
        "signature": "Na",
        "signature_type": "element",
        "consensus_score": 100.0,
        "source_resolvers": ["name_ccd"],
        "hit_type": "identity",
    }
    # no skeleton_fp signature stored -> candidate fp unavailable
    per = _verify(mgr, _mk_results(atom_count_fragment=1), "923", "PUBCHEM_CID", chem_group)
    hit = per["seg_6_SOD"][0]
    assert hit.is_verified is False
    assert hit.rejection_reason == "fingerprint_unavailable"
    assert getattr(hit, "ground_truth_override", None) is None


# --- helper unit tests ------------------------------------------------------

@pytest.mark.parametrize("path_value,expected", [
    ({"atom_count_fragment": 1}, 1),
    ({"atom_count_fragment": 4}, 4),
    ({"atom_count_total": 3}, 3),
    ({}, None),
])
def test_monoatomic_atom_count(path_value, expected):
    results = MagicMock()
    results.get_data.side_effect = lambda p, default=None: (
        path_value if p == "universe/segments/X/properties" else default
    )
    assert _monoatomic_atom_count(results, "X") == expected


def test_element_ground_truth_guards():
    results = MagicMock()
    results.get_data.side_effect = lambda p, default=None: (
        {"atom_count_fragment": 1} if p == "universe/segments/X/properties" else default
    )
    assert _element_ground_truth(results, "X", "ELEMENT", "identity") is True
    assert _element_ground_truth(results, "X", "PUBCHEM_CID", "identity") is False
    assert _element_ground_truth(results, "X", "ELEMENT", "similarity") is False
