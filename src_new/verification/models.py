"""Data models for the verification pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class VerificationScore:
    """A single verification score comparing simulation vs canonical signature."""
    kind: str  # "identity" | "similarity"
    metric_name: str
    raw_score: float
    normalized_score: float  # 0-100


@dataclass
class AnnotationQuality:
    """Quality assessment of annotation data for an identifier."""
    database: str
    score: float  # 0-100
    signals: list[str] = field(default_factory=list)  # list of quality signal names found


@dataclass
class VerifiedHit:
    """Result of verification for a single identification hit.
    
    Non-verification is a normal outcome, not a fatal failure.
    When is_verified=False, the hit was not confirmed through verification.
    """
    identifier: str
    ident_type: str
    database: str
    resolver_score: float  # original resolver confidence, 0-100
    similarity_score: float | None
    annotation_quality_score: float | None
    final_confidence: float
    supporting_evidence_count: int  # how many distinct resolvers found this hit
    is_verified: bool
    rejection_reason: str | None = None
    
    @classmethod
    def unverified(
        cls,
        identifier: str,
        ident_type: str,
        database: str,
        resolver_score: float = 0.0,
        supporting_evidence_count: int = 1,
        rejection_reason: str = "not_verified",
    ) -> VerifiedHit:
        """Create an unverified hit representing the non-failure non-verification path.
        
        This factory method encodes that non-verification is a normal outcome.
        """
        return cls(
            identifier=identifier,
            ident_type=ident_type,
            database=database,
            resolver_score=resolver_score,
            similarity_score=None,
            annotation_quality_score=None,
            final_confidence=0.0,
            supporting_evidence_count=supporting_evidence_count,
            is_verified=False,
            rejection_reason=rejection_reason,
        )
