"""Red-team D-13a/D-13b: dual-tier evidence counting + chemical window priority.

D-13a: with dual-key persistence (``{resolver}`` + ``{resolver}@sim``), one
resolver reporting the same accession in both tiers must count as ONE evidence
source for ``consensus_score`` and ``source_resolvers`` /
``supporting_evidence_count``.  Counting record names inflates every
dual-listed group by log2(3)/log2(2) and misstates the evidence.

D-13b: inside the chemical verify-window family, *non-formula identity*
groups (``inchikey_*``, ``pubchem_struct`` identity rows, ...) must enter the
window before candidate and similarity groups.  The consensus-tie lottery
(~14k capped-100 chemical candidates per mdCATH ligand segment) and the F14
skeleton rerank (which cannot mirror-resolve non-CID identifiers such as an
InChIKey, so it ranks them below every resolved PubChem candidate — observed
live: GT InChIKey at position 14,215 / 14,311 on entry 2605 segment B) must
not be able to evict the exact row from the 100-slot window.  Campaign
evidence (2026-10-26 reviewer): ga1 kept the single ``inchikey_self`` row at
the last window slot on the nine formula-flood entries (2504, 2605, 2623,
2821, 2907, 3098, 5499, 6100, 7564); d13 evicted it everywhere.
"""

from __future__ import annotations

import json

import pytest

from src_new.verification.dedup import RawHit, deduplicate_and_score
from src_new.verification.manager import _family_interleave

FIXTURE_PATH = (
    __file__.rsplit("/", 1)[0] + "/fixtures/2504_d13_identifiers_B.json"
)


def _hit(resolver: str, score: float, hit_type: str, ident: str = "X") -> RawHit:
    return RawHit(
        identifier=ident,
        ident_type="INCHIKEY",
        resolver_name=resolver,
        resolver_score=score,
        signature="sig",
        signature_type="INCHIKEY",
        hit_type=hit_type,
    )


# ---------------------------------------------------------------- D-13a ----

class TestDualTierEvidenceCounting:
    def test_dual_tier_resolver_counts_once_for_consensus(self):
        # Real dual-listed shape: identity rows always score 100.0 and the
        # @sim listing carries the raw similarity value; one source total.
        base = [_hit("inchikey_self", 100.0, "identity")]
        dual = base + [_hit("inchikey_self@sim", 99.9, "similarity")]
        m_base = deduplicate_and_score(base)[("X", "INCHIKEY")]
        m_dual = deduplicate_and_score(dual)[("X", "INCHIKEY")]
        assert m_dual["consensus_score"] == m_base["consensus_score"]

    def test_dual_tier_sub100_similarity_not_inflated(self):
        # Sub-cap similarity-only group: one resolver's two listing KEYS must
        # score exactly like the single listing (pre-D-13a this was ~1.585x).
        single = [_hit("pubchem_struct", 60.0, "similarity")]
        dual = single + [_hit("pubchem_struct@sim", 50.0, "similarity",
                              ident="X")]
        m_single = deduplicate_and_score(single)[("X", "INCHIKEY")]
        m_dual = deduplicate_and_score(dual)[("X", "INCHIKEY")]
        assert m_dual["consensus_score"] == m_single["consensus_score"]

    def test_dual_tier_source_resolvers_collapsed_to_base(self):
        dual = [
            _hit("inchikey_self", 100.0, "identity"),
            _hit("inchikey_self@sim", 100.0, "similarity"),
        ]
        meta = deduplicate_and_score(dual)[("X", "INCHIKEY")]
        assert sorted(meta["source_resolvers"]) == ["inchikey_self"]
        # supporting_evidence_count downstream = len(source_resolvers)
        assert len(meta["source_resolvers"]) == 1

    def test_two_genuinely_distinct_resolvers_still_count_twice(self):
        dual = [
            _hit("inchikey_self", 100.0, "identity"),
            _hit("inchikey_pubchem", 100.0, "identity"),
            _hit("inchikey_pubchem@sim", 99.0, "similarity"),
        ]
        meta = deduplicate_and_score(dual)[("X", "INCHIKEY")]
        assert sorted(meta["source_resolvers"]) == [
            "inchikey_pubchem", "inchikey_self",
        ]
        # sub-cap: two distinct similarity sources genuinely raise the score
        one = deduplicate_and_score(
            [_hit("pubchem_struct", 60.0, "similarity")])[("X", "INCHIKEY")]
        two = deduplicate_and_score([
            _hit("pubchem_struct", 60.0, "similarity"),
            _hit("chembl_struct", 55.0, "similarity"),
        ])[("X", "INCHIKEY")]
        assert two["consensus_score"] > one["consensus_score"]
