"""Verification manager for BioID v2 pipeline."""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..config.loader import RunConfig
    from ..results.results_manager import ResultsManager

from .base import VerificationWorker, SignatureFetcher, AnnotationQualityScorer
from .dedup import RawHit, collect_hits, deduplicate_and_score
from .models import VerifiedHit, VerificationScore, AnnotationQuality
from .registry import VerificationRegistry, get_default_registry


class VerificationManager:
    """Manages the verification pipeline for identification results.
    
    Consumes identification results from ResultsManager and re-verifies hits
    by comparing simulation-extracted signatures against canonical database signatures.
    
    Non-verification is a normal outcome, not a fatal failure.
    """
    
    def __init__(
        self, 
        config: RunConfig,
        registry: VerificationRegistry | None = None,
    ) -> None:
        """Initialize the verification manager.
        
        Args:
            config: Run configuration with verification settings.
            registry: VerificationRegistry with workers, fetchers, and scorers.
                     If None, uses get_default_registry() (empty lists).
        """
        self.config = config
        self._verification_config = config.verification
        self._registry = registry if registry is not None else get_default_registry()
    
    def verify_all(
        self, 
        results: ResultsManager
    ) -> dict[str, list[VerifiedHit]]:
        """Verify all identification hits from the results manager.
        
        Args:
            results: ResultsManager containing identification results to verify.
            
        Returns:
            Dict mapping segment name -> list of VerifiedHit objects.
            Each hit has is_verified=True if verification succeeded, False otherwise.
        """
        per_segment_results: dict[str, list[VerifiedHit]] = {}
        
        # Get all segment names from identifiers data
        identifiers_data = results.get_data("identifiers")
        if not identifiers_data or not isinstance(identifiers_data, dict):
            return per_segment_results
        
        segment_names = list(identifiers_data.keys())
        
        for segment in segment_names:
            # Check if identifiers/{segment}/ exists
            segment_path = f"identifiers/{segment}"
            if not results.data_exists(segment_path):
                continue
            
            # Collect and deduplicate hits
            raw_hits = collect_hits(results, segment)
            if not raw_hits:
                continue
            
            deduped = deduplicate_and_score(raw_hits)
            if not deduped:
                continue
            
            # Sort groups by consensus_score descending
            sorted_groups = sorted(
                deduped.items(),
                key=lambda x: x[1]["consensus_score"],
                reverse=True
            )
            
            # Take top N
            top_n = self._verification_config.verify_top_n
            top_groups = sorted_groups[:top_n]
            
            verified_hits: list[VerifiedHit] = []
            
            for (normalized_id, ident_type), metadata in top_groups:
                signature = metadata["signature"]
                signature_type = metadata["signature_type"]
                consensus_score = metadata["consensus_score"]
                source_resolvers = metadata["source_resolvers"]
                hit_type = metadata["hit_type"]
                
                
                # Look up SignatureFetcher
                fetcher = self._registry.get_fetcher(ident_type)
                canonical_signature: str | None = None
                if fetcher:
                    try:
                        canonical_signature = fetcher.fetch(normalized_id, ident_type)
                    except Exception:
                        # Fetch failed, but we continue
                        pass
                
                # Look up applicable workers
                workers = self._registry.get_applicable_workers(
                    signature_type, ident_type
                )
                
                # Try verification with workers
                similarity_score: VerificationScore | None = None
                rejection_reason: str | None = None
                
                if workers:
                    for worker in workers:
                        try:
                            score = worker.verify(signature, normalized_id, ident_type, canonical_signature)
                            if score is not None:
                                similarity_score = score
                                break
                        except Exception:
                            # Worker failed, try next one
                            continue
                    
                    if similarity_score is None:
                        rejection_reason = "verification_failed"
                else:
                    rejection_reason = "no_worker"
                
                
                # Look up AnnotationQualityScorer
                scorer = self._registry.get_scorer(ident_type)
                annotation_score: float | None = None
                if scorer:
                    try:
                        quality = scorer.score(normalized_id, ident_type)
                        if quality is not None:
                            annotation_score = quality.normalized_score if hasattr(quality, 'normalized_score') else quality.score
                    except Exception:
                        # Scorer failed, continue
                        pass
                
                # Aggregate final confidence with configured weights
                w_resolver = self._verification_config.resolver_weight
                w_similarity = self._verification_config.similarity_weight
                w_annotation = self._verification_config.annotation_weight
                
                resolver_component = min(consensus_score, 100.0)
                similarity_component = (
                    similarity_score.normalized_score if similarity_score else 0.0
                )
                annotation_component = annotation_score if annotation_score else 0.0
                
                # Sanitize NaN/Inf in components
                if similarity_component is not None and (math.isnan(similarity_component) or math.isinf(similarity_component)):
                    similarity_component = 0.0
                if annotation_component is not None and (math.isnan(annotation_component) or math.isinf(annotation_component)):
                    annotation_component = 0.0
                
                final_confidence = (
                    w_resolver * resolver_component +
                    w_similarity * similarity_component +
                    w_annotation * annotation_component
                )
                
                # Sanitize NaN/Inf in final_confidence
                if math.isnan(final_confidence) or math.isinf(final_confidence):
                    final_confidence = 0.0
                
                # Determine if verified
                min_confidence = self._verification_config.min_final_confidence
                has_positive_evidence = similarity_score is not None or annotation_score is not None
                
                if final_confidence >= min_confidence and has_positive_evidence:
                    # Create verified hit
                    verified_hit = VerifiedHit(
                        identifier=normalized_id,
                        ident_type=ident_type,
                        database=ident_type.replace("_ID", "").lower(),
                        resolver_score=min(consensus_score, 100.0),
                        similarity_score=similarity_score.normalized_score if similarity_score else None,
                        annotation_quality_score=annotation_score,
                        final_confidence=min(final_confidence, 100.0),
                        supporting_evidence_count=len(source_resolvers),
                        is_verified=True,
                    )
                else:
                    # Create unverified hit
                    if rejection_reason is None:
                        rejection_reason = "below_threshold"
                    
                    verified_hit = VerifiedHit.unverified(
                        identifier=normalized_id,
                        ident_type=ident_type,
                        database=ident_type.replace("_ID", "").lower(),
                        resolver_score=min(consensus_score, 100.0),
                        supporting_evidence_count=len(source_resolvers),
                        rejection_reason=rejection_reason,
                    )
                
                verified_hits.append(verified_hit)
            
            # Store results back to ResultsManager
            output_path = f"verification/{segment}/verified_hits"
            hits_as_dicts = [dataclasses.asdict(hit) for hit in verified_hits]
            results.set_data(output_path, hits_as_dicts)
            
            per_segment_results[segment] = verified_hits
        
        return per_segment_results
