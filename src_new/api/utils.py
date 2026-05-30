"""Utility functions for BAT3 Pipeline API."""

from __future__ import annotations


def build_database_url(identifier: str, ident_type: str) -> str | None:
    """Return a canonical database URL for an identifier type."""
    # Normalize identifier type
    ident_upper = ident_type.upper()
    
    if ident_upper == "PDB_ID":
        return f"https://www.rcsb.org/structure/{identifier}"
    if ident_upper == "UNIPROT_ID":
        return f"https://www.uniprot.org/uniprotkb/{identifier}"
    if ident_upper in ("PUBCHEM_CID", "PUBCHEM"):
        return f"https://pubchem.ncbi.nlm.nih.gov/compound/{identifier}"
    if ident_upper in ("CHEMBL_ID", "CHEMBL"):
        return f"https://www.ebi.ac.uk/chembl/compound_report_card/{identifier.upper()}/"
    if ident_upper in ("CHEBI_ID", "CHEBI"):
        chebi_id = identifier.replace("CHEBI:", "")
        return f"https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI:{chebi_id}"
    if ident_upper in ("ALPHAFOLD_ID", "ALPHAFOLD"):
        return f"https://alphafold.ebi.ac.uk/entry/{identifier}"
    return None
