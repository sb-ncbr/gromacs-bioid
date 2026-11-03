"""Deduplication and consensus scoring for identification hits."""

from __future__ import annotations

import logging

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

logger = logging.getLogger("verification")

if TYPE_CHECKING:
    from ..results.results_manager import ResultsManager

# F-18: single source of truth for the generator-name -> signature-type map.
from ..signatures.canonical import CANONICAL_SIGNATURE_TYPES as _CANONICAL_SIGNATURE_TYPES
from ..signatures.canonical import canonical_signature_type as _canonical_signature_type


# Belief-term calibration (v3.142 "R-a", user-approved 2026-10-23). Grounded on
# the 5,993-annotation organic-GT campaign corpus (strict family-scope replay,
# 6,076 entry-segment windows / 64,346 verified groups): kappa=1/3 shared the
# top concordance (0.8412) with argmax accuracy 0.9934; rho is order-irrelevant
# (monotone transform over eff), fixed at 1/2 for legible value semantics:
# every additional independent identity resolution halves residual doubt; three
# similarity chains ~ one identity claim. Evidence: .tmp/CALIBRATION_v3142.md.
# Rationale: resolver outputs are PROPOSALS, not evidence (user doctrine) — the
# raw resolver_score magnitudes (pubchem-family threshold stubs, identity hits
# hardcoded 100) must never enter confidence. What counts as external-database
# belief is the agreement STRUCTURE: how many distinct resolver chains assert
# this record, weighted by claim strength (identity > similarity).
BELIEF_RHO = 0.5
BELIEF_KAPPA = 1.0 / 3.0


def resolver_belief(n_identity_chains: int, n_similarity_chains: int) -> float:
    """External-database belief score 0-100 from resolver agreement structure.

    belief = 100 * (1 - BELIEF_RHO**(n_id + BELIEF_KAPPA*n_sim)); 0 for no chains.
    Values: 1 identity -> 50.0; 2 identities / 1 identity + 3 similarities ->
    75.0; 3 identities -> 87.5; lone similarity chain ~ 20.6. Never reaches 100:
    agreement asymptotically approaches certainty but never declares it —
    certainty is owned by verification (skeleton/alignment/ground truth).
    The explicit cap also guards float underflow (rho**eff -> 0.0 for eff>~106
    would otherwise print exact 100.0).
    """
    eff = n_identity_chains + BELIEF_KAPPA * n_similarity_chains
    if eff <= 0.0:
        return 0.0
    return min(100.0 * (1.0 - BELIEF_RHO ** eff), 99.9999)


# Red-team batch-4 (D-08): belief must count EVIDENCE FAMILIES (distinct
# databases/source classes), not resolver names. Multiple chains hit the
# SAME index and are not independent evidence:
#   formula_pubchem + formula_pubchem_local + formula_hfamily -> the one
#       PubChem formula index (a candidate LIST, not an exact accession)
#   inchikey_pubchem + inchikey_self -> the one InChIKey family
#   blast_uniprot + blast_swissprot_protein -> the one Swiss-Prot search
# Unknown resolvers fall back to their own name (never collapse what we
# cannot prove identical).
RESOLVER_SOURCES: dict[str, str] = {
    "formula_pubchem": "pubchem-formula",
    "formula_pubchem_local": "pubchem-formula",
    "formula_hfamily": "pubchem-formula",
    "pubchem_struct": "pubchem-structure",
    "idsm_pubchem": "pubchem-structure",
    "inchikey_pubchem": "inchikey",
    "inchikey_self": "inchikey",
    "chembl_struct": "chembl-structure",
    "idsm_chembl": "chembl-structure",
    "formula_chembl": "chembl-formula",
    "idsm_chebi": "chebi-structure",
    "lipid_maps": "lipidmaps",
    "glycan_composition": "glycan-composition",
    "blast_uniprot": "uniprot-seq",
    "blast_swissprot_protein": "uniprot-seq",
    "blast_pdb_protein": "rcsb-seq",
    "blast_pdb_nucleic": "rcsb-seq",
    "blast_nr_protein": "nr-seq",
    "blast_nt": "nt-seq",
    "blast_core_nt": "nt-seq",
    "foldseek_3di": "foldseek-struct",
    "alphafind_struct": "alphafind-struct",
    "atom": "atom",
    "name": "name-lookup",
}
# Sources that emit CANDIDATE LISTS (formula/composition index hits): an
# "identity" assertion coming exclusively from these is a candidate
# assertion (C-09b), not an exact-record confirmation.
FORMULA_SOURCES = frozenset(
    {"pubchem-formula", "chembl-formula", "glycan-composition"})

