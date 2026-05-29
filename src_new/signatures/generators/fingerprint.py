"""Fingerprint signature generator."""

from __future__ import annotations

import hashlib
import logging

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class FingerprintGenerator(SignatureGenerator):
    """Hash-based fingerprint generator.
    
    Bug fix: Harden the hash to include more structural information
    to prevent trivial collisions between isomers.
    """
    
    name = "fingerprint"
    signature_type = "hash"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        return True
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        # Include atom count
        atom_count = fragment.n_atoms
        
        # Include sorted bond information with elements
        bonds = []
        try:
            for atom_idx1, atom_idx2 in fragment.bonds.indices:
                elem1 = fragment.atoms.elements[fragment.atoms.indices.tolist().index(int(atom_idx1))]
                elem2 = fragment.atoms.elements[fragment.atoms.indices.tolist().index(int(atom_idx2))]
                # Sort elements to make bond order-independent
                bond_tuple = tuple(sorted([elem1, elem2]))
                bonds.append(bond_tuple)
        except Exception:
            pass
        
        bonds.sort()
        
        # Include residue names if present
        resnames = []
        try:
            resnames = sorted(set(fragment.residues.resnames))
        except Exception:
            pass
        
        # Build hash input with all structural information
        hash_input = f"{atom_count}_{bonds}_{resnames}"
        
        return hashlib.sha512(hash_input.encode("utf-8")).hexdigest()
