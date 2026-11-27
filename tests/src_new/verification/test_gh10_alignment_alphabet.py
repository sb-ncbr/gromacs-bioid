"""GitHub #10: alphabet handling in the shared local alignment."""
import logging

from src_new.verification.alignment import local_identity_coverage
from src_new.verification.workers.sequence_worker import SequenceVerificationWorker

RNA = "CGGUGAGAAGGG"
PROTEIN = "MAVPETRPNHTIYINNLNEKIKKDELKKSLYAIFSQFGQILDILVSRSLK"


def test_rna_vs_protein_entity_is_not_comparable_and_quiet(caplog):
    with caplog.at_level(logging.WARNING):
        assert local_identity_coverage(RNA, PROTEIN, is_nucleotide=True) is None
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_nucleotide_reference_with_ambiguity_codes_scores():
    ident, cov = local_identity_coverage(RNA, RNA + "RYN", is_nucleotide=True)
    assert ident == 1.0 and cov == 1.0


def test_selenoprotein_letters_no_longer_raise():
    seq = "MKTAYIAKQRUQISFVKSHFSRQ"
    out = local_identity_coverage(seq, seq)
    assert out is not None and out[0] == 1.0 and out[1] == 1.0


def test_heuristic_unchanged_without_type():
    # protein-like letters that are also IUPAC codes stay on the protein path
    out = local_identity_coverage("MKHVSADKW", "MKHVSADKW")
    assert out == (1.0, 1.0)


def test_sequence_worker_rna_against_mixed_entities_picks_rna():
    w = SequenceVerificationWorker()
    score = w._score_best_orientation(RNA, PROTEIN, try_revcomp=True)
    assert score is None
    score = w._score_best_orientation(RNA, RNA, try_revcomp=True)
    assert score is not None and score.normalized_score == 100.0
