"""W5/F-N1c: exact short identity override for nucleotide BLAST identity pass.

House testing style: fabricated blastn JSON via patched _run_blast_local.
Boundary rules under test (nucleotide, query <= 25 nt): accepted iff
identity_p == 1.0 AND coverage_p == 1.0 AND subject_len == query_len,
regardless of evalue/bits. Everything else unchanged.
"""
from __future__ import annotations

import pytest
from unittest.mock import patch

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.blast import (
    BLASTResolverPDBNT,
    BLASTResolverPDBAA,
    _SHORT_IDENTITY_MAX_QLEN,
)


@pytest.fixture
def config() -> RunConfig:
    return RunConfig()


def make_hit(accessions, identity, align_len, bits, evalue, subject_len=None):
    h = {
        "description": [{"accession": acc} for acc in accessions],
        "hsps": [{
            "identity": identity,
            "align_len": align_len,
            "bit_score": bits,
            "evalue": evalue,
        }],
    }
    if subject_len is not None:
        h["len"] = subject_len
    return h


def make_blast_json(hits, query_len):
    return [{
        "BlastOutput2": {
            "report": {
                "results": {
                    "search": {
                        "query_len": query_len,
                        "hits": hits,
                    }
                }
            }
        }
    }]


SHORT_SEQ = "CGCGAAAATTTTCGCG"  # 16 nt
L = len(SHORT_SEQ)


class TestExactShortIdentityOverride:
    def test_perfect_short_accepted_despite_gates(self, config):
        """100% full-length both-directions 16-mer: evalue=999, bits=5 -> accepted."""
        resolver = BLASTResolverPDBNT(config)
        json_data = make_blast_json(
            [make_hit(["1BNA_A"], identity=L, align_len=L, bits=5.0, evalue=999.0, subject_len=L)],
            query_len=L,
        )
        with patch.object(resolver, "_run_blast_local", return_value=json_data):
            out = resolver._run_blast_identity(SHORT_SEQ, "")
        assert out == ["1BNA_A"]
        meta = resolver.get_last_resolution_metadata()
        assert "exact_short_identity" in meta["1BNA_A"]["note"]

    def test_longer_subject_refused(self, config):
        """Perfect full-query match INSIDE a long subject is NOT the same molecule."""
        resolver = BLASTResolverPDBNT(config)
        json_data = make_blast_json(
            [make_hit(["LONG_RRNA"], identity=L, align_len=L, bits=40.0, evalue=0.3, subject_len=3000)],
            query_len=L,
        )
        with patch.object(resolver, "_run_blast_local", return_value=json_data):
            out = resolver._run_blast_identity(SHORT_SEQ, "")
        assert out == []

    def test_partial_identity_refused(self, config):
        """15/16 identical (93.75%) must stay refused."""
        resolver = BLASTResolverPDBNT(config)
        json_data = make_blast_json(
            [make_hit(["ALMOST"], identity=L - 1, align_len=L, bits=30.0, evalue=0.01, subject_len=L)],
            query_len=L,
        )
        with patch.object(resolver, "_run_blast_local", return_value=json_data):
            out = resolver._run_blast_identity(SHORT_SEQ, "")
        assert out == []

    def test_partial_coverage_refused(self, config):
        """100% identity over 12 of 16 nt (cov 0.75) must stay refused."""
        resolver = BLASTResolverPDBNT(config)
        json_data = make_blast_json(
            [make_hit(["WINDOW"], identity=12, align_len=12, bits=24.0, evalue=0.05, subject_len=12)],
            query_len=L,
        )
        with patch.object(resolver, "_run_blast_local", return_value=json_data):
            out = resolver._run_blast_identity(SHORT_SEQ, "")
        assert out == []

    def test_above_length_bound_refused(self, config):
        """Perfect 26-mer self-match is above the override bound and unreachable
        for strict gates -> refused (bound documented as <=25)."""
        seq26 = "A" * (_SHORT_IDENTITY_MAX_QLEN + 1)
        resolver = BLASTResolverPDBNT(config)
        json_data = make_blast_json(
            [make_hit(["TWENTY_SIX"], identity=len(seq26), align_len=len(seq26),
                      bits=1.0, evalue=55.0, subject_len=len(seq26))],
            query_len=len(seq26),
        )
        with patch.object(resolver, "_run_blast_local", return_value=json_data):
            out = resolver._run_blast_identity(seq26, "")
        assert out == []

    def test_protein_path_unchanged(self, config):
        """Protein resolver does not gain the override (strict gates only)."""
        resolver = BLASTResolverPDBAA(config)
        seq = "MEEPQSDPSV"
        json_data = make_blast_json(
            [make_hit(["6XU8_A"], identity=len(seq), align_len=len(seq),
                      bits=12.0, evalue=88.0, subject_len=len(seq))],
            query_len=len(seq),
        )
        with patch.object(resolver, "_run_blast_local", return_value=json_data):
            out = resolver._run_blast_identity(seq, "")
        assert out == []

    def test_duplicate_accessions_deduped(self, config):
        resolver = BLASTResolverPDBNT(config)
        hits = [make_hit(["1BNA_A"], identity=L, align_len=L, bits=1, evalue=9, subject_len=L),
                make_hit(["1BNA_A"], identity=L, align_len=L, bits=1, evalue=9, subject_len=L)]
        with patch.object(resolver, "_run_blast_local", return_value=make_blast_json(hits, L)):
            out = resolver._run_blast_identity(SHORT_SEQ, "")
        assert out == ["1BNA_A"]

    def test_missing_subject_len_refused(self, config):
        """Legacy JSON without hit['len'] can never satisfy both-direction rule."""
        resolver = BLASTResolverPDBNT(config)
        h = make_hit(["NOLEN"], identity=L, align_len=L, bits=1, evalue=9)
        with patch.object(resolver, "_run_blast_local", return_value=make_blast_json([h], L)):
            out = resolver._run_blast_identity(SHORT_SEQ, "")
        assert out == []
