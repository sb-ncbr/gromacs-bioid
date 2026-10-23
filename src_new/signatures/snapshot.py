"""Snapshot utilities for parallel signature generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SegmentSignatureSnapshot:
    """Serializable snapshot of segment data for parallel signature generation.
    
    Contains all data needed to reconstruct a mock AtomGroup and MoleculeInstance
    for signature generation in a worker process.
    """
    segment_name: str
    atom_indices: list[int]
    elements: list[str]
    names: list[str]
    resnames: list[str]
    resids: list[int]
    segids: list[str]
    masses: list[float]
    positions: list[list[float]]  # plain list, not np.ndarray
    bonds: list[tuple[int, int]]
    flags: dict[str, bool]
    atom_count: int
    residue_count: int
    molecule_type: str
    instance_id: str
    chain_ids: list[str]
    copy_number: int
    element_composition: dict[str, int]
    # B-18 (red-team 4.10): faithful atom->residue / chain mapping so the
    # worker can rebuild a REAL AtomGroup (None = legacy snapshot, falls
    # back to resid-first-appearance grouping)
    atom_resindices: list[int] | None = None
    atom_chain_ids: list[str] | None = None


def build_signature_snapshot(
    segment_name: str,
    fragment: Any,  # MDAnalysis.AtomGroup
    instance: Any,  # MoleculeInstance
    facade: Any,    # LoadedUniverse
) -> SegmentSignatureSnapshot:
    """Build a serializable snapshot from segment data.
    
    Args:
        segment_name: Name/ID of the segment.
        fragment: MDAnalysis AtomGroup for the fragment.
        instance: MoleculeInstance for the segment.
        facade: LoadedUniverse for segment properties.
        
    Returns:
        SegmentSignatureSnapshot with all data converted to plain Python types.
    """
    import numpy as np
    
    # Extract atom data
    atoms = fragment.atoms
    
    # Get elements (handle missing)
    elements = list(atoms.elements) if hasattr(atoms, 'elements') else [''] * len(atoms)
    
    # Get names
    names = list(atoms.names) if hasattr(atoms, 'names') else [''] * len(atoms)
    
    # Get resnames
    resnames = list(atoms.resnames) if hasattr(atoms, 'resnames') else [''] * len(atoms)
    
    # Get resids
    resids = list(atoms.resids) if hasattr(atoms, 'resids') else [0] * len(atoms)
    
    # Get segids
    segids = list(atoms.segids) if hasattr(atoms, 'segids') else [''] * len(atoms)
    
    # Get masses
    masses = list(atoms.masses) if hasattr(atoms, 'masses') else [0.0] * len(atoms)
    
    # Get positions - convert numpy array to plain list
    if hasattr(atoms, 'positions'):
        positions = atoms.positions.tolist() if hasattr(atoms.positions, 'tolist') else [list(p) for p in atoms.positions]
    else:
        positions = [[0.0, 0.0, 0.0]] * len(atoms)
    
    # Get bonds - convert to plain tuples
    bonds = []
    if hasattr(atoms, 'bonds'):
        try:
            bond_indices = atoms.bonds.indices
            for bond in bond_indices:
                bonds.append((int(bond[0]), int(bond[1])))
        except Exception:
            pass
    
    # Get molecule type as string
    mol_type = instance.molecule_type.value if hasattr(instance.molecule_type, 'value') else str(instance.molecule_type)
    
    # Get element composition
    elem_comp = dict(instance.element_composition) if instance.element_composition else {}
    
    return SegmentSignatureSnapshot(
        segment_name=segment_name,
        atom_indices=list(atoms.indices) if hasattr(atoms, 'indices') else list(range(len(atoms))),
        elements=elements,
        names=names,
        resnames=resnames,
        resids=resids,
        segids=segids,
        masses=masses,
        positions=positions,
        bonds=bonds,
        flags=dict(facade.get_segment_properties(segment_name).flags) if facade else {},
        atom_count=len(atoms),
        residue_count=len(fragment.residues) if hasattr(fragment, 'residues') else 0,
        molecule_type=mol_type,
        instance_id=instance.instance_id,
        chain_ids=list(instance.chain_ids) if instance.chain_ids else [segment_name],
        copy_number=instance.copy_number,
        element_composition=elem_comp,
        atom_resindices=([int(r) for r in atoms.resindices]
                         if hasattr(atoms, 'resindices') else None),
        atom_chain_ids=([str(c) for c in atoms.chainIDs]
                        if hasattr(atoms, 'chainIDs') else None),
    )