# Structure-search resolvers: their hits are pure spatial evidence. Under
# ruling D2 ("tiebreak") they are excluded from consensus diversity and
# belief and may only order equal-consensus rows (corpus c13 item 2).
_STRUCTURE_MODE_RESOLVERS = frozenset(
    {"mmcif_struct", "pdb_struct_protein", "pdb_struct_nucleotide",
     "foldseek_3di", "alphafind_struct"})

# D-08 pooling: SWISSPROT_ID and UNIPROT_ID name the SAME accession
# namespace searched by the same source (Swiss-Prot); their rows must pool
# into ONE evidence family instead of forming never-merged twin groups.
_POOL_IDENT_TYPES = {"SWISSPROT_ID": "UNIPROT_ID"}


def _resolver_source(resolver_name: str) -> str:
    """Evidence-family id for a resolver name (fallback: the name itself).

    D-13: collect_hits passes the record KEY as resolver_name, and the
    dual-key layout persists similarity listings under "{resolver}@sim" —
    strip the tier suffix so both listings of one resolver map to the same
    evidence family (and unknown "@sim" names fall back to the base name).
    """
    name = resolver_name.split("@", 1)[0]
    return RESOLVER_SOURCES.get(name, name)


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
            
            # Determine signature type: prefer from resolver result, fallback to canonical mapping
            signature_type = resolver_result.get("signature_type")
            if signature_type is None:
                signature_type = _canonical_signature_type(generator_name)
            if signature_type is None:
                logger.warning(f"Unknown signature generator '{generator_name}', using fallback")
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
                        try:
                            score = float(item[1])
                        except (TypeError, ValueError):
                            # v3.143 (red-team D-14): one malformed score must
                            # not abort the whole segment — skip it, count the
                            # skip in the logs, keep the good hits.
                            logger.warning(
                                f"collect_hits: skipping malformed score "
                                f"{item!r} from {resolver_name}/{generator_name}"
                            )
                            continue
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
    hits: list[RawHit],
    structure_mode: str = "full",
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
    # Group by (normalized_identifier, ident_type); D-08: UniProt-family
    # ident types pool by accession (same database, same namespace).
    groups: dict[tuple[str, str], list[RawHit]] = {}
    
    for hit in hits:
        pooled_type = _POOL_IDENT_TYPES.get(hit.ident_type, hit.ident_type)
        key = (normalize_identifier(hit.identifier, hit.ident_type), pooled_type)
        if key not in groups:
            groups[key] = []
        groups[key].append(hit)
    
    # Compute consensus for each group
    result: dict[tuple[str, str], dict] = {}
    
    for (normalized_id, ident_type), group_hits in groups.items():
        structure_corroborated = any(
            h.resolver_name.split("@", 1)[0] in _STRUCTURE_MODE_RESOLVERS
            for h in group_hits)
        scoring_hits = group_hits
        if structure_mode == "tiebreak":
            # structure sources never raise a score in tiebreak mode — not
            # even when they are the ONLY sources (the row stays, attributed,
            # with zero scoring mass and is kept out of the window by the
            # manager's structure-only exclusion).
            scoring_hits = [h for h in group_hits
                            if h.resolver_name.split("@", 1)[0]
                            not in _STRUCTURE_MODE_RESOLVERS]
        
        # base_score = max resolver_score in the group
        base_score = max((hit.resolver_score for hit in scoring_hits),
                         default=0.0)
        
        # Sanitize NaN/Inf in base_score
        if math.isnan(base_score) or math.isinf(base_score):
            base_score = 0.0
        
        # diversity = number of distinct resolver BASE names; D-13a:
        # collect_hits passes the record KEY as resolver_name and dual-mode
        # resolvers persist their similarity listing under "{resolver}@sim",
        # so a record-name count would score one dual-listed resolver as two
        # evidence sources.  Source attribution (source_resolvers and the
        # supporting_evidence_count derived from it) uses the same base-name
        # collapse.
        distinct_resolvers = {hit.resolver_name.split("@", 1)[0]
                              for hit in scoring_hits}
        diversity = len(distinct_resolvers)
        
        # consensus_score = base_score * log2(1 + diversity)
        consensus_score = base_score * math.log2(1 + diversity)
        
        # Sanitize NaN/Inf in consensus_score
        if math.isnan(consensus_score) or math.isinf(consensus_score):
            consensus_score = 0.0
        
        # Cap consensus_score at 100
        consensus_score = min(consensus_score, 100.0)
        
        # Collect source_resolvers list (full attribution — including the
        # structure sources that tiebreak mode excluded from SCORING)
        all_resolvers = {hit.resolver_name.split("@", 1)[0]
                         for hit in group_hits}
        source_resolvers = sorted(all_resolvers)
        
        # v3.142 belief term: agreement-structure belief from chain counts.
        # Red-team batch-4 (D-08): chains are distinct EVIDENCE SOURCES
        # (databases), not resolver names — formula_pubchem/local/hfamily
        # are one source, the two Swiss-Prot BLASTs are one source, etc.
        # resolver-chain counts are retained below for transparency.
        n_identity_chains = len({h.resolver_name for h in scoring_hits
                                 if h.hit_type == "identity"})
        n_similarity_chains = len({h.resolver_name for h in scoring_hits
                                   if h.hit_type == "similarity"})
        identity_sources = {_resolver_source(h.resolver_name)
                            for h in scoring_hits if h.hit_type == "identity"}
        similarity_sources = {_resolver_source(h.resolver_name)
                              for h in scoring_hits if h.hit_type == "similarity"}
        # D-13b: a dual-mode resolver's identity and similarity listings
        # now persist under distinct keys (2a) and one accession can carry
        # the SAME source in both tiers. Count each source at its
        # strongest tier only — otherwise every exact construct would
        # inherit n_id=1 + n_sim=1 = 60.3 from its own database.
        similarity_sources -= identity_sources
        # C-09b: split identity chains into exact-record sources and
        # formula/candidate-list sources — a formula-index hit is not an
        # accession confirmation. Candidates count with the κ-weighted
        # similarity slot in the belief, not as full identity chains.
        nonformula_identity = identity_sources - FORMULA_SOURCES
        formula_identity = identity_sources & FORMULA_SOURCES
        n_identity_sources = len(nonformula_identity)
        n_candidate_sources = len(formula_identity)
        n_similarity_sources = len(similarity_sources)
        belief = resolver_belief(
            n_identity_sources, n_similarity_sources + n_candidate_sources)
        
        # Pick representative signature from hit with highest resolver_score
        best_hit = max(group_hits, key=lambda h: h.resolver_score)
        
        # Red-team batch-4 (D-02): the representative alone is not enough —
        # expose every DISTINCT member signature (resolver_score order,
        # representative first) so the manager can run workers against all
        # of them. The representative may be an inchikey/name while another
        # member carries the smiles/fasta that has a real worker.
        ordered = sorted(group_hits, key=lambda h: -h.resolver_score)
        member_signatures: list[tuple[str, str]] = []
        seen_types: set[str] = set()
        if best_hit.signature:
            member_signatures.append((best_hit.signature, best_hit.signature_type))
            seen_types.add(best_hit.signature_type)
        for h in ordered:
            if h.signature and h.signature_type not in seen_types:
                seen_types.add(h.signature_type)
                member_signatures.append((h.signature, h.signature_type))
        
        # Determine hit_type (identity takes precedence if mixed).
        # C-09b: identity asserted ONLY by formula/candidate-list sources
        # is a CANDIDATE assertion — the formula index contains a structure
        # consistent with the sum formula, which is not an exact-record
        # confirmation. Candidates still verify (via skeleton/worker — the
        # F7 gate owns the verdict), but never BY assertion, and they rank
        # below true-identity rows in the fidelity view.
        if nonformula_identity:
            effective_hit_type = "identity"
        elif formula_identity:
            effective_hit_type = "candidate"
        else:
            effective_hit_type = "similarity"
        
        result[(normalized_id, ident_type)] = {
            "consensus_score": consensus_score,
            "source_resolvers": source_resolvers,
            "signature": best_hit.signature,
            "signature_type": best_hit.signature_type,
            "member_signatures": member_signatures,
            "hit_type": effective_hit_type,
            "belief": belief,
            "n_identity_chains": n_identity_chains,
            "n_similarity_chains": n_similarity_chains,
            "n_identity_sources": n_identity_sources,
            "n_candidate_sources": n_candidate_sources,
            "n_similarity_sources": n_similarity_sources,
            "structure_corroborated": structure_corroborated,
        }
    
    return result
