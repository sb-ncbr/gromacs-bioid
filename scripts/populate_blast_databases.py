#!/usr/bin/env python3
"""
Populate BLAST databases safely with atomic staging + symlink swap.

Downloads NCBI BLAST databases into a target directory using update_blastdb.pl,
verifies each download, and atomically swaps in the new version via symlink.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

# Globals for discovered paths
_UPDATE_BLASTDB_PATH: str = ""
_BLASTDBCMD_PATH: str = ""

# Database type mapping for metadata URL construction
_DB_TYPE_MAP: dict[str, str] = {
    "nr": "prot",
    "swissprot": "prot",
    "pdbaa": "prot",
    "pdbnt": "nucl",
    "core_nt": "nucl",
    "nt": "nucl",
}


def _find_command(cmd: str) -> str:
    """Find a command in PATH or common system locations."""
    # Check PATH first
    path = shutil.which(cmd)
    if path:
        return path
    # Fallback to common system locations
    for candidate in (
        "/usr/bin/ncbi-blast+/" + cmd,
        "/usr/local/bin/" + cmd,
        "/usr/bin/" + cmd,
    ):
        if shutil.which(candidate):
            return candidate
    return ""


def log(msg: str) -> None:
    """Print timestamped log message to stderr."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {msg}", file=sys.stderr)


def _file_md5(path: Path) -> str:
    """Calculate MD5 hash of a file."""
    md5_hash = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5_hash.update(chunk)
    return md5_hash.hexdigest()


def check_dependencies() -> bool:
    """Check that required tools are available."""
    global _UPDATE_BLASTDB_PATH, _BLASTDBCMD_PATH
    _UPDATE_BLASTDB_PATH = _find_command("update_blastdb.pl")
    _BLASTDBCMD_PATH = _find_command("blastdbcmd")
    
    if _UPDATE_BLASTDB_PATH:
        log(f"Found update_blastdb.pl at: {_UPDATE_BLASTDB_PATH}")
    else:
        log("WARNING: update_blastdb.pl not found; will use direct HTTP download")
    
    if _BLASTDBCMD_PATH:
        log(f"Found blastdbcmd at: {_BLASTDBCMD_PATH}")
    else:
        log("ERROR: blastdbcmd not found — verification will fail")
        return False
    
    return True


