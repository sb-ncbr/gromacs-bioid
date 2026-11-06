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


def hit_display_name(hit: dict) -> Optional[str]:
    """The hit's own name, else a read-time fill for chemical identifiers;
    always capitalized."""
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
    return None
