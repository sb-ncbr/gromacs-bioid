"""Display names for verified hits (BACKEND_GAPS G5, chemical side).

The verification scorers thread `name` onto macromolecular hits (PDB title,
UniProt protein name); chemical hits carried none, so the UI showed InChIKeys
("PubChem PXXJHWLDUBFPOL-UHFFFAOYSA-N" for benzamidine) and "Element CA".
At read time a missing name is filled from data the API already has:
  ELEMENT                -> the element name (RDKit periodic table)
  PUBCHEM_CID / INCHIKEY -> the PubChem mirror's IUPAC name
so runs verified before the scorer change get names too. Names are returned
whole — some IUPAC names exceed 100 characters; the UI truncates for display.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Optional

_MIRROR_DEFAULT = "/app/databases/pubchem/current/pubchem.sqlite"
_db = None
_db_ready = False


def _mirror():
    """Lazy per-process PubChem mirror handle (None when absent)."""
    global _db, _db_ready
    if not _db_ready:
        _db_ready = True
        try:
            from ..molecules.pubchem_db import PubChemDB
            db = PubChemDB(os.environ.get("PUBCHEM_LOCAL_DB", _MIRROR_DEFAULT))
            _db = db if db.exists() else None
        except Exception:
            _db = None
    return _db


@lru_cache(maxsize=1)
def _periodic_table():
    from rdkit import Chem
    return Chem.GetPeriodicTable()


def element_name(symbol: str) -> Optional[str]:
    """'CA' / 'Ca' -> 'Calcium'; None when not an element symbol."""
    sym = str(symbol or "").strip()
    if not sym:
        return None
    sym = sym[0].upper() + sym[1:].lower()
    try:
        pt = _periodic_table()
        z = pt.GetAtomicNumber(sym)
        return pt.GetElementName(z) if z > 0 else None
    except Exception:
        return None


# An ELEMENT hit is a one-atom molecule, which in a simulation is an ion
# (UI audit 2026-11-08: CHARMM CLA showed as "Chlorine", the Cl2 gas).
_ANIONS = {"F": "Fluoride", "Cl": "Chloride", "Br": "Bromide", "I": "Iodide"}
# One-atom species that are not ions: noble-gas fluids, and the nonmetals
# whose lone atom has no single usual charge.
_NOT_IONS = {"H", "He", "B", "C", "N", "O", "Ne", "Si", "P", "S", "Ar", "As",
             "Se", "Kr", "Te", "Xe", "Rn"}


def ion_name(symbol: str) -> Optional[str]:
    """'CL' -> 'Chloride', 'NA' -> 'Sodium ion', 'AR' -> 'Argon'."""
    name = element_name(symbol)
    if name is None:
        return None
    sym = str(symbol).strip()
    sym = sym[0].upper() + sym[1:].lower()
    if sym in _ANIONS:
        return _ANIONS[sym]
    return name if sym in _NOT_IONS else f"{name} ion"


@lru_cache(maxsize=20000)
def _pubchem_name(ident_type: str, identifier: str) -> Optional[str]:
    db = _mirror()
    if db is None:
        return None
    try:
        row = db.by_inchikey(identifier) if ident_type == "INCHIKEY" else db.by_cid(identifier)
    except Exception:
        return None
    return (getattr(row, "iupac_name", None) or None) if row is not None else None


_FIRST_WORD = re.compile(r"[A-Za-z]{2,}")


def capitalize_name(name: Optional[str]) -> Optional[str]:
    """Upper-case the first letter of the name proper (user 2026-11-06:
    "make sure all molecule names are capitalized" — IUPAC names came
    lower-case: "oxidane", "benzenecarboximidamide"). Chemical convention:
    the first letter of the first real word, not of locant/stereo/italic
    prefixes — "[(2R)-3-hexadecanoyloxy..." -> "[(2R)-3-Hexadecanoyloxy...",
    "n-butane" -> "n-Butane". Names already starting upper-case (UniProt,
    element names, PDB titles) are unchanged."""
    if not name:
        return name
    m = _FIRST_WORD.search(name)
    if m is None or not m.group(0)[0].islower():
        return name
    i = m.start()
    return name[:i] + name[i].upper() + name[i + 1:]


# Common names that beat the stored/IUPAC name (UI pass 2026-11-07: water
# showed as "Oxidane"). Keyed by identifier, so it also overrides the name
# the scorer stored on runs verified before this change.
_COMMON_NAMES = {
    ("PUBCHEM_CID", "962"): "Water",
    ("INCHIKEY", "XLYOFNOQVPJJNP-UHFFFAOYSA-N"): "Water",
}


@lru_cache(maxsize=20000)
def _pubchem_title(ident_type: str, identifier: str) -> Optional[str]:
    """PubChem's common name (Title) for a chemical hit, from the optional
    titles file beside the mirror. None when the file, the compound or a
    usable title is missing — most lookups for obscure CIDs end here."""
    try:
        from ..molecules.pubchem_titles import default_titles
        titles = default_titles()
        if ident_type == "PUBCHEM_CID":
            return titles.title(identifier) if identifier.isdigit() else None
        db = _mirror()
        row = db.by_inchikey(identifier) if db is not None else None
        return titles.title(row.cid) if row is not None else None
    except Exception:
        return None


def hit_display_name(hit: dict) -> Optional[str]:
    """Display name, first available of: a fixed common name (water), the
    ion name for one-atom hits, the PubChem title (common name) for chemical
    hits, the hit's own name, a read-time fill (IUPAC). Always capitalized."""
    ident_type = str(hit.get("ident_type") or "").upper()
    identifier = str(hit.get("identifier") or "").strip()
    if (ident_type, identifier) in _COMMON_NAMES:
        return _COMMON_NAMES[(ident_type, identifier)]
    if ident_type == "ELEMENT" and identifier:
        # Beats the stored name: scorers stored the element name ("Chlorine").
        name = ion_name(identifier)
        if name:
            return name
    if ident_type in ("PUBCHEM_CID", "INCHIKEY") and identifier:
        title = _pubchem_title(ident_type, identifier)
        if title:
            return capitalize_name(title)
    return capitalize_name(_raw_display_name(hit))


def _raw_display_name(hit: dict) -> Optional[str]:
    name = hit.get("name")
    if name:
        return name
    ident_type = str(hit.get("ident_type") or "").upper()
    identifier = str(hit.get("identifier") or "").strip()
    if not identifier:
        return None
    if ident_type == "ELEMENT":
        return element_name(identifier)
    if ident_type in ("PUBCHEM_CID", "INCHIKEY"):
        return _pubchem_name(ident_type, identifier)
    if ident_type == "SLM_ID":
        return _swisslipids_name(identifier)
    return None


def _swisslipids_name(identifier: str) -> Optional[str]:
    """SwissLipids name from the local index (no scorer records one)."""
    try:
        from ..config.loader import IdentifiersConfig
        from ..identification.reference_indexes import swisslipids_record
        rec = swisslipids_record(IdentifiersConfig.swisslipids_db, identifier)
    except Exception:
        return None
    return rec[2] if rec and rec[2] else None
