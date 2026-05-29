"""Base class for signature generators."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from MDAnalysis import AtomGroup

from ..config.loader import SignaturesConfig
from ..molecules.instances import MoleculeInstance
from ..loader.universe_facade import LoadedUniverse

logger = logging.getLogger("base")


class SignatureGenerator(ABC):
    """Abstract base class for signature generators.
    
    Subclasses must implement _is_applicable() and _generate() methods.
    The base class handles enabled state and error handling.
    """
    
    name: str = ""
    signature_type: str = ""
    
    def __init__(self, config: SignaturesConfig) -> None:
        """Initialize the generator with configuration.
        
        Args:
            config: SignaturesConfig instance containing feature toggles.
        """
        self.config = config
        self.enabled = getattr(config, self.name, True)
    
    def is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        """Check if this generator can produce a signature for the fragment.
        
        Args:
            instance: MoleculeInstance describing the molecule.
            fragment: AtomGroup representing the molecular fragment.
            facade: LoadedUniverse providing segment properties.
            
        Returns:
            True if the generator is enabled and applicable, False otherwise.
        """
        if not self.enabled:
            return False
        return self._is_applicable(instance, fragment, facade)
    
    def generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str | None:
        """Generate a signature for the fragment.
        
        Args:
            instance: MoleculeInstance describing the molecule.
            fragment: AtomGroup representing the molecular fragment.
            facade: LoadedUniverse providing segment properties.
            
        Returns:
            Signature string, or None if generation fails or is disabled.
        """
        if not self.enabled:
            return None
        try:
            return self._generate(instance, fragment, facade)
        except Exception as exc:
            logger.error(f"Signature generation failed for {self.name}: {exc}")
            return None
    
    @abstractmethod
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        """Check applicability (internal implementation).
        
        Args:
            instance: MoleculeInstance describing the molecule.
            fragment: AtomGroup representing the molecular fragment.
            facade: LoadedUniverse providing segment properties.
            
        Returns:
            True if applicable, False otherwise.
        """
        ...
    
    @abstractmethod
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        """Generate signature (internal implementation).
        
        Args:
            instance: MoleculeInstance describing the molecule.
            fragment: AtomGroup representing the molecular fragment.
            facade: LoadedUniverse providing segment properties.
            
        Returns:
            Signature string.
            
        Raises:
            Exception: If generation fails.
        """
        ...
