"""PDB structure identifier resolver using RCSB Search API."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile

import requests
from requests import Response

from ...config.loader import RunConfig
from ..base import IdentifierResolver, IdentifierResolutionError

logger = logging.getLogger("identifier")


class PDBStructResolver(IdentifierResolver):
    """
    PDBStructResolver identifies protein/nucleic acid structures using PDB structure database search.
    """

    def __init__(self, config: RunConfig, as_protein: bool, as_nucleotide: bool) -> None:
        """
        Initialize PDBStructResolver.
        
        Args:
            config: RunConfig instance.
            as_protein: True for protein mode.
            as_nucleotide: True for nucleotide mode.
        """
        super().__init__(config)
        assert as_protein or as_nucleotide, "One mode of operation is necessary"
        
        self._protein_mode = as_protein
        self._nucleotide_mode = as_nucleotide
        
        # Set resolver metadata
        self.name = "pdb_struct_protein" if as_protein else "pdb_struct_nucleotide"
        self.identifier_type = "PDB_ID"
        self.accepted_signatures = ["pdb_protein" if as_protein else "pdb_nucleic", "topology_less_pdb"]
        
        self.config = config

    def _is_applicable(self, signature: str) -> bool:
        """
        Check if signature is applicable (assumes PDB output is valid).
        
        Args:
            signature: The signature string to check.
            
        Returns:
            True (always applicable for valid PDB signatures).
        """
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """
        Resolve signature to exact-match identifiers.
        
        Args:
            signature: PDB structure string.
            working_directory: Working directory for operations.
            
        Returns:
            List of PDB identifiers with >= 99.9% similarity.
        """
        # Create temp file for PDB structure
        fd, pdb_path = tempfile.mkstemp(suffix=".pdb", dir=working_directory if working_directory else tempfile.gettempdir())
        os.close(fd)
        
        try:
            with open(pdb_path, 'w') as f:
                f.write(signature)
            
            deployment_file_access = self.config.pdb.use_deployment_file_access
            
            results = self._pdb_fetch_identical_structures(pdb_path, deployment_file_access)
            return results
        except Exception as exc:
            logger.warning(f"PDB structure resolution failed: {exc}")
            return []
        finally:
            if os.path.exists(pdb_path):
                os.unlink(pdb_path)

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """
        Resolve signature to similar identifiers.
        
        Args:
            signature: PDB structure string.
            working_directory: Working directory for operations.
            
        Returns:
            List of (identifier, similarity_score) tuples.
        """
        # Create temp file for PDB structure
        fd, pdb_path = tempfile.mkstemp(suffix=".pdb", dir=working_directory if working_directory else tempfile.gettempdir())
        os.close(fd)
        
        try:
            with open(pdb_path, 'w') as f:
                f.write(signature)
            
            deployment_file_access = self.config.pdb.use_deployment_file_access
            
            results = self._pdb_fetch_similar_structures(pdb_path, deployment_file_access)
            return results
        except Exception as exc:
            logger.warning(f"PDB structure resolution failed: {exc}")
            return []
        finally:
            if os.path.exists(pdb_path):
                os.unlink(pdb_path)

    def _upload_file(self, pdb_path: str) -> str | None:
        """
        Upload PDB file to remote server (placeholder).
        
        Args:
            pdb_path: Path to the PDB file.
            
        Returns:
            None (upload not implemented in this deployment).
        """
        pdb_name = os.path.basename(pdb_path)
        logger.debug(f"Upload not available for '{pdb_name}'")
        return None

    def _delete_file(self, pdb_name: str) -> None:
        """
        Remove uploaded PDB file from remote server (no-op).
        
        Args:
            pdb_name: Name of the file to delete.
        """
        logger.debug(f"Delete not available for '{pdb_name}'")

    def _fetch_pdb_similarity(self, remote_path: str, as_protein: bool, as_nucleic: bool) -> dict:
        """
        Execute RCSB structural similarity search.
        
        Args:
            remote_path: URL or path to the PDB file.
            as_protein: Search protein entries.
            as_nucleic: Search nucleic acid entries.
            
        Returns:
            JSON response from RCSB API.
            
        Raises:
            IdentifierResolutionError: On request failure.
        """
        url = "https://search.rcsb.org/rcsbsearch/v2/query"
        
        required_entity_type = "Protein (only)" if as_protein else "Nucleic acid (only)"
        
        request = {
            "query": {
                "type": "group",
                "logical_operator": "and",
                "nodes": [
                    {
                        "type": "terminal",
                        "service": "structure",
                        "parameters": {
                            "value": {"url": remote_path, "format": "pdb"},
                            "similarity_type": "local",
                            "target_search_space": "assembly",
                            "number_of_candidates": 10000
                        }
                    },
                    {
                        "type": "terminal",
                        "service": "text",
                        "parameters": {
                            "attribute": "rcsb_entry_info.selected_polymer_entity_types",
                            "operator": "in",
                            "value": [required_entity_type]
                        }
                    }
                ]
            },
            "return_type": "entry"
        }

        logger.info("RCSB structure search request: similarity_type=local target_search_space=assembly")
        logger.debug(f"Querying RCSB API for '{remote_path}'")
        
        try:
            response: Response = requests.post(url, json=request, headers={"Content-Type": "application/json"}, timeout=30)
            response.raise_for_status()
            response_json: dict = response.json()
            return response_json
        except requests.exceptions.Timeout:
            raise IdentifierResolutionError("RCSB API request timed out")
        except requests.exceptions.RequestException as exc:
            raise IdentifierResolutionError(f"RCSB API request failed: {exc}")

    def _parse_pdb_response(self, response: dict) -> list[tuple[str, float]]:
        """
        Parse RCSB similarity search response.
        
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

    def _pdb_fetch_similar_structures(self, pdb_path: str, deployment_file_access: bool) -> list[tuple[str, float]]:
        """
        Execute remote PDB similarity search.
        
        Args:
            pdb_path: Path to local PDB file.
            deployment_file_access: If True, file is accessible via API without upload.
            
        Returns:
            List of (PDB ID, similarity percentage) tuples.
        """
        logger.debug(f"Resolving PDB similarity search for '{pdb_path}'")

        if deployment_file_access:
            filename = os.path.basename(pdb_path)
            uuid = self.config.pdb.curr_uuid
            if not uuid:
                logger.warning("PDB query skipped: curr_uuid is empty")
                return []
            base = self.config.pdb.deployment_file_url.rstrip('/')
            remote_path = f"{base}/files/{uuid}/input/{filename}"
            logger.info(f"PDB query remote_path: {remote_path}")
        else:
            filename = self._upload_file(pdb_path)
            if filename is None:
                logger.warning("PDB upload not available and deployment file access disabled; skipping search")
                return []
            # Construct remote URL from config (upload mode not fully implemented)
            logger.warning("Upload mode not fully implemented; skipping search")
            return []

        response = self._fetch_pdb_similarity(remote_path, self._protein_mode, self._nucleotide_mode)
        similar_structures = self._parse_pdb_response(response)
        
        if not deployment_file_access and filename:
            self._delete_file(filename)
        
        return similar_structures

    def _pdb_fetch_identical_structures(self, pdb_path: str, deployment_file_access: bool) -> list[str]:
        """
        Execute remote PDB identity search.
        
        Args:
            pdb_path: Path to local PDB file.
            deployment_file_access: If True, file is accessible via API without upload.
            
        Returns:
            List of PDB identifiers with >= 99.9% similarity.
        """
        logger.debug(f"Resolving PDB identity search for '{pdb_path}'")
        
        similar_results = self._pdb_fetch_similar_structures(pdb_path, deployment_file_access)
        
        # Use >= 99.9 tolerance instead of exact == 100 float equality
        identical = [
            pdb_id
            for pdb_id, similarity in similar_results
            if similarity >= 99.9
        ]
        
        return identical


class PDBStructResolverProtein(PDBStructResolver):
    """PDB structure resolver for protein structures."""
    
    def __init__(self, config: RunConfig) -> None:
        """Initialize PDB structure resolver for proteins."""
        super().__init__(config, as_protein=True, as_nucleotide=False)


class PDBStructResolverNucleotide(PDBStructResolver):
    """PDB structure resolver for nucleotide structures."""
    
    def __init__(self, config: RunConfig) -> None:
        """Initialize PDB structure resolver for nucleotides."""
        super().__init__(config, as_protein=False, as_nucleotide=True)
