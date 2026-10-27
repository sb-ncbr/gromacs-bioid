"""Force-field mapping dictionaries for lipids and glycans."""

from __future__ import annotations

LIPID_FORCEFIELD_MAPS: dict[str, dict[str, str]] = {
    "charmm36": {
        "POPC": "PC(16:0/18:1(9Z))",
        "DOPC": "PC(18:1(9Z)/18:1(9Z))",
        "DPPC": "PC(16:0/16:0)",
        "DMPC": "PC(14:0/14:0)",
        "POPS": "PS(16:0/18:1(9Z))",
        "DOPS": "PS(18:1(9Z)/18:1(9Z))",
        "POPE": "PE(16:0/18:1(9Z))",
        "DOPE": "PE(18:1(9Z)/18:1(9Z))",
        "DPPE": "PE(16:0/16:0)",
        "DLPC": "PC(12:0/12:0)",
        # B-15 (red-team 4.9): PG class + cardiolipins were unmapped and
        # fell through to the literal "LIPID"
        "POPG": "PG(16:0/18:1(9Z))",
        "DOPG": "PG(18:1(9Z)/18:1(9Z))",
        "DLPG": "PG(12:0/12:0)",
        "DMPG": "PG(14:0/14:0)",
        "TOCL1": "CL(18:1(9Z)/18:1(9Z)/18:1(9Z)/18:1(9Z))",
        "TOCL2": "CL(18:1(9Z)/18:1(9Z)/18:1(9Z)/18:1(9Z))",
        "TMCL1": "CL(14:0/14:0/14:0/14:0)",
        "TMCL2": "CL(14:0/14:0/14:0/14:0)",
        "CDL":  "CL",
        "CDL1": "CL",
        "CDL2": "CL",
        # B-15: valid LIPID MAPS abbreviation for cholesterol (the
        # "sterol(cholesterol)" literal resolved to nothing)
        "CHL1": "ST 27:1;O",
        "CHOL": "ST 27:1;O",
        "CHL":  "ST 27:1;O",
        "DPSC": "SM(d18:1/16:0)",
        "DPSM": "SM(d18:1/16:0)",
        "POPA": "PA(16:0/18:1(9Z))",
        "DOPA": "PA(18:1(9Z)/18:1(9Z))",
        "PI":   "PI",
        "PAPI": "PI(16:0/20:4(5Z,8Z,11Z,14Z))",
        "POPI": "PI(16:0/18:1(9Z))",
    },
    # Martini common names
    "martini": {
        "POPC": "PC(16:0/18:1(9Z))",
        "DOPC": "PC(18:1(9Z)/18:1(9Z))",
        "DPPC": "PC(16:0/16:0)",
        "CHOL": "ST 27:1;O",
    },
    # GROMOS common names
    "gromos": {
        "POPC": "PC(16:0/18:1(9Z))",
        "DPPC": "PC(16:0/16:0)",
    },
}

GLYCAN_FORCEFIELD_MAPS: dict[str, dict[str, str]] = {
    "charmm36": {
        "GLC": "Hex",
        "GAL": "Hex",
        "MAN": "Hex",
        "FUC": "dHex",
        "NAG": "HexNAc",
        "NGA": "HexNAc",
        "SIA": "NeuAc",
        "NGS": "HexNAc",
        "BGLC": "Hex",
        "AGLC": "Hex",
        "BGAL": "Hex",
        "AGAL": "Hex",
        "BMAN": "Hex",
        "AMAN": "Hex",
    },
    "glycam": {
        "0GA": "Hex",
        "4GB": "Hex",
        "6MB": "Hex",
        "0SA": "NeuAc",
        "0LB": "dHex",
        "0YB": "HexNAc",
    },
    # wave-2 item 8a: PDB CCD codes — what crystallographic deposits (1FC1
    # class) actually carry; the composition classes follow the GlyCosmos
    # vocabulary emitted by GlycanCompositionGenerator.
    "ccd": {
        # hexoses
        "GLC": "Hex", "BGC": "Hex", "AGC": "Hex",
        "GAL": "Hex", "MAN": "Hex", "BMA": "Hex",
        "FRU": "Hex",
        # N-acetylhexosamines
        "NAG": "HexNAc", "NGA": "HexNAc",
        "BNG": "HexNAc", "NDG": "HexNAc",
        # deoxyhexoses
        "FUC": "dHex", "FCA": "dHex", "RAM": "dHex",
        # sialic acids
        "SIA": "NeuAc", "NGC": "NeuGc", "NGE": "NeuGc",
    },
}

# every residue name any glycan forcefield/CCD table knows — the molecule
# typing name-table (wave-2 item 8a; names only, never a composition band)
GLYCAN_RESNAMES: frozenset = frozenset(
    name for mapping in GLYCAN_FORCEFIELD_MAPS.values() for name in mapping
)
