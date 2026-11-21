"""2026-11-21 (mdval audit item 1): absolute identity rule for nucleotides.

The balanced-preset audit left 111 of 158 nucleic-acid segments
unidentified: blastn identity still needed e <= 1e-50 and bits >= 51, which
a PERFECT match of ~26-104 nt can never reach on pdbnt. The e-values below
are the ones measured on production pdbnt for perfect substrings of 1KX5_I
(147 nt nucleosome DNA).
"""
from __future__ import annotations

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.blast import BLASTResolverNT, BLASTResolverPDBNT

# production pdbnt, perfect substrings of 1KX5_I: length -> (e-value as
# measured, bit score approximate: 1.85 bits per matching nt)
MEASURED = {30: (4.8e-10, 56.5), 60: (3e-26, 111.0), 80: (3.6e-37, 148.0),
            100: (3.6e-48, 185.0)}

# 147-nt stand-in for 1KX5_I (the hits are synthetic, only lengths matter)
SEQ_1KX5_I = ("ACGTTGCA" * 19)[:147]


def _json(query_len, hits):
    return [{"BlastOutput2": {"report": {"results": {"search": {
        "query_len": query_len, "hits": hits}}}}}]


def _hit(acc, subject_len, hsps):
    return {"description": [{"accession": acc}], "len": subject_len, "hsps": hsps}


def _hsp(identity, align_len, q, s, evalue, bits, strand="Plus"):
    return {"identity": identity, "align_len": align_len,
            "query_from": q[0], "query_to": q[1], "hit_from": s[0], "hit_to": s[1],
            "query_strand": "Plus", "hit_strand": strand,
            "evalue": evalue, "bit_score": bits}


def _identity(hits, query, cls=BLASTResolverPDBNT):
    r = cls(RunConfig())
    r._run_blast_local = lambda seq, wd: _json(len(query), hits)
    return r, r._run_blast_identity(query, "")


@pytest.mark.parametrize("length", sorted(MEASURED))
def test_perfect_1kx5_substring_is_identity(length):
    """The pdbnt record of the simulated chain: the query is the whole chain,
    the subject SEQRES carries a few unmodelled terminal nucleotides."""
    evalue, bits = MEASURED[length]
    query = SEQ_1KX5_I[10:10 + length]
    subject_len = length + 6
    hits = [_hit("9NA1_A", subject_len, [_hsp(length, length, (1, length), (4, length + 3),
                                                evalue, bits)])]
    r, out = _identity(hits, query)
    assert out == ["9NA1_A"]
    meta = r.get_last_resolution_metadata()["9NA1_A"]
    assert meta["identity_p"] == 1.0 and meta["coverage_p"] == 1.0


@pytest.mark.parametrize("length", sorted(MEASURED))
def test_perfect_substring_inside_the_147nt_chain_is_similarity(length):
    """The same perfect match against 1KX5_I itself (147 nt): subject coverage
    < 0.9 and more than 25 unaligned nt at a terminus — a piece of a longer
    molecule, similarity only (as for proteins)."""
    evalue, bits = MEASURED[length]
    query = SEQ_1KX5_I[30:30 + length]
    hits = [_hit("1KX5_I", 147, [_hsp(length, length, (1, length), (31, 30 + length),
                                       evalue, bits)])]
    r, out = _identity(hits, query)
    assert out == []
    r.blast_config.similarity_match_max_evalue = 0.1
    sim = dict(r._run_blast_similarity(query, ""))
    assert sim == {"1KX5_I": 100.0}
    assert r.get_last_resolution_metadata()["1KX5_I"]["identity_gate_fail"] == "scov"


def test_terminal_overhang_override_applies_to_nucleotides():
    """60-nt simulated chain, 72-nt SEQRES (6 unmodelled nt at each end):
    scov 0.83 but only terminal overhang, so identity, tagged like proteins."""
    query = SEQ_1KX5_I[:60]
    hits = [_hit("9NA2_B", 72, [_hsp(60, 60, (1, 60), (7, 66), *MEASURED[60])])]
    r, out = _identity(hits, query)
    assert out == ["9NA2_B"]
    assert r.get_last_resolution_metadata()["9NA2_B"]["scov_gate"] == "terminal_override"


