"""SSH/SCP upload utilities for PDB/mmCIF file transfer.

This module provides helper functions for uploading files to a remote server
via SSH/SCP and deleting them afterwards. Uses paramiko for SSH operations.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ...config.loader import PDBConfig

logger = logging.getLogger("identifier")


def has_ssh_config(config: "PDBConfig") -> bool:
    """Check if SSH configuration is present and complete.
    
    Args:
        config: PDBConfig instance to check.
        
    Returns:
        True if all required SSH fields are non-empty, False otherwise.
    """
    return bool(
        config.ssh_host
        and config.ssh_user
        and config.ssh_key
        and config.ssh_remote_path
        and config.ssh_public_url
    )


def ssh_upload(
    local_path: str,
    remote_subdir: str,
    config: "PDBConfig",
) -> Optional[str]:
    """Upload a file to remote server via SSH/SCP.
    
    Args:
        local_path: Path to the local file to upload.
        remote_subdir: Subdirectory under ssh_remote_path (e.g., '{uuid}/input').
        config: PDBConfig with SSH configuration.
        
    Returns:
        Public URL to the uploaded file, or None if upload failed.
    """
    if not has_ssh_config(config):
        logger.warning("SSH config incomplete; cannot upload")
        return None
    
    try:
        # Lazy import paramiko to avoid dependency issues when not needed
        import paramiko
        from paramiko import SSHClient
        from scp import SCPClient
    except ImportError as exc:
        logger.warning(f"paramiko/scp not available: {exc}")
        return None
    
    filename = os.path.basename(local_path)
    remote_dir = os.path.join(config.ssh_remote_path, remote_subdir)
    
    logger.debug(f"SSH upload: {local_path} -> {config.ssh_host}:{remote_dir}")
    
    client: Optional[SSHClient] = None
    try:
        client = SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Expand ~ in ssh_key path
        key_path = os.path.expanduser(config.ssh_key)
        
        client.connect(
            hostname=config.ssh_host,
            username=config.ssh_user,
            key_filename=key_path,
            timeout=30,
        )
        
        # Ensure remote directory exists
        _ensure_remote_dir(client, remote_dir)
        
        # Upload file
        with SCPClient(client.get_transport()) as scp:
            scp.put(local_path, remote_path=remote_dir)
        
        # Construct public URL
        public_url = f"{config.ssh_public_url.rstrip('/')}/{remote_subdir}/{filename}"
        logger.info(f"SSH upload successful: {public_url}")
        return public_url
        
    except Exception as exc:
        logger.warning(f"SSH upload failed: {exc}")
        return None
    finally:
        if client is not None:
            client.close()


def ssh_delete(remote_subdir: str, filename: str, config: "PDBConfig") -> bool:
    """Delete a file from remote server via SSH.
    
    Args:
        remote_subdir: Subdirectory under ssh_remote_path.
        filename: Name of the file to delete.
        config: PDBConfig with SSH configuration.
        
    Returns:
        True if deletion succeeded or was skipped, False on error.
    """
    if not has_ssh_config(config):
        logger.debug("SSH config incomplete; skipping delete")
        return True
    
    try:
        import paramiko
        from paramiko import SSHClient
    except ImportError as exc:
        logger.warning(f"paramiko not available for delete: {exc}")
        return False
    
    remote_path = os.path.join(config.ssh_remote_path, remote_subdir, filename)
    logger.debug(f"SSH delete: {config.ssh_host}:{remote_path}")
    
    client: Optional[SSHClient] = None
    try:
        client = SSHClient()
        client.load_system_host_keys()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        key_path = os.path.expanduser(config.ssh_key)
        
        client.connect(
            hostname=config.ssh_host,
            username=config.ssh_user,
            key_filename=key_path,
            timeout=30,
        )
        
        # Execute rm command
        stdin, stdout, stderr = client.exec_command(f"rm -f '{remote_path}'")
        exit_status = stdout.channel.recv_exit_status()
        
        if exit_status != 0:
            error = stderr.read().decode("utf-8", errors="replace")
            logger.warning(f"SSH delete failed (exit {exit_status}): {error}")
            return False
        
        logger.debug(f"SSH delete successful: {remote_path}")
        return True
        
    except Exception as exc:
        logger.warning(f"SSH delete failed: {exc}")
        return False
    finally:
        if client is not None:
            client.close()


def _ensure_remote_dir(client: "SSHClient", remote_dir: str) -> None:
    """Ensure a remote directory exists via SSH mkdir -p.
    
    Args:
        client: Connected SSHClient instance.
        remote_dir: Remote directory path to create.
    """
    stdin, stdout, stderr = client.exec_command(f"mkdir -p '{remote_dir}'")
    exit_status = stdout.channel.recv_exit_status()
    if exit_status != 0:
        error = stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Failed to create remote directory {remote_dir}: {error}")
