"""Morgan fingerprint signature generator."""

from __future__ import annotations

import logging

from MDAnalysis import AtomGroup
from rdkit import Chem
from rdkit.Chem import rdDetermineBonds, EditableMol, rdFingerprintGenerator

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class MorganFingerprintGenerator(SignatureGenerator):
    """Morgan fingerprint generator using RDKit."""
    
    name = "morgan_fingerprint"
    signature_type = "morgan_fp"
    
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
                is_atom_bonded[atom_indices[int(atom_idx1)]] = True
                is_atom_bonded[atom_indices[int(atom_idx2)]] = True
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
        atom_idx_to_index = {
            atom_idx: i for i, atom_idx in enumerate(fragment.atoms.indices)
        }
        
        molecule_build = EditableMol(Chem.Mol())
        atom_idx_to_rdkit_idx = _fragment_to_rdkit_atoms(
            fragment, atom_idx_to_index, molecule_build
        )
        _fragment_to_rdkit_bonds(fragment, atom_idx_to_rdkit_idx, molecule_build)
        
        molecule = molecule_build.GetMol()
        
        # Try to determine bond orders
        try:
            charge = sum(atom.GetFormalCharge() for atom in molecule.GetAtoms())
            rdDetermineBonds.DetermineBondOrders(
                molecule, allowChargedFragments=True, embedChiral=False, charge=charge
            )
        except Exception:
            pass
        
        molecule = Chem.RemoveHs(molecule, sanitize=False)
        
        # Generate Morgan fingerprint
        gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
        fp = gen.GetFingerprint(molecule)
        
        # Convert to hex string
        try:
            return fp.ToHex()
        except AttributeError:
            # Fallback: manually convert bit vector to hex
            bv = fp.ToBitString()
            # Convert binary string to hex
            int_val = int(bv, 2)
            return format(int_val, 'x').zfill(len(bv) // 4)


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
    for atom_idx1, atom_idx2 in fragment.bonds.indices:
        atom_idx1_rdkit = atom_idx_to_rdkit_idx[atom_idx1]
        atom_idx2_rdkit = atom_idx_to_rdkit_idx[atom_idx2]
        molecule.AddBond(atom_idx1_rdkit, atom_idx2_rdkit, Chem.BondType.SINGLE)
