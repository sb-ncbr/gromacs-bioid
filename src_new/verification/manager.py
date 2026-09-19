"""Verification manager for BioID v2 pipeline."""

from __future__ import annotations

import dataclasses
import math
from typing import TYPE_CHECKING

import logging

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from ..config.loader import RunConfig
    from ..results.results_manager import ResultsManager

from .base import VerificationWorker, SignatureFetcher, AnnotationQualityScorer
from .dedup import RawHit, collect_hits, deduplicate_and_score
from .models import VerifiedHit, VerificationScore, AnnotationQuality
from ..signatures.skeletize import from_smiles, hex_to_fp, parse_signature, skeleton_fp as _skel_fp, tanimoto as _skel_tanimoto
from .models import CHEMICAL_IDENT_TYPES, SKELF_VERIFY_THRESHOLD
from .registry import VerificationRegistry, get_default_registry


def _molecule_skeleton_fp_hex(results, segment: str):
    """Fetch the molecule's skeleton_fp signature hex for a segment, if any."""
    try:
        value = results.get_data(f"signatures/{segment}/generated/skeleton_fp")
    except Exception:
        return None
    if not value:
        return None
    hex_part, _ = parse_signature(str(value))
    return hex_part


def _chemical_corroboration(results, segment: str, canonical_signature):
    """Skeleton Tanimoto between molecule and candidate canonical SMILES.

    Returns (sim, method) or (None, reason).
    """
    if not canonical_signature or not isinstance(canonical_signature, str):
        return None, "fingerprint_unavailable"
    mol_hex = _molecule_skeleton_fp_hex(results, segment)
    if not mol_hex:
        return None, "fingerprint_unavailable"
    try:
        mol_fp = hex_to_fp(mol_hex)
        cand_fp = _skel_fp(from_smiles(canonical_signature))
        if mol_fp is None or cand_fp is None:
            return None, "fingerprint_unavailable"
        return _skel_tanimoto(mol_fp, cand_fp), "skelfp:v1"
    except Exception:
        return None, "fingerprint_unavailable"


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
        results: ResultsManager,
        deadline_epoch: float | None = None,
    ) -> dict[str, list[VerifiedHit]]:
        """Verify all identification hits from the results manager.

        Args:
            results: ResultsManager containing identification results to verify.
            deadline_epoch: Optional wall-clock deadline (time.time() seconds).
                When exceeded, verification returns the partial results gathered
                so far instead of burning more time on fetch-bound candidate
                fan-out (stage-time-budget policy, wave-3 stall fix).

        Returns:
            Dict mapping segment name -> list of VerifiedHit objects.
            Each hit has is_verified=True if verification succeeded, False otherwise.
        """
        import time as _time
        per_segment_results: dict[str, list[VerifiedHit]] = {}

        def _over_budget() -> bool:
            return deadline_epoch is not None and _time.time() > deadline_epoch

        # Get all segment names from identifiers data
        identifiers_data = results.get_data("identifiers")
        if not identifiers_data or not isinstance(identifiers_data, dict):
            return per_segment_results
        
        segment_names = list(identifiers_data.keys())
        
        for segment in segment_names:
            if _over_budget():
                logger.warning(f"verify_all: deadline exceeded before segment {segment}; returning partial results")
                return per_segment_results
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
            
            # Batch-warm canonical structures for chemical candidates (one CSV
            # call per ~50 CIDs instead of N serial 503-prone calls; F7 gate)
            try:
                chem_cids = [str(nid) for (nid, it), _m in top_groups if it in CHEMICAL_IDENT_TYPES]
                if chem_cids:
                    from .fetchers.compound_fetcher import prefetch_pubchem
                    prefetch_pubchem(chem_cids)
            except Exception as warm_exc:
                logger.warning(f"chemical prefetch failed (non-fatal): {warm_exc}")
            
            verified_hits: list[VerifiedHit] = []

            for (normalized_id, ident_type), metadata in top_groups:
                if _over_budget():
                    logger.warning(
                        f"verify_all: deadline exceeded mid-segment {segment} "
                        f"({len(verified_hits)}/{len(top_groups)} verified); returning partial results"
                    )
                    return per_segment_results
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
                
                skeleton_sim = None
                skeleton_method = None
                if ident_type in CHEMICAL_IDENT_TYPES:
                    skeleton_sim, _c_m = _chemical_corroboration(
                        results, segment, canonical_signature
                    )
                    skeleton_method = _c_m if skeleton_sim is not None else None

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

                # Structure-anchored reranking for chemical candidates:
                # the skeleton-Tanimoto between Molecule and candidate (F7 evidence)
                # is truth the worker's signature-vs-canonical proxy lacks when
                # the generated SMILES is corrupted. Raise-only: rescues correct
                # hits buried in formula floods; never lets junk sink below legacy.
                if ident_type in CHEMICAL_IDENT_TYPES and skeleton_sim is not None:
                    similarity_component = max(similarity_component, skeleton_sim * 100.0)
                
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
                # Identity hits can be verified without similarity/annotation scores
                # For non-identity hits, require positive evidence (score > 0)
                min_confidence = self._verification_config.min_final_confidence
                has_positive_evidence = (
                    similarity_score is not None or 
                    (annotation_score is not None and annotation_score > 0) or 
                    hit_type == "identity"
                )
                
                # F7 chemical gate: identity/candidate hits are NEVER sufficient
                # for chemical compounds - require skeleton-fingerprint
                # corroboration between the molecule and the candidate structure.
                if ident_type in CHEMICAL_IDENT_TYPES:
                    has_positive_evidence = (
                        skeleton_sim is not None
                        and skeleton_sim >= SKELF_VERIFY_THRESHOLD
                    )
                    if not has_positive_evidence:
                        rejection_reason = (
                            "fingerprint_mismatch" if skeleton_sim is not None
                            else "fingerprint_unavailable"
                        )
                
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
                        skeleton_sim=skeleton_sim,
                        skeleton_method=skeleton_method,
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
                    if ident_type in CHEMICAL_IDENT_TYPES:
                        verified_hit.skeleton_sim = skeleton_sim
                        verified_hit.skeleton_method = skeleton_method
                
                verified_hits.append(verified_hit)
            
            # Store results back to ResultsManager
            output_path = f"verification/{segment}/verified_hits"
            hits_as_dicts = [dataclasses.asdict(hit) for hit in verified_hits]
            results.set_data(output_path, hits_as_dicts)
            
            per_segment_results[segment] = verified_hits
        
        return per_segment_results
