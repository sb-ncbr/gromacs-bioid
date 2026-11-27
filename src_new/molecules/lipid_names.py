"""Lipid residue names -> LIPID MAPS shorthand (pure data, no imports).

2026-11-21 (mdval audit item 4): one table for lipid typing
(instances.LIPID_RESNAMES) and the lipid_shorthand generator
(signatures/forcefield_maps). It lives in molecules/ because the loader
cannot import signatures/ at module level (circular import).

ALL_ATOM_SHORTHAND covers the all-atom names: CHARMM36 (toppar_c36_jul24,
the lipid keys of identification/name_tables/maps.json, whose
maps_provenance.json gives the chemistry), plus the CHARMM-GUI/Slipids/AMBER
names that follow the same two-letter tail convention. Tails are sn-1/sn-2;
the resolver queries the species (class + total composition), so the order
of the chains only matters for display.

MARTINI_SHORTHAND names the Martini lipids whose all-atom parent is
documented (Martini 2 lipidome). A coarse-grained molecule is never
verified; the shorthand is only shown as "by name".
"""

from __future__ import annotations

# fatty acyl chains (LIPID MAPS notation)
_C6 = "6:0"
_C7 = "7:0"
_C10 = "10:0"
_C11 = "11:0"
_C12 = "12:0"
_C14 = "14:0"
_C16 = "16:0"
_C16_1 = "16:1(9Z)"
_C18 = "18:0"
_C18_1 = "18:1(9Z)"
_C18_1V = "18:1(11Z)"          # vaccenyl
_C18_2 = "18:2(9Z,12Z)"
_C18_3 = "18:3(9Z,12Z,15Z)"
_C20_1 = "20:1(11Z)"
_C20_4 = "20:4(5Z,8Z,11Z,14Z)"
_C22_1 = "22:1(13Z)"
_C22_6 = "22:6(4Z,7Z,10Z,13Z,16Z,19Z)"
_C24_1 = "24:1(15Z)"


def _gpl(head: str, sn1: str, sn2: str) -> str:
    return f"{head}({sn1}/{sn2})"


# two-letter tail codes of the CHARMM36 / CHARMM-GUI glycerophospholipids
_TAILS: dict[str, tuple[str, str]] = {
    "DL": (_C12, _C12), "DM": (_C14, _C14), "DP": (_C16, _C16),
    "DS": (_C18, _C18), "DO": (_C18_1, _C18_1), "DY": (_C16_1, _C16_1),
    "DX": (_C16_1, _C16_1), "DG": (_C20_1, _C20_1), "DE": (_C22_1, _C22_1),
    "DN": (_C24_1, _C24_1), "DA": (_C20_4, _C20_4), "DU": (_C18_2, _C18_2),
    "PO": (_C16, _C18_1), "PL": (_C16, _C18_2), "PA": (_C16, _C20_4),
    "PY": (_C16, _C16_1), "PV": (_C16, _C18_1V), "SO": (_C18, _C18_1),
    "SL": (_C18, _C18_2), "SA": (_C18, _C20_4), "SD": (_C18, _C22_6),
    "YO": (_C16_1, _C18_1), "OY": (_C18_1, _C16_1), "LL": (_C18_2, _C18_3),
    "OA": (_C18_1, _C20_4), "PD": (_C16, _C22_6),
}
# (head group suffix -> LIPID MAPS class)
_HEADS = {"PC": "PC", "PE": "PE", "PS": "PS", "PG": "PG", "PA": "PA"}

ALL_ATOM_SHORTHAND: dict[str, str] = {}
for _code, (_sn1, _sn2) in _TAILS.items():
    for _suffix, _cls in _HEADS.items():
        ALL_ATOM_SHORTHAND[f"{_code}{_suffix}"] = _gpl(_cls, _sn1, _sn2)

