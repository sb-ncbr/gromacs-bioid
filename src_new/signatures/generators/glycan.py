"""Glycan composition signature generator."""

from __future__ import annotations

import logging
from collections import Counter

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance, MoleculeType
from ...loader.universe_facade import LoadedUniverse
from ..forcefield_maps import GLYCAN_FORCEFIELD_MAPS
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class GlycanCompositionGenerator(SignatureGenerator):
    """Glycan composition generator using force-field maps."""
    
    name = "glycan_composition"
    signature_type = "glycan_composition"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        return instance.molecule_type == MoleculeType.CARBOHYDRATE
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        # wave-2 item 8b: consult ALL forcefield/CCD maps (union) — the
        # charmm36-only lookup dropped GLYCAM and CCD codes as 'X'.
        ff_maps: dict[str, str] = {}
        for mapping in GLYCAN_FORCEFIELD_MAPS.values():
            ff_maps.update(mapping)
        
        # Count monosaccharide classes
        class_counts = Counter()
        
        for resname in fragment.residues.resnames:
            resname_upper = resname.upper()
            if resname_upper in ff_maps:
                class_counts[ff_maps[resname_upper]] += 1
            else:
                # Unmapped residue - use "X"
                class_counts["X"] += 1
        
        # Build composition string like Hex(3)HexNAc(2)dHex(1)
        # Sort classes alphabetically
        sorted_classes = sorted(class_counts.keys())
        parts = []
        for cls in sorted_classes:
            count = class_counts[cls]
            parts.append(f"{cls}({count})")
        
        return "".join(parts)
