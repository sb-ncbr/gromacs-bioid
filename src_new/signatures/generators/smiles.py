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

        # Kekulization is the DOCUMENTED unbounded RDKit operation on
        # pathological molecules (coordinate perception of junk clusters
        # degenerates valences/skeletons; KeKulize then spins for hours-days
        # with no log lines). Production freeze root cause (2026-09-20):
        # smiles on virtual-class fragments hit SanitizeMol full-kekulize and
        # pinned worker threads indefinitely. Policy: never run kekulization.
        # RemoveHs runs WITHOUT sanitization; SanitizeMol skips the KEKULIZE
        # op; MolToSmiles emits without kekule normalization. The resulting
        # string remains an honest structural string for recognition paths
        # (we never pass it back into RDKit), and the generator can no
        # longer hold a slot hostage.
        try:
            molecule = Chem.RemoveHs(molecule, sanitize=False)
        except Exception as exc:
            logger.warning("smiles: RemoveHs failed (%s), skipping segment molecule", exc)
            return ""
        if self._sanitize:
            try:
                from rdkit.Chem import SanitizeFlags
                Chem.SanitizeMol(
                    molecule,
                    sanitizeOps=SanitizeFlags.SANITIZE_ALL ^ SanitizeFlags.SANITIZE_KEKULIZE,
                )
            except Exception as exc:
                salvaged = _canonicalize_for_roundtrip(molecule)
                if salvaged:
                    logger.info("smiles: partial sanitize failed (%s); "
                                "emitted canonical neutral-parent string", exc)
                    return salvaged
                logger.warning("smiles: partial sanitize failed (%s) and canonical salvage failed; returning unsanitized string", exc)
        try:
            return Chem.MolToSmiles(molecule, kekuleSmiles=False)
        except Exception as exc:
            logger.warning("smiles: MolToSmiles failed (%s); returning empty", exc)
            return ""


def _canonicalize_for_roundtrip(molecule: Mol) -> str | None:
    """Salvage a re-parseable canonical SMILES from a molecule whose formal
    charges are ALL generator compensation artifacts.

    Generator molecules are built element-only with SetNoImplicit atoms; the
    topology carries no charge data, so every formal charge present was
    assigned by DetermineBondOrders valence compensation (S0-OQ-2: 525/525
    explicit_valence). Consumers re-parse with FULL sanitize
    (skeletize.from_smiles), so the emitted string must survive that.

    Tier 1 (neutral canonical): clear compensation charges + NoImplicit,
    sanitize minus kekulization, canonical emit -- preserves real bond orders
    whenever the neutral chemistry is legal.
    Tier 2 (skeleton collapse): the generator's own skeleton-currency
    collapse (skeletize_mol: single bonds, no charges, no aromaticity,
    valence-tolerant) -- bond-order information is NOT part of the skelfp
    metric currency, so the skeleton string is metrically equivalent
    downstream while being robustly re-parseable.
    Returns None when neither tier re-parses (caller then falls back to the
    legacy raw string -- no silent signature loss).
    """
    try:
        work = Chem.Mol(molecule)
        for atom in work.GetAtoms():
            atom.SetFormalCharge(0)
            atom.SetNoImplicit(False)
        try:
            from rdkit.Chem import SanitizeFlags
            Chem.SanitizeMol(
                work,
                sanitizeOps=SanitizeFlags.SANITIZE_ALL ^ SanitizeFlags.SANITIZE_KEKULIZE,
            )
            return Chem.MolToSmiles(work, kekuleSmiles=False)
        except Exception:
            pass
        from ..skeletize import skeletize_mol
        collapsed = skeletize_mol(work)
        if collapsed is None:
            return None
        # Minimal-charge repair: some heavy graphs REQUIRE charge even when
        # neutral-parented (quaternary ammonium [N+] with 4 neighbours, oxonium
        # [O+] with 3). Zeroing charges makes them unparseable; assign the
        # minimal legalizing charge instead (consumers collapse charges away
        # in skelfp currency anyway).
        out = Chem.MolToSmiles(collapsed, kekuleSmiles=False)
        for _attempt in range(12):
            if Chem.MolFromSmiles(out) is not None:
                return out
            try:
                Chem.SanitizeMol(collapsed)
            except Exception as exc:
                m = re.search(r"atom # (\d+)", str(exc))
                if not m:
                    return None
                atom = collapsed.GetAtomWithIdx(int(m.group(1)))
                sym = atom.GetSymbol()
                nbonds = atom.GetTotalDegree()
                if sym in ("N", "P") and nbonds >= 4 and atom.GetFormalCharge() == 0:
                    atom.SetFormalCharge(+1)
                elif sym in ("O", "S") and nbonds >= 3 and atom.GetFormalCharge() == 0:
                    atom.SetFormalCharge(+1)
                elif sym in ("O", "S") and nbonds <= 1 and atom.GetFormalCharge() == 0:
                    atom.SetFormalCharge(-1)
                else:
                    return None
                collapsed.UpdatePropertyCache(strict=False)
                out = Chem.MolToSmiles(collapsed, kekuleSmiles=False)
            else:
                return out
        # Contract: downstream parses with FULL sanitize (skeletize.from_smiles)
        return out if Chem.MolFromSmiles(out) is not None else None
    except Exception:
        return None


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
