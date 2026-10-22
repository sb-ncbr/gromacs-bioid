"""Red-team Batch 1.5 (BLAST) regression tests.

  C-21: coverage was align_len/query_len (align_len includes gap columns ->
        coverage can exceed 1.0 and gaps inflate it); only hsps[0] was read
        -> split alignments lost coverage; no subject coverage existed.
  C-03: protein identity required evalue <= 1e-50 AND bits >= 51 — physically
        unreachable for < ~75-80 aa (BPTI-58 best 7.4e-39, villin-35 1.2e-19,
        insulin-30 8.9e-17, ubiquitin-76/SwissProt 4.6e-50) AND arbitrary at
        the boundary (composition-based statistics give identical subjects
        different e-values). The nucleotide path already had the F-N1c
        exact-match escape; proteins had none.
"""
from __future__ import annotations

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.blast import (
    BLASTResolverNT,
    BLASTResolverPDBAA,
)


def _json(query_len: int, hits: list[dict]) -> list[dict]:
    """_run_blast_local returns a list of already-parsed BLAST JSON docs."""
    return [{
        "BlastOutput2": {
            "report": {
                "results": {"search": {
                    "query_len": query_len,
                    "hits": hits,
                }},
            },
        },
    }]


def _hit(accessions, subject_len, hsps):
    return {
        "description": [{"accession": a} for a in accessions],
        "len": subject_len,
        "hsps": hsps,
    }


def _hsp(identity, align_len, q_from, q_to, s_from, s_to, evalue, bits):
    return {
        "identity": identity, "align_len": align_len,
        "query_from": q_from, "query_to": q_to,
        "hit_from": s_from, "hit_to": s_to,
        "evalue": evalue, "bit_score": bits,
    }


class TestC21CoverageMath:
    def test_gaps_no_longer_inflate_coverage(self):
        """76-column alignment with 10 subject-insertion gap columns over a
        66-aa query: old coverage = 76/66 = 1.15; true qcov = 1.0."""
        r = BLASTResolverPDBAA(RunConfig())
        hits = r._process_blast_results(_json(66, [_hit(
            ["X"], 200,
            [_hsp(identity=66, align_len=76, q_from=1, q_to=66,
                  s_from=5, s_to=70, evalue=1e-10, bits=120)],
        )]))
        assert len(hits) == 1
        assert hits[0].coverage_p == pytest.approx(1.0)
        assert hits[0].coverage_p <= 1.0, "coverage must never exceed 1.0"
        assert hits[0].identity_p == pytest.approx(66 / 76)

    def test_split_hsps_merge_query_coverage(self):
        """Two HSPs covering query 1-40 and 41-76: old code read hsps[0]
        only (coverage 40/76 = 0.53); true merged qcov = 1.0."""
        r = BLASTResolverPDBAA(RunConfig())
        hits = r._process_blast_results(_json(76, [_hit(
            ["Y"], 76,
            [_hsp(identity=40, align_len=40, q_from=1, q_to=40,
                  s_from=1, s_to=40, evalue=1e-20, bits=80),
             _hsp(identity=35, align_len=36, q_from=41, q_to=76,
                  s_from=41, s_to=76, evalue=1e-15, bits=60)],
        )]))
        assert hits[0].coverage_p == pytest.approx(1.0)
        assert hits[0].identity_p == pytest.approx(75 / 76)

    def test_subject_coverage_reported(self):
        r = BLASTResolverPDBAA(RunConfig())
        hits = r._process_blast_results(_json(58, [_hit(
            ["Z"], 580,
            [_hsp(identity=58, align_len=58, q_from=1, q_to=58,
                  s_from=100, s_to=157, evalue=1e-30, bits=90)],
        )]))
        assert hits[0].subject_cov_p == pytest.approx(58 / 580)


class TestC03LengthAwareProteinIdentity:
    """Probe shapes from C/blast_probe.py (audit appendix C)."""

    def _resolver(self, monkeypatch, query_len, hits, cls=BLASTResolverPDBAA):
        r = cls(RunConfig())
        monkeypatch.setattr(r, "_run_blast_local",
                            lambda seq, wd: _json(query_len, hits))
        return r

    def test_bpti58_perfect_match_now_identity(self, monkeypatch):
        """BPTI probe: best_100%_evalue=7.4e-39, bits below 51 — the old gates
        could never accept this, even at 100% identity and full coverage."""
        r = self._resolver(monkeypatch, 58, [_hit(
            ["2PTC"], 58,
            [_hsp(identity=58, align_len=58, q_from=1, q_to=58,
                  s_from=1, s_to=58, evalue=7.4e-39, bits=45)],
        )])
        out = r._run_blast_identity("RPDFCLEPPYTGPCKARIIRYFYNAKAGLCQTFVYGGCRAKRNNFKSAEDCMRTCGGA", "")
        assert "2PTC" in out, (
            "perfect 100%-identity full-coverage protein match rejected by "
            "length-dependent evalue/bit gates (C-03)"
        )

    def test_domain_size_subject_is_not_identity(self, monkeypatch):
        """Same perfect 58-aa alignment embedded in a 580-aa subject
        (scov = 0.1): not the same molecule — must NOT be identity."""
        r = self._resolver(monkeypatch, 58, [_hit(
            ["FUSION"], 580,
            [_hsp(identity=58, align_len=58, q_from=1, q_to=58,
                  s_from=100, s_to=157, evalue=7.4e-39, bits=45)],
        )])
        out = r._run_blast_identity("A" * 58, "")
        assert "FUSION" not in out, (
            "perfect local alignment inside a large subject must not count as "
            "identity (need subject coverage >= 0.9)"
        )

    def test_nucleotide_strict_gates_unchanged(self, monkeypatch):
        """The F-N1c short override did not weaken the nucleotide strict
        path: a long-query perfect match with weak e-value stays OUT."""
        r = self._resolver(monkeypatch, 400, [_hit(
            ["NA_X"], 400,
            [_hsp(identity=400, align_len=400, q_from=1, q_to=400,
                  s_from=1, s_to=400, evalue=1e-5, bits=30)],
        )], cls=BLASTResolverNT)
        out = r._run_blast_identity("ACGT" * 100, "")
        assert "NA_X" not in out, "nucleotide identity gates must stay strict"

    def test_imperfect_match_still_not_identity(self, monkeypatch):
        r = self._resolver(monkeypatch, 100, [_hit(
            ["NEAR"], 100,
            [_hsp(identity=97, align_len=100, q_from=1, q_to=100,
                  s_from=1, s_to=100, evalue=1e-60, bits=200)],
        )])
        out = r._run_blast_identity("A" * 100, "")
        assert "NEAR" not in out
