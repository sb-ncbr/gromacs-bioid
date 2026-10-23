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
        
        # v3.143 (B-16): Hill system — C first, H second, then alphabetical
        # (no C: fully alphabetical). The local PubChem mirror normalises to
        # Hill, and ChEMBL's exact-string lookup was missing every compound
        # containing B/Br/Cl/F because our output was plain alphabetical.
        def _hill_order(elems):
            rest = sorted(e for e in elems if e not in ("C", "H"))
            out = []
            if "C" in elems:
                out.append("C")
                if "H" in elems:
                    out.append("H")
            elif "H" in elems:
                rest.remove("H")
                out = ["H"]
            return out + rest
        sorted_elements = _hill_order(list(composition.keys()))
        
        # Build formula string like C6H12O6
        parts = []
        for elem in sorted_elements:
            count = composition[elem]
            if count == 1:
                parts.append(elem)
            else:
                parts.append(f"{elem}{count}")
        
        return "".join(parts)
