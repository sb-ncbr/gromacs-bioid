"""SELFIES signature generator."""

from __future__ import annotations

import logging

import selfies
from MDAnalysis import AtomGroup
from rdkit import Chem
from rdkit.Chem import rdDetermineBonds, EditableMol

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ..base import SignatureGenerator
from ._perceive_cache import (
    build_once_cached, build_once_family_mol, assign_stereo_from_3d)

logger = logging.getLogger("base")


class SelfiesGenerator(SignatureGenerator):
    """SELFIES generator using RDKit and selfies package."""
    
    name = "selfies"
    signature_type = "selfies"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        # W3.1 P24 follow-up / wave-2 item 8d mirror: glycan segments
        # are carried by the glycan_composition signature — smiles got
        # this guard in item 8d, selfies (added later in B-14) did not,
        # and the 1IGT glycans kept reaching the bond-order ladder
        # through this generator (MolToSmiles fails on the unsanitized
        # fallback mol anyway, so the attempt is pure wasted budget).
        from ...molecules.instances import MoleculeType
        if instance.molecule_type == MoleculeType.CARBOHYDRATE:
            return False

        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)
        
        # Need elements
        if not props.flags.get(SegmentProperty.HAS_ELEMENTS.value, False):
            return False
        
        # Need at least 2 atoms
        if fragment.n_atoms < 2:
            return False
        
        # Don't process too large molecules
        if fragment.n_atoms > self.config.smiles_maximum_number_of_atoms:
            return False
        
        # Check all atoms are interconnected via bonds
        atom_indices = {int(idx): i for i, idx in enumerate(fragment.atoms.indices)}
        is_atom_bonded = [False] * len(atom_indices)
        
        try:
            for atom_idx1, atom_idx2 in fragment.bonds.indices:
                # B-08: skip endpoints outside the fragment
                i1 = atom_indices.get(int(atom_idx1))
                i2 = atom_indices.get(int(atom_idx2))
                if i1 is not None:
                    is_atom_bonded[i1] = True
                if i2 is not None:
                    is_atom_bonded[i2] = True
        except Exception:
            return False
        
        if not all(is_atom_bonded):
            return False
        
        return True
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        # B-14 (red-team 4.1): shared perceive-once family "rdkit_once".
        molecule = build_once_cached(
            fragment, "rdkit_once", lambda: build_once_family_mol(fragment),
            timeout_s=getattr(self.config, "perceive_timeout_s", 300),
        )
        # B-11 (red-team 4.5): stereo from 3D on the private copy
        assign_stereo_from_3d(molecule, fragment)

        molecule = Chem.RemoveHs(molecule, sanitize=False)
        
        # Get canonical SMILES
        smiles = Chem.MolToSmiles(molecule)
        
        # Encode to SELFIES
        selfies_str = selfies.encoder(smiles)
        return selfies_str


def _fragment_to_rdkit_atoms(
    fragment: AtomGroup,
    atom_idx_to_index: dict[int, int],
    molecule: EditableMol,
) -> dict[int, int]:
    """Add atoms from fragment to RDKit molecule."""
    idx_atom_to_rdkit = {}
    for atom_idx in fragment.atoms.indices:
        atom_elem = str(fragment.atoms.elements[atom_idx_to_index[atom_idx]]).title()
        atom = Chem.Atom(atom_elem)
        atom.SetNoImplicit(True)
        idx_atom_to_rdkit[atom_idx] = molecule.AddAtom(atom)
    return idx_atom_to_rdkit


def _fragment_to_rdkit_bonds(
    fragment: AtomGroup,
    atom_idx_to_rdkit_idx: dict[int, int],
    molecule: EditableMol,
) -> None:
    """Add bonds from fragment to RDKit molecule."""
    from ._perceive_cache import _intra_bond_pairs
    for atom_idx1, atom_idx2 in _intra_bond_pairs(fragment):
        atom_idx1_rdkit = atom_idx_to_rdkit_idx[atom_idx1]
        atom_idx2_rdkit = atom_idx_to_rdkit_idx[atom_idx2]
        molecule.AddBond(atom_idx1_rdkit, atom_idx2_rdkit, Chem.BondType.SINGLE)
