"""mmCIF structure identifier resolver using RCSB Search API."""

from __future__ import annotations

import json
import logging
import os
import tempfile

import requests

from ...config.loader import RunConfig
from ..base import IdentifierResolver, IdentifierResolutionError

logger = logging.getLogger("identifier")


class MmCifResolver(IdentifierResolver):
    """
    MmCifResolver identifies structures using mmCIF format via RCSB Search API.
    """

    def __init__(self, config: RunConfig) -> None:
        """
        Initialize MmCifResolver.
        
        Args:
            config: RunConfig instance.
        """
        super().__init__(config)
        
        # Set resolver metadata
        self.name = "mmcif_struct"
        self.identifier_type = "PDB_ID"
        self.accepted_signatures = ["mmcif"]
        
        self.config = config

    def _is_applicable(self, signature: str) -> bool:
        """
        Check if signature is a valid mmCIF string.
        
        Args:
            signature: The mmCIF string to check.
            
        Returns:
            True if applicable, False otherwise.
        """
        if not signature or len(signature.strip()) == 0:
            return False
        
        # Basic validation: mmCIF files typically start with data_ or have specific markers
        # For now, just check non-empty
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """
        Resolve signature to exact-match identifiers.
        
        Not practical for exact match; returns empty list.
        
        Args:
            signature: mmCIF structure string.
            working_directory: Working directory for operations.
            
        Returns:
            Empty list (exact match not practical for structure search).
        """
        logger.debug(f"MmCif identity search not implemented")
        return []

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """
        Resolve signature to similar identifiers using RCSB structure search.
        
        Args:
            signature: mmCIF structure string.
            working_directory: Working directory for operations.
            
        Returns:
            List of (PDB ID, score*100) tuples.
        """
        # Create temp file for mmCIF structure
        fd, cif_path = tempfile.mkstemp(suffix=".cif", dir=working_directory if working_directory else tempfile.gettempdir())
        os.close(fd)
        
        try:
            with open(cif_path, 'w') as f:
                f.write(signature)
            
            results = self._mmcif_similarity_search(cif_path)
            return results
        except Exception as exc:
            logger.warning(f"MmCif structure resolution failed: {exc}")
            return []
        finally:
            if os.path.exists(cif_path):
                os.unlink(cif_path)

    def _upload_cif_file(self, cif_path: str) -> str | None:
        """
        Upload mmCIF file to make it accessible via URL (placeholder).
        
        Args:
            cif_path: Path to mmCIF file.
            
        Returns:
            None (upload not implemented in this deployment).
        """
        cif_name = os.path.basename(cif_path)
        logger.debug(f"Upload not available for mmCIF file '{cif_name}'")
        return None

    def _fetch_mmcif_similarity(self, remote_path: str) -> dict:
        """
        Execute RCSB structural similarity search for mmCIF file.
        
        Args:
            remote_path: URL to the mmCIF file.
            
        Returns:
            JSON response from RCSB API.
            
        Raises:
            IdentifierResolutionError: On request failure.
        """
        url = "https://search.rcsb.org/rcsbsearch/v2/query"
        
        request = {
            "query": {
                "type": "group",
                "logical_operator": "and",
                "nodes": [
                    {
                        "type": "terminal",
                        "service": "structure",
                        "parameters": {
                            "value": {
                                "url": remote_path,
                                "format": "cif"
                            },
                            "similarity_type": "local",
                            "target_search_space": "assembly",
                            "number_of_candidates": 10000
                        }
                    }
                ]
            },
            "return_type": "entry"
        }

        logger.info("RCSB structure search request: similarity_type=local target_search_space=assembly")
        logger.debug(f"Querying RCSB API for mmCIF structure '{remote_path}'")
        
        try:
            response = requests.post(url, json=request, headers={"Content-Type": "application/json"}, timeout=30)
            response.raise_for_status()
            response_json: dict = response.json()
            return response_json
        except requests.exceptions.Timeout:
            raise IdentifierResolutionError("RCSB API request timed out")
        except requests.exceptions.RequestException as exc:
            raise IdentifierResolutionError(f"RCSB API request failed: {exc}")

    def _parse_mmcif_response(self, response: dict) -> list[tuple[str, float]]:
        """
        Parse RCSB similarity search response for mmCIF.
        
        Args:
            response: Response from RCSB API.
            
        Returns:
            List of (identifier, score*100) tuples.
        """
        if "result_set" not in response:
            return []

        results: list[tuple[str, float]] = []
        for hit in response["result_set"]:
            identifier = hit.get("identifier", "")
            score = hit.get("score", 0.0)
            results.append((identifier, score * 100))
        
        return results

    def _mmcif_similarity_search(self, cif_path: str) -> list[tuple[str, float]]:
        """
        Execute complete mmCIF similarity search workflow.
        
        Args:
            cif_path: Path to mmCIF file.
            
        Returns:
            List of (PDB ID, similarity percentage) tuples.
        """
        logger.debug(f"Resolving mmCIF similarity search for '{cif_path}'")
        
        # Check if deployment file access is enabled
        if self.config.pdb.use_deployment_file_access:
            filename = os.path.basename(cif_path)
            uuid = self.config.pdb.curr_uuid
            if not uuid:
                logger.warning("mmCIF query skipped: curr_uuid is empty")
                return []
            base = self.config.pdb.deployment_file_url.rstrip('/')
            remote_path = f"{base}/files/{uuid}/input/{filename}"
            logger.info(f"mmCIF query remote_path: {remote_path}")
            
            # Fetch similar structures
            response = self._fetch_mmcif_similarity(remote_path)
            return self._parse_mmcif_response(response)
        else:
            # Upload mode not implemented; return empty results gracefully
            logger.warning("mmCIF upload mode not implemented and deployment file access disabled; skipping search")
            return []