ALL_ATOM_SHORTHAND.update({
    # CHARMM spellings outside the two-letter pattern
    "DLiPC": _gpl("PC", _C18_2, _C18_2), "DLiPE": _gpl("PE", _C18_2, _C18_2),
    "DLIPC": _gpl("PC", _C18_2, _C18_2), "DLIPE": _gpl("PE", _C18_2, _C18_2),
    "DLIPA": _gpl("PA", _C18_2, _C18_2), "DLIPG": _gpl("PG", _C18_2, _C18_2),
    "DLIPS": _gpl("PS", _C18_2, _C18_2),
    "DIPA": _gpl("PA", _C18_3, _C18_3),          # CHARMM: di-alpha-linolenoyl
    "DDOPC": _gpl("PC", _C22_6, _C22_6), "DDOPE": _gpl("PE", _C22_6, _C22_6),
    "DDOPS": _gpl("PS", _C22_6, _C22_6),
    "PDOPC": _gpl("PC", _C16, _C22_6), "PDOPE": _gpl("PE", _C16, _C22_6),
    "DCPC": _gpl("PC", _C11, _C11), "DDPC": _gpl("PC", _C10, _C10),
    "C6DHPC": _gpl("PC", _C6, _C6), "C7DHPC": _gpl("PC", _C7, _C7),
    "PPPE": _gpl("PE", _C16, _C16_1),            # CHARMM: 16:0/16:1 cis-9
    # phosphatidylinositols and phosphoinositides
    "PI": "PI",
    "POPI": _gpl("PI", _C16, _C18_1), "PAPI": _gpl("PI", _C16, _C20_4),
    "SAPI": _gpl("PI", _C18, _C20_4), "SDPI": _gpl("PI", _C18, _C22_6),
    "PLPI": _gpl("PI", _C16, _C18_2),
    "POPI13": _gpl("PIP", _C16, _C18_1), "POPI14": _gpl("PIP", _C16, _C18_1),
    "POPI15": _gpl("PIP", _C16, _C18_1),
    "POPI24": _gpl("PIP2", _C16, _C18_1), "POPI25": _gpl("PIP2", _C16, _C18_1),
    "SAPI13": _gpl("PIP", _C18, _C20_4), "SAPI14": _gpl("PIP", _C18, _C20_4),
    "SAPI15": _gpl("PIP", _C18, _C20_4),
    "SAPI24": _gpl("PIP2", _C18, _C20_4), "SAPI25": _gpl("PIP2", _C18, _C20_4),
    "SAPI2C": _gpl("PIP2", _C18, _C20_4), "SAPI2D": _gpl("PIP2", _C18, _C20_4),
    "DMPI24": _gpl("PIP2", _C14, _C14), "DMPI25": _gpl("PIP2", _C14, _C14),
    # lyso lipids (species already)
    "LPC12": "LPC 12:0", "LPC14": "LPC 14:0",
    "LMPG": "LPG 14:0", "LPPG": "LPG 16:0",
    # sphingomyelins (d18:1 sphingosine base)
    "PSM": "SM(d18:1/16:0)", "DPSM": "SM(d18:1/16:0)", "DPSC": "SM(d18:1/16:0)",
    "SSM": "SM(d18:1/18:0)", "OSM": "SM(d18:1/18:1(9Z))",
    "ASM": "SM(d18:1/20:0)", "BSM": "SM(d18:1/22:0)", "23SM": "SM(d18:1/23:0)",
    "LSM": "SM(d18:1/24:0)", "NSM": "SM(d18:1/24:1(15Z))",
    # ceramides
    "CER160": "Cer(d18:1/16:0)", "CER180": "Cer(d18:1/18:0)",
    "CER181": "Cer(d18:1/18:1(9Z))", "CER200": "Cer(d18:1/20:0)",
    "CER220": "Cer(d18:1/22:0)", "CER240": "Cer(d18:1/24:0)",
    "CER241": "Cer(d18:1/24:1(15Z))", "CER2": "Cer(d18:1/24:0)",
    # sterols (LIPID MAPS species)
    "CHL1": "ST 27:1;O", "CHOL": "ST 27:1;O", "CHL": "ST 27:1;O",
    "ERG": "ST 28:3;O", "SITO": "ST 29:1;O", "STIG": "ST 29:2;O",
    # cardiolipins (charge variants share the structure class)
    "TOCL1": "CL(18:1(9Z)/18:1(9Z)/18:1(9Z)/18:1(9Z))",
    "TOCL2": "CL(18:1(9Z)/18:1(9Z)/18:1(9Z)/18:1(9Z))",
    "TMCL1": "CL(14:0/14:0/14:0/14:0)", "TMCL2": "CL(14:0/14:0/14:0/14:0)",
    "TLCL1": f"CL({_C18_2}/{_C18_2}/{_C18_2}/{_C18_2})",
    "TLCL2": f"CL({_C18_2}/{_C18_2}/{_C18_2}/{_C18_2})",
    "TYCL1": f"CL({_C16_1}/{_C16_1}/{_C16_1}/{_C16_1})",
    "TYCL2": f"CL({_C16_1}/{_C16_1}/{_C16_1}/{_C16_1})",
    "LOACL1": f"CL({_C18_2}/{_C18_2}/{_C18_2}/{_C18_1})",
    "LOACL2": f"CL({_C18_2}/{_C18_2}/{_C18_2}/{_C18_1})",
    "LOCCL1": f"CL({_C18_2}/{_C18_2}/{_C18_2}/{_C18_1})",
    "LOCCL2": f"CL({_C18_2}/{_C18_2}/{_C18_2}/{_C18_1})",
    "PVCL2": f"CL({_C16}/{_C18_1V}/{_C16}/{_C18_1V})",
    "CDL": "CL", "CDL1": "CL", "CDL2": "CL",
})

