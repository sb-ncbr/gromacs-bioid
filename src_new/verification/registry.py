"""Registry for verification workers, fetchers, and scorers."""

from __future__ import annotations

from .base import VerificationWorker, SignatureFetcher, AnnotationQualityScorer


class VerificationRegistry:
    """Registry for verification components.
    
    Manages lookup of applicable workers, fetchers, and scorers based on
    signature and identifier types.
    """
    
    def __init__(
        self,
        workers: list[VerificationWorker],
        fetchers: list[SignatureFetcher],
        scorers: list[AnnotationQualityScorer],
    ) -> None:
        """Initialize the registry.
        
        Args:
            workers: List of verification workers.
            fetchers: List of signature fetchers.
            scorers: List of annotation quality scorers.
        """
        self._workers = workers
        self._fetchers = fetchers
        self._scorers = scorers
    
    def get_applicable_workers(
        self, 
        signature_type: str, 
        ident_type: str
    ) -> list[VerificationWorker]:
        """Get all workers applicable to the given signature and identifier types.
        
        Args:
            signature_type: The type of signature (e.g., "pdb", "chembl").
            ident_type: The type of identifier (e.g., "PDB_ID", "CHEMBL_ID").
            
        Returns:
            List of applicable VerificationWorker instances.
        """
        return [
            worker for worker in self._workers
            if worker.is_applicable(signature_type, ident_type)
        ]
    
    def get_fetcher(self, ident_type: str) -> SignatureFetcher | None:
        """Get a fetcher that supports the given identifier type.
        
        Args:
            ident_type: The type of identifier.
            
        Returns:
            A SignatureFetcher instance, or None if no fetcher supports this type.
        """
        for fetcher in self._fetchers:
            if fetcher.supports(ident_type):
                return fetcher
        return None
    
    def get_scorer(self, ident_type: str) -> AnnotationQualityScorer | None:
        """Get a scorer that supports the given identifier type.
        
        Args:
            ident_type: The type of identifier.
            
        Returns:
            An AnnotationQualityScorer instance, or None if no scorer supports this type.
        """
        for scorer in self._scorers:
            if scorer.supports(ident_type):
                return scorer
        return None


def get_default_registry() -> VerificationRegistry:
    """Get a default registry with compound, sequence, and structure workers/fetchers/scorers.
    
    Returns:
        VerificationRegistry with:
        - workers: [CompoundVerificationWorker(), SequenceVerificationWorker(), StructureVerificationWorker()]
        - fetchers: [CompoundSignatureFetcher(), SequenceSignatureFetcher(), StructureSignatureFetcher()]
        - scorers: [PDBAnnotationScorer(), UniProtAnnotationScorer(), 
                     PubChemAnnotationScorer(), ChemblAnnotationScorer(), 
                     ChebiAnnotationScorer()]
    """
    from .fetchers import CompoundSignatureFetcher, SequenceSignatureFetcher, StructureSignatureFetcher
    from .scorers import (
        PDBAnnotationScorer,
        UniProtAnnotationScorer,
        PubChemAnnotationScorer,
        ChemblAnnotationScorer,
        ChebiAnnotationScorer,
    )
    from .workers import CompoundVerificationWorker, SequenceVerificationWorker, StructureVerificationWorker
    
    return VerificationRegistry(
        workers=[CompoundVerificationWorker(), SequenceVerificationWorker(), StructureVerificationWorker()],
        fetchers=[CompoundSignatureFetcher(), SequenceSignatureFetcher(), StructureSignatureFetcher()],
        scorers=[
            PDBAnnotationScorer(),
            UniProtAnnotationScorer(),
            PubChemAnnotationScorer(),
            ChemblAnnotationScorer(),
            ChebiAnnotationScorer(),
        ],
    )
