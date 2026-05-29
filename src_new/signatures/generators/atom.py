"""Atom signature generator."""

from __future__ import annotations

import logging

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from src.constants import ATOMTABLE_ELEMENTS_MASSES
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class AtomGenerator(SignatureGenerator):
    """Generator that produces element name for single-atom fragments."""
    
    name = "atom"
    signature_type = "element"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)
        
        # Need elements
        if not props.flags.get(SegmentProperty.HAS_ELEMENTS.value, False):
            return False
        
        # Need exactly one atom
        return fragment.n_atoms == 1
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        element = str(fragment.atoms.elements[0]).title()
        
        # Validate against known elements
        if element not in ATOMTABLE_ELEMENTS_MASSES:
            raise RuntimeError(f"Invalid atomic element: {element}")
        
        return element
