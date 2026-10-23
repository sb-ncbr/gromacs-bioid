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

# Red-team batch-4 (known issue #2): degenerate similarity measurements must
# never count as positive evidence. Floors are per worker metric; metrics not
# listed (chemical multi-fingerprint, element identity) keep their own gates —
# chemicals are already gated by SKELF_VERIFY_THRESHOLD. Conservative by
# design: only scores no true hit could plausibly produce are rejected.
SIMILARITY_FLOORS: dict[str, float] = {
    "tm_score": 30.0,                   # TM < 0.30 is random for ~150 aa
    "structure_sequence_proxy": 25.0,
    "seq_identity_coverage": 25.0,
}


def similarity_meets_floor(metric_name: str, normalized_score: float) -> bool:
    """True when a worker similarity score is non-degenerate for its metric.

    Unknown metrics pass — they carry their own verification gates. This is
    the single choke point the manager uses so a 0.0-TM row or a 12 % gap-
    scattered alignment can never masquerade as corroboration."""
    floor = SIMILARITY_FLOORS.get(metric_name)
    return floor is None or normalized_score >= floor


def ref_seq_sha1(reference_sequence: str) -> str:
    """Stable short hash of a reference sequence for equivalence classes
    (red-team batch-4, D-06): classes are keyed on reference CONTENT, never
    on a rounded alignment/TM score. 16 hex chars are ample collision
    resistance at record counts (birthday bound ~4e9)."""
    import hashlib
    return hashlib.sha1(reference_sequence.encode("utf-8")).hexdigest()[:16]


@dataclass
class VerificationScore:
    """A single verification score comparing simulation vs canonical signature."""
    kind: str  # "identity" | "similarity"
    metric_name: str
    raw_score: float
    normalized_score: float  # 0-100
    # Red-team batch-4: additive measurement detail (e.g. reference-normalized
    # TM, matched chain pair). Threaded to VerifiedHit.similarity_details.
    details: dict = field(default_factory=dict)


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
    final_confidence: float | None  # None only on legacy v3.140 plateau runs (v3.142+: always emitted)
    supporting_evidence_count: int  # how many distinct resolvers found this hit
    is_verified: bool
    rejection_reason: str | None = None
    # F7: skeleton-fingerprint corroboration for chemical hits (None = not computed)
    skeleton_sim: float | None = None
    skeleton_method: str | None = None
    # F-17 (2026-10-04): telemetry flag — True when a NON-CHEMICAL identity
    # hit reached is_verified by assertion alone, i.e. corroboration fetch /
    # verification workers produced no similarity score (outage, missing
    # fetcher, worker None). DOES NOT change verification semantics: the hit
    # remains verified/identity exactly as before (user ruling); the flag only
    # records that fact for later surfacing (UI/methodology accounting).
    verified_without_corroboration: bool = False
    # v3.142 (R-a): agreement-structure belief score 0-100 ("how much external
    # databases believe this is the molecule"), magnitude-free per calibrated
    # chains formula (see dedup.resolver_belief). THIS is the resolver component
    # of final_confidence going forward; resolver_score above is retained as the
    # legacy min(consensus,100) trace for old-runner comparability. Additive;
    # None on hits emitted before v3.142.
    belief: float | None = None
    # v3.142 (Phase 4): visual-collapse equivalence class id ("skeleton:",
    # "align:", "tm:", "element:", "record:" prefixes). Same verified
    # structure => same class id across database records. Additive; None on
    # hits emitted before v3.142.
    equivalence_class_id: str | None = None
    # Red-team batch-4 (D-13): additive measurement detail from the worker
    # (query-vs-reference normalization, matched chain pair, later per 5.2
    # alignment identity/coverage). None on hits emitted before batch 4.
    similarity_details: dict | None = None
    # Element ground truth (user ruling 2026-10-11): for a monoatomic segment,
    # an ELEMENT identity hit IS the ground truth — there is no fetchable
    # annotation evidence for a bare element by construction, so the weighted
    # aggregate (resolver 0.4 + similarity 0.4 + annotation 0.2) structurally
    # caps at 80. VerificationManager lifts such hits to final_confidence=100
    # and records the rule id here for auditability. None = normal weighted path.
    ground_truth_override: str | None = None
    
    @classmethod
    def unverified(
        cls,
        identifier: str,
        ident_type: str,
        database: str,
        resolver_score: float = 0.0,
        supporting_evidence_count: int = 1,
        rejection_reason: str = "not_verified",
        similarity_score: float | None = None,
        annotation_quality_score: float | None = None,
        similarity_details: dict | None = None,
    ) -> VerifiedHit:
        """Create an unverified hit representing the non-failure non-verification path.

        This factory method encodes that non-verification is a normal outcome.
        v3.143 (D-17): keep the measurements when a worker/scorer actually
        ran — a rejected row with S=12 must not look like 'never compared'.
        final_confidence stays the 0.0 rejection floor.
        """
        return cls(
            identifier=identifier,
            ident_type=ident_type,
            database=database,
            resolver_score=resolver_score,
            similarity_score=similarity_score,
            annotation_quality_score=annotation_quality_score,
            final_confidence=0.0,
            supporting_evidence_count=supporting_evidence_count,
            is_verified=False,
            rejection_reason=rejection_reason,
            similarity_details=similarity_details,
        )
