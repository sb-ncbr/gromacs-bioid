"""Utility functions for BAT3 Pipeline API."""

from __future__ import annotations


def build_database_url(identifier: str, ident_type: str) -> str | None:
    """Return a canonical database URL for an identifier type."""
    db = ident_type.replace("_ID", "").lower()
    if db == "pdb":
        return f"https://www.rcsb.org/structure/{identifier}"
    if db == "uniprot":
        return f"https://www.uniprot.org/uniprotkb/{identifier}"
    if db == "pubchem":
        return f"https://pubchem.ncbi.nlm.nih.gov/compound/{identifier}"
    if db == "chembl":
        return f"https://www.ebi.ac.uk/chembl/compound_report_card/{identifier.upper()}/"
    if db == "chebi":
        chebi_id = identifier.replace("CHEBI:", "")
        return f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:{chebi_id}"
    if db == "alphafold":
        return f"https://alphafold.ebi.ac.uk/entry/{identifier}"
    return None
