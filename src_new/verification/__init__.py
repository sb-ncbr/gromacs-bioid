"""Verification module for BioID v2 pipeline.

This module provides the verification layer that consumes identification results
and re-verifies hits by comparing simulation-extracted signatures against
canonical database signatures.

Non-verification is a normal outcome, not a fatal failure.
"""

from .base import VerificationWorker, SignatureFetcher, AnnotationQualityScorer
from .models import VerifiedHit, VerificationScore, AnnotationQuality
from .registry import VerificationRegistry, get_default_registry
from .dedup import RawHit, collect_hits, deduplicate_and_score, normalize_identifier
from .manager import VerificationManager
from .fetchers import CompoundSignatureFetcher, SequenceSignatureFetcher, StructureSignatureFetcher
from .workers import CompoundVerificationWorker, SequenceVerificationWorker, StructureVerificationWorker
from .scorers import (
    PDBAnnotationScorer,
    UniProtAnnotationScorer,
    PubChemAnnotationScorer,
    ChemblAnnotationScorer,
    ChebiAnnotationScorer,
)

__all__ = [
    "VerificationWorker",
    "SignatureFetcher",
    "AnnotationQualityScorer",
    "VerifiedHit",
    "VerificationScore",
    "AnnotationQuality",
    "VerificationRegistry",
    "get_default_registry",
    "RawHit",
    "collect_hits",
    "deduplicate_and_score",
    "normalize_identifier",
    "VerificationManager",
    "CompoundSignatureFetcher",
    "SequenceSignatureFetcher",
    "StructureSignatureFetcher",
    "CompoundVerificationWorker",
    "SequenceVerificationWorker",
    "StructureVerificationWorker",
    "PDBAnnotationScorer",
    "UniProtAnnotationScorer",
    "PubChemAnnotationScorer",
    "ChemblAnnotationScorer",
    "ChebiAnnotationScorer",
]
