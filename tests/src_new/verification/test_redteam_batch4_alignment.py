"""Red-team batch-4 (5.2) — D-01 sequence-alignment semantics.

D-01: the sequence similarity S was "identity over a global alignment" with
gaps cheaper than mismatches, so (a) length differences diluted the score
(the correct full-length entry for a simulated 120-residue domain scored
12/100, BELOW a random same-length sequence at 18/100), and (b) "coverage"
was always 1.0.

These pins lock the fix: local BLOSUM62 (-11/-1) alignment, with
  identity = matches / aligned (both-residue) columns
  query_coverage = query residues inside the alignment / len(query)
  S = identity * query_coverage * 100
Both numbers are persisted in score.details.

Expected ordering on the probe corpus (d_p1 reconstruction):
  domain(120) vs its full-length parent(1000)  ~100
  chimera(A+B) vs A ~50  (right number, RIGHT reason: coverage 0.5)
  50%-mutated same-length homolog       mid-range
  random same-length sequence           < floor (25)
"""

from __future__ import annotations

import random

import pytest

from src_new.verification.alignment import local_identity_coverage
from src_new.verification.workers.sequence_worker import SequenceVerificationWorker
from src_new.verification.workers.structure_worker import StructureVerificationWorker
from src_new.verification.workers import structure_worker as sw
from src_new.verification.models import similarity_meets_floor

_ALPHABET = "ACDEFGHIKLMNPQRSTVWY"


def _rand_seq(n: int, rng: random.Random) -> str:
    return "".join(rng.choice(_ALPHABET) for _ in range(n))


def _mutate(seq: str, fraction: float, rng: random.Random) -> str:
    out = []
    for ch in seq:
        if rng.random() < fraction:
            out.append(rng.choice([c for c in _ALPHABET if c != ch]))
        else:
            out.append(ch)
    return "".join(out)


@pytest.fixture(scope="module")
def corpus() -> dict:
    rng = random.Random(20261023)
    domain = _rand_seq(120, rng)
    full = _rand_seq(440, rng) + domain + _rand_seq(440, rng)  # 1000 aa
    homolog = _mutate(domain, 0.5, rng)
    random_120 = _rand_seq(120, rng)
    ch_a = _rand_seq(60, rng)
    ch_b = _rand_seq(60, rng)
    return {"domain": domain, "full": full, "homolog": homolog,
            "random": random_120, "chimera": ch_a + ch_b, "chimera_a": ch_a}


def _worker_score(query: str, reference: str) -> float:
    worker = SequenceVerificationWorker()
    score = worker.verify(query, "X00000", "UNIPROT_ID", reference,
                          signature_type="residue_sequence_protein")
    assert score is not None, "worker returned None"
    return score.normalized_score


class TestLocalIdentityCoverage:
    def test_fragment_vs_full_identity_and_coverage(self, corpus):
        out = local_identity_coverage(corpus["domain"], corpus["full"])
        assert out is not None
        identity, coverage = out
        assert identity >= 0.99, identity        # aligned columns are exact
        assert coverage >= 0.99, coverage        # whole query is inside

    def test_chimera_coverage_is_half(self, corpus):
        out = local_identity_coverage(corpus["chimera"], corpus["chimera_a"])
        assert out is not None
        identity, coverage = out
        assert 0.4 <= coverage <= 0.6, coverage  # only half the query explained

    def test_empty_and_garbage_inputs_return_none(self):
        assert local_identity_coverage("", "ACDE") is None
        assert local_identity_coverage("ACDE", "") is None
        assert local_identity_coverage("", "") is None

    def test_hugematrix_guard(self, monkeypatch):
        from src_new.verification import alignment as al
        monkeypatch.setattr(al, "MAX_ALIGN_MATRIX_CELLS", 10)
        assert al.local_identity_coverage("A" * 20, "A" * 20) is None


class TestWorkerScoringSemantics:
    def test_domain_fragment_scores_high(self, corpus):
        s = _worker_score(corpus["domain"], corpus["full"])
        assert s >= 95.0, f"correct full-length entry must win: {s}"

    def test_random_scores_below_floor(self, corpus):
        s = _worker_score(corpus["random"], corpus["domain"])
        assert s < 25.0, f"random 120-mer must stay below the floor: {s}"
        assert not similarity_meets_floor("seq_identity_coverage", s)

    def test_correct_entry_beats_homolog_beats_random(self, corpus):
        s_full = _worker_score(corpus["domain"], corpus["full"])
        s_homo = _worker_score(corpus["domain"], corpus["homolog"])
        s_rand = _worker_score(corpus["random"], corpus["domain"])
        assert s_full > s_homo > s_rand, (s_full, s_homo, s_rand)

    def test_chimera_penalized_by_coverage(self, corpus):
        s = _worker_score(corpus["chimera"], corpus["chimera_a"])
        assert 35.0 <= s <= 65.0, s

    def test_details_carry_both_numbers(self, corpus):
        worker = SequenceVerificationWorker()
        score = worker.verify(corpus["domain"], "X00000", "UNIPROT_ID",
                              corpus["full"],
                              signature_type="residue_sequence_protein")
        assert score is not None
        assert score.details.get("alignment_identity") is not None
        assert score.details.get("query_coverage") is not None
        assert score.details["alignment_identity"] >= 99.0
        assert score.details["query_coverage"] >= 99.0


class TestStructureProxyUsesLocalAlignment:
    def test_proxy_fragment_scores_high(self, corpus):
        """The structure sequence-proxy shares the helper: a short query
        chain embedded in a long reference must not be diluted."""
        import math

        def helix(n, phase=0.0):
            return [[2.3 * math.cos(phase + i * 1.745),
                     2.3 * math.sin(phase + i * 1.745), 1.5 * i]
                    for i in range(n)]

        def pdb_chain(chain, coords, resname):
            lines = ["HEADER    SYNTH"]
            serial = 1
            for i, (x, y, z) in enumerate(coords, start=1):
                lines.append(
                    f"ATOM  {serial:5d} {'CA':^4s} {resname:>3s} {chain}{i:4d}    "
                    f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00           C")
                serial += 1
            lines += ["TER", "END"]
            return "\n".join(lines) + "\n"

        q_pdb = pdb_chain("A", helix(10), "ALA")
        c_pdb = pdb_chain("A", helix(30, phase=0.7), "ALA")
        worker = StructureVerificationWorker()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sw, "_TMTOOLS_AVAILABLE", False)
            score = worker.verify(q_pdb, "9XXX", "PDB_ID", c_pdb,
                                  signature_type="pdb_protein")
        assert score is not None
        assert score.metric_name == "structure_sequence_proxy"
        # 10-ALA chain inside 30-ALA chain: local identity 100, coverage 100
        assert score.normalized_score >= 95.0, score
        assert score.details.get("alignment_identity") is not None

    def test_proxy_still_none_on_unparsable(self, minimal_pdb):
        worker = StructureVerificationWorker()
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(sw, "_TMTOOLS_AVAILABLE", False)
            assert worker.verify(minimal_pdb, "9XXX", "PDB_ID",
                                 "NOT A STRUCTURE",
                                 signature_type="pdb_protein") is None
