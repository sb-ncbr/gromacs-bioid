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


# ---------------------------------------------------------------------------
# Download failure taxonomy (see validation/download-resolution-pattern.md)
# ---------------------------------------------------------------------------
# Terminal: retrying is pointless (upstream permanently unavailable/unusable).
TERMINAL_FAILURE_CLASSES = frozenset({
    "project_not_found",
    "no_simulation_files",
})
# Transient network/download failures use class "download_failed".

# S3 cache configuration (mdfind pattern). Optional: fallback is disabled
# unless all four env vars are present.
S3_ENDPOINT = os.getenv("MDFIND_S3_ENDPOINT", "")
S3_BUCKET = os.getenv("MDFIND_S3_BUCKET", "")
S3_ACCESS_KEY = os.getenv("MDFIND_S3_ACCESS_KEY", "")
S3_SECRET_KEY = os.getenv("MDFIND_S3_SECRET_KEY", "")

_s3_client = None


def _get_s3_client():
    """Return a boto3 S3 client, or None when credentials/boto3 are absent."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    if not (S3_ENDPOINT and S3_BUCKET and S3_ACCESS_KEY and S3_SECRET_KEY):
        return None
    try:
        import boto3
        from botocore.config import Config
        _s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            config=Config(
                retries={"max_attempts": 5, "mode": "adaptive"},
                connect_timeout=10,
                read_timeout=300,
            ),
        )
    except Exception as exc:
        logger.warning(f"S3 fallback unavailable: {exc}")
        return None
    return _s3_client


def _http_download_atomic(url: str, dest: Path, expected_size: Optional[int],
                          attempts: int = 4) -> None:
    """Download url to dest via a .part file (atomic rename on success).

    Retries with exponential backoff (2s * 2**n). Raises on final failure.
    """
    part = dest.with_name(dest.name + ".part")
    last_err: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            with requests.get(url, stream=True, timeout=(30, 300)) as resp:
                resp.raise_for_status()
                with open(part, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):
                        if chunk:
                            f.write(chunk)
            if expected_size is not None and part.stat().st_size != expected_size:
                raise IOError(
                    f"size mismatch for {dest.name}: got {part.stat().st_size}, "
                    f"expected {expected_size}"
                )
            os.replace(part, dest)
            return
        except Exception as exc:  # noqa: BLE001 - retried below
            last_err = exc
            try:
                part.unlink()
            except OSError:
                pass
            time.sleep(2 * (2 ** attempt))
    raise last_err if last_err else IOError(f"download failed: {url}")


def _s3_key_candidates(internal_id: Optional[str], accession: str,
                       filename: str) -> List[str]:
    """Key cascade for the mddbr S3 cache (first hit wins).

    The cache predates MDposit and keys mddbr files by the legacy short
    accession (mddbr_A0001_<file>), so derive it from the canonical
    MD-A00001 form where possible. Legacy padding drops one zero from
    the 5-digit MDposit id (MD-A00001 -> A0001).
    """
    keys: List[str] = []
    if internal_id:
        keys.append(internal_id)
    keys.append(f"mddbr/{accession}/{filename}")
    keys.append(f"mddbr_{accession}_{filename}")
    short = accession[3:] if accession.startswith("MD-") else accession
    if short != accession:
        keys.append(f"mddbr_{short}_{filename}")
    import re
    legacy = re.fullmatch(r"MD-A0(\d{4})", accession)
    if legacy:
        keys.append(f"mddbr_A{legacy.group(1)}_{filename}")
    return keys


def _s3_download(s3, key: str, dest: Path, expected_size: Optional[int]) -> bool:
    """Try one S3 key. Returns True on success."""
    part = dest.with_name(dest.name + ".part")
    try:
        from boto3.s3.transfer import TransferConfig
        s3.download_file(
            Bucket=S3_BUCKET, Key=key, Filename=str(part),
            Config=TransferConfig(
                multipart_threshold=8 * 2 ** 20,
                multipart_chunksize=8 * 2 ** 20,
                max_concurrency=4,
            ),
        )
        if expected_size is not None and part.stat().st_size != expected_size:
            logger.warning(f"s3://{S3_BUCKET}/{key}: size mismatch")
            part.unlink()
            return False
        os.replace(part, dest)
        return True
    except Exception as exc:
        logger.info(f"S3 miss/fail for key {key}: {exc}")
        try:
            part.unlink()
        except OSError:
            pass
        return False


def _fetch_one_file(accession: str, filename: str, internal_id: Optional[str],
                    expected_size: Optional[int], input_dir: str):
    """HTTP-first with S3 fallback for a single file.

    Returns (status, resolver, size_bytes): status in {"ok", "failed"},
    resolver in {"http", "s3", None}.
    """
    url = f"{MDDBR_API_BASE.rstrip('/')}/projects/{accession}/files/{filename}"
    dest = Path(input_dir) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    try:
        _http_download_atomic(url, dest, expected_size)
        return "ok", "http", dest.stat().st_size
    except Exception as exc:
        logger.warning(f"HTTP download failed for {filename}: {exc}")

    s3 = _get_s3_client()
    if s3 is not None:
        for key in _s3_key_candidates(internal_id, accession, filename):
            if _s3_download(s3, key, dest, expected_size):
                return "ok", "s3", dest.stat().st_size

    return "failed", None, 0


def download_simulation_files(
    db_session,
    entry_id: int,
    local_accession: str,
    input_dir: str
) -> tuple:
    """
    Download simulation files from MDDBR for a given entry.

    Returns (ok, failure_class): ok True on success; on failure,
    failure_class is one of TERMINAL_FAILURE_CLASSES or "download_failed".
    A per-file audit record is written to download_report.json in the
    entry directory (see validation/download-resolution-pattern.md).
    
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
    
    report = {"accession": local_accession, "entry_id": entry_id,
              "files": [], "result": "failed", "failure_class": None}

    def _finish(ok: bool, failure_class=None):
        import json as _json
        from datetime import datetime as _dt
        report["result"] = "ok" if ok else "failed"
        report["failure_class"] = failure_class
        report["ts"] = _dt.utcnow().isoformat() + "Z"
        try:
            entry_dir = os.path.dirname(input_dir.rstrip("/"))
            os.makedirs(entry_dir, exist_ok=True)
            with open(os.path.join(entry_dir,
                                   "download_report.json"), "w") as fh:
                _json.dump(report, fh, indent=2)
        except OSError as rep_err:
            logger.warning(f"Could not write download_report.json: {rep_err}")
        return ok, failure_class

    try:
        api_base = MDDBR_API_BASE

        # Get filenotes; 404 means the project is permanently unavailable
        filenotes_url = f"{api_base}/projects/{local_accession}/filenotes"
        logger.info(f"Fetching filenotes from {filenotes_url}")

        resp = requests.get(filenotes_url, timeout=MDDBR_TIMEOUT)
        if resp.status_code == 404:
            logger.error(f"Project {local_accession} not found on MDDBR")
            return _finish(False, "project_not_found")
        resp.raise_for_status()
        filenotes = resp.json()

        if not filenotes:
            logger.error(f"No filenotes found for project {local_accession}")
            return _finish(False, "no_simulation_files")
        
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
            return _finish(False, "no_simulation_files")

        if trajectory_file:
            logger.info(f"Found trajectory file: {trajectory_file.get('filename')}")
            files_to_download.append(trajectory_file)

        # Download files: HTTP origin first, S3 cache fallback (mdfind pattern)
        for file in files_to_download:
            filename = file.get("filename")
            expected = file.get("length")
            status, resolver, size = _fetch_one_file(
                local_accession, filename, file.get("internalId"), expected, input_dir
            )
            report["files"].append({
                "name": filename, "resolver": resolver, "status": status,
                "size_bytes": size, "expected_length": expected,
            })
            if status != "ok":
                logger.error(f"All routes failed for {filename} ({local_accession})")
                return _finish(False, "download_failed")
            logger.info(f"Downloaded {filename} via {resolver} ({size} bytes)")

        return _finish(True)

    except requests.HTTPError as e:
        status_code = getattr(e.response, "status_code", None)
        cls = "project_not_found" if status_code == 404 else "download_failed"
        logger.error(f"HTTP error downloading files for entry {entry_id}: {e}")
        return _finish(False, cls)
    except Exception as e:
        logger.error(f"Error downloading files for entry {entry_id}: {e}")
        import traceback
        traceback.print_exc()
        return _finish(False, "download_failed")
