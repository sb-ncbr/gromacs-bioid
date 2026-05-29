"""Deduplication and consensus scoring for identification hits."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..results.results_manager import ResultsManager


@dataclass
class RawHit:
    """A raw identification hit from a resolver."""
    identifier: str
    ident_type: str
    resolver_name: str
    resolver_score: float
    signature: str
    signature_type: str
    hit_type: str  # "identity" or "similarity"


def normalize_identifier(identifier: str, ident_type: str) -> str:
    """Normalize an identifier based on its type.
    
    Args:
        identifier: The identifier string to normalize.
        ident_type: The type of identifier (e.g., "PDB_ID", "CHEMBL_ID").
        
    Returns:
        Normalized identifier string.
    """
    ident_type_upper = ident_type.upper()
    
    if ident_type_upper == "PDB_ID":
        # Uppercase, strip _entity suffixes (e.g., 1abc_1 -> 1ABC)
        return identifier.upper().split("_")[0]
    
    elif ident_type_upper == "CHEMBL_ID":
        # Strip CHEMBL prefix if present, store canonical form as CHEMBL{ID}
        stripped = identifier
        if stripped.upper().startswith("CHEMBL"):
            stripped = stripped[6:]  # Remove "CHEMBL" prefix
        # Return canonical form
        return f"CHEMBL{stripped}"
    
    elif ident_type_upper == "CHEBI_ID":
        # Ensure CHEBI: prefix
        if not identifier.upper().startswith("CHEBI:"):
            return f"CHEBI:{identifier}"
        return identifier
    
    elif ident_type_upper == "UNIPROT_ID":
        # Uppercase
        return identifier.upper()
    
    elif ident_type_upper == "PUBCHEM_CID":
        # Just the string (it's numeric)
        return str(identifier)
    
    elif ident_type_upper == "ALPHAFOLD_ID":
        # Keep as-is
        return identifier
    
    else:
        # Default: strip whitespace, uppercase
        return identifier.strip().upper()


def collect_hits(results: ResultsManager, segment: str) -> list[RawHit]:
    """Collect all hits for a segment from ResultsManager.
    
    Args:
        results: ResultsManager containing identification results.
        segment: The segment/fragment name to collect hits for.
        
    Returns:
        Flat list of RawHit objects.
    """
    hits: list[RawHit] = []
    
    # Read all paths under identifiers/{segment}/
    base_path = f"identifiers/{segment}"
    data = results.get_data(base_path)
    
    if not data or not isinstance(data, dict):
        return hits
    
    # Iterate over signature generators
    for generator_name, generator_data in data.items():
        if not isinstance(generator_data, dict):
            continue
        
        # Iterate over resolvers
        for resolver_name, resolver_result in generator_data.items():
            # Skip non-dict entries (like "attempted" list)
            if not isinstance(resolver_result, dict):
                continue
            
            # Extract required fields
            signature = resolver_result.get("signature")
            hit_type = resolver_result.get("hit_type")
            hit_list = resolver_result.get("hits")
            ident_type = resolver_result.get("ident_type", "")
            
            if not signature or not hit_type or not hit_list or not ident_type:
                continue
            
            # Determine signature type from generator name
            signature_type = generator_name.lower().replace("_", "")
            
            # Process hits based on type
            if hit_type == "identity":
                # hits is list[str], each hit gets resolver_score=100.0
                for identifier in hit_list:
                    if isinstance(identifier, str):
                        hits.append(RawHit(
                            identifier=identifier,
                            ident_type=ident_type,
                            resolver_name=resolver_name,
                            resolver_score=100.0,
                            signature=signature,
                            signature_type=signature_type,
                            hit_type=hit_type
                        ))
            
            elif hit_type == "similarity":
                # hits is list[tuple[str, float]], each hit gets its float score
                for item in hit_list:
                    if isinstance(item, (list, tuple)) and len(item) >= 2:
                        identifier = item[0]
                        score = float(item[1])
                        hits.append(RawHit(
                            identifier=identifier,
                            ident_type=ident_type,
                            resolver_name=resolver_name,
                            resolver_score=score,
                            signature=signature,
                            signature_type=signature_type,
                            hit_type=hit_type
                        ))
    
    return hits


def deduplicate_and_score(
    hits: list[RawHit]
) -> dict[tuple[str, str], dict]:
    """Deduplicate hits and compute consensus scores.
    
    Groups hits by normalized identifier and ident_type, then computes
    a consensus score based on resolver diversity.
    
    Args:
        hits: List of RawHit objects.
        
    Returns:
        Dict mapping (normalized_id, ident_type) -> metadata dict with:
        - consensus_score: float
        - source_resolvers: list[str]
        - signature: str
        - signature_type: str
        - hit_type: str
    """
    # Group by (normalized_identifier, ident_type)
    groups: dict[tuple[str, str], list[RawHit]] = {}
    
    for hit in hits:
        key = (normalize_identifier(hit.identifier, hit.ident_type), hit.ident_type)
        if key not in groups:
            groups[key] = []
        groups[key].append(hit)
    
    # Compute consensus for each group
    result: dict[tuple[str, str], dict] = {}
    
    for (normalized_id, ident_type), group_hits in groups.items():
        # base_score = max resolver_score in the group
        base_score = max(hit.resolver_score for hit in group_hits)
        
        # diversity = number of distinct resolver_names
        distinct_resolvers = set(hit.resolver_name for hit in group_hits)
        diversity = len(distinct_resolvers)
        
        # consensus_score = base_score * log2(1 + diversity)
        consensus_score = base_score * math.log2(1 + diversity)
        
        # Collect source_resolvers list
        source_resolvers = sorted(distinct_resolvers)
        
        # Pick representative signature from hit with highest resolver_score
        best_hit = max(group_hits, key=lambda h: h.resolver_score)
        
        # Determine hit_type (identity takes precedence if mixed)
        has_identity = any(h.hit_type == "identity" for h in group_hits)
        effective_hit_type = "identity" if has_identity else "similarity"
        
        result[(normalized_id, ident_type)] = {
            "consensus_score": consensus_score,
            "source_resolvers": source_resolvers,
            "signature": best_hit.signature,
            "signature_type": best_hit.signature_type,
            "hit_type": effective_hit_type,
        }
    
    return result
