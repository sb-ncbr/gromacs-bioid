"""AlphaFind structure identifier resolver."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ...config.loader import RunConfig
from ..base import IdentifierResolver, IdentifierResolutionError

logger = logging.getLogger("identifier")


class AlphaFindStructResolver(IdentifierResolver):
    """
    AlphaFindStructResolver identifies protein structures using AlphaFind structure database search.
    """

    def __init__(self, config: RunConfig) -> None:
        """
        Initialize AlphaFindStructResolver.
        
        Args:
            config: RunConfig instance.
        """
        super().__init__(config)
        
        # Set resolver metadata
        self.name = "alphafind_struct"
        self.identifier_type = "ALPHAFOLD_ID"
        self.accepted_signatures = ["pdb_protein"]
        
        self.config = config
        self.alphafind_config = config.alphafind
        
        # Set up requests session with retry logic
        self._session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create a requests session with retry configuration."""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.alphafind_config.retry_count,
            backoff_factor=self.alphafind_config.retry_delay_s,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        
        return session

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
            List of AlphaFold identifiers with 100% alignment.
        """
        # Create temp file for PDB structure
        fd, pdb_path = tempfile.mkstemp(suffix=".pdb", dir=working_directory if working_directory else tempfile.gettempdir())
        os.close(fd)
        
        try:
            with open(pdb_path, 'w') as f:
                f.write(signature)
            
            results = self._alphafind_identity(pdb_path)
            return results
        except Exception as exc:
            logger.warning(f"AlphaFind structure resolution failed: {exc}")
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
            
            results = self._alphafind_similarity(pdb_path)
            return results
        except Exception as exc:
            logger.warning(f"AlphaFind structure resolution failed: {exc}")
            return []
        finally:
            if os.path.exists(pdb_path):
                os.unlink(pdb_path)

    def _alphafind_post(self, pdb_path: str) -> dict | None:
        """
        Execute AlphaFind API request using requests library.
        
        Args:
            pdb_path: Path to PDB file.
            
        Returns:
            JSON response as dict, or None on failure.
        """
        url = self.alphafind_config.url
        timeout = self.alphafind_config.request_timeout_s
        
        logger.debug(f"AlphaFind POST to {url}")
        
        try:
            with open(pdb_path, 'rb') as f:
                files = {'file': f}
                response = self._session.post(
                    url, 
                    files=files, 
                    timeout=timeout,
                    headers={'accept': 'application/json'}
                )
                response.raise_for_status()
                return response.json()
        except requests.exceptions.Timeout:
            logger.warning(f"AlphaFind request timed out after {timeout}s")
            return None
        except requests.exceptions.RequestException as exc:
            logger.error(f"AlphaFind request failed: {exc}")
            return None
        except json.JSONDecodeError as exc:
            logger.error(f"AlphaFind response parsing failed: {exc}")
            return None

    def _alphafind_fetch_response(self, pdb_path: str) -> dict | None:
        """
        Execute AlphaFind similarity search with retry logic.
        
        Args:
            pdb_path: Path to PDB file.
            
        Returns:
            JSON response dict if successful, None on failure.
        """
        logger.debug(f"AlphaFind resolving similarity search for '{pdb_path}'")
        
        # Initial request
        response = self._alphafind_post(pdb_path)
        
        if response and 'results' in response:
            return response
        
        # Retry loop (the session already has retries, but we keep the polling behavior)
        retry_count = self.alphafind_config.retry_count
        retry_delay = self.alphafind_config.retry_delay_s
        
        for attempt in range(retry_count):
            time.sleep(retry_delay)
            logger.debug(f"AlphaFind retry attempt {attempt + 1}/{retry_count}")
            
            response = self._alphafind_post(pdb_path)
            
            if response and 'results' in response:
                return response
        
        return None

    def _alphafind_similarity(self, pdb_path: str) -> list[tuple[str, float]]:
        """
        Execute AlphaFind similarity search.
        
        Args:
            pdb_path: Path to PDB file.
            
        Returns:
            List of (AlphaFold ID, aligned_percentage) tuples.
        """
        response = self._alphafind_fetch_response(pdb_path)
        
        if response is None or 'results' not in response:
            return []

        results: list[tuple[str, float]] = []
        for entry in response['results']:
            if 'object_id' in entry and 'aligned_percentage' in entry:
                results.append((entry['object_id'], entry['aligned_percentage']))
        
        return results

    def _alphafind_identity(self, pdb_path: str) -> list[str]:
        """
        Execute AlphaFind identity search.
        
        Args:
            pdb_path: Path to PDB file.
            
        Returns:
            List of AlphaFold identifiers with 100% alignment.
        """
        similar_results = self._alphafind_similarity(pdb_path)
        
        # Filter for exact matches (100% aligned)
        identical = [
            entry_id 
            for entry_id, aligned_pct in similar_results 
            if aligned_pct == 100.0
        ]
        
        return identical