def create_staging_dir(target_dir: Path, db_name: str) -> Path:
    """Create a staging directory for a database download."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    staging_name = f"{db_name}-{timestamp}"
    staging_dir = target_dir / ".staging" / staging_name
    staging_dir.mkdir(parents=True, exist_ok=True)
    log(f"Created staging directory: {staging_dir}")
    return staging_dir


def _download_with_update_blastdb(staging_dir: Path, db_name: str, source: str, num_threads: int) -> bool:
    """Download a single database using update_blastdb.pl."""
    cmd = [
        _UPDATE_BLASTDB_PATH,
        "--decompress",
        "--source", source,
        "--quiet",
    ]
    if num_threads > 0:
        cmd.extend(["--num_threads", str(num_threads)])
    cmd.append(db_name)

    log(f"Downloading {db_name} from {source}...")
    try:
        result = subprocess.run(
            cmd,
            cwd=staging_dir,
            capture_output=True,
            text=True,
            timeout=None  # No timeout - let K8s handle it
        )
        if result.returncode != 0:
            log(f"ERROR: Download failed for {db_name}")
            log(f"stdout: {result.stdout}")
            log(f"stderr: {result.stderr}")
            return False
        log(f"Download completed for {db_name}")
        return True
    except subprocess.TimeoutExpired:
        log(f"ERROR: Download timed out for {db_name}")
        return False
    except Exception as e:
        log(f"ERROR: Exception during download of {db_name}: {e}")
        return False


def _download_with_urllib(staging_dir: Path, db_name: str) -> bool:
    """Download a BLAST database directly via HTTP using only Python stdlib."""
    base_url = "https://ftp.ncbi.nlm.nih.gov/blast/db"
    db_type = _DB_TYPE_MAP.get(db_name, "prot")
    
    # 1. Download metadata JSON
    meta_url = f"{base_url}/{db_name}-{db_type}-metadata.json"
    log(f"Fetching metadata: {meta_url}")
    meta_path = staging_dir / f"{db_name}-{db_type}-metadata.json"
    try:
        urllib.request.urlretrieve(meta_url, meta_path)
    except Exception as exc:
        log(f"ERROR: Failed to fetch metadata for {db_name}: {exc}")
        return False
    
    with open(meta_path) as f:
        meta = json.load(f)
    
    num_volumes = meta.get("number-of-volumes", 1)
    log(f"{db_name}: {num_volumes} volume(s) to download")
    
    # Get actual filenames from metadata to handle varying digit formats (nr uses 3 digits, others use 2)
    files_list = meta.get("files", [])
    
    # 2. Download each volume
    for vol in range(num_volumes):
        if files_list and vol < len(files_list):
            # Extract filename from full FTP URL in metadata
            vol_file = files_list[vol].split("/")[-1]
        elif num_volumes == 1:
            vol_file = f"{db_name}.tar.gz"
        else:
            vol_file = f"{db_name}.{vol:02d}.tar.gz"
        vol_url = f"{base_url}/{vol_file}"
        vol_path = staging_dir / vol_file
        md5_url = f"{vol_url}.md5"
        md5_path = staging_dir / f"{vol_file}.md5"
        
        log(f"Downloading volume {vol+1}/{num_volumes}: {vol_file}")
        
        try:
            urllib.request.urlretrieve(vol_url, vol_path)
        except Exception as exc:
            log(f"ERROR: Failed to download {vol_file}: {exc}")
            return False
        
        # Download and verify MD5
        try:
            urllib.request.urlretrieve(md5_url, md5_path)
            expected_md5 = md5_path.read_text().strip().split()[0]
            actual_md5 = _file_md5(vol_path)
            if actual_md5 != expected_md5:
                log(f"ERROR: MD5 mismatch for {vol_file}: expected {expected_md5}, got {actual_md5}")
                return False
            log(f"MD5 OK for {vol_file}")
        except Exception:
            log(f"WARNING: Could not verify MD5 for {vol_file}, continuing...")
        
        # Extract
        log(f"Extracting {vol_file}...")
        try:
            with tarfile.open(vol_path, "r:gz") as tar:
                tar.extractall(path=staging_dir)
        except Exception as exc:
            log(f"ERROR: Failed to extract {vol_file}: {exc}")
            return False
        
        # Clean up
        vol_path.unlink()
        if md5_path.exists():
            md5_path.unlink()
    
    # Clean up metadata
    meta_path.unlink()
    log(f"Downloaded {db_name} ({num_volumes} volume(s))")
    return True


def download_database(staging_dir: Path, db_name: str, source: str, num_threads: int) -> bool:
    """Download a single database using update_blastdb.pl or direct HTTP fallback."""
    has_update_blastdb = _UPDATE_BLASTDB_PATH and str(_UPDATE_BLASTDB_PATH).strip()
    
    if has_update_blastdb:
        log(f"Attempting download via update_blastdb.pl for {db_name}...")
        if _download_with_update_blastdb(staging_dir, db_name, source, num_threads):
            return True
        log(f"update_blastdb.pl failed for {db_name}, falling back to direct HTTP download...")
    else:
        log(f"update_blastdb.pl not available, using direct HTTP download for {db_name}...")
    
    return _download_with_urllib(staging_dir, db_name)


def verify_database(staging_dir: Path, db_name: str) -> bool:
    """Verify downloaded database with blastdbcmd -info."""
    cmd = [_BLASTDBCMD_PATH, "-db", db_name, "-info"]
    log(f"Verifying {db_name}...")
    try:
        result = subprocess.run(
            cmd,
            cwd=staging_dir,
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            log(f"ERROR: Verification failed for {db_name}")
            log(f"stderr: {result.stderr}")
            return False
        log(f"Verification passed for {db_name}")
        return True
    except Exception as e:
        log(f"ERROR: Exception during verification of {db_name}: {e}")
        return False


def atomic_symlink_swap(target_dir: Path, db_name: str, staging_dir: Path) -> bool:
    """
    Atomically swap the live symlink to point to the new staging directory.
    
    Uses os.symlink + os.replace pattern for atomic operation on POSIX systems.
    """
    live_path = target_dir / db_name
    temp_link = target_dir / f".{db_name}.tmp"
    
    # Remove any existing temp link
    if temp_link.exists() or temp_link.is_symlink():
        temp_link.unlink()
    
    # Create new symlink at temp location pointing to staging dir
    # Use relative path from symlink location to target
    rel_staging = os.path.relpath(staging_dir, target_dir)
    os.symlink(rel_staging, temp_link)
    log(f"Created temporary symlink: {temp_link} -> {rel_staging}")
    
    # Atomic rename: replace old live symlink (or directory) with new one
    try:
        if live_path.exists() or live_path.is_symlink():
            # If it's a symlink or file, we can replace directly
            if live_path.is_symlink() or live_path.is_file():
                os.replace(temp_link, live_path)
                log(f"Atomic swap complete: {live_path} -> {rel_staging}")
            else:
                # It's a directory - need to remove first
                shutil.rmtree(live_path)
                os.replace(temp_link, live_path)
                log(f"Atomic swap complete (removed old dir): {live_path} -> {rel_staging}")
        else:
            # No existing path, just rename temp to live
            os.replace(temp_link, live_path)
            log(f"Created new symlink: {live_path} -> {rel_staging}")
        return True
    except Exception as e:
        log(f"ERROR: Failed to perform atomic swap: {e}")
        # Clean up temp link
        if temp_link.exists() or temp_link.is_symlink():
            temp_link.unlink()
        return False


def cleanup_old_staging(target_dir: Path, db_name: str, keep_count: int = 2) -> None:
    """
    Clean up old staging directories for a database, keeping the most recent ones.
    
    Keeps keep_count most recent staging dirs plus the current live one.
    """
    staging_base = target_dir / ".staging"
    if not staging_base.exists():
        return
    
    # Find all staging dirs for this database
    pattern = f"{db_name}-"
    staging_dirs = []
    for entry in staging_base.iterdir():
        if entry.is_dir() and entry.name.startswith(pattern):
            staging_dirs.append(entry)
    
    # Sort by name (which includes timestamp) descending - newest first
    staging_dirs.sort(key=lambda x: x.name, reverse=True)
    
    # Keep the most recent ones, remove the rest
    to_remove = staging_dirs[keep_count:]
    for old_dir in to_remove:
        try:
            shutil.rmtree(old_dir)
            log(f"Cleaned up old staging directory: {old_dir}")
        except Exception as e:
            log(f"WARNING: Failed to clean up {old_dir}: {e}")


def process_database(
    target_dir: Path,
    db_name: str,
    source: str,
    num_threads: int,
    keep_staging: bool
) -> bool:
    """Process a single database: download, verify, swap, cleanup."""
    log(f"Processing database: {db_name}")
    
    # Create staging directory
    staging_dir = create_staging_dir(target_dir, db_name)
    
    try:
        # Download
        if not download_database(staging_dir, db_name, source, num_threads):
            log(f"FAILED: Download failed for {db_name}")
            return False
        
        # Verify
        if not verify_database(staging_dir, db_name):
            log(f"FAILED: Verification failed for {db_name}")
            return False
        
        # Atomic swap
        if not atomic_symlink_swap(target_dir, db_name, staging_dir):
            log(f"FAILED: Symlink swap failed for {db_name}")
            return False
        
        # Cleanup old staging (unless --keep-staging)
        if not keep_staging:
            cleanup_old_staging(target_dir, db_name, keep_count=2)
        
        log(f"SUCCESS: {db_name} is ready")
        return True
        
    except Exception as e:
        log(f"ERROR: Unexpected error processing {db_name}: {e}")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download NCBI BLAST databases with atomic staging + symlink swap"
    )
    parser.add_argument(
        "--databases",
        type=str,
        default="nr,swissprot,pdbaa,pdbnt,core_nt,nt",
        help="Comma-separated list of databases to download (default: nr,swissprot,pdbaa,pdbnt,core_nt,nt)"
    )
    parser.add_argument(
        "--target-dir",
        type=Path,
        default=Path("/app/databases"),
        help="Target directory for databases (default: /app/databases)"
    )
    parser.add_argument(
        "--source",
        type=str,
        choices=["ncbi", "aws", "gcp"],
        default="ncbi",
        help="Download source (default: ncbi)"
    )
    parser.add_argument(
        "--num-threads",
        type=int,
        default=0,
        help="Number of threads for download (default: 0 = auto)"
    )
    parser.add_argument(
        "--keep-staging",
        action="store_true",
        help="Keep all staging directories (for debugging)"
    )
    
    args = parser.parse_args()
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    # Ensure target directory exists
    args.target_dir.mkdir(parents=True, exist_ok=True)
    log(f"Target directory: {args.target_dir}")
    log(f"Source: {args.source}")
    log(f"Threads: {args.num_threads if args.num_threads > 0 else 'auto'}")
    
    # Parse database list
    databases = [db.strip() for db in args.databases.split(",") if db.strip()]
    if not databases:
        log("ERROR: No databases specified")
        return 1
    
    log(f"Databases to download: {', '.join(databases)}")
    
    # Process each database
    failed = []
    for db_name in databases:
        if not process_database(
            target_dir=args.target_dir,
            db_name=db_name,
            source=args.source,
            num_threads=args.num_threads,
            keep_staging=args.keep_staging
        ):
            failed.append(db_name)
    
    # Summary
    log("=" * 60)
    if failed:
        log(f"FAILED: {len(failed)} database(s) failed: {', '.join(failed)}")
        return 1
    else:
        log(f"SUCCESS: All {len(databases)} database(s) downloaded and verified")
        return 0


if __name__ == "__main__":
    sys.exit(main())
