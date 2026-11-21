"""Force-field mapping dictionaries for lipids and glycans."""

from __future__ import annotations

from ..molecules.lipid_names import ALL_ATOM_SHORTHAND, MARTINI_SHORTHAND

# 2026-11-21 (mdval audit item 4): the all-atom map is molecules/lipid_names
# (CHARMM36 + CHARMM-GUI/Slipids names, ~200; was 35 hand-written entries —
# PAPC, PAPS, DSPC, PSM, SOPE... returned None). The B-15 additions (PG
# class, cardiolipins, "ST 27:1;O" cholesterol, SM) are part of it.
# Coarse-grained molecules skip the generator (nothing to verify against);
# the "martini" map gives their by-name lead (loader/fragment_store).
LIPID_FORCEFIELD_MAPS: dict[str, dict[str, str]] = {
    "charmm36": {name.upper(): shorthand for name, shorthand in ALL_ATOM_SHORTHAND.items()},
    # Martini 2 lipidome names with a documented all-atom parent
    "martini": dict(MARTINI_SHORTHAND),
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
