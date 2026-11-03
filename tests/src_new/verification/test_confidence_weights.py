"""Tests for v3.142 Phase 3: confidence weight normalization + provenance."""
from src_new.verification.manager import CONFIDENCE_FORMULA_VERSION, normalize_weights


# ------------------------------------------------------------ normalize_weights

def test_default_weights_pass_through():
    assert normalize_weights(0.4, 0.4, 0.2) == (0.4, 0.4, 0.2)


def test_unnormalized_weights_are_divided_by_sum():
    assert normalize_weights(0.5, 0.5, 0.5) == (1.0 / 3.0,) * 3


def test_all_zero_sum_falls_back_to_equal_thirds():
    assert normalize_weights(0.0, 0.0, 0.0) == (1.0 / 3.0,) * 3


def test_negative_and_nan_weights_are_clamped_to_zero():
    r, s, a = normalize_weights(-0.5, float("nan"), 0.4)
    assert (r, s, a) == (0.0, 0.0, 1.0)


def test_single_positive_weight_absorbs_all_mass():
    assert normalize_weights(0.0, 2.0, 0.0) == (0.0, 1.0, 0.0)


def test_effective_weights_always_sum_to_one():
    for raw in [(0.4, 0.4, 0.2), (0.5, 0.5, 0.5), (0.0, 0.0, 0.0),
                (-1.0, 0.1, 0.1), (1.0, 1.0, 1.0)]:
        assert abs(sum(normalize_weights(*raw)) - 1.0) < 1e-12


# ------------------------------------------------------------- meta provenance

def test_formula_version_constant_present():
    assert isinstance(CONFIDENCE_FORMULA_VERSION, str)
    assert CONFIDENCE_FORMULA_VERSION.startswith("v3.144"), \
        "c13 fix F3 bumped the blend semantics (unmeasured similarity re-weights)"
