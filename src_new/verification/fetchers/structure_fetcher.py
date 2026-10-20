"""Structure signature fetcher for PDB structures."""

from __future__ import annotations

import logging
import re

from ..base import SignatureFetcher
from . import rcsb_cache

logger = logging.getLogger(__name__)


# AFDB model-file URL template + version preference. Live evidence
# (2026-10-19, worker-pod egress): v4 URLs 404, v6 serves real models —
# walk newest-first so future version bumps keep working.
_AFDB_FILE_TPL = "https://alphafold.ebi.ac.uk/files/AF-{acc}-F1-model_v{ver}.pdb"
_AFDB_MODEL_VERSIONS = (6, 5, 4)
_AF_WRAPPED_ID_RE = re.compile(r"^AF-([A-Z0-9]+?)-F\d+-model_v\d+$", re.IGNORECASE)


def _alphafold_accession(identifier: str) -> str:
    """Normalize an AlphaFold-family identifier to a bare UniProt accession.

    AlphaFind's stage API emits raw UniProt accessions as object_id
    ("P01542"; live probe 2026-10-19); handle the wrapped
    "AF-<ACC>-F1-model_vN" form defensively too."""
    ident = identifier.strip().upper()
    m = _AF_WRAPPED_ID_RE.match(ident)
    return m.group(1) if m else ident


class StructureSignatureFetcher(SignatureFetcher):
    """Fetches canonical PDB structures for structural identifiers."""
    
    SUPPORTED_TYPES = {"PDB_ID", "ALPHAFIND_ID", "ALPHAFOLD_ID"}
    
    def supports(self, ident_type: str) -> bool:
        """Check if this fetcher supports the given identifier type."""
        return ident_type in self.SUPPORTED_TYPES
    
    def fetch(self, identifier: str, ident_type: str) -> str | None:
        """Fetch the canonical PDB structure for a structural identifier.
        
        Args:
            identifier: The identifier (e.g., "6VXX" for PDB; UniProt
                accession such as "P01542" for AlphaFold-family types).
            ident_type: The type of identifier ("PDB_ID", "ALPHAFIND_ID",
                or "ALPHAFOLD_ID").
            
        Returns:
            The PDB file content as a string, or None if not found or on error.
        """
        try:
            if ident_type == "PDB_ID":
                return self._fetch_pdb(identifier)
            elif ident_type in ("ALPHAFOLD_ID", "ALPHAFIND_ID"):
                # AlphaFind object_ids are UniProt accessions of AlphaFold DB
                # models (live stage-API evidence 2026-10-19, superseding the
                # historic "hits are PDB IDs" assumption); fetch the model
                # from AFDB. ALPHAFIND_ID kept as a legacy alias.
                return self._fetch_alphafold(identifier)
            else:
                logger.warning(f"Unknown structure ident_type: {ident_type}")
                return None
        except Exception as e:
            logger.warning(f"StructureSignatureFetcher fetch failed for {identifier}: {e}")
            return None
    
    def _fetch_alphafold(self, identifier: str) -> str | None:
        """Fetch an AlphaFold DB model PDB by UniProt accession.

        Tries model versions newest-first (v6, v5, v4); earlier versions
        already 404 for some entries, and hardcoding a single version would
        silently break on the next AFDB release bump."""
        acc = _alphafold_accession(identifier)
        for ver in _AFDB_MODEL_VERSIONS:
            url = _AFDB_FILE_TPL.format(acc=acc, ver=ver)
            try:
                r = rcsb_cache.get_cached(url, timeout=30)
            except Exception as e:
                logger.debug(f"AFDB fetch error ({url}): {e}")
                continue
            if r is None:
                continue
            status = r.status_code if isinstance(getattr(r, "status_code", None), int) else 200
            text = r.text or ""
            if status == 200 and "ATOM" in text:
                return text
        logger.warning(f"No AFDB model found for accession {acc} (tried v{_AFDB_MODEL_VERSIONS[0]}..v{_AFDB_MODEL_VERSIONS[-1]})")
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
