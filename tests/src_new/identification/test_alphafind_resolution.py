"""AlphaFind resolver tests: aligned_percentage normalization + identity filter.

Evidence basis (2026-10-19 live stage-API probe, crambin/1CRN): the current
endpoint returns aligned_percentage on a 0..1 scale and object_id as a bare
UniProt accession ("P01542"). Pre-v3.138 code compared identity against
exactly 100.0 on that scale, so identity hits could never fire, and 0..1
values leaked into a 0..100 consensus pipeline.
"""

from __future__ import annotations

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.alphafind import (
    AlphaFindStructResolver,
    _normalize_aligned_percentage,
)


@pytest.fixture
def resolver() -> AlphaFindStructResolver:
    return AlphaFindStructResolver(RunConfig())


class TestNormalizeAlignedPercentage:
    def test_fraction_scaled_to_percentage(self):
        assert _normalize_aligned_percentage(1.0) == 100.0

    def test_partial_fraction(self):
        assert _normalize_aligned_percentage(0.978) == pytest.approx(97.8)

    def test_percentage_passthrough(self):
        assert _normalize_aligned_percentage(97.8) == pytest.approx(97.8)

    def test_bad_value_is_zero(self):
        assert _normalize_aligned_percentage("junk") == 0.0
        assert _normalize_aligned_percentage(None) == 0.0


class TestSimilarityNormalizationWiring:
    def test_results_normalized(self, resolver):
        fake_response = {
            "results": [
                {"object_id": "P01542", "aligned_percentage": 1.0},
                {"object_id": "P99999", "aligned_percentage": 0.5},
            ]
        }
        resolver._alphafind_fetch_response = lambda _p: fake_response
        assert resolver._alphafind_similarity("/tmp/x.pdb") == [
            ("P01542", 100.0),
            ("P99999", 50.0),
        ]

    def test_missing_fields_skipped(self, resolver):
        fake_response = {"results": [{"object_id": "P01542"}]}
        resolver._alphafind_fetch_response = lambda _p: fake_response
        assert resolver._alphafind_similarity("/tmp/x.pdb") == []


class TestIdentityFilter:
    def test_full_alignment_is_identity(self, resolver):
        resolver._alphafind_similarity = lambda _p: [("P01542", 100.0)]
        assert resolver._alphafind_identity("/tmp/x.pdb") == ["P01542"]

    def test_boundary_tolerance(self, resolver):
        resolver._alphafind_similarity = lambda _p: [
            ("A", 99.5),
            ("B", 99.49),
        ]
        assert resolver._alphafind_identity("/tmp/x.pdb") == ["A"]

    def test_fraction_input_no_longer_dropped(self, resolver):
        # the exact regression: 1.0-scale input used to die at == 100.0
        resolver._alphafind_fetch_response = lambda _p: {
            "results": [{"object_id": "P01542", "aligned_percentage": 1.0}]
        }
        assert resolver._alphafind_identity("/tmp/x.pdb") == ["P01542"]

    def test_resolver_declares_alphafold_id_type(self, resolver):
        # taxonomy decision (2026-10-20): AlphaFind emits ALPHAFOLD_ID and
        # the verification chain (structure worker/fetcher, AFDB v6->v4)
        # supports that type directly.
        assert resolver.identifier_type == "ALPHAFOLD_ID"
        assert resolver.accepted_signatures == ["ca_only_pdb"]
