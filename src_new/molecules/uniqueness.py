from __future__ import annotations

from dataclasses import dataclass
from .instances import MoleculeInstance, MoleculeType


@dataclass
class MolecularFingerprint:
    atom_count: int
    residue_count: int
    element_composition: dict
    molecule_type: MoleculeType
    formula_hash: str = ""

    def to_key(self) -> str:
        # deterministic key string including type, atoms, residues, elements (sorted), and formula hash if present
        # Example: "type:protein|atoms:100|residues:10|elements:C=50,H=80,...|formula:..."
        elements_str = ",".join(f"{k}={v}" for k, v in sorted(self.element_composition.items()))
        parts = [
            f"type:{self.molecule_type.value}",
            f"atoms:{self.atom_count}",
            f"residues:{self.residue_count}",
            f"elements:{elements_str}",
        ]
        if self.formula_hash:
            parts.append(f"formula:{self.formula_hash}")
        return "|".join(parts)


def create_fingerprint(instance: MoleculeInstance) -> MolecularFingerprint:
    # For small_molecule with element_composition, create formula_hash like "C10H15N5O8P3" (elements sorted alphabetically)
    formula_hash = ""
    if instance.molecule_type == MoleculeType.SMALL_MOLECULE and instance.element_composition:
        # Create formula string with elements sorted alphabetically
        formula_parts = []
        for elem in sorted(instance.element_composition.keys()):
            count = instance.element_composition[elem]
            formula_parts.append(f"{elem}{count}")
        formula_hash = "".join(formula_parts)
    
    return MolecularFingerprint(
        atom_count=instance.atom_count,
        residue_count=len(instance.residue_indices) if instance.residue_indices else len(instance.resids),
        element_composition=dict(instance.element_composition),
        molecule_type=instance.molecule_type,
        formula_hash=formula_hash,
    )


def compute_uniqueness_key(instance: MoleculeInstance) -> str:
    # For proteins, include resnames sequence in the key
    # For others, use fingerprint.to_key()
    if instance.molecule_type == MoleculeType.PROTEIN:
        # Include resnames sequence in the key for proteins
        resnames_str = ",".join(instance.resnames) if instance.resnames else ""
        fp = create_fingerprint(instance)
        elements_str = ",".join(f"{k}={v}" for k, v in sorted(instance.element_composition.items()))
        parts = [
            f"type:{instance.molecule_type.value}",
            f"atoms:{instance.atom_count}",
            f"residues:{len(instance.resids)}",
            f"resnames:{resnames_str}",
            f"elements:{elements_str}",
        ]
        if fp.formula_hash:
            parts.append(f"formula:{fp.formula_hash}")
        return "|".join(parts)
    else:
        fp = create_fingerprint(instance)
        return fp.to_key()


def collapse_to_unique_instances(instances: list[MoleculeInstance]) -> dict[str, MoleculeInstance]:
    # Return dict mapping key -> first representative instance
    result = {}
    for instance in instances:
        key = compute_uniqueness_key(instance)
        if key not in result:
            result[key] = instance
    return result


def group_by_uniqueness(instances: list[MoleculeInstance]) -> dict[str, list[MoleculeInstance]]:
    # Return dict mapping key -> list of instances sharing that key
    groups = {}
    for instance in instances:
        key = compute_uniqueness_key(instance)
        if key not in groups:
            groups[key] = []
        groups[key].append(instance)
    return groups


def count_unique_by_type(instances: list[MoleculeInstance]) -> dict[str, int]:
    # collapse to unique, then count per molecule_type.value
    unique = collapse_to_unique_instances(instances)
    counts = {}
    for instance in unique.values():
        type_val = instance.molecule_type.value
        counts[type_val] = counts.get(type_val, 0) + 1
    return counts
