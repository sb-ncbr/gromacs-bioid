"""Utility functions for BAT3 Pipeline API."""

from __future__ import annotations

import re
from typing import Optional

# PDB identifiers are a 4-character residue/structure code optionally followed
# by a chain suffix (e.g. "1HRC_A"). Only the 4-character code is a valid
# rcsb.org structure id.
_PDB_WITH_CHAIN_RE = re.compile(r"^([A-Za-z0-9]{4})[_\-\s]?([A-Za-z0-9])$")
_PDB_PLAIN_RE = re.compile(r"^[A-Za-z0-9]{4}$")


def normalize_identifier(identifier: Optional[str], ident_type: str) -> Optional[str]:
    """Return a canonical display form of an identifier for a given type.

    - PDB_ID: strips a trailing chain suffix (e.g. ``1HRC_A`` -> ``1HRC``)
      and uppercases the 4-character code.
    - CHEMBL_ID / CHEMBL: ensures the ``CHEMBL`` prefix is present
      (bare digits such as ``12345`` -> ``CHEMBL12345``) and uppercases.
    - Any other type (or a missing/empty identifier): returned unchanged.

    This is a pure function with no I/O so it can be unit tested directly.
    """
    if identifier is None:
        return None

    ident_upper = (ident_type or "").upper()

    if ident_upper == "PDB_ID":
        candidate = identifier.strip()
        if not candidate:
            return identifier
        match = _PDB_WITH_CHAIN_RE.match(candidate)
        if match:
            return match.group(1).upper()
        if _PDB_PLAIN_RE.match(candidate):
            return candidate.upper()
        return candidate

    if ident_upper in ("CHEMBL_ID", "CHEMBL"):
        candidate = identifier.strip()
        if not candidate:
            return identifier
        if candidate.isdigit():
            return f"CHEMBL{candidate}"
        # Already carries (or partially carries) the prefix; normalize case.
        return candidate.upper()

    return identifier


def build_database_url(identifier: Optional[str], ident_type: Optional[str]) -> Optional[str]:
    """Return a canonical database URL for an identifier type.

    Values only: the response field names and shapes are unchanged, only the
    ``database_url`` value is canonicalized. PDB hits have any chain suffix
    stripped and the 4-character code uppercased; bare CHEMBL digits are given
    the ``CHEMBL`` prefix and use the explore/compound URL. Other identifier
    types are left unchanged. Returns ``None`` for unknown types or empty input.
    """
    if identifier is None or not str(identifier).strip():
        return None

    ident_upper = (ident_type or "").upper()

    if ident_upper == "PDB_ID":
        normalized = normalize_identifier(identifier, ident_type)
        if not normalized:
            return None
        return f"https://www.rcsb.org/structure/{normalized}"
    if ident_upper == "UNIPROT_ID":
        return f"https://www.uniprot.org/uniprotkb/{identifier}"
    if ident_upper in ("PUBCHEM_CID", "PUBCHEM"):
        return f"https://pubchem.ncbi.nlm.nih.gov/compound/{identifier}"
    if ident_upper in ("CHEMBL_ID", "CHEMBL"):
        normalized = normalize_identifier(identifier, ident_type)
        if not normalized:
            return None
        return f"https://www.ebi.ac.uk/chembl/explore/compound/{normalized}"
    if ident_upper in ("CHEBI_ID", "CHEBI"):
        chebi_id = identifier.replace("CHEBI:", "")
        return f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:{chebi_id}"
    if ident_upper in ("ALPHAFOLD_ID", "ALPHAFOLD"):
        return f"https://alphafold.ebi.ac.uk/entry/{identifier}"
    return None
