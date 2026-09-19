"""Base class for identifier resolvers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from ..config.loader import RunConfig
from .cache_manager import ResolverCache

logger = logging.getLogger("identifier")

def safe_tmp_dir(working_directory: str | None = None) -> str:
    """Return a writable temporary directory.

    Uses working_directory only when it exists and is writable for the
    current process; otherwise falls back to the system temp dir.
    Run/input directories may be owned by a different uid than the worker
    (scheduler-created NFS dirs), so resolvers must not assume writability.
    """
    import os as _os
    import tempfile as _tempfile

    if working_directory and _os.path.isdir(working_directory) and _os.access(working_directory, _os.W_OK):
        return working_directory
    fallback = _tempfile.gettempdir()
    if working_directory and working_directory != fallback:
        logger.warning(
            f"Working directory '{working_directory}' is not writable; "
            f"using '{fallback}' for resolver temp files"
        )
    return fallback



class IdentifierResolutionError(Exception):
    """Raised when identifier resolution fails."""
    pass


class IdentifierResolver(ABC):
    """Abstract base class for identifier resolvers.
    
    Subclasses must implement _is_applicable(), _resolve_identity(), and 
    _resolve_similarity() methods. The base class handles enabled state,
    caching, and error handling.
    """
    
    name: str = ""
    identifier_type: str = ""  # e.g. "PDB_ID", "CHEMBL_ID"
    accepted_signatures: list[str] = []  # e.g. ["smiles", "inchikey"]
    
    def __init__(self, config: RunConfig) -> None:
        """Initialize the resolver with configuration.

        Args:
            config: RunConfig instance containing feature toggles.
        """
        self.config = config
        # Read enablement from IdentifiersConfig automatically by name
        self.enabled_identity = getattr(config.identifiers, self.name, True)
        # Wall-clock deadline for cooperative stage time budgets (set by the
        # resolution manager between calls; None = no budget). Resolvers with
        # expensive internal loops (network fan-out) MUST poll _over_budget().
        self._stage_deadline_epoch: float | None = None

    def _over_budget(self) -> bool:
        """True when the caller-assigned stage deadline has passed."""
        import time as _time
        dl = getattr(self, "_stage_deadline_epoch", None)
        return dl is not None and _time.time() > dl
        self.enabled_similarity = getattr(config.identifiers, f"{self.name}_similarity", True)
        self._last_resolution_metadata: dict[str, dict] | None = None
        self._last_error: str | None = None
    
    def is_applicable(self, signature: str, signature_type: str, as_similarity: bool = False) -> bool:
        """Check if this resolver can resolve the signature.
        
        Args:
            signature: The signature string to check.
            signature_type: Type of signature (e.g. "smiles", "inchikey").
            as_similarity: If True, check similarity mode enablement.
            
        Returns:
            True if the resolver is enabled and applicable, False otherwise.
        """
        # Check enabled flags
        if as_similarity:
            if not self.enabled_similarity:
                return False
        else:
            if not self.enabled_identity:
                return False
        
        # Check signature type
        if signature_type not in self.accepted_signatures:
            return False
        
        return self._is_applicable(signature)
    
    def resolve(
        self, 
        signature: str, 
        as_similarity: bool = False, 
        working_directory: str = "",
        cache: ResolverCache | None = None
    ) -> list[str] | list[tuple[str, float]] | None:
        """Resolve a signature to identifiers.
        
        Args:
            signature: The signature string to resolve.
            as_similarity: If True, perform similarity search.
            working_directory: Working directory for resolver operations.
            cache: Optional cache instance. If None, no caching is performed.
            
        Returns:
            List of identifiers (identity) or list of (identifier, score) tuples (similarity),
            or None if resolution fails or is disabled.
        """
        # Clear metadata from previous resolution
        self._last_resolution_metadata = None
        self._last_error = None
        
        # Check cache first
        if cache is not None:
            if as_similarity:
                cached = cache.fetch_similarity_identifiers(self.name, signature)
                if cached:
                    return cached
            else:
                cached = cache.fetch_identity_identifiers(self.name, signature)
                if cached:
                    return cached
        
        # Call appropriate resolve method
        try:
            if as_similarity:
                result = self._resolve_similarity(signature, working_directory)
            else:
                result = self._resolve_identity(signature, working_directory)
            
            # Store in cache
            if cache is not None and result is not None:
                if as_similarity:
                    cache.save_similarity_identifiers(self.name, signature, result)
                else:
                    # Convert to list[str] if needed
                    if isinstance(result, list) and len(result) > 0:
                        if isinstance(result[0], tuple):
                            # Extract just identifiers
                            cache.save_identity_identifiers(
                                self.name, 
                                signature, 
                                [ident for ident, _ in result]
                            )
                        else:
                            cache.save_identity_identifiers(self.name, signature, result)
            
            return result
        except IdentifierResolutionError as exc:
            self._last_error = str(exc)
            logger.error(f"Resolution failed for {self.name}: {exc}")
            raise  # Re-raise so callers can handle appropriately
        except Exception as exc:
            self._last_error = str(exc)
            logger.error(f"Unexpected error in {self.name} resolver: {exc}")
            return None
    
    def get_last_error(self) -> str | None:
        """Return the last resolution error message, if any."""
        return self._last_error

    @abstractmethod
    def _is_applicable(self, signature: str) -> bool:
        """Check applicability (internal implementation).
        
        Args:
            signature: The signature string to check.
            
        Returns:
            True if applicable, False otherwise.
        """
        ...
    
    @abstractmethod  
    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve signature to exact-match identifiers.
        
        Args:
            signature: The signature string to resolve.
            working_directory: Working directory for resolver operations.
            
        Returns:
            List of identifier strings.
            
        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        ...
    
    @abstractmethod
    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve signature to similar identifiers.
        
        Args:
            signature: The signature string to resolve.
            working_directory: Working directory for resolver operations.
            
        Returns:
            List of (identifier, similarity_score) tuples.
            
        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        ...

    def get_last_resolution_metadata(self) -> dict[str, dict] | None:
        """Return optional per-accession metadata from the last resolve() call."""
        return self._last_resolution_metadata
