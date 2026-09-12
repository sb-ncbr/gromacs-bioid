"""Skeleton fingerprint ("skelfp") signature generator.

Emits a bond-order/aromaticity/charge/protonation-insensitive fingerprint for
small molecules: "skelfp:v1:<hex>|<heavyFormula>". This is the verification +
validation currency for chemistry (F12, docs/CHEMISTRY_FIX_TODO.md).
"""

from __future__ import annotations

import logging
from typing import Optional

from MDAnalysis import AtomGroup
from rdkit import Chem
from rdkit.Chem import rdDetermineBonds, EditableMol

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ..base import SignatureGenerator
from ..skeletize import format_signature
from .smiles import _fragment_to_rdkit_atoms, _fragment_to_rdkit_bonds

logger = logging.getLogger("base")


class SkeletonFingerprintGenerator(SignatureGenerator):
    """Heavy-atom skeleton fingerprint generator (F12)."""

    name = "skeleton_fp"
    signature_type = "skeleton_fp"
    MAX_PERCEPTION_ATOMS = 150

    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)

        if not props.flags.get(SegmentProperty.HAS_ELEMENTS.value, False):
            return False
        if fragment.n_atoms < 2:
            return False
        if fragment.n_atoms > self.config.smiles_maximum_number_of_atoms:
            return False

        atom_indices = {int(idx): i for i, idx in enumerate(fragment.atoms.indices)}
        is_atom_bonded = [False] * len(atom_indices)
        try:
            for atom_idx1, atom_idx2 in fragment.bonds.indices:
                is_atom_bonded[atom_indices[int(atom_idx1)]] = True
                is_atom_bonded[atom_indices[int(atom_idx2)]] = True
            return all(is_atom_bonded)
        except Exception:
            # No bond records: coordinate perception fallback (bounded atoms)
            return fragment.n_atoms <= self.MAX_PERCEPTION_ATOMS

    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> Optional[str]:
        atom_idx_to_index = {
            atom_idx: i for i, atom_idx in enumerate(fragment.atoms.indices)
        }

        molecule_build = EditableMol(Chem.Mol())
        atom_idx_to_rdkit_idx = _fragment_to_rdkit_atoms(
            fragment, atom_idx_to_index, molecule_build
        )
        try:
            _fragment_to_rdkit_bonds(fragment, atom_idx_to_rdkit_idx, molecule_build)
            molecule = molecule_build.GetMol()
        except Exception:
            # Topology without bond records: perceive connectivity from 3D
            mol_tmp = molecule_build.GetMol()
            conf = Chem.Conformer(mol_tmp.GetNumAtoms())
            for atom_idx, rdkit_idx in atom_idx_to_rdkit_idx.items():
                pos = fragment.atoms.positions[atom_idx_to_index[atom_idx]]
                conf.SetAtomPosition(
                    rdkit_idx,
                    (float(pos[0]), float(pos[1]), float(pos[2])),
                )
            mol_tmp.AddConformer(conf, assignId=True)
            try:
                rdDetermineBonds.DetermineBonds(mol_tmp, charge=0)
            except Exception as exc:
                logger.debug("skeleton_fp: perception failed: %s", exc)
                return None
            molecule = mol_tmp

        if molecule.GetNumBonds() == 0:
            # radius-2 Morgan FP of unconnected atoms carries no structural signal
            logger.debug("skeleton_fp: zero bonds; skipping (%d atoms)", fragment.n_atoms)
            return None

        return format_signature(molecule)


