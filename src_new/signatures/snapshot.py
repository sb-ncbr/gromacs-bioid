"""Snapshot utilities for parallel signature generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _local_bonds(atoms) -> list[tuple[int, int]]:
    """W3.1-3 (A6): FRAGMENT-LOCAL bond indices. Universe-level indices
    made the per-unique group key differ per physical copy, so the W3 A6
    dedup never fired (F14 ran per-copy chemistry). Cross-fragment bond
    endpoints are dropped."""
    try:
        idx_map = {int(ix): i for i, ix in enumerate(atoms.indices)}
    except Exception:
        return []
    out = []
    try:
        for a, b in atoms.bonds.indices:
            ia, ib = idx_map.get(int(a)), idx_map.get(int(b))
            if ia is not None and ib is not None:
                out.append((min(ia, ib), max(ia, ib)))
    except Exception:
        return []
    return sorted(out)


def _stereo_tags(bonds, elements, names, positions) -> tuple:
    """W3.1-3 (A6): cheap stereo signature — the signed tetrahedral
    volume at each stereocentre CANDIDATE (an atom with four distinctly
    ranked neighbours). Proper rotations/translations preserve the
    sign; reflection flips it, so R and S land in different unique
    groups while copies of one enantiomer share theirs. Centres whose
    four substituent ranks are not all distinct (symmetric substituents)
    are not stereocentres and are skipped; degenerate/missing geometry
    contributes no tag."""
    import numpy as np

    n = len(elements)
    if not bonds or n == 0 or positions is None or len(positions) != n:
        return ()
    nbrs: list[list[int]] = [[] for _ in range(n)]
    for a, b in bonds:
        if 0 <= a < n and 0 <= b < n:
            nbrs[a].append(b)
            nbrs[b].append(a)
    # Morgan-style iterative ranking, seeded by (element, name)
    seed = [((elements[i] if i < len(elements) else ""),
             (names[i] if i < len(names) else "")) for i in range(n)]
    uniq = {k: j for j, k in enumerate(sorted(set(seed)))}
    rank = [uniq[v] for v in seed]
    for _ in range(3):
        new = [(rank[i], tuple(sorted(rank[j] for j in nbrs[i])))
               for i in range(n)]
        uniq = {k: j for j, k in enumerate(sorted(set(new)))}
        rank = [uniq[v] for v in new]
    tags = []
    for i in range(n):
        if len(nbrs[i]) != 4:
            continue
        if len({rank[j] for j in nbrs[i]}) != 4:
            continue  # symmetric substituents: not a stereocentre
        order = sorted(nbrs[i], key=lambda j: -rank[j])
        try:
            c = np.asarray(positions[i], dtype=float)
            v = [np.asarray(positions[j], dtype=float) - c for j in order]
            det = float(np.linalg.det(
                np.array([v[0] - v[3], v[1] - v[3], v[2] - v[3]])))
        except Exception:
            continue
        if abs(det) < 1e-6:
            continue  # planar/degenerate geometry: no chirality signal
        tags.append((i, 1 if det > 0 else -1))
    return tuple(tags)


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
    # W3.1-3 (A6): per-stereocentre signed-volume parities, local indices
    stereo_tags: tuple = ()


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
    
    # Get bonds - convert to plain tuples (universe indices; the worker
    # and the group key remap them to fragment-local as needed)
    bonds = []
    if hasattr(atoms, 'bonds'):
        try:
            bond_indices = atoms.bonds.indices
            for bond in bond_indices:
                bonds.append((int(bond[0]), int(bond[1])))
        except Exception:
            pass
    # W3.1-3 (A6): stereo signature from FRAGMENT-LOCAL bonds
    stereo_tags = _stereo_tags(_local_bonds(atoms), elements, names, positions)
    
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
        stereo_tags=stereo_tags,
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
