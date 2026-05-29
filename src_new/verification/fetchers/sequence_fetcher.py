"""Sequence signature fetcher for proteins and nucleic acids."""

from __future__ import annotations

import logging
import requests

from ..base import SignatureFetcher

logger = logging.getLogger(__name__)


class SequenceSignatureFetcher(SignatureFetcher):
    """Fetches canonical sequences for protein/nucleic acid identifiers."""
    
    SUPPORTED_TYPES = {"PDB_ID", "UNIPROT_ID", "ALPHAFOLD_ID"}
    
    def supports(self, ident_type: str) -> bool:
        """Check if this fetcher supports the given identifier type."""
        return ident_type in self.SUPPORTED_TYPES
    
    def fetch(self, identifier: str, ident_type: str) -> str | None:
        """Fetch the canonical sequence for a protein/nucleic acid identifier.
        
        Args:
            identifier: The identifier (e.g., "1ABC" for PDB, "P04637" for UniProt).
            ident_type: The type of identifier ("PDB_ID", "UNIPROT_ID", or "ALPHAFOLD_ID").
            
        Returns:
            The canonical sequence string (no newlines), or None if not found or on error.
        """
        try:
            if ident_type == "PDB_ID":
                return self._fetch_pdb(identifier)
            elif ident_type == "UNIPROT_ID":
                return self._fetch_uniprot(identifier)
            elif ident_type == "ALPHAFOLD_ID":
                return self._fetch_alphafold(identifier)
            else:
                logger.warning(f"Unknown sequence ident_type: {ident_type}")
                return None
        except Exception as e:
            logger.warning(f"SequenceSignatureFetcher fetch failed for {identifier}: {e}")
            return None
    
    def _fetch_pdb(self, pdb_id: str) -> str | None:
        """Fetch sequence from PDB."""
        # Strip _entity suffix if present
        if '_' in pdb_id:
            pdb_id = pdb_id.split('_', maxsplit=1)[0]
        
        url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id.lower()}/1"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            seq = data.get("entity_poly", {}).get("pdbx_seq_one_letter_code_can")
            if seq:
                return seq.replace("\n", "")
            return None
        except Exception as e:
            logger.warning(f"PDB {pdb_id} fetch sequence failed: {e}")
            return None
    
    def _fetch_uniprot(self, uniprot_id: str) -> str | None:
        """Fetch sequence from UniProt."""
        url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            lines = r.text.splitlines()
            # Skip header lines (starting with '>') and join sequence lines
            seq = ''.join(line.strip() for line in lines if not line.startswith('>'))
            return seq if seq else None
        except Exception as e:
            logger.warning(f"UniProt {uniprot_id} fetch FASTA failed: {e}")
            return None
    
    def _fetch_alphafold(self, alphafold_id: str) -> str | None:
        """Fetch sequence from AlphaFold (via UniProt)."""
        try:
            # Extract UniProt ID from AlphaFold ID (format: AF-UNIPROTID-F1-model_vX)
            uniprot_id = alphafold_id.split('-')[1]
            return self._fetch_uniprot(uniprot_id)
        except Exception as e:
            logger.warning(f"AlphaFold {alphafold_id} fetch FASTA failed: {e}")
            return None
