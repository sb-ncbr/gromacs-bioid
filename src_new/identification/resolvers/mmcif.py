"""mmCIF structure identifier resolver using RCSB Search API."""

from __future__ import annotations

import json
import logging
import os
import tempfile

import requests

from ...config.loader import RunConfig
from ..base import IdentifierResolver, IdentifierResolutionError, safe_tmp_dir
from ._ssh_upload import has_ssh_config, ssh_delete, ssh_upload

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
        fd, cif_path = tempfile.mkstemp(suffix=".cif", dir=safe_tmp_dir(working_directory))
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
        Upload mmCIF file to remote server via SSH/SCP.
        
        Args:
            cif_path: Path to mmCIF file.
            
        Returns:
            Public URL to the uploaded file, or None if upload failed.
        """
        config = self.config.pdb
        
        if config.use_deployment_file_access:
            logger.debug("Using deployment file access; no upload needed")
            return None
        
        if not has_ssh_config(config):
            logger.debug("SSH config not present; cannot upload")
            return None
        
        # Use curr_uuid for remote subdir, or generate a temp one
        uuid = config.curr_uuid or "temp"
        remote_subdir = f"{uuid}/input"
        
        public_url = ssh_upload(cif_path, remote_subdir, config)
        return public_url

    def _delete_cif_file(self, remote_url: str) -> None:
        """
        Remove uploaded mmCIF file from remote server via SSH.
        
        Args:
            remote_url: URL of the file to delete.
        """
        config = self.config.pdb
        
        if config.use_deployment_file_access:
            logger.debug("Using deployment file access; no delete needed")
            return
        
        if not has_ssh_config(config):
            logger.debug("SSH config not present; skipping delete")
            return
        
        # remote_url format: {ssh_public_url}/{uuid}/input/{filename}
        base_url = config.ssh_public_url.rstrip('/')
        if remote_url.startswith(base_url):
            relative_path = remote_url[len(base_url):].lstrip('/')
            parts = relative_path.split('/')
            if len(parts) >= 3:
                remote_subdir = '/'.join(parts[:-1])
                filename = parts[-1]
                ssh_delete(remote_subdir, filename, config)
            else:
                logger.warning(f"Cannot parse remote path from URL: {remote_url}")
        else:
            logger.debug(f"Delete not applicable for '{remote_url}'")

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
            # Upload mode via SSH
            remote_path = self._upload_cif_file(cif_path)
            if remote_path is None:
                logger.warning("mmCIF upload not available and deployment file access disabled; skipping search")
                return []
            logger.info(f"mmCIF upload mode remote_path: {remote_path}")
            
            # Fetch similar structures
            response = self._fetch_mmcif_similarity(remote_path)
            results = self._parse_mmcif_response(response)
            
            # Clean up uploaded file
            self._delete_cif_file(remote_path)
            
            return results
