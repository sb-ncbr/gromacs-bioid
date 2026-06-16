"""Manager for identifier resolution across results."""

from __future__ import annotations

import logging

from ..config.loader import RunConfig
from ..results.results_manager import ResultsManager
from .base import IdentifierResolver
from .cache_manager import ResolverCache
from .registry import IdentifierRegistry

logger = logging.getLogger("identifier")

_CANONICAL_SIGNATURE_TYPES: dict[str, str] = {
    "smiles": "smiles",
    "smiles_not_sanitized": "smiles",
    "inchi_key": "inchikey",
    "morgan_fingerprint": "morgan_fingerprint",
    "selfies": "selfies",
    "molecular_formula": "formula",
    "fasta_map_protein": "residue_sequence_protein",
    "fasta_map_nucleic": "residue_sequence_nucleotide",
    "fasta_resname_protein": "residue_sequence_protein",
    "fasta_resname_nucleic": "residue_sequence_nucleotide",
    "pdb_protein": "pdb_protein",
    "pdb_not_sanitized_protein": "pdb_protein",
    "pdb_backbone_protein": "pdb_protein",
    "pdb_backbone_not_sanitized_protein": "pdb_protein",
    "pdb_nucleic": "pdb_nucleic",
    "pdb_not_sanitized_nucleic": "pdb_nucleic",
    "pdb_backbone_nucleic": "pdb_nucleic",
    "pdb_backbone_not_sanitized_nucleic": "pdb_nucleic",
    "ca_only_pdb": "ca_only_pdb",
    "tdi": "3di_sequence",
    "lipid_shorthand": "lipid_shorthand",
    "glycan_composition": "glycan_composition",
    "mmcif": "mmcif",
    "name_chain": "name",
    "name_molecule": "name",
    "name_segment": "name",
    "atom": "element",
    "fingerprint": "hash",
}