def test_one_mismatch_in_60nt_stays_similarity():
    """59/60 = 0.983 identity is below the 0.99 floor, despite e = 1e-24."""
    query = SEQ_1KX5_I[:60]
    hits = [_hit("9MUT_A", 60, [_hsp(59, 60, (1, 60), (1, 60), 1e-24, 105.0)])]
    r, out = _identity(hits, query)
    assert out == []
    sim = dict(r._run_blast_similarity(query, ""))
    assert sim["9MUT_A"] == pytest.approx(100.0 * 59 / 60)
    assert r.get_last_resolution_metadata()["9MUT_A"]["identity_gate_fail"] == "identity"


def test_partial_query_coverage_stays_similarity():
    query = SEQ_1KX5_I[:80]
    hits = [_hit("9PRT_A", 60, [_hsp(60, 60, (1, 60), (1, 60), *MEASURED[60])])]
    _r, out = _identity(hits, query)
    assert out == []


def test_reverse_complement_is_not_identity():
    """blastn's minus-strand HSP (hit_from > hit_to) is the partner strand of
    a duplex. Coordinates are normalised (subject coverage was negative) and
    the hit stays similarity."""
    query = SEQ_1KX5_I[:60]
    hits = [_hit("1KX5_J", 60, [_hsp(60, 60, (1, 60), (60, 1), *MEASURED[60], strand="Minus")])]
    r = BLASTResolverPDBNT(RunConfig())
    parsed = r._process_blast_results(_json(60, hits))
    assert parsed[0].opposite_strand
    assert parsed[0].subject_cov_p == pytest.approx(1.0)
    assert parsed[0].subject_span == (1, 60)
    _r, out = _identity(hits, query)
    assert out == []


def test_palindrome_with_both_strands_is_identity():
    """A self-complementary query aligns on both strands of the same
    subject: one Plus HSP is enough."""
    query = "GCGCAATTGCGCGCGCAATTGCGCGCGCAATTGC"  # 34 nt
    n = len(query)
    hits = [_hit("9PAL_A", n, [_hsp(n, n, (1, n), (1, n), 1e-12, 60.0),
                               _hsp(n, n, (1, n), (n, 1), 1e-12, 60.0, strand="Minus")])]
    _r, out = _identity(hits, query)
    assert out == ["9PAL_A"]


def test_unknown_subject_coverage_is_not_identity_for_nucleotides():
    """Without alignment coordinates the subject coverage is unknown: proteins
    keep the legacy 'admissible', nucleotides do not (F-N1c never let a query
    inside a longer subject claim identity)."""
    query = SEQ_1KX5_I[:60]
    hits = [{"description": [{"accession": "NOCOORD"}], "len": 3000,
             "hsps": [{"identity": 60, "align_len": 60, "evalue": 1e-30, "bit_score": 111.0}]}]
    _r, out = _identity(hits, query)
    assert out == []


def test_short_queries_keep_the_fn1c_rule():
    """<= 25 nt: the absolute gate does not apply (a 20-mer inside a 22-nt
    subject is NOT accepted); only subject length == query length is."""
    query = SEQ_1KX5_I[:20]
    hits = [_hit("NEAR_LEN", 22, [_hsp(20, 20, (1, 20), (2, 21), 1.0, 40.0)]),
            _hit("SAME_LEN", 20, [_hsp(20, 20, (1, 20), (1, 20), 1.0, 40.0)])]
    r, out = _identity(hits, query)
    assert out == ["SAME_LEN"]
    assert r.get_last_resolution_metadata()["SAME_LEN"]["note"].startswith("exact_short_identity")


def test_deep_nt_resolver_uses_the_same_rule():
    query = SEQ_1KX5_I[:100]
    hits = [_hit("CP000001.1", 100, [_hsp(100, 100, (1, 100), (1, 100), *MEASURED[100])])]
    _r, out = _identity(hits, query, cls=BLASTResolverNT)
    assert out == ["CP000001.1"]
