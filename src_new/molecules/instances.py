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


# --- segment-type knowledge tables (v3.140; see V-36 ledger note) -----------
# Shared home: molecules/ has no upward dependency, so both loader (typing)
# and signatures/forcefield_maps (shorthand) can ground on the same list.
# Water resname nomenclature across common force fields; structural
# detection (1 O + 2 H) in the classifier covers what this table misses.
WATER_RESNAMES: frozenset[str] = frozenset({
    "SOL", "HOH", "WAT", "TIP3", "TIP3P", "TIP4P", "T4P",
    "SPC", "SPCE", "OPC", "OPC3", "T3P", "T5P",
})

# Canonical lipid resnames — the union of forcefield_maps.LIPID_FORCEFIELD_MAPS
# keys (CHARMM36/gromos/martini) plus the cardiolipin family whose C/O
# composition (~4.5-5) sits outside the legacy glycerol lipid band (1..3)
# and therefore used to be typed UNKNOWN (observed: TOCL2, POPE in run
# a5b785cc/b4813beb). Extend as new families are encountered.
LIPID_RESNAMES: frozenset[str] = frozenset({
    # phosphatidylcholines/-ethanolamines/-serines/-glycerols
    "POPC", "DOPC", "DPPC", "DMPC", "DLPC",
    "POPE", "DOPE", "DPPE", "POPS", "DOPS",
    "POPG", "DOPG", "DLPG", "DMPG",
    "POPA", "DOPA",
    # cardiolipins (CHARMM36/martini)
    "TOCL1", "TOCL2", "TMCL1", "TMCL2", "CDL", "CDL1", "CDL2",
    # sterols / sphingomyelins / phosphatidylinositols (from forcefield maps)
    "CHOL", "CHL1", "DPSM", "DPSC", "PI", "PAPI", "POPI",
})


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
