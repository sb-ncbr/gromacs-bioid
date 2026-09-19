"""Structure signature fetcher for PDB structures."""

from __future__ import annotations

import logging

from ..base import SignatureFetcher
from . import rcsb_cache

logger = logging.getLogger(__name__)


class StructureSignatureFetcher(SignatureFetcher):
    """Fetches canonical PDB structures for structural identifiers."""
    
    SUPPORTED_TYPES = {"PDB_ID", "ALPHAFIND_ID"}
    
    def supports(self, ident_type: str) -> bool:
        """Check if this fetcher supports the given identifier type."""
        return ident_type in self.SUPPORTED_TYPES
    
    def fetch(self, identifier: str, ident_type: str) -> str | None:
        """Fetch the canonical PDB structure for a structural identifier.
        
        Args:
            identifier: The identifier (e.g., "6VXX" for PDB).
            ident_type: The type of identifier ("PDB_ID" or "ALPHAFIND_ID").
            
        Returns:
            The PDB file content as a string, or None if not found or on error.
        """
        try:
            if ident_type == "PDB_ID":
                return self._fetch_pdb(identifier)
            elif ident_type == "ALPHAFIND_ID":
                # AlphaFind hits are PDB IDs, but ALPHAFOLD_ID (different) has no deposited PDB
                # For ALPHAFOLD_ID format (AF-UNIPROTID-F1-model_vX), return None
                logger.warning(f"ALPHAFIND_ID/ALPHAFOLD_ID {identifier} has no deposited PDB structure")
                return None
            else:
                logger.warning(f"Unknown structure ident_type: {ident_type}")
                return None
        except Exception as e:
            logger.warning(f"StructureSignatureFetcher fetch failed for {identifier}: {e}")
            return None
    
    def _fetch_pdb(self, pdb_id: str) -> str | None:
        """Fetch PDB file from RCSB.
        
        Downloads the .pdb file (not .cif) since simulation signatures are PDB strings.
        Strips _entity suffix, uppercases, downloads from RCSB.
        """
        # Strip _entity suffix if present
        if '_' in pdb_id:
            pdb_id = pdb_id.split('_', maxsplit=1)[0]
        
        # Uppercase the PDB ID
        pdb_id = pdb_id.upper()
        
        url = f"https://files.rcsb.org/download/{pdb_id}.pdb"
        try:
            r = rcsb_cache.get_cached(url, timeout=30)
            if r is None:
                return None
            return r.text
        except Exception as e:
            logger.warning(f"PDB {pdb_id} fetch structure failed: {e}")
            return None
