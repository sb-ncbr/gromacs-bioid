"""Red-team D-13 (subtask 1) — strongest-tier counting for dual-mode sources.

D-13 persists a resolver's identity and similarity listings under DISTINCT
keys ({resolver} and {resolver}@sim). One source can therefore appear in
BOTH lists for the same accession; counting both tiers would inflate every
exact protein hit from belief 50.00 to 60.3 (the double-count signature).

Rule (2b): a source present in both tiers counts at its strongest tier
only (identity). Cross-source similarity still counts.
"""

from __future__ import annotations

import pytest

from src_new.verification.dedup import (
    RawHit, deduplicate_and_score, resolver_belief, _resolver_source,
)


def _rh(identifier, ident_type, resolver, sig="MKVL", stype="residue_sequence_protein",
        hit_type="identity", score=90.0):
    return RawHit(identifier, ident_type, resolver, score, sig, stype, hit_type)


class TestStrongestTierCounting:
    def test_identity_and_similarity_same_source_counts_once(self):
        """The D-13 double-count guard: blast_pdb_protein identity AND
        blast_pdb_protein@sim similarity for one accession -> belief 50.00,
        never 60.3."""
        out = deduplicate_and_score([
            _rh("1FI3_A", "PDB_ID", "blast_pdb_protein",
                hit_type="identity", score=100.0),
            _rh("1FI3_A", "PDB_ID", "blast_pdb_protein@sim",
                hit_type="similarity"),
        ])
        meta = out[("1FI3", "PDB_ID")]  # PDB_ID normalization strips _chain
        assert meta["n_identity_sources"] == 1
        assert meta["n_similarity_sources"] == 0
        assert meta["belief"] == pytest.approx(resolver_belief(1, 0))
        assert meta["belief"] == pytest.approx(50.0)

    def test_cross_source_similarity_still_counts(self):
        """PDB identity + UniProt similarity = two genuine evidence
        families — the guard must not eat cross-source signal."""
        out = deduplicate_and_score([
            _rh("P00101", "UNIPROT_ID", "blast_pdb_protein",
                hit_type="identity", score=100.0),
            _rh("P00101", "UNIPROT_ID", "blast_uniprot@sim",
                hit_type="similarity"),
        ])
        meta = out[("P00101", "UNIPROT_ID")]
        assert meta["n_identity_sources"] == 1
        assert meta["n_similarity_sources"] == 1
        assert meta["belief"] == pytest.approx(resolver_belief(1, 1))

    def test_similarity_only_sources_unchanged(self):
        """Pre-D-13 behaviour for similarity-only groups is preserved."""
        out = deduplicate_and_score([
            _rh("P00102", "UNIPROT_ID", "blast_pdb_protein@sim",
                hit_type="similarity"),
            _rh("P00102", "UNIPROT_ID", "blast_uniprot@sim",
                hit_type="similarity"),
        ])
        meta = out[("P00102", "UNIPROT_ID")]
        assert meta["n_similarity_sources"] == 2
        assert meta["belief"] == pytest.approx(resolver_belief(0, 2))

    def test_sim_suffix_maps_to_same_family(self):
        """collect_hits passes the record KEY as resolver_name, so @sim
        keys must collapse into the same evidence family as the base
        resolver — and unknown @sim names fall back to the base name."""
        assert _resolver_source("blast_pdb_protein@sim") == _resolver_source("blast_pdb_protein") == "rcsb-seq"
        assert _resolver_source("inchikey_pubchem@sim") == "inchikey"
        assert _resolver_source("custom_tool@sim") == "custom_tool"