class IdentifierResolutionManager:
    """Manager for resolving identifiers from signatures in results.
    
    Handles two-phase resolution: identity first, then similarity.
    """
    
    def __init__(
        self, 
        registry: IdentifierRegistry, 
        config: RunConfig,
        signature_type_map: dict[str, str] | None = None,
    ) -> None:
        """Initialize the resolution manager.
        
        Args:
            registry: IdentifierRegistry containing available resolvers.
            config: RunConfig for cache and settings.
            signature_type_map: Optional mapping from generator name to signature type.
        """
        self._registry = registry
        self._config = config
        self._signature_type_map = signature_type_map
        self._cache: ResolverCache | None = None
    
    @property
    def cache(self) -> ResolverCache:
        """Lazy cache initialization."""
        if self._cache is None:
            self._cache = ResolverCache(self._config)
        return self._cache
    
    def resolve(
        self, 
        results: ResultsManager, 
        segment: str, 
        signature_generator_name: str, 
        signature: str,
        cache: ResolverCache | None = None,
        working_directory: str = "",
    ) -> bool:
        """Attempt identity then similarity resolution for one signature.
        
        Args:
            results: ResultsManager to read/write data.
            segment: Fragment/segment name.
            signature_generator_name: Name of the signature generator.
            signature: The signature string to resolve.
            cache: Optional ResolverCache instance. If None, uses self.cache.
            
        Returns:
            True if any hit was found, False otherwise.
        """
        # Determine signature type from generator name
        if self._signature_type_map is not None:
            signature_type = self._signature_type_map.get(signature_generator_name)
        else:
            signature_type = None
        
        if signature_type is None:
            # Fallback: use canonical mapping
            signature_type = _CANONICAL_SIGNATURE_TYPES.get(signature_generator_name)
        if signature_type is None:
            logger.warning(f"Unknown signature generator '{signature_generator_name}', cannot determine signature type. Skipping.")
            return False
        
        # Use provided cache or lazy-initialized one
        if cache is None:
            cache = self.cache
        
        # Track attempted resolvers
        attempted_resolvers: list[str] = []
        hits_found = False
        
        # Phase 1: Identity resolution
        identity_resolvers = self._registry.get_applicable_resolvers(
            signature_type, 
            as_similarity=False
        )
        
        for resolver in identity_resolvers:
            # Check if resolver is applicable for this specific signature
            if not resolver.is_applicable(signature, signature_type, as_similarity=False):
                continue
            
            attempted_resolvers.append(resolver.name)
            
            # Check if we should skip due to existing data
            data_path = f"identifiers/{segment}/{signature_generator_name}/{resolver.name}"
            if not self._config.identifiers.overwrite_existing:
                if results.data_exists(data_path):
                    existing = results.get_data(data_path)
                    if existing and existing.get("hits"):
                        logger.debug(
                            f"Skipping {resolver.name} for {segment}: "
                            f"existing hits found"
                        )
                        hits_found = True
                        continue
            
            # Attempt resolution
            result = resolver.resolve(
                signature=signature,
                as_similarity=False,
                working_directory=working_directory,
                cache=cache
            )
            
            if result:
                hits_found = True
                resolver_data = {
                    "signature": signature,
                    "hit_type": "identity",
                    "hits": result,
                    "ident_type": resolver.identifier_type,
                    "signature_type": signature_type
                }
                metadata = resolver.get_last_resolution_metadata()
                if metadata is not None:
                    resolver_data["hits_metadata"] = metadata
                results.set_data(
                    f"identifiers/{segment}/{signature_generator_name}/{resolver.name}",
                    resolver_data
                )
        
        # Phase 2: Similarity resolution
        similarity_resolvers = self._registry.get_applicable_resolvers(
            signature_type, 
            as_similarity=True
        )
        
        for resolver in similarity_resolvers:
            # Check if resolver is applicable for this specific signature
            if not resolver.is_applicable(signature, signature_type, as_similarity=True):
                continue
            
            attempted_resolvers.append(resolver.name)
            
            # Check if we should skip due to existing data
            data_path = f"identifiers/{segment}/{signature_generator_name}/{resolver.name}"
            if not self._config.identifiers.overwrite_existing:
                if results.data_exists(data_path):
                    existing = results.get_data(data_path)
                    if existing and existing.get("hits"):
                        logger.debug(
                            f"Skipping {resolver.name} for {segment}: "
                            f"existing hits found"
                        )
                        hits_found = True
                        continue
            
            # Attempt resolution
            result = resolver.resolve(
                signature=signature,
                as_similarity=True,
                working_directory=working_directory,
                cache=cache
            )
            
            if result:
                hits_found = True
                resolver_data = {
                    "signature": signature,
                    "hit_type": "similarity",
                    "hits": result,
                    "ident_type": resolver.identifier_type,
                    "signature_type": signature_type
                }
                metadata = resolver.get_last_resolution_metadata()
                if metadata is not None:
                    resolver_data["hits_metadata"] = metadata
                results.set_data(
                    f"identifiers/{segment}/{signature_generator_name}/{resolver.name}",
                    resolver_data
                )
        
        # Record attempted resolvers
        if attempted_resolvers:
            results.set_data(
                f"identifiers/{segment}/{signature_generator_name}/attempted",
                attempted_resolvers
            )
        
        return hits_found
    
    def resolve_all(self, results: ResultsManager, working_directory: str = "") -> None:
        """Iterate all fragments/signatures in results and resolve.
        
        Args:
            results: ResultsManager containing signature data.
        """
        # Initialize cache once for all resolutions
        cache = self.cache
        
        # Get fragment names from signatures data
        signatures_data = results.get_data("signatures")
        if not signatures_data or not isinstance(signatures_data, dict):
            logger.warning("No signatures data found in results")
            return
        
        fragment_names = list(signatures_data.keys())
        
        for fragment_name in fragment_names:
            # Get generated signatures for this fragment
            generated_path = f"signatures/{fragment_name}/generated"
            generated = results.get_data(generated_path)
            
            if not generated or not isinstance(generated, dict):
                logger.debug(f"No generated signatures for fragment: {fragment_name}")
                continue
            
            # Iterate over signature generators and their signatures
            for generator_name, signature in generated.items():
                if not signature:
                    logger.debug(f"Empty signature for {generator_name} in {fragment_name}")
                    continue
                
                # Ensure attempted path is initialized
                attempted_path = f"identifiers/{fragment_name}/{generator_name}/attempted"
                if results.get_data(attempted_path) is None:
                    results.set_data(attempted_path, [])
                
                logger.info(
                    f"Resolving {generator_name} signature for {fragment_name}"
                )
                
                try:
                    self.resolve(
                        results=results,
                        segment=fragment_name,
                        signature_generator_name=generator_name,
                        signature=signature,
                        cache=cache,
                        working_directory=working_directory,
                    )
                except Exception as exc:
                    logger.error(
                        f"Failed to resolve {generator_name} for {fragment_name}: {exc}"
                    )
