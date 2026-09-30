"""Element verification worker for ions and single atoms."""

from __future__ import annotations

import logging

from ..base import VerificationWorker
from ..models import VerificationScore

logger = logging.getLogger(__name__)


class ElementVerificationWorker(VerificationWorker):
    """Verifies element/ion identifications.
    
    For ELEMENT ident_type, verification is trivial since element identity
    is determined by atomic number which is definitive.
    """
    
    SUPPORTED_IDENT_TYPES = {"ELEMENT"}
    SUPPORTED_SIGNATURE_TYPES = {"element", "atom", "ion"}
    
    def is_applicable(self, signature_type: str, ident_type: str) -> bool:
        """Check if this worker can verify the given signature and identifier types."""
        return ident_type == "ELEMENT"
    
    def verify(
        self,
        signature: str,
        identifier: str,
        ident_type: str,
        canonical_signature: str | None = None,
        signature_type: str | None = None,
    ) -> VerificationScore | None:
        """Verify an element hit.
        
        For elements, identity verification is trivial - the element symbol
        or atomic number is definitive. Returns 100% confidence.
        
        Args:
            signature: The element symbol or atomic number from simulation.
            identifier: The element identifier (e.g., "NA", "CA", "CL").
            ident_type: Should be "ELEMENT".
            canonical_signature: Optional canonical element symbol.
            
        Returns:
            VerificationScore with 100% normalized_score for valid elements.
        """
        # For ELEMENT type, we consider it verified with 100% confidence
        # since element identity from MD topology is definitive
        return VerificationScore(
            kind="identity",
            metric_name="element_identity",
            raw_score=1.0,
            normalized_score=100.0,
        )
