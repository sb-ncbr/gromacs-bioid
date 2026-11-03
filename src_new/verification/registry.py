"""Registry for verification workers, fetchers, and scorers."""

from __future__ import annotations

from .base import VerificationWorker, SignatureFetcher, AnnotationQualityScorer


# Red-team batch-4: signature kinds whose canonical form is a 3D structure
# (route structural identifiers to StructureSignatureFetcher for these).
_STRUCTURE_SIG_TYPES = {
    "pdb_protein", "pdb_nucleic", "ca_only_pdb", "mmcif",
    "pdb_protein_backbone", "pdb_nucleic_backbone",
}


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
    
    def get_fetcher(
        self,
        ident_type: str,
        signature_type: str | None = None,
    ) -> SignatureFetcher | None:
        """Get a fetcher that supports the given identifier type.

        Args:
            ident_type: The type of identifier.
            signature_type: Optional signature kind. Red-team batch-4 (known
                fetcher-routing bug): PDB_ID/ALPHAFOLD-family identifiers are
                supported by BOTH the sequence fetcher and the structure
                fetcher, and first-registration order silently routed every
                PDB_ID to the sequence fetcher — which is why all structure
                hits were tm:0.0. When the signature kind is known, structure
                kinds route to StructureSignatureFetcher and fasta kinds to
                SequenceSignatureFetcher; without it the historical order is
                preserved.

        Returns:
            A SignatureFetcher instance, or None if no fetcher supports this
            type.
        """
        if signature_type:
            st = signature_type.lower()
            prefer_structure = st in _STRUCTURE_SIG_TYPES or st.endswith("_pdb")
            for fetcher in self._fetchers:
                if not fetcher.supports(ident_type):
                    continue
                name = type(fetcher).__name__
                if prefer_structure and name == "StructureSignatureFetcher":
                    return fetcher
                if not prefer_structure and name == "SequenceSignatureFetcher":
                    return fetcher
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

    def begin_segment(self, *, live_fetch: bool, budget: int,
                      timeout_s: float,
                      min_interval_s: float = 1.0) -> None:
        """Per-segment wiring for budget-aware scorers (v3.142 1c).

        Scorers that consume live API budget (PubChem mirror live-fill)
        expose configure()/begin_segment(); scorers without those hooks are
        untouched. Called by the manager once per segment from config.
        Item-4 correction (11-03): min_interval_s is the per-process PUG
        rate limit knob (annotation_live_min_interval_s).
        """
        for scorer in self._scorers:
            configure = getattr(scorer, "configure", None)
            if callable(configure):
                configure(live_fetch=live_fetch, timeout_s=timeout_s,
                          min_interval_s=min_interval_s)
            begin = getattr(scorer, "begin_segment", None)
            if callable(begin):
                begin(budget)


def get_default_registry() -> VerificationRegistry:
    """Get a default registry with compound, sequence, structure, and element workers/fetchers/scorers.
    
    Returns:
        VerificationRegistry with:
        - workers: [ElementVerificationWorker(), CompoundVerificationWorker(), SequenceVerificationWorker(), StructureVerificationWorker()]
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
    from .workers import CompoundVerificationWorker, SequenceVerificationWorker, StructureVerificationWorker, ElementVerificationWorker
    
    # Element worker goes first to handle ELEMENT ident_type before other workers
    return VerificationRegistry(
        workers=[ElementVerificationWorker(), CompoundVerificationWorker(), SequenceVerificationWorker(), StructureVerificationWorker()],
        fetchers=[CompoundSignatureFetcher(), SequenceSignatureFetcher(), StructureSignatureFetcher()],
        scorers=[
            PDBAnnotationScorer(),
            UniProtAnnotationScorer(),
            PubChemAnnotationScorer(),
            ChemblAnnotationScorer(),
            ChebiAnnotationScorer(),
        ],
    )
