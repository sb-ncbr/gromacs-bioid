"""Molecular formula signature generator."""

from __future__ import annotations

import logging

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ..base import SignatureGenerator
from ._perceive_cache import _h_deficiency

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
        
        # B-10 (red-team 4.4): united-atom masses carry their implicit H;
        # without this cholesterol queries as "C27O". Mass-less H-less
        # systems (open-valence mode) keep raw counts: an implicit-H count
        # cannot be inferred without perception.
        _hmap = _h_deficiency(fragment)
        if _hmap:
            inferred_h = sum(_hmap.values())
            if inferred_h:
                composition["H"] = composition.get("H", 0) + inferred_h
        
        # v3.143 (B-16): Hill system — C first, H second, then alphabetical
        # (no C: fully alphabetical). The local PubChem mirror normalises to
        # Hill, and ChEMBL's exact-string lookup was missing every compound
        # containing B/Br/Cl/F because our output was plain alphabetical.
        def _hill_order(elems):
            # Deploy-gate fix (v3.143-b1 E2E): the no-carbon branch previously
            # did rest.remove("H") on a list that excludes H -> water crashed
            # the generator ('list.remove(x)' error on TIP3). Hill without C
            # is plain alphabetical (H2O -> H,O).
            if "C" in elems:
                out = ["C"] + (["H"] if "H" in elems else [])
                return out + sorted(e for e in elems if e not in ("C", "H"))
            return sorted(elems)
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


class MolecularFormulaHeavyGenerator(MolecularFormulaGenerator):
    """B-10: heavy-atom formula variant, emitted ONLY for H-deficient
    (united-atom / H-less) fragments so resolvers keep the raw counted
    string next to the H-inferred canonical one."""

    name = "molecular_formula_heavy"

    def _is_applicable(self, instance, fragment, facade) -> bool:
        return _h_deficiency(fragment) is not None

    def _generate(self, instance, fragment, facade) -> str:
        composition = {}
        for elem in fragment.atoms.elements:
            if elem:
                composition[elem] = composition.get(elem, 0) + 1
        def _hill_order(elems):
            if "C" in elems:
                out = ["C"] + (["H"] if "H" in elems else [])
                return out + sorted(e for e in elems if e not in ("C", "H"))
            return sorted(elems)
        parts = []
        for elem in _hill_order(list(composition.keys())):
            count = composition[elem]
            parts.append(elem if count == 1 else f"{elem}{count}")
        return "".join(parts)
