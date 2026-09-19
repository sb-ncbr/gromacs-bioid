"""ChEMBL identifier resolver with structural search."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from ..base import IdentifierResolver, IdentifierResolutionError

if TYPE_CHECKING:
    from ...config.loader import RunConfig

logger = logging.getLogger("identifier")


class ChemblResolver(IdentifierResolver):
    """Resolver for SMILES/SELFIES signatures using ChEMBL structural search."""

    name = "chembl_struct"
    identifier_type = "CHEMBL_ID"
    accepted_signatures = ["smiles", "selfies"]

    def __init__(self, config: RunConfig) -> None:
        """Initialize ChEMBL resolver with configuration.

        Args:
            config: RunConfig instance containing chembl settings.
        """
        super().__init__(config)
        # Fix: Move settings mutation to __init__ instead of module level
        try:
            from chembl_webresource_client.settings import Settings
            Settings.Instance().TIMEOUT = 10
            Settings.Instance().CACHING = False
            Settings.Instance().TOTAL_RETRIES = 10
        except ImportError:
            logger.warning("chembl_webresource_client not installed; resolver will fail at runtime")

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature is applicable for ChEMBL search.

        Args:
            signature: The signature string to check.

        Returns:
            True (assumes valid SMILES/SELFIES from signature generator).
        """
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve SMILES/SELFIES to exact-match ChEMBL IDs.

        Args:
            signature: SMILES or SELFIES string to resolve.
            working_directory: Unused.

        Returns:
            List of ChEMBL ID strings (without "CHEMBL" prefix).

        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        # Decode SELFIES to SMILES if needed
        smiles = self._decode_selfies(signature)
        # Identity = 100% similarity
        return chembl_fetch_similarity_match(smiles, threshold=100, include_similarity=False)

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve SMILES/SELFIES to similar ChEMBL IDs.

        Args:
            signature: SMILES or SELFIES string to resolve.
            working_directory: Unused.

        Returns:
            List of (ChEMBL_ID, similarity_score) tuples.

        Raises:
            IdentifierResolutionError: If resolution fails (no results is OK).
        """
        # Decode SELFIES to SMILES if needed
        smiles = self._decode_selfies(signature)
        threshold = self.config.chembl.similarity_threshold
        return chembl_fetch_similarity_match(smiles, threshold=threshold, include_similarity=True)

    def _decode_selfies(self, signature: str) -> str:
        """Decode SELFIES to SMILES if signature is SELFIES.

        Args:
            signature: SMILES or SELFIES string.

        Returns:
            SMILES string.
        """
        # Check if this looks like SELFIES (contains [C], [O], etc.)
        if "[" in signature and "]" in signature:
            try:
                import selfies
                return selfies.decoder(signature)
            except ImportError:
                logger.warning("selfies package not installed; treating as SMILES")
            except Exception as exc:
                logger.warning(f"SELFIES decode failed: {exc}; treating as SMILES")
        return signature


import json
import urllib.parse
import urllib.request


def chembl_fetch_similarity_match(
    smiles: str,
    threshold: int,
    include_similarity: bool = False,
) -> list[str] | list[tuple[str, float]]:
    """Search ChEMBL for similarity matches of SMILES.

    Args:
        smiles: SMILES string to search.
        threshold: Similarity threshold (0-100, 100 = identity).
        include_similarity: If True, return (id, score) tuples; else just IDs.

    Returns:
        List of ChEMBL ID strings (without "CHEMBL" prefix) or (id, score) tuples.

    Raises:
        IdentifierResolutionError: On ChEMBL search failure.
    """
    # Try the chembl_webresource_client first
    try:
        from chembl_webresource_client.new_client import new_client

        results: list[str] | list[tuple[str, float]] = []
        similarity = new_client.similarity
        records = similarity.filter(smiles=smiles, similarity=threshold).only(
            ["molecule_chembl_id", "similarity"]
        )

        for record in records:
            if (
                "similarity" not in record
                or "molecule_chembl_id" not in record
                or "CHEMBL" not in record["molecule_chembl_id"]
            ):
                continue

            score: float = record["similarity"]
            # Fix: Robust ChEMBL ID parsing (old code used .split("CHEMBL")[1])
            chembl_id: str = record["molecule_chembl_id"].replace("CHEMBL", "", 1)

            if include_similarity:
                results.append((chembl_id, score))
            else:
                results.append(chembl_id)

        return results
    except ImportError:
        logger.debug("chembl_webresource_client not available; falling back to REST API")
    except Exception as exc:
        logger.debug(f"chembl_webresource_client failed: {exc}; falling back to REST API")
    
    # Fallback to direct ChEMBL REST API
    try:
        # URL-encode the SMILES string
        encoded_smiles = urllib.parse.quote(smiles, safe='')
        url = f"https://www.ebi.ac.uk/chembl/api/data/similarity/{encoded_smiles}/{threshold}.json?only=molecule_chembl_id,similarity&limit=100"
        
        logger.debug(f"Querying ChEMBL REST API: {url}")
        
        req = urllib.request.Request(url)
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        results: list[str] | list[tuple[str, float]] = []
        molecules = data.get('molecules', [])
        
        for mol in molecules:
            chembl_id_raw = mol.get('molecule_chembl_id', '')
            similarity_score = mol.get('similarity', 0.0)
            
            if not chembl_id_raw or 'CHEMBL' not in chembl_id_raw:
                continue
            
            # Parse ChEMBL ID by removing the "CHEMBL" prefix
            chembl_id = chembl_id_raw.replace("CHEMBL", "", 1)
            
            if include_similarity:
                results.append((chembl_id, float(similarity_score)))
            else:
                results.append(chembl_id)
        
        return results
    except Exception as exc:
        raise IdentifierResolutionError(f"[Identifier] CHEMBL searching failed (client and REST API): {exc}")
