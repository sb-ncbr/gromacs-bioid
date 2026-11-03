"""c13 fix F3: unmeasured similarity must re-weight, never zero (manager blend),
and must surface as the distinct label "similarity_unmeasured".

Corpus evidence: a UniProt 500 on entry 10187 zeroed the GT identity hit's
similarity term (confidence 84 -> 44, rank 1 -> 15). With F3 the term is left
UNMEASURED and _compose_confidence re-weights over the measured terms, the
same treatment the annotation term got in red-team wave-2 item 1c.
"""

from __future__ import annotations

import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src_new.verification.manager import CONFIDENCE_FORMULA_VERSION, _compose_confidence


def test_all_terms_measured_matches_weighted_sum():
    # w sum == 1 pre-normalized, so num/den == num
    c = _compose_confidence(0.4, 0.4, 0.2, 80.0, 90.0, 70.0)
    assert abs(c - (0.4 * 80 + 0.4 * 90 + 0.2 * 70)) < 1e-9


def test_unmeasured_similarity_reweights_not_zeros():
    measured = _compose_confidence(0.4, 0.4, 0.2, 80.0, 90.0, 70.0)
    unmeasured = _compose_confidence(0.4, 0.4, 0.2, 80.0, None, 70.0)
    # re-weighted: (0.4*80 + 0.2*70) / 0.6 == 76.67 — NOT 0.4*80+0.4*0+0.2*70=46
    assert abs(unmeasured - (0.4 * 80 + 0.2 * 70) / 0.6) < 1e-9
    assert unmeasured > measured * 0.9, "identity-hit confidence must not collapse"


def test_unmeasured_annotation_still_reweights():
    c = _compose_confidence(0.4, 0.4, 0.2, 80.0, 90.0, None)
    assert abs(c - (0.4 * 80 + 0.4 * 90) / 0.8) < 1e-9


def test_both_unmeasured_falls_back_to_resolver_only():
    c = _compose_confidence(0.4, 0.4, 0.2, 80.0, None, None)
    assert abs(c - 80.0) < 1e-9


def test_measured_zero_stays_zero():
    c = _compose_confidence(0.4, 0.4, 0.2, 80.0, 0.0, 70.0)
    assert abs(c - (0.4 * 80 + 0.2 * 70)) < 1e-9


def test_formula_version_bumped_for_c13_fix():
    assert CONFIDENCE_FORMULA_VERSION == "v3.144.0"


# ---------------------------------------------------------------------------
# Reviewer narrowing (c13 re-check): the re-weight applies ONLY to a
# transient outage. A definitive failure (404/obsolete accession) or
# no_worker keeps the pre-F3 measured 0.0 — re-weighting those would raise
# identity hits on dead accessions.
# ---------------------------------------------------------------------------

def _run_blend_case(tmp_path, fetch_behavior):
    """One identity UniProt group, NO verification workers; the canonical
    fetch behaves per fetch_behavior (steady string = definitive path,
    raising TransientFetchError = outage path)."""
    import time
    from types import SimpleNamespace
    from unittest.mock import patch, MagicMock

    from src_new.config.loader import RunConfig
    from src_new.results.results_manager import ResultsManager
    from src_new.verification.dedup import RawHit, deduplicate_and_score
    from src_new.verification.manager import VerificationManager

    class _F:
        def supports(self, _it):
            return True

        def fetch(self, _nid, _it):
            return fetch_behavior()

    mgr = VerificationManager.__new__(VerificationManager)
    mgr._registry = SimpleNamespace(
        get_fetcher=lambda ident_type, signature_type=None: _F(),
        get_applicable_workers=lambda st, it: [],
        get_scorer=lambda *a, **k: None)
    mgr._verification_config = RunConfig().verification

    groups = deduplicate_and_score([
        RawHit("P00698", "UNIPROT_ID", "blast_uniprot", 100.0,
               "MKVLAAAA", "residue_sequence_protein", "identity")])
    results = ResultsManager(tmp_path / "r.json")
    results.set_data("identifiers/SEG1/genA/res0", {
        "signature": "MKVLAAAA", "hit_type": "identity", "hits": ["P00698"],
        "ident_type": "UNIPROT_ID",
        "signature_type": "residue_sequence_protein"})
    with patch("src_new.verification.manager.collect_hits",
               return_value=[MagicMock()]), \
         patch("src_new.verification.manager.deduplicate_and_score",
               return_value=groups):
        mgr.verify_all(results, deadline_epoch=time.time() + 60)
    return results.get_data("verification/SEG1/verified_hits")[0]


def test_no_worker_without_transient_keeps_measured_zero(tmp_path):
    """No worker, canonical fetched fine: the similarity term is a measured
    0.0 (pre-F3 behavior). Identity still verifies without corroboration
    (F-17), but the confidence is the DRAGGED-DOWN value
    (1/3*50 + 1/3*0)/(2/3) == 25 — not the re-weighted resolver-only 50."""
    hit = _run_blend_case(tmp_path, lambda: "MKVLAAAA")
    assert hit["verified_without_corroboration"] is True
    assert hit["final_confidence"] == 25.0, \
        "no_worker must keep the measured 0.0, not re-weight to resolver-only"


def test_transient_outage_reweights_to_resolver_only(tmp_path):
    """Transient outage with no worker: the term is unmeasured, the blend
    re-weights — confidence falls back to the resolver belief (50)."""
    import pytest as _pytest
    from src_new.verification.base import TransientFetchError

    def boom():
        raise TransientFetchError("HTTP 503")

    hit = _run_blend_case(tmp_path, boom)
    assert hit["verified_without_corroboration"] is True
    assert hit["final_confidence"] == _pytest.approx(50.0)