# GitHub #16: neutral glycerolipids (diacyl-/triacylglycerols, cholesteryl
# ester); NMRlipids 718 evidence: AMBER Lipid17 DOG = 1,2-dioleoyl-sn-glycerol.
# Several names are also PDB CCD codes (DOG 2-deoxyglucose, DMG
# dimethylglycine, DPG 2,3-diphosphoglycerate, SOG octyl thioglucoside, TRIS)
# or other force-field residues (CHARMM36 TRIP is tricosanoic acid), so a name
# only counts when the atoms ARE the named species: carbon and oxygen counts
# exactly those of the shorthand, no P/N/S (neutral_glycerolipid_shorthand).
# Kept out of ALL_ATOM_SHORTHAND / instances.LIPID_RESNAMES.
NEUTRAL_GLYCEROLIPID_SHORTHAND: dict[str, str] = {
    "DOG": _gpl("DG", _C18_1, _C18_1), "DOGL": _gpl("DG", _C18_1, _C18_1),
    "POG": _gpl("DG", _C16, _C18_1), "POGL": _gpl("DG", _C16, _C18_1),
    "DPG": _gpl("DG", _C16, _C16), "DPGL": _gpl("DG", _C16, _C16),
    "SOG": _gpl("DG", _C18, _C18_1), "SOGL": _gpl("DG", _C18, _C18_1),
    "SAG": _gpl("DG", _C18, _C20_4), "SAGL": _gpl("DG", _C18, _C20_4),
    "PLG": _gpl("DG", _C16, _C18_2), "SLG": _gpl("DG", _C18, _C18_2),
    "DLIG": _gpl("DG", _C18_2, _C18_2), "DMG": _gpl("DG", _C14, _C14),
    "DSG": _gpl("DG", _C18, _C18), "DLG": _gpl("DG", _C12, _C12),
    "PDG": _gpl("DG", _C16, _C22_6),
    "TRIO": f"TG({_C18_1}/{_C18_1}/{_C18_1})", "TOG": f"TG({_C18_1}/{_C18_1}/{_C18_1})",
    "TRIP": f"TG({_C16}/{_C16}/{_C16})", "TRIS": f"TG({_C18}/{_C18}/{_C18})",
    "TRIL": f"TG({_C18_2}/{_C18_2}/{_C18_2})",
    "CHOLE": "CE 18:1",
}
# backbone carbons / oxygens per class: glycerol C3 + one ester O pair per
# chain + free OH (DG 5 O, TG 6 O); cholesterol C27 + one ester (2 O)
_NEUTRAL_CLASS_ATOMS = {"DG": (3, 5), "TG": (3, 6), "CE": (27, 2)}


def neutral_glycerolipid_shorthand(resname: str, composition: dict) -> str | None:
    """The shorthand of a neutral glycerolipid residue name, only when the
    element counts are exactly those of that species (GitHub #16)."""
    shorthand = NEUTRAL_GLYCEROLIPID_SHORTHAND.get(str(resname).strip().upper())
    if shorthand is None or any(composition.get(e, 0) for e in ("P", "N", "S")):
        return None
    cls = shorthand.split("(", 1)[0].split(" ", 1)[0]
    base_c, oxygens = _NEUTRAL_CLASS_ATOMS[cls]
    chains = (shorthand.split("(", 1)[1].rsplit(")", 1)[0].split("/")
              if "(" in shorthand else [shorthand.split(" ", 1)[1]])
    carbons = base_c + sum(int(c.split(":", 1)[0]) for c in chains)
    if composition.get("C", 0) != carbons or composition.get("O", 0) != oxygens:
        return None
    return shorthand

