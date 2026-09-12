"""Data models for the verification pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field


# Identifier types that name chemical compounds. For these, hit_type=="identity"
# must NEVER be sufficient evidence on its own (a formula/candidate list is not
# a compound confirmation): verification requires skeleton-fingerprint
# corroboration (F7, docs/CHEMISTRY_FIX_TODO.md).
CHEMICAL_IDENT_TYPES = frozenset({
    "PUBCHEM_CID", "CHEMBL_ID", "CHEBI_ID", "CHEBI", "INCHIKEY",
    "SMILES", "SELFIES", "PUBCHEM_SID",
})

# Minimum molecule-vs-candidate skeleton Tanimoto for chemical verification.
# Probe anchors: neutral-vs-dianion 1.0; true vs formula-mate 0.19; prodrug 0.58.
SKELF_VERIFY_THRESHOLD = 0.7


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
    # F7: skeleton-fingerprint corroboration for chemical hits (None = not computed)
    skeleton_sim: float | None = None
    skeleton_method: str | None = None
    
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
