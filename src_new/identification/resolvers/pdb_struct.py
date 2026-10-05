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
from ..base import IdentifierResolver, IdentifierResolutionError, safe_tmp_dir
from ._ssh_upload import has_ssh_config, ssh_delete, ssh_upload

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
        fd, pdb_path = tempfile.mkstemp(suffix=".pdb", dir=safe_tmp_dir(working_directory))
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
        # F-23 containment (2026-10-04): in nucleotide mode the uploaded
        # payload is pure nucleic acid, which the protein-centric RCSB
        # structure-search backend rejects by design — HTTP 400 (proven live:
        # 1UBQ payload -> 200/464; 1BNA payload -> 400). Pre-F-23 every NA
        # entry burned an attempt and produced fake-fixable 400 spam in
        # stage_errors. Skip the call and record the declared verdict
        # `na_mode_unsupported` instead (countable, non-failure class).
        if getattr(self, "_nucleotide_mode", False):
            logger.info(
                "RCSB structure search skipped (pdb_struct): nucleotide-mode "
                "payload is rejected by design upstream; verdict=na_mode_unsupported"
            )
            self._last_error = "na_mode_unsupported"
            return []

        # Create temp file for PDB structure
        fd, pdb_path = tempfile.mkstemp(suffix=".pdb", dir=safe_tmp_dir(working_directory))
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
        Upload PDB file to remote server via SSH/SCP.
        
        Args:
            pdb_path: Path to the PDB file.
            
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
        
        public_url = ssh_upload(pdb_path, remote_subdir, config)
        return public_url

    def _delete_file(self, pdb_name: str) -> None:
        """
        Remove uploaded PDB file from remote server via SSH.
        
        Args:
            pdb_name: Name of the file to delete (actually the full remote subdir path in upload mode).
        """
        config = self.config.pdb
        
        if config.use_deployment_file_access:
            logger.debug("Using deployment file access; no delete needed")
            return
        
        if not has_ssh_config(config):
            logger.debug("SSH config not present; skipping delete")
            return
        
        # pdb_name in upload mode is the full URL; extract subdir and filename
        # Format: {ssh_public_url}/{uuid}/input/{filename}
        base_url = config.ssh_public_url.rstrip('/')
        if pdb_name.startswith(base_url):
            relative_path = pdb_name[len(base_url):].lstrip('/')
            # relative_path is like "{uuid}/input/{filename}"
            parts = relative_path.split('/')
            if len(parts) >= 3:
                remote_subdir = '/'.join(parts[:-1])
                filename = parts[-1]
                ssh_delete(remote_subdir, filename, config)
            else:
                logger.warning(f"Cannot parse remote path from URL: {pdb_name}")
        else:
            logger.debug(f"Delete not applicable for '{pdb_name}'")

    def _fetch_pdb_similarity(self, remote_path: str, entity_types: list[str]) -> dict:
        """
        Execute RCSB structural similarity search.
        
        Args:
            remote_path: URL or path to the PDB file.
            entity_types: Values for the selected_polymer_entity_types filter
                (e.g. ["Protein (only)"], or ["Protein/NA"] for the F-24
                additive mixed-complex query).
            
        Returns:
            JSON response from RCSB API.
            
        Raises:
            IdentifierResolutionError: On request failure.
        """
        url = "https://search.rcsb.org/rcsbsearch/v2/query"

        required_entity_type = entity_types
        
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
                            "value": required_entity_type
                        }
                    }
                ]
            },
            "return_type": "entry",
            # F-25: without request_options/paginate, RCSB v2 silently returns
            # only the default 10 rows regardless of number_of_candidates
            # (probed live 2026-10-04: same query -> (464 total, 10 rows) vs
            # (464 total, 100 rows) with rows=100). Match the 10000-candidate
            # intent; the parser reads the whole result_set.
            "request_options": {
                "paginate": {
                    "start": 0,
                    "rows": 10000
                }
            }
        }

        logger.info("RCSB structure search request: similarity_type=local target_search_space=assembly, paginated rows=10000")
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
            remote_path = self._upload_file(pdb_path)
            if remote_path is None:
                logger.warning("PDB upload not available and deployment file access disabled; skipping search")
                return []
            logger.info(f"PDB upload mode remote_path: {remote_path}")

        base_type = "Protein (only)" if self._protein_mode else "Nucleic acid (only)"
        response = self._fetch_pdb_similarity(remote_path, [base_type])
        similar_structures = self._parse_pdb_response(response)

        # F-24 (2026-10-05, audit): additive mixed-complex channel. When the
        # flag is ON, query the "Protein/NA" entity class as an EXTRA call and
        # APPEND unique hits — the base list above is never modified
        # (additive-invariant; flag default OFF => identical legacy output).
        if getattr(self.config.pdb, "rcsb_include_mixed_complexes", False):
            try:
                addon_response = self._fetch_pdb_similarity(remote_path, ["Protein/NA"])
                addon_hits = self._parse_pdb_response(addon_response)
                seen = {identifier for identifier, _ in similar_structures}
                added = 0
                for identifier, score in addon_hits:
                    if identifier not in seen:
                        similar_structures.append((identifier, score))
                        seen.add(identifier)
                        added += 1
                logger.info(f"F-24 additive Protein/NA query: {len(addon_hits)} hits ({added} new) appended")
            except IdentifierResolutionError as exc:
                # Addon failure must not degrade the base channel
                logger.warning(f"F-24 additive Protein/NA query failed (base results kept): {exc}")

        if not deployment_file_access and remote_path:
            self._delete_file(remote_path)

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
