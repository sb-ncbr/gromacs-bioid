"""Molecular formula signature generator."""

from __future__ import annotations

import logging

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class MolecularFormulaGenerator(SignatureGenerator):
    """Molecular formula generator."""
    
    name = "molecular_formula"
    signature_type = "formula"
    
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
        return props.flags.get(SegmentProperty.HAS_ELEMENTS.value, False)
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        # Use element_composition from instance if available, otherwise compute from fragment
        if instance.element_composition:
            composition = instance.element_composition
        else:
            composition = {}
            for elem in fragment.atoms.elements:
                if elem:
                    composition[elem] = composition.get(elem, 0) + 1
        
        # Sort elements alphabetically (Hill system would put C first, then H, then alphabetical)
        # For simplicity, just sort alphabetically as specified
        sorted_elements = sorted(composition.keys())
        
        # Build formula string like C6H12O6
        parts = []
        for elem in sorted_elements:
            count = composition[elem]
            if count == 1:
                parts.append(elem)
            else:
                parts.append(f"{elem}{count}")
        
        return "".join(parts)
