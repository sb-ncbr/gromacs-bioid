"""Tests for the v3.142 R-a resolver-belief term (dedup.resolver_belief).

Calibrated constants are corpus-fixed facts (κ=1/3, ρ=1/2, user-approved
2026-10-23; evidence .tmp/CALIBRATION_v3142.md): these tests pin the agreed
value semantics so a future "tweak" is a deliberate change, not drift.
"""
from src_new.verification.dedup import (
    BELIEF_KAPPA,
    BELIEF_RHO,
    RawHit,
    deduplicate_and_score,
    resolver_belief,
)


def _hit(identifier="123", ident_type="PUBCHEM_CID", resolver="pubchem_sim",
         score=80.0, hit_type="similarity"):
    return RawHit(
        identifier=identifier,
        ident_type=ident_type,
        resolver_name=resolver,
        resolver_score=score,
        signature="C(CC)",
        signature_type="smiles",
        hit_type=hit_type,
    )


# ---------------------------------------------------------------- resolver_belief

def test_belief_zero_chains_is_zero():
    assert resolver_belief(0, 0) == 0.0


def test_belief_single_identity_chain_halves_doubt():
    assert resolver_belief(1, 0) == 50.0


def test_belief_two_identity_chains_is_75():
    assert resolver_belief(2, 0) == 75.0


def test_belief_three_similarity_chains_equal_one_identity():
    assert abs(resolver_belief(0, 3) - resolver_belief(1, 0)) < 1e-9


def test_belief_never_reaches_100():
    assert resolver_belief(50, 200) < 100.0


def test_belief_monotone_in_both_chain_kinds():
    # κ=1/3: 3 sims == 1 identity; 4 sims (eff 1.33) outrank 1 identity.
    assert resolver_belief(2, 0) > resolver_belief(1, 1) > resolver_belief(1, 0)
    assert resolver_belief(1, 0) > resolver_belief(0, 2)


def test_belief_constants_are_calibrated_values():
    assert BELIEF_RHO == 0.5
    assert abs(BELIEF_KAPPA - 1.0 / 3.0) < 1e-12


# ------------------------------------------------------- deduplicate_and_score

def test_group_belief_uses_identity_and_similarity_chains():
    groups = deduplicate_and_score([
        _hit(resolver="pubchem_formula", hit_type="identity", score=100.0),
        _hit(resolver="pubchem_sim", hit_type="similarity", score=80.0),
    ])
    g = groups[("123", "PUBCHEM_CID")]
    assert g["n_identity_chains"] == 1
    assert g["n_similarity_chains"] == 1
    assert abs(g["belief"] - 100.0 * (1.0 - 0.5 ** (1.0 + 1.0 / 3.0))) < 1e-9


def test_group_belief_counts_distinct_resolvers_not_records():
    groups = deduplicate_and_score([
        _hit(resolver="pubchem_sim", hit_type="similarity"),
        _hit(resolver="pubchem_sim", hit_type="similarity"),  # duplicate chain
    ])
    g = groups[("123", "PUBCHEM_CID")]
    assert g["n_similarity_chains"] == 1


def test_group_belief_ignores_resolver_score_magnitude():
    low = deduplicate_and_score([
        _hit(resolver="a", hit_type="identity", score=12.0)])
    high = deduplicate_and_score([
        _hit(resolver="a", hit_type="identity", score=100.0)])
    assert low[("123", "PUBCHEM_CID")]["belief"] == high[("123", "PUBCHEM_CID")]["belief"]


def test_consensus_score_unchanged_legacy_field():
    groups = deduplicate_and_score([
        _hit(resolver="a", hit_type="similarity", score=80.0)])
    assert abs(groups[("123", "PUBCHEM_CID")]["consensus_score"] - 80.0) < 1e-9
