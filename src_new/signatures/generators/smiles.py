"""SMILES signature generators."""

from __future__ import annotations

import logging
import re

import numpy as np
from MDAnalysis import AtomGroup
from rdkit import Chem
from rdkit.Chem import rdDetermineBonds, EditableMol, Mol

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class SimpleSmilesGenerator(SignatureGenerator):
    """SMILES generator with sanitization."""
    
    name = "smiles"
    signature_type = "smiles"
    MAX_PERCEPTION_ATOMS = 150

    def __init__(self, config: SignaturesConfig, sanitize: bool = True) -> None:
        super().__init__(config)
        self._sanitize = sanitize
        if not sanitize:
            self.name = "smiles_not_sanitized"
    
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
        
        bonded_all = True
        try:
            for atom_idx1, atom_idx2 in fragment.bonds.indices:
                is_atom_bonded[atom_indices[int(atom_idx1)]] = True
                is_atom_bonded[atom_indices[int(atom_idx2)]] = True
            bonded_all = all(is_atom_bonded)
        except Exception:
            # No bond records in topology: allow coordinate-based bond
            # perception on small molecules (bounded cost, see _generate)
            return fragment.n_atoms <= self.MAX_PERCEPTION_ATOMS

        return bonded_all
    
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
        perceived = False
        try:
            _fragment_to_rdkit_bonds(fragment, atom_idx_to_rdkit_idx, molecule_build)
        except Exception:
            # Topology carries no bond records: perceive bonds from 3D
            # coordinates (small molecules only, guarded by _is_applicable)
            mol_tmp = molecule_build.GetMol()
            conf = Chem.Conformer(mol_tmp.GetNumAtoms())
            for atom_idx, rdkit_idx in atom_idx_to_rdkit_idx.items():
                pos = fragment.atoms.positions[atom_idx_to_index[atom_idx]]
                conf.SetAtomPosition(
                    rdkit_idx,
                    (float(pos[0]), float(pos[1]), float(pos[2])),
                )
            mol_tmp.AddConformer(conf, assignId=True)
            rdDetermineBonds.DetermineBonds(mol_tmp, charge=0)
            molecule_build = EditableMol(mol_tmp)
            perceived = True

        molecule = molecule_build.GetMol()
        if perceived:
            logger.debug("smiles: bonds perceived from coordinates (%d atoms)", fragment.n_atoms)
        _fix_bond_orders_rdkit(molecule)
        molecule = Chem.RemoveHs(molecule, sanitize=self._sanitize)
        
        if self._sanitize:
            Chem.SanitizeMol(molecule)
        
        return Chem.MolToSmiles(molecule)


class SimpleSmilesGeneratorNoSanitize(SimpleSmilesGenerator):
    """SMILES generator without sanitization."""
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, sanitize=False)


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


def _fix_bond_orders_rdkit(molecule: Mol, max_attempts: int = 20) -> None:
    """Determine bond orders using RDKit's DetermineBondOrders.
    
    Bug fix: Uses regex to extract charge from error message instead of fragile string parsing.
    """
    charge = sum(atom.GetFormalCharge() for atom in molecule.GetAtoms())
    
    while max_attempts > 0:
        max_attempts -= 1
        try:
            rdDetermineBonds.DetermineBondOrders(
                molecule, allowChargedFragments=True, embedChiral=False, charge=charge
            )
            return
        except ValueError as e:
            # Bug fix: Use regex to extract charge from error message
            match = re.search(r'input\s*\(\s*(-?\d+)\s*\)', str(e))
            if match:
                charge = int(match.group(1))
            else:
                # If we can't parse the charge, break and return unsanitized
                break
    
    # If we get here, DetermineBondOrders failed - that's ok, return unsanitized
    logger.debug("DetermineBondOrders failed, returning unsanitized molecule")
