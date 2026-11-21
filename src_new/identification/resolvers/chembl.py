"""ChEMBL identifier resolver with structural search."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from ..base import IdentifierResolver, IdentifierResolutionError
from ._smiles_query import query_smiles, refusal

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
            # 2, not 10: ChEMBL's API answers 500 in bursts, and 10 retries of
            # a 10 s timeout cost a run over a minute per search
            Settings.Instance().TOTAL_RETRIES = 2
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
        # v3.143 (red-team C-17): RETIRED — Tanimoto 1.0 is not identity
        # (see idsm.py note; exact matches remain available as similarity=100).
        logger.debug("ChEMBL identity lookup retired (Tanimoto 1.0 is not identity, C-17)")
        return []

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
        # 2026-11-21 (mdval audit item 6): an impossible valence is declined
        # here (ChEMBL answered HTTP 500, which counted as an outage)
        reason = refusal(smiles)
        if reason:
            logger.info(f"{self.name}: query declined ({reason})")
            self._last_error = reason
            return []
        threshold = self.config.chembl.similarity_threshold
        return chembl_fetch_similarity_match(smiles, threshold=threshold, include_similarity=True,
                                             give_up=self._over_budget)

    def _decode_selfies(self, signature: str) -> str:
        """Decode SELFIES to SMILES if signature is SELFIES.

        Args:
            signature: SMILES or SELFIES string.

        Returns:
            SMILES string.
        """
        # 2026-11-21 (mdval audit item 6): by the signature type
        return query_smiles(signature, getattr(self, "_signature_type", None))


import urllib.parse

from ... import http_retry


def chembl_fetch_similarity_match(
    smiles: str,
    threshold: int,
    include_similarity: bool = False,
    give_up=None,
) -> list[str] | list[tuple[str, float]]:
    """Search ChEMBL for similarity matches of SMILES.

    Args:
        smiles: SMILES string to search.
        threshold: Similarity threshold (0-100, 100 = identity).
        include_similarity: If True, return (id, score) tuples; else just IDs.
        give_up: Optional callable; True stops the REST fallback's retries
            (the stage budget ran out).

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
        
        # 2026-11-21 (mdval audit item 6): requests with retries
        # (http_retry) instead of one urllib attempt; counted by
        # service_stats like every requests call.
        response = http_retry.request(
            "GET", url, headers={"Accept": "application/json"}, timeout=30, give_up=give_up)
        if response.status_code >= 400:
            raise IdentifierResolutionError(
                f"HTTP {response.status_code}: {http_retry.body_excerpt(response)}")
        data = response.json()
        
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
