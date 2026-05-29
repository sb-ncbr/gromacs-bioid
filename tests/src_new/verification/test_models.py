"""Tests for verification data models."""

from __future__ import annotations

from src_new.verification.models import VerifiedHit, VerificationScore, AnnotationQuality


def test_verified_hit_creation() -> None:
    """Create a VerifiedHit with all fields and assert values."""
    hit = VerifiedHit(
        identifier="962",
        ident_type="PUBCHEM_CID",
        database="pubchem",
        resolver_score=100.0,
        similarity_score=98.5,
        annotation_quality_score=85.0,
        final_confidence=94.5,
        supporting_evidence_count=2,
        is_verified=True,
    )
    
    assert hit.identifier == "962"
    assert hit.ident_type == "PUBCHEM_CID"
    assert hit.database == "pubchem"
    assert hit.resolver_score == 100.0
    assert hit.similarity_score == 98.5
    assert hit.annotation_quality_score == 85.0
    assert hit.final_confidence == 94.5
    assert hit.supporting_evidence_count == 2
    assert hit.is_verified is True
    assert hit.rejection_reason is None


def test_verified_hit_unverified_factory() -> None:
    """Call VerifiedHit.unverified(...) and assert is_verified=False, final_confidence=0.0, rejection_reason='not_verified'."""
    hit = VerifiedHit.unverified(
        identifier="962",
        ident_type="PUBCHEM_CID",
        database="pubchem",
        resolver_score=50.0,
        supporting_evidence_count=1,
        rejection_reason="not_verified",
    )
    
    assert hit.identifier == "962"
    assert hit.ident_type == "PUBCHEM_CID"
    assert hit.database == "pubchem"
    assert hit.resolver_score == 50.0
    assert hit.similarity_score is None
    assert hit.annotation_quality_score is None
    assert hit.final_confidence == 0.0
    assert hit.supporting_evidence_count == 1
    assert hit.is_verified is False
    assert hit.rejection_reason == "not_verified"


def test_verification_score_creation() -> None:
    """Create VerificationScore and assert fields."""
    score = VerificationScore(
        kind="similarity",
        metric_name="multi_fingerprint_tanimoto",
        raw_score=0.95,
        normalized_score=95.0,
    )
    
    assert score.kind == "similarity"
    assert score.metric_name == "multi_fingerprint_tanimoto"
    assert score.raw_score == 0.95
    assert score.normalized_score == 95.0


def test_annotation_quality_creation() -> None:
    """Create AnnotationQuality and assert fields."""
    quality = AnnotationQuality(
        database="pdb",
        score=85.0,
        signals=["resolution", "r_free", "experimental_method"],
    )
    
    assert quality.database == "pdb"
    assert quality.score == 85.0
    assert quality.signals == ["resolution", "r_free", "experimental_method"]
    
    # Test default empty signals
    quality2 = AnnotationQuality(
        database="chembl",
        score=50.0,
    )
    assert quality2.database == "chembl"
    assert quality2.score == 50.0
    assert quality2.signals == []
