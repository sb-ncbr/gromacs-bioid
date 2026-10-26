"""Red-team D-13 (subtask 3) — single BLAST run, tiered listings, gate noise.

2a: identity and similarity are two views over ONE processed BLAST run —
previously each phase re-ran blastp, doubling the protein BLAST wall time
that dominates the identify stage.

2d: similarity rows carry subject_cov_p, and protein hits that failed the
C-03 identity gate record the FIRST failing gate (identity|qcov|scov) so a
rerun's gate-fail classes are measurable offline (A/B ablation) and the UI
can show "{p}% identity over {c}%".
"""

from __future__ import annotations

import pytest

from src_new.config.loader import RunConfig
from src_new.identification.resolvers.blast import BlastHit, BLASTResolverPDBAA


def _resolver() -> BLASTResolverPDBAA:
    cfg = RunConfig()
    r = BLASTResolverPDBAA(cfg)
    r._preflight_check = lambda: None  # DB files not needed for unit tiering
    return r


def _hit(accessions, identity_p, coverage_p, *, evalue=1e-120, bits=300.0,
         subject_len=None, subject_cov_p=None, subject_span=None, subject_gap=None):
    return BlastHit(accessions, evalue, bits, identity_p, coverage_p,
                    subject_len=subject_len, subject_cov_p=subject_cov_p,
                    subject_span=subject_span,
                    subject_max_internal_gap=subject_gap)


class TestSingleRunTiering:
    def test_identity_and_similarity_share_one_blast_run(self, monkeypatch):
        r = _resolver()
        calls = {"n": 0}

        def fake_local(sequence, working_directory):
            calls["n"] += 1
            return None  # empty result set is fine — we count runs

        monkeypatch.setattr(r, "_run_blast_local", fake_local)
        r._run_blast_identity("MKVLWAALLVTFLAGCQAK", "/tmp")
        r._run_blast_similarity("MKVLWAALLVTFLAGCQAK", "/tmp")
        assert calls["n"] == 1

    def test_fresh_sequence_reruns_blast(self, monkeypatch):
        r = _resolver()
        calls = {"n": 0}
        monkeypatch.setattr(
            r, "_run_blast_local",
            lambda sequence, working_directory: calls.__setitem__("n", calls["n"] + 1))
        r._run_blast_identity("MKVLWAALLVTFLAGCQAK", "/tmp")
        r._run_blast_similarity("ACDEFGHIKLMNPQRSTVWY", "/tmp")
        assert calls["n"] == 2


class TestGateTiering:
    def _run(self, r, hits, monkeypatch):
        monkeypatch.setattr(r, "_processed_hits", lambda seq, wd: hits)
        accepted = r._run_blast_identity("Q" * 50, "/tmp")
        identity_meta = r.get_last_resolution_metadata()
        similar = dict(r._run_blast_similarity("Q" * 50, "/tmp"))
        sim_meta = r.get_last_resolution_metadata()
        return accepted, identity_meta, similar, sim_meta

    def test_exact_hit_in_both_tiers(self, monkeypatch):
        """A perfect construct tiers as identity AND stays in the
        similarity listing (dedup's strongest-tier guard owns belief)."""
        r = _resolver()
        hits = [_hit(["2TAG_A"], 1.0, 1.0, subject_len=100,
                     subject_cov_p=0.92, subject_span=(1, 92), subject_gap=0)]
        accepted, identity_meta, similar, sim_meta = self._run(r, hits, monkeypatch)
        assert accepted == ["2TAG_A"]
        assert "2TAG_A" in similar
        assert "identity_gate_fail" not in sim_meta["2TAG_A"]
        assert sim_meta["2TAG_A"]["subject_cov_p"] == 0.92

    def test_scov_reject_records_gate_fail(self, monkeypatch):
        """Exact alignment inside a much larger subject fails scov and the
        similarity row must SAY so (plus carry the coverage numbers)."""
        r = _resolver()
        hits = [_hit(["1FUS_A"], 1.0, 1.0, subject_len=580,
                     subject_cov_p=0.10, subject_span=(100, 157), subject_gap=0)]
        accepted, _, similar, sim_meta = self._run(r, hits, monkeypatch)
        assert accepted == []
        assert "1FUS_A" in similar
        assert sim_meta["1FUS_A"]["identity_gate_fail"] == "scov"
        assert sim_meta["1FUS_A"]["subject_cov_p"] == 0.10

    def test_identity_reject_records_gate_fail(self, monkeypatch):
        """98%-identical engineered constructs stay similarity with the
        honest 'identity' reason — never promoted."""
        r = _resolver()
        hits = [_hit(["9MUT_A"], 0.98, 1.0, subject_len=50,
                     subject_cov_p=1.0, subject_span=(1, 50), subject_gap=0)]
        accepted, _, similar, sim_meta = self._run(r, hits, monkeypatch)
        assert accepted == []
        assert sim_meta["9MUT_A"]["identity_gate_fail"] == "identity"

    def test_qcov_reject_records_gate_fail(self, monkeypatch):
        r = _resolver()
        hits = [_hit(["9PRTL_A"], 1.0, 0.80, subject_len=40,
                     subject_cov_p=1.0, subject_span=(1, 40), subject_gap=0)]
        accepted, _, similar, sim_meta = self._run(r, hits, monkeypatch)
        assert accepted == []
        if "9PRTL_A" in similar:  # may fail similarity qcov too; only identity tier is asserted
            assert sim_meta["9PRTL_A"]["identity_gate_fail"] == "qcov"


