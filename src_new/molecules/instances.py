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
    # bughunt BH-001: crystallographic/heavy-water spellings — the water
    # rule is residue-based (see universe_facade._classify_molecule_type)
    # so these must be present even though the atoms come without bonds.
    "H2O", "DOD", "HHO", "OH2", "WAT4", "WAT5", "HO4", "DWQ",
})

# Canonical lipid resnames — the union of forcefield_maps.LIPID_FORCEFIELD_MAPS
# keys (CHARMM36/gromos/martini) plus the cardiolipin family whose C/O
# composition (~4.5-5) sits outside the legacy glycerol lipid band (1..3)
# and therefore used to be typed UNKNOWN (observed: TOCL2, POPE in run
# a5b785cc/b4813beb). Extend as new families are encountered.
# 2026-11-21 (mdval audit item 4): grounded on molecules/lipid_names — every
# all-atom name with a shorthand (CHARMM36 lipid keys of maps.json, the
# CHARMM-GUI/Slipids two-letter tail names) plus the CHARMM36 ether lipids
# and pyrophosphates. DSPC (401 segments), PSM, SOPE, PLPC, SDPC... were
# composition-typed and fell through the 35-name shorthand map.
from .lipid_names import (  # noqa: E402  (pure data module)
    ALL_ATOM_SHORTHAND as _ALL_ATOM_SHORTHAND,
    MARTINI_LIPID_NAMES as _MARTINI_LIPID_NAMES,
    OTHER_ALL_ATOM_LIPIDS as _OTHER_ALL_ATOM_LIPIDS,
)

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
}) | frozenset(n.upper() for n in _ALL_ATOM_SHORTHAND) | _OTHER_ALL_ATOM_LIPIDS

# 2026-11-21 (mdval audit item 4/8b): Martini lipid names, typed lipid ONLY in
# coarse-grained systems — several are PDB CCD codes too (APC, PPC, FPC).
CG_LIPID_RESNAMES: frozenset[str] = frozenset(
    n.upper() for n in _MARTINI_LIPID_NAMES)

# 2026-11-21 (mdval audit item 8b): coarse-grained water residue/bead names
# (Martini W/WF antifreeze, polarizable PW (W, WP, WM beads), big BW, SPICA
# and SIRAH SW/WN/WT4/WLS). Martini "W" is four waters in one bead; the
# single-atom name fallback read it as tungsten and typed it an ion.
CG_WATER_RESNAMES: frozenset[str] = frozenset({
    "W", "WF", "PW", "BW", "SW", "WN", "WP", "WM", "WT4", "WLS", "WAT",
    "SOL", "H2O",
})
CG_WATER_BEADS: frozenset[str] = frozenset({
    "W", "WF", "WP", "WM", "BW", "SW", "WN", "PW", "WT", "WL",
})
# Martini ion beads / residues (ION residue with NA+, CL-, ... beads)
CG_ION_RESNAMES: frozenset[str] = frozenset({
    "ION", "NA+", "CL-", "K+", "CA+", "CA2+", "MG2+", "NA", "CL", "K", "CA",
    "MG", "NC3+", "SOD", "CLA", "POT",
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
