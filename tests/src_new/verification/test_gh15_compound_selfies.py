"""GitHub #15: CompoundVerificationWorker decodes selfies signatures."""
import logging

import pytest

pytest.importorskip("selfies")

from src_new.verification.workers.compound_worker import CompoundVerificationWorker

_ASPIRIN = "CC(=O)Oc1ccccc1C(=O)O"
_ASPIRIN_SELFIES = __import__("selfies").encoder(_ASPIRIN)


def test_selfies_signature_scores_without_warnings(caplog):
    with caplog.at_level(logging.WARNING):
        score = CompoundVerificationWorker().verify(
            _ASPIRIN_SELFIES, "2244", "PUBCHEM_CID", canonical_signature=_ASPIRIN,
            signature_type="selfies")
    assert score is not None and score.normalized_score == 100.0
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]


def test_bracketed_smiles_not_decoded_as_selfies():
    score = CompoundVerificationWorker().verify(
        "CC[C@H](N)O", "1", "PUBCHEM_CID", canonical_signature="CC[C@H](N)O",
        signature_type="smiles")
    assert score is not None and score.normalized_score == 100.0
