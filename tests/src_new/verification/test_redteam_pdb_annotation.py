"""Red-team wave-2 (item 1): PDB annotation scorer — the refine-list type bug.

Root cause: RCSB core/entry `refine` is a LIST of objects; the scorer called
`.get()` on it (outside its try), raised AttributeError, manager swallowed it,
and every entry with a refine block (i.e. essentially every X-ray structure)
silently lost its annotation score (annotation_quality_score null → confidence
formula taxed 0.2·0). Fixes: refine/exptl handled as dict-or-list, the whole
parse inside the try, failure returns None (unknown) instead of 0.0, and the
manager re-weights the remaining terms when the annotation is unknown.

Score contract (base 20 + resolution 20 + r_free 20 + method 20 + models>1 10
+ polymer>0 10, capped 100): X-ray single-model → 90 with r_free; cryo-EM →
70; NMR ensemble → 60 — matching the observed non-null d13b values.
"""

from unittest.mock import Mock, patch

from src_new.verification.manager import _compose_confidence
from src_new.verification.scorers.pdb_scorer import PDBAnnotationScorer


def _payload(*, resolution=None, refine=None, method=None, deposited=1, polymer=1):
    exptl = [] if method is None else [{"method": method}]
    return {
        "rcsb_entry_info": {
            "resolution_combined": resolution,
            "deposited_model_count": deposited,
            "polymer_entity_count": polymer,
        },
        "refine": refine,
        "exptl": exptl,
    }


def _scored(payload):
    with patch(
        "src_new.verification.scorers.pdb_scorer.rcsb_cache.get_cached"
    ) as mock_get:
        resp = Mock()
        resp.json.return_value = payload
        mock_get.return_value = resp
        return PDBAnnotationScorer().score("1ABC", "PDB_ID")


class TestPDBScorerRefineShape:
    def test_xray_refine_list_scores_90_with_rfree(self):
        q = _scored(_payload(
            resolution=[1.6],
            refine=[{"ls_rfactor_rfree": 0.21}],   # the real RCSB shape
            method="X-RAY DIFFRACTION",
        ))
        assert q is not None
        assert q.score == 90.0
        assert "r_free" in q.signals

    def test_refine_legacy_dict_shape_also_scored(self):
        q = _scored(_payload(
            resolution=[2.0],
            refine={"ls_rfactor_rfree": 0.25},     # defensive: dict tolerated
        ))
        assert q is not None
        assert "r_free" in q.signals
        assert q.score == 70.0  # base + resolution + r_free + polymer

    def test_refine_present_without_rfree_no_signal_no_crash(self):
        # the old code crashed on ANY refine list — including ones without
        # r_free (e.g. 22DR); must score defensively
        q = _scored(_payload(resolution=[1.9], refine=[{"other": 1}], method="X-RAY DIFFRACTION"))
        assert q is not None
        assert q.score == 70.0
        assert "r_free" not in q.signals

    def test_cryo_em_scores_70(self):
        q = _scored(_payload(
            resolution=[3.1],
            refine=None,
            method="ELECTRON MICROSCOPY",
        ))
        assert q is not None
        assert q.score == 70.0   # base + resolution + method + polymer

    def test_nmr_ensemble_scores_60(self):
        q = _scored(_payload(
            resolution=None,
            refine=None,
            method="SOLUTION NMR",
            deposited=20,
        ))
        assert q is not None
        assert q.score == 60.0   # base + method + deposited + polymer

    def test_malformed_payload_returns_none_unknown(self):
        # non-dict root → parse failure → UNKNOWN (None), not a real 0.0
        with patch(
            "src_new.verification.scorers.pdb_scorer.rcsb_cache.get_cached"
        ) as mock_get:
            resp = Mock()
            resp.json.return_value = ["not", "an", "entry"]
            mock_get.return_value = resp
            assert PDBAnnotationScorer().score("0BAD", "PDB_ID") is None


class TestComposeConfidenceUnknownAnnotation:
    """None annotation = unknown → re-weight over measured terms (item 1c)."""

    def test_unknown_reweights(self):
        # 0.4/0.4/0.2 weights, belief 50, similarity 100: 60 known-good
        # becomes (0.4·50 + 0.4·100) / 0.8 = 75 — not 60 (the 0-tax).
        v = _compose_confidence(0.4, 0.4, 0.2, 50.0, 100.0, None)
        assert abs(v - 75.0) < 1e-9

    def test_real_zero_keeps_weight(self):
        v = _compose_confidence(0.4, 0.4, 0.2, 50.0, 100.0, 0.0)
        assert abs(v - 60.0) < 1e-9

    def test_present_annotation_classic_formula(self):
        v = _compose_confidence(0.4, 0.4, 0.2, 50.0, 100.0, 90.0)
        assert abs(v - 78.0) < 1e-9

    def test_zero_weight_guard(self):
        assert _compose_confidence(0.0, 0.0, 1.0, 50.0, 50.0, None) == 0.0
