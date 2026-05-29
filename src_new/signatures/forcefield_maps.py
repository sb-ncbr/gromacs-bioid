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
        "CHL1": "sterol(cholesterol)",
        "CHOL": "sterol(cholesterol)",
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
        "CHOL": "sterol(cholesterol)",
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
}
