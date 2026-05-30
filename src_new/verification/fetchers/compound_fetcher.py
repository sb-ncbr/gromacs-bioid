"""Compound signature fetcher for small molecules."""

from __future__ import annotations

import logging
import requests

from ..base import SignatureFetcher

logger = logging.getLogger(__name__)


class CompoundSignatureFetcher(SignatureFetcher):
    """Fetches canonical SMILES for compound identifiers."""
    
    SUPPORTED_TYPES = {"PUBCHEM_CID", "CHEMBL_ID", "CHEBI_ID"}
    
    def supports(self, ident_type: str) -> bool:
        """Check if this fetcher supports the given identifier type."""
        return ident_type in self.SUPPORTED_TYPES
    
    def fetch(self, identifier: str, ident_type: str) -> str | None:
        """Fetch the canonical SMILES for a compound identifier.
        
        Args:
            identifier: The compound identifier (e.g., "962" for PubChem CID).
            ident_type: The type of identifier ("PUBCHEM_CID", "CHEMBL_ID", or "CHEBI_ID").
            
        Returns:
            The canonical SMILES string, or None if not found or on error.
        """
        try:
            if ident_type == "PUBCHEM_CID":
                return self._fetch_pubchem(identifier)
            elif ident_type == "CHEMBL_ID":
                return self._fetch_chembl(identifier)
            elif ident_type == "CHEBI_ID":
                return self._fetch_chebi(identifier)
            else:
                logger.warning(f"Unknown compound ident_type: {ident_type}")
                return None
        except Exception as e:
            logger.warning(f"CompoundSignatureFetcher fetch failed for {identifier}: {e}")
            return None
    
    def _fetch_pubchem(self, cid: str) -> str | None:
        """Fetch SMILES from PubChem."""
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/CanonicalSMILES/TXT"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            return r.text.strip()
        except Exception as e:
            logger.warning(f"PubChem {cid} fetch SMILES failed: {e}")
            return None
    
    def _fetch_chembl(self, chembl_id: str) -> str | None:
        """Fetch SMILES from ChEMBL."""
        # Canonicalize: strip CHEMBL prefix if present, then prepend it back
        chembl_id = chembl_id.upper()
        if chembl_id.startswith("CHEMBL"):
            chembl_id = chembl_id[6:]  # Strip prefix
        chembl_id = f"CHEMBL{chembl_id}"
        url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data.get("molecule_structures", {}).get("canonical_smiles")
        except Exception as e:
            logger.warning(f"ChEMBL {chembl_id} fetch SMILES failed: {e}")
            return None
    
    def _fetch_chebi(self, chebi_id: str) -> str | None:
        """Fetch SMILES from ChEBI."""
        # Strip CHEBI: prefix if present
        chebi_num = chebi_id.upper()
        if chebi_num.startswith("CHEBI:"):
            chebi_num = chebi_num[6:]  # Strip prefix
        url = f"https://www.ebi.ac.uk/chebi/backend/api/public/compound/{chebi_num}/"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            smiles = data.get("default_structure", {}).get("smiles")
            return smiles.strip() if smiles else None
        except Exception as e:
            logger.warning(f"ChEBI {chebi_id} fetch SMILES failed: {e}")
            return None
