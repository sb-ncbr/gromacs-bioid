"""RCSB Chemical Component Dictionary (CCD) lookups with safety layers.

- data.rcsb.org REST (healthy from cluster; verified vs AZL/CLR/HEM)
- NFS/durable cache incl. negative caches (404s) so placeholders stay cheap
- blacklist: placeholder junk (UNK/LIG/MOL/...), standard amino/nucleic acids,
  waters and common ions -- these must never reach the dictionary
- alias table: classical force-field aliases -> CCD codes (CHL1->CLR etc.)

Failure mode: any error -> (None) and callers treat resname as non-CCD.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass

from ..verification.fetchers.compound_fetcher import _polite_get

logger = logging.getLogger(__name__)

CCD_CACHE = "/data/validation/sim_cache/ccd"

# Placeholders and structural classes that must never reach the dictionary.
_BLACKLIST = {
    # placeholders used by topology authors (poison: some exist in CCD!)
    "UNK", "LIG", "MOL", "DRG", "DUM", "XXX", "LGN", "SOL", "MLI",
    # amino acids
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    "HID", "HIE", "HIP", "CYX", "ASH", "GLH", "LYN", "MEU",
    # nucleic
    "A", "C", "G", "T", "U", "DA", "DC", "DG", "DT", "DU", "ATP", "ADP", "AMP",
    # waters
    "WAT", "HOH", "TP3", "TIP", "TIP3", "OPC", "SPC",
    # common ions
    "NA", "CL", "K", "CA", "MG", "ZN", "MN", "FE", "CU", "NI", "CD", "HG",
    "SO4", "PO4", "EDO", "GOL", "PEG", "ACT",
}

# Historical force-field aliases -> CCD codes (curated; extend deliberately).
_ALIASES = {
    "CHL1": "CLR",
    "CHOL": "CLR",
    "CHL": "CLR",
    "POP1": "POPC",
    "DPPC": "DPPC",
    "DLPC": "LPC12",
}

_TOKEN_RE = re.compile(r"^[A-Z0-9]{2,5}$")


@dataclass(frozen=True)
class CcdRecord:
    resname: str
    smiles: str
    inchikey: str
    formula: str


def _cache_path(resname: str) -> str:
    return os.path.join(CCD_CACHE, hashlib.sha1(resname.encode()).hexdigest()[:24] + ".json")


def _cache_read(resname: str):
    try:
        with open(_cache_path(resname)) as fh:
            return json.load(fh)
    except Exception:
        return "miss"


def _cache_write(resname: str, payload) -> None:
    try:
        os.makedirs(CCD_CACHE, exist_ok=True)
        with open(_cache_path(resname), "w") as fh:
            json.dump(payload, fh)
    except OSError:
        pass


def normalize_resname(raw: str) -> str | None:
    """Clean a topology resname into a dictionary candidate, or None.

    Returns None for placeholders/blacklisted/odd shapes - the resolver then
    treats the name as non-CCD (safe no-op, never a wrong positive).
    """
    if not raw:
        return None
    token = raw.strip().upper()
    if not (2 <= len(token) <= 5) or not _TOKEN_RE.match(token):
        return None
    if token in _BLACKLIST:
        return None
    return _ALIASES.get(token, token)


def lookup_ccd(resname: str) -> CcdRecord | None:
    """Look up a normalized resname in the CCD (REST + durable cache)."""
    token = normalize_resname(resname)
    if token is None:
        return None

    cached = _cache_read(token)
    if cached != "miss":
        if not cached:
            return None
        return CcdRecord(**cached)

    url = f"https://data.rcsb.org/rest/v1/core/chemcomp/{token}"
    r = _polite_get(url)
    record = None
    if r is not None:
        try:
            d = r.json()
            desc = d.get("rcsb_chem_comp_descriptor") or {}
            smiles = (desc.get("SMILES") or "").strip()
            ik = (desc.get("InChIKey") or "").strip()
            formula = ((d.get("chem_comp") or {}).get("formula") or "").replace(" ", "")
            if smiles or ik:
                record = CcdRecord(resname=token, smiles=smiles, inchikey=ik, formula=formula)
        except Exception as exc:
            logger.warning(f"CCD parse failed for {token}: {exc}")

    # cache hit or negative (None) - placeholders stay cheap
    _cache_write(token, record.__dict__ if record else None)
    return record
