"""Lipid shorthand signature generator."""

from __future__ import annotations

import logging

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance, MoleculeType
from ...loader.universe_facade import LoadedUniverse
from ..forcefield_maps import LIPID_FORCEFIELD_MAPS
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class LipidShorthandGenerator(SignatureGenerator):
    """Lipid shorthand generator using force-field maps."""
    
    name = "lipid_shorthand"
    signature_type = "lipid_shorthand"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        return instance.molecule_type == MoleculeType.LIPID
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        # Use charmm36 as default forcefield
        ff_maps = LIPID_FORCEFIELD_MAPS.get("charmm36", {})
        
        # Get unique residue names from fragment
        resnames = list(set(fragment.residues.resnames))
        
        if len(resnames) == 1:
            # Single residue type - look up in map
            resname = resnames[0].upper()
            if resname in ff_maps:
                return ff_maps[resname]
        elif len(resnames) > 1:
            # Multiple residues - check if all map to same shorthand
            shorthands = set()
            for resname in resnames:
                shorthand = ff_maps.get(resname.upper())
                if shorthand:
                    shorthands.add(shorthand)
            
            if len(shorthands) == 1:
                return shorthands.pop()
        
        # Fall back to generic composition
        return "LIPID"
