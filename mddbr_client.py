"""MDDBR API client for fetching project data."""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from config import MDDBR_API_BASE

# Fix #1: Define MDDBR_TIMEOUT constant
MDDBR_TIMEOUT = 30  # seconds

logger = logging.getLogger(__name__)


class MddbrClient:
    """Client for MDDBR API with pagination and rate limiting support."""

    def __init__(self, api_base: str = MDDBR_API_BASE, rate_limit_delay: float = 1.0):
        """
        Initialize MDDBR client.

        Args:
            api_base: Base URL for MDDBR API.
            rate_limit_delay: Delay between requests in seconds for rate limiting.
        """
        self.api_base = api_base.rstrip("/")
        self.rate_limit_delay = rate_limit_delay
        self._last_request_time: float = 0

    def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        if self._last_request_time > 0:
            elapsed = time.time() - self._last_request_time
            if elapsed < self.rate_limit_delay:
                sleep_time = self.rate_limit_delay - elapsed
                time.sleep(sleep_time)
        self._last_request_time = time.time()

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> requests.Response:
        """Make an HTTP request with rate limiting."""
        self._rate_limit()
        url = f"{self.api_base}/{endpoint.lstrip('/')}"
        logger.debug(f"MDDBR API request: {method} {url}")
        response = requests.request(method, url, timeout=30, **kwargs)
        response.raise_for_status()
        return response

    def list_projects(
        self,
        limit: int = 100,
        page: int = 1,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch project listing from MDDBR.

        Args:
            limit: Maximum number of projects to return.
            page: Page number for pagination.
            status: Optional status filter.

        Returns:
            Dict with project data and pagination info.
        """
        params = {"limit": limit, "page": page}
        if status:
            params["status"] = status

        response = self._request("GET", "/projects", params=params)
        return response.json()

    def get_references(self, local_accession: str) -> List[Dict[str, Any]]:
        """
        Fetch references for a project.

        Args:
            local_accession: The project's local accession identifier.

        Returns:
            List of reference dictionaries.
        """
        endpoint = f"/projects/{local_accession}/references"
        response = self._request("GET", endpoint)
        data = response.json()
        return data.get("references", []) if isinstance(data, dict) else data

    def get_filenotes(self, local_accession: str) -> List[Dict[str, Any]]:
        """
        Fetch file metadata (filenotes) for a project.

        Args:
            local_accession: The project's local accession identifier.

        Returns:
            List of filenote dictionaries.
        """
        endpoint = f"/projects/{local_accession}/filenotes"
        response = self._request("GET", endpoint)
        data = response.json()
        return data if isinstance(data, list) else data.get("filenotes", [])

    def get_project(self, local_accession: str) -> Dict[str, Any]:
        """
        Fetch project metadata.

        Args:
            local_accession: The project's local accession identifier.

        Returns:
            Dict with project metadata.
        """
        endpoint = f"/projects/{local_accession}"
        response = self._request("GET", endpoint)
        return response.json()

    def download_file(self, url: str, dest_path: str) -> Path:
        """
        Download a file from a URL.

        Args:
            url: URL to download from.
            dest_path: Destination file path.

        Returns:
            Path to the downloaded file.
        """
        dest = Path(dest_path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Downloading file from {url} to {dest}")
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()

        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        logger.info(f"File downloaded to {dest}")
        return dest

    def fetch_all_projects(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Fetch all projects up to specified limit.

        Args:
            limit: Maximum number of projects to fetch.

        Returns:
            List of project dictionaries.
        """
        all_projects = []
        page = 1

        while True:
            data = self.list_projects(limit=100, page=page)
            projects = data.get("projects", [])
            all_projects.extend(projects)

            if limit and len(all_projects) >= limit:
                return all_projects[:limit]

            if not projects or len(projects) < 100:
                break

            page += 1

        return all_projects

    def fetch_project_full(self, local_accession: str) -> Dict[str, Any]:
        """
        Fetch complete project data including references and filenotes.

        Args:
            local_accession: The project's local accession identifier.

        Returns:
            Dict with complete project data.
        """
        project = self.get_project(local_accession)
        references = self.get_references(local_accession)
        filenotes = self.get_filenotes(local_accession)

        return {
            "project": project,
            "references": references,
            "filenotes": filenotes,
        }


# Module-level client instance
_client: Optional[MddbrClient] = None


def get_client() -> MddbrClient:
    """Get or create the module-level MDDBR client."""
    global _client
    if _client is None:
        _client = MddbrClient()
    return _client


def list_projects(limit: int = 100, page: int = 1, status: Optional[str] = None) -> Dict[str, Any]:
    """List projects."""
    return get_client().list_projects(limit, page, status)


def get_project(local_accession: str) -> Dict[str, Any]:
    """Get project metadata."""
    return get_client().get_project(local_accession)


def get_references(local_accession: str) -> List[Dict[str, Any]]:
    """Get project references."""
    return get_client().get_references(local_accession)


def get_filenotes(local_accession: str) -> List[Dict[str, Any]]:
    """Fetch filenotes for a project."""
    return get_client().get_filenotes(local_accession)


def download_file(url: str, dest_path: str) -> Path:
    """Download a file."""
    return get_client().download_file(url, dest_path)


def fetch_all_projects(limit: int = None) -> List[Dict[str, Any]]:
    """Fetch all projects up to limit."""
    return get_client().fetch_all_projects(limit=limit)


def fetch_project_full(local_accession: str) -> Dict[str, Any]:
    """Fetch complete project data."""
    return get_client().fetch_project_full(local_accession)


def download_simulation_files(
    db_session,
    entry_id: int,
    local_accession: str,
    input_dir: str
) -> bool:
    """
    Download simulation files from MDDBR for a given entry.
    
    Downloads structure files (topology or PDB) and trajectory files.
    BAT3 can load from various formats:
    - AMBER: .prmtop + .nc/.xtc
    - GROMACS: .tpr, .top+.gro, .itp+.gro
    - PDB: .pdb (with or without trajectory)
    - MMCIF: .cif
    
    Args:
        db_session: Database session
        entry_id: Entry ID
        local_accession: Project local accession
        input_dir: Directory to download files to
        
    Returns:
        True if files downloaded successfully, False otherwise
    """
    import os
    
    try:
        # Use the configured MDDBR_API_BASE directly
        api_base = MDDBR_API_BASE
        
        # Get filenotes
        filenotes_url = f"{api_base}/projects/{local_accession}/filenotes"
        logger.info(f"Fetching filenotes from {filenotes_url}")
        
        resp = requests.get(filenotes_url, timeout=MDDBR_TIMEOUT)
        resp.raise_for_status()
        filenotes = resp.json()
        
        if not filenotes:
            logger.error(f"No filenotes found for project {local_accession}")
            return False
        
        logger.info(f"Found {len(filenotes)} files for project {local_accession}")
        
        # Identify files to download
        # Priority: topology files > structure PDB files > trajectory files
        topology_file = None
        structure_pdb_file = None  # Fallback if no topology
        trajectory_file = None
        
        for file in filenotes:
            filename = file.get("filename", "")
            
            # Topology files (highest priority)
            if filename.endswith(".prmtop") or filename.endswith(".parm7"):
                topology_file = file
            elif filename.endswith(".top"):
                topology_file = file
            elif filename.endswith(".tpr"):
                topology_file = file
            elif filename.endswith(".itp"):
                topology_file = file
            
            # Structure PDB files (fallback if no topology)
            elif filename.endswith(".pdb"):
                # Prefer structure.pdb, average.pdb, or firstFrame.pdb
                if filename in ["structure.pdb", "average.pdb", "firstFrame.pdb"]:
                    if structure_pdb_file is None:
                        structure_pdb_file = file
                elif structure_pdb_file is None:
                    structure_pdb_file = file
            
            # Trajectory files
            elif filename.endswith(".bin") or filename.endswith(".dcd") or filename.endswith(".xtc") or filename.endswith(".nc"):
                # Prefer main trajectory over PCA trajectories
                if filename == "trajectory.bin" or filename == "trajectory.xtc" or filename == "trajectory.dcd":
                    trajectory_file = file
                elif trajectory_file is None:
                    trajectory_file = file
        
        # Determine what to download
        files_to_download = []
        
        if topology_file:
            logger.info(f"Found topology file: {topology_file.get('filename')}")
            files_to_download.append(topology_file)
        elif structure_pdb_file:
            logger.info(f"Found structure PDB file (no topology): {structure_pdb_file.get('filename')}")
            files_to_download.append(structure_pdb_file)
        else:
            logger.error(f"No topology or structure file found for {local_accession}")
            return False
        
        if trajectory_file:
            logger.info(f"Found trajectory file: {trajectory_file.get('filename')}")
            files_to_download.append(trajectory_file)
        
        # Download files
        for file in files_to_download:
            filename = file.get("filename")
            url = f"{api_base}/projects/{local_accession}/files/{filename}"
            dest = os.path.join(input_dir, filename)
            logger.info(f"Downloading: {url}")
            download_file(url, dest)
        
        # Verify files were downloaded
        downloaded_files = os.listdir(input_dir)
        logger.info(f"Successfully downloaded {len(downloaded_files)} files: {downloaded_files}")
        
        return len(downloaded_files) > 0
        
    except Exception as e:
        logger.error(f"Error downloading files for entry {entry_id}: {e}")
        import traceback
        traceback.print_exc()
        return False
