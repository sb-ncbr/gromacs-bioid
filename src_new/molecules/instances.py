from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class MoleculeType(str, Enum):
    PROTEIN = "protein"
    WATER = "water"
    ION = "ion"
    SMALL_MOLECULE = "small_molecule"
    LIPID = "lipid"
    CARBOHYDRATE = "carbohydrate"
    NUCLEIC = "nucleic"
    UNKNOWN = "unknown"


@dataclass
class MoleculeInstance:
    instance_id: str
    atom_indices: list[int] = field(default_factory=list)
    residue_indices: list[int] = field(default_factory=list)
    segment_ids: list[str] = field(default_factory=list)
    chain_ids: list[str] = field(default_factory=list)
    resids: list[int] = field(default_factory=list)
    resnames: list[str] = field(default_factory=list)
    molecule_type: MoleculeType = MoleculeType.UNKNOWN
    copy_number: int = 1
    confidence: float = 1.0
    provenance: dict = field(default_factory=dict)
    atom_count: int = 0
    element_composition: dict = field(default_factory=dict)
