"""mmCIF structure identifier resolver using RCSB Search API."""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile

import requests

from ...config.loader import RunConfig
from ..base import IdentifierResolver, IdentifierResolutionError, safe_tmp_dir
from ._ssh_upload import has_ssh_config, ssh_delete, ssh_upload

logger = logging.getLogger("identifier")

# F-23 containment support: classify pure-NA mmCIF payloads (which the
# protein-centric RCSB structure-search backend rejects by design, HTTP 400).
_NA_POLYMER_PREFIXES = (
    "polydeoxyribonucleotide",  # also matches the ".../polyribonucleotide hybrid" token prefix
    "polyribonucleotide",
)
_ENTITY_POLY_TYPE_RE = re.compile(r"_entity_poly\.type\s+['\"]?([^'\"\s;]+)")


# Stage-2 residues for header-less coordinate content (F-23, live evidence:
# our own generator emits a minimal 8-column _atom_site loop where
# _entity_poly.type lines are absent, so polymer-type detection alone
# under-fires).
_AMINO_RESNAMES = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
    "MSE", "SEC", "PYL", "HYP",
}
_NA_RESNAMES = {
    "A", "C", "G", "U", "I", "DA", "DC", "DG", "DT", "DU", "DI",
    "PSU", "5MU", "OMC", "OMG", "1MA", "6MZ", "7MG", "2MG",
}


def _resname_token_sets(text: str) -> tuple[set[str], set[str]]:
    """Collect amino-acid vs nucleic residue names from ATOM/HETATM rows.

    Only active for the minimal generated format (header declares
    _atom_site.label_comp_id at token index 3); anything else returns
    empty sets and the caller falls back to unclassified."""
    if "_atom_site.label_comp_id" not in text:
        return set(), set()
    amino, na = set(), set()
    for line in text.splitlines():
        if not line.startswith(("ATOM", "HETATM")):
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        comp = parts[3].strip().strip("'\"").upper()
        if comp in _AMINO_RESNAMES:
            amino.add(comp)
        elif comp in _NA_RESNAMES:
            na.add(comp)
    return amino, na


def _na_only_mmcif_payload(text: str) -> bool:
    """True when the mmCIF text contains nucleic-acid polymer entities and
    NO polypeptide/protein content (i.e. a payload class the protein-centric
    RCSB backend cannot process). Unclassifiable text returns False (server
    decides, preserving pre-F-23 behavior).

    Stage 1: _entity_poly.type polymer classes (full mmCIF files).
    Stage 2: residue-name scan of ATOM records (trimmed signatures)."""
    types = set()
    for match in _ENTITY_POLY_TYPE_RE.finditer(text):
        tok = match.group(1).rstrip("'\"").lower()
        types.add(tok)
    if types:
        has_protein = any(t.startswith("polypeptide") for t in types)
        has_na = any(any(t.startswith(p) for p in _NA_POLYMER_PREFIXES) for t in types)
        return has_na and not has_protein
    amino, na = _resname_token_sets(text)
    if amino or na:
        return len(na) > 0 and len(amino) == 0
    return False


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
        # F-23 containment (2026-10-04): this resolver has no composition
        # filter, so pure-NA payloads reach RCSB and are rejected by design
        # (HTTP 400; pre-F-23 this produced fake-fixable 400 spam in
        # stage_errors, e.g. 1,691 zero-hit NA attempts). Skip the call and
        # record the declared verdict `na_mode_unsupported` (countable,
        # non-failure class). Mixed protein+NA payloads still go through —
        # the protein-centric engine can process the protein part.
        if _na_only_mmcif_payload(signature):
            logger.info(
                "RCSB structure search skipped (mmcif): pure-NA payload is "
                "rejected by design upstream; verdict=na_mode_unsupported"
            )
            self._last_error = "na_mode_unsupported"
            return []

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