class TestFixBTerminalOverhang:
    """D-13 Fix B (subtask 4): scov < 0.9 is accepted ONLY when the
    unaligned subject residues sit at the termini (expression tags,
    unobserved/disordered ends) — never a domain inside a larger protein."""

    def _run_identity(self, r, hits, monkeypatch):
        monkeypatch.setattr(r, "_processed_hits", lambda seq, wd: hits)
        accepted = r._run_blast_identity("Q" * 50, "/tmp")
        return accepted, r.get_last_resolution_metadata()

    def test_expression_tag_accepted(self, monkeypatch):
        """50-aa query exact over residues 26..75 of a 100-aa subject
        (25-aa N-tag + 25-aa C-tail) -> identity, tagged as override."""
        r = _resolver()
        hits = [_hit(["0TAG_A"], 1.0, 1.0, subject_len=100,
                     subject_cov_p=0.50, subject_span=(26, 75), subject_gap=0)]
        accepted, meta = self._run_identity(r, hits, monkeypatch)
        assert accepted == ["0TAG_A"]
        assert meta["0TAG_A"]["scov_gate"] == "terminal_override"

    def test_domain_inside_larger_protein_rejected(self, monkeypatch):
        """Exact 58-aa domain at residues 100..157 of a 580-aa protein:
        99-aa unaligned N-side + huge C-side -> stays similarity as scov."""
        r = _resolver()
        hits = [_hit(["9DOM_A"], 1.0, 1.0, subject_len=580,
                     subject_cov_p=0.10, subject_span=(100, 157), subject_gap=0)]
        accepted, meta = self._run_identity(r, hits, monkeypatch)
        assert accepted == []

    def test_internal_gap_rejected(self, monkeypatch):
        """Termini fine but a 30-aa unaligned stretch INSIDE the subject
        alignment is not an expression tag -> similarity."""
        r = _resolver()
        hits = [_hit(["9GAP_A"], 1.0, 1.0, subject_len=110,
                     subject_cov_p=0.73, subject_span=(1, 110), subject_gap=30)]
        accepted, meta = self._run_identity(r, hits, monkeypatch)
        assert accepted == []

    def test_one_long_terminal_rejected(self, monkeypatch):
        """A 200-aa unaligned C-terminus exceeds the tag allowance even
        with no internal gaps — that is a different construct."""
        r = _resolver()
        hits = [_hit(["9LONG_A"], 1.0, 1.0, subject_len=250,
                     subject_cov_p=0.20, subject_span=(1, 50), subject_gap=0)]
        accepted, meta = self._run_identity(r, hits, monkeypatch)
        assert accepted == []

    def test_normal_scov_pass_untagged(self, monkeypatch):
        r = _resolver()
        hits = [_hit(["1FI3_A"], 1.0, 1.0, subject_len=82,
                     subject_cov_p=1.0, subject_span=(1, 82), subject_gap=0)]
        accepted, meta = self._run_identity(r, hits, monkeypatch)
        assert accepted == ["1FI3_A"]
        assert "scov_gate" not in meta["1FI3_A"]


class TestSubjectGeometryParsing:
        r = _resolver()
        payload = [{
            "BlastOutput2": {
                "report": {"results": {"search": {
                    "query_len": 100,
                    "hits": [{
                        "description": [{"accession": "9GAP_A", "title": "x"}],
                        "len": 300,
                        "hsps": [
                            {"bit_score": 300.0, "evalue": 1e-120,
                             "align_len": 50, "identity": 50,
                             "query_from": 1, "query_to": 50,
                             "hit_from": 1, "hit_to": 50},
                            {"bit_score": 300.0, "evalue": 1e-120,
                             "align_len": 50, "identity": 50,
                             "query_from": 51, "query_to": 100,
                             "hit_from": 100, "hit_to": 149},
                        ],
                    }],
                }}}
            }
        }]
        hits = r._process_blast_results(payload)
        assert len(hits) == 1
        h = hits[0]
        assert h.subject_span == (1, 149)
        assert h.subject_max_internal_gap == 49  # 51..99 unaligned inside the subject
        assert h.subject_cov_p == pytest.approx(100 / 300)  # merged ALIGNED intervals only
