"""Base classes for the verification pipeline."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import VerificationScore, AnnotationQuality


class VerificationWorker(ABC):
    """Abstract base class for verification workers.
    
    Each worker implements verification for a specific signature/identifier type pair.
    """
    
    @abstractmethod
    def is_applicable(self, signature_type: str, ident_type: str) -> bool:
        """Check if this worker can verify the given signature and identifier types."""
        pass
    
    @abstractmethod
    def verify(
        self,
        signature: str,
        identifier: str,
        ident_type: str,
        canonical_signature: str | None = None,
        signature_type: str | None = None,
    ) -> VerificationScore | None:
        """Verify a hit by comparing simulation signature against canonical signature.

        Args:
            signature: The signature extracted from simulation.
            identifier: The identifier (e.g., database ID).
            ident_type: The type of identifier (e.g., "PUBCHEM_CID").
            canonical_signature: Optional pre-fetched canonical signature for comparison.
            signature_type: Optional canonical signature type (e.g.,
                "residue_sequence_nucleotide"); only the sequence worker
                uses it (wave-7 orientation handling). Others ignore it.

        Returns:
            VerificationScore if verification was performed, None if not applicable.
            Non-verification is a normal outcome, not an error.
        """
        pass


class SignatureFetcher(ABC):
    """Abstract base class for fetching canonical signatures from databases."""
    
    @abstractmethod
    def supports(self, ident_type: str) -> bool:
        """Check if this fetcher supports the given identifier type."""
        pass
    
    @abstractmethod
    def fetch(self, identifier: str, ident_type: str) -> str | None:
        """Fetch the canonical signature for an identifier.
        
        Returns:
            The canonical signature string, or None if not found.
            None is a normal outcome, not an error.
        """
        pass


class AnnotationQualityScorer(ABC):
    """Abstract base class for scoring annotation quality."""
    
    @abstractmethod
    def supports(self, ident_type: str) -> bool:
        """Check if this scorer supports the given identifier type."""
        pass
    
    @abstractmethod
    def score(self, identifier: str, ident_type: str) -> AnnotationQuality | None:
        """Score the annotation quality for an identifier.
        
        Returns:
            AnnotationQuality if scoring was performed, None if not applicable.
            None is a normal outcome, not an error.
        """
        pass
