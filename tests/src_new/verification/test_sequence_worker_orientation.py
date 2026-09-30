"""Wave-7 Phase 5 (C1): orientation-aware NA sequence verification.

Nucleotide queries score all four orientation senses and take the max;
protein scoring is untouched (gating by signature_type).
"""
from __future__ import annotations

import pytest

from src_new.molecules.nucleic_acid import sequence_orientation_variants
from src_new.verification.workers.sequence_worker import SequenceVerificationWorker


class TestOrientationVariants:
    def test_dna_four_senses(self):
        q = "GAGGT"
        variants = sequence_orientation_variants(q)
        expected = {"GAGGT", "TGGAG", "CTCCA", "ACCTC"}
        assert set(variants) == expected
        assert variants[0] == q

    def test_rna_pair_added_when_u(self):
        q = "GAGGU"
        variants = sequence_orientation_variants(q)
        # DNA pair (U->A tolerated) plus RNA pair (A<->U)
        assert "CUCCA" in variants          # RNA complement
        assert "ACCUC" in variants          # RNA revcomp
        assert len(variants) >= 5

    def test_x_n_passthrough(self):
        variants = sequence_orientation_variants("AXNG")
        assert "TXNC" in variants  # DNA complement of AXNG (X->X, N->N)

    def test_dedup(self):
        variants = sequence_orientation_variants("ATAT")
        assert len(variants) == len(set(variants))


class TestWorkerOrientationScoring:
    CANONICAL = "GAGGTGGGCAGGTGGA"  # fixture strand C

    def _worker(self):
        return SequenceVerificationWorker()

    @pytest.mark.parametrize("query", [
        CANONICAL,                                    # forward
        CANONICAL[::-1],                              # reversed (BFS artefact)
        "CTCCACCCGTCCACCT",                           # complement
        "TCCACCTGCCCACCTC",                           # reverse-complement
    ])
    def test_nucleotide_all_orientations_score_100(self, query):
        w = self._worker()
        score = w.verify(query, "fake_nt", "NT_ID",
                         canonical_signature=self.CANONICAL,
                         signature_type="residue_sequence_nucleotide")
        assert score is not None
        assert score.normalized_score == pytest.approx(100.0, abs=1e-6)

    def test_forward_is_not_damaged(self):
        w = self._worker()
        fwd = w.verify(self.CANONICAL, "x", "NT_ID",
                       canonical_signature=self.CANONICAL,
                       signature_type="residue_sequence_nucleotide")
        assert fwd.normalized_score == pytest.approx(100.0, abs=1e-6)

    def test_protein_path_untouched_by_orientation_logic(self):
        """Reversed protein must NOT be rescued (protein path == forward only)."""
        w = self._worker()
        prot = "MAGGLKDCF"
        score_oriented = w.verify(
            prot[::-1], "x", "UNIPROT_ID", canonical_signature=prot,
            signature_type="residue_sequence_protein")
        score_forward = w.verify(
            prot[::-1], "x", "UNIPROT_ID", canonical_signature=prot,
            signature_type="residue_sequence_nucleotide")
        assert score_oriented.normalized_score < 99.0  # not rescued
        # sanity: with NA gating the same string IS rescued (alphabet-safe here:
        # protein letters are preserved as-is, complement only flips ACGTUNX)
        assert score_forward.normalized_score >= score_oriented.normalized_score

    def test_score_never_below_forward_only(self):
        """No-regression property across orientations."""
        w = self._worker()
        for variant in sequence_orientation_variants(self.CANONICAL):
            with_variants = w.verify(variant, "x", "NT_ID",
                                     canonical_signature=self.CANONICAL,
                                     signature_type="residue_sequence_nucleotide")
            forward_only = w._compute_alignment_score(variant, self.CANONICAL)
            assert with_variants.normalized_score >= (
                forward_only.normalized_score if forward_only else 0.0
            )