# CHARMM36 lipids of maps.json without a shorthand here (ether lipids and
# pyrophosphates: no LIPID MAPS species query BioID can trust). Typed lipid;
# name_maps still identifies them.
OTHER_ALL_ATOM_LIPIDS: frozenset[str] = frozenset({
    "DHPCE", "DMPCE", "DMPEE", "DOPCE", "DOPEE", "DPPEE", "POPCE", "POPEE",
    "DOPP1", "DOPP2", "DOPP3", "POPP1", "POPP2", "POPP3", "TIPA", "QMPE",
})

# B-15 (red-team 4.9): AMBER Lipid14/17/21 split a lipid into one head
# residue (PC/PE/PG/PS) and two tail residues named by the fatty acid.
LIPID21_HEADS: frozenset[str] = frozenset({"PC", "PE", "PG", "PS"})
LIPID21_TAIL_CHAINS: dict[str, str] = {
    "LA": "12:0", "MY": "14:0", "PA": "16:0", "PO": "16:1(9Z)",
    "ST": "18:0", "OL": "18:1(9Z)", "LI": "18:2(9Z,12Z)",
    "AR": "20:4(5Z,8Z,11Z,14Z)",
}
LIPID21_TAILS: frozenset[str] = frozenset(LIPID21_TAIL_CHAINS)

# Martini 2 lipidome names with a documented all-atom parent (by name only)
MARTINI_SHORTHAND: dict[str, str] = {
    name: ALL_ATOM_SHORTHAND[name]
    for name in ("POPC", "POPE", "POPS", "POPG", "POPA", "DOPC", "DOPE",
                 "DOPS", "DOPG", "DPPC", "DPPE", "DPPG", "DPPS", "DSPC",
                 "PAPC", "PAPE", "PAPS", "DAPC", "DAPE", "DAPS", "DPSM",
                 "CHOL", "POPI")
}
MARTINI_SHORTHAND.update({
    # Martini "I" tail = linoleoyl (18:2), "U" = docosahexaenoyl (22:6)
    "PIPC": _gpl("PC", _C16, _C18_2), "PIPE": _gpl("PE", _C16, _C18_2),
    "PIPS": _gpl("PS", _C16, _C18_2), "DIPC": _gpl("PC", _C18_2, _C18_2),
    "PUPC": _gpl("PC", _C16, _C22_6), "PUPE": _gpl("PE", _C16, _C22_6),
    "PUPS": _gpl("PS", _C16, _C22_6),
    "POP1": _gpl("PIP", _C16, _C18_1), "POP2": _gpl("PIP2", _C16, _C18_1),
    "POP3": _gpl("PIP3", _C16, _C18_1),
})

# Martini lipid residue names that are typed lipid in coarse-grained systems
# even without a documented shorthand (the Martini 2 lipidome, Ingolfsson
# 2014 plasma membrane set)
MARTINI_LIPID_NAMES: frozenset[str] = frozenset(MARTINI_SHORTHAND) | frozenset({
    "BNSM", "DBSM", "DXSM", "PNSM", "POSM", "PGSM", "PGPC", "PGPE", "PEPC",
    "PRPC", "PQPC", "PQPE", "PQPS", "OAPC", "OAPE", "OAPI", "OIPC", "OIPE",
    "OUPC", "OUPE", "OPPC", "OGPC", "OBPC", "DPMC", "DPME", "POME", "PAME",
    "PUME", "PAPA", "PIPA", "PUPA", "PIPX", "POPX", "LPC", "LPPC", "PPC",
    "PPE", "DUPE", "DUPS", "DPAC", "FPC", "PAPI", "PIPI", "PUPI", "DPG1",
    "DPG3", "DXG1", "DXG3", "CHYO", "CHYA", "CHYI", "DPCE", "DXCE", "PNCE",
    "PBCE", "PWCE", "PXCE", "APC", "APE", "DAPA",
})
