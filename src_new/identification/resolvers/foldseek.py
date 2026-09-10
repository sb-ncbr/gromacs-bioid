"""Foldseek 3Di sequence identifier resolver."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile

from ...config.loader import RunConfig
from ..base import IdentifierResolver, IdentifierResolutionError, safe_tmp_dir

logger = logging.getLogger("identifier")


class Foldseek3DiResolver(IdentifierResolver):
    """
    Foldseek3DiResolver identifies 3Di sequences using Foldseek search.
    """

    def __init__(self, config: RunConfig) -> None:
        """
        Initialize Foldseek3DiResolver.
        
        Args:
            config: RunConfig instance.
        """
        super().__init__(config)
        
        # Set resolver metadata
        self.name = "foldseek_3di"
        self.identifier_type = "UNIPROT_ID"
        self.accepted_signatures = ["3di_sequence"]
        
        self.config = config
        self.foldseek_config = config.foldseek
        
        # Check if foldseek is available
        self._foldseek_available = self._check_foldseek()

    def _check_foldseek(self) -> bool:
        """Check if foldseek executable is available."""
        try:
            result = subprocess.run(
                [self.foldseek_config.foldseek_exec, "--version"],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            logger.warning(f"Foldseek executable '{self.foldseek_config.foldseek_exec}' not found or not executable")
            return False

    def _is_applicable(self, signature: str) -> bool:
        """
        Check if signature is a valid 3Di sequence.
        
        Args:
            signature: The 3Di sequence string to check.
            
        Returns:
            True if applicable, False otherwise.
        """
        if not signature or len(signature.strip()) == 0:
            return False
        
        # 3Di sequences use specific alphabet (letters representing 3D states)
        # Basic validation: non-empty string
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """
        Resolve signature to exact-match identifiers.
        
        Not practical for exact match; returns empty list.
        
        Args:
            signature: 3Di sequence string.
            working_directory: Working directory for operations.
            
        Returns:
            Empty list (exact match not practical for 3Di sequences).
        """
        logger.debug(f"Foldseek identity search not implemented for 3Di sequences")
        return []

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """
        Resolve signature to similar identifiers using Foldseek.
        
        Args:
            signature: 3Di sequence string.
            working_directory: Working directory for operations.
            
        Returns:
            List of (UniProt accession, score) tuples.
        """
        if not self._foldseek_available:
            logger.warning("Foldseek not available, skipping similarity search")
            return []
        
        # Create temporary directory for foldseek operations
        tmp_dir = tempfile.mkdtemp(prefix="foldseek_", dir=safe_tmp_dir(working_directory))
        
        try:
            return self._run_foldseek_search(signature, tmp_dir)
        except Exception as exc:
            logger.warning(f"Foldseek search failed: {exc}")
            return []
        finally:
            # Clean up all temporary files
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def _write_fasta_file(self, sequence: str, output_path: str) -> None:
        """
        Write sequence to FASTA format file.
        
        Args:
            sequence: 3Di sequence string.
            output_path: Path to output FASTA file.
        """
        with open(output_path, 'w') as f:
            f.write(">query\n")
            f.write(sequence + "\n")

    def _run_foldseek_createdb(self, input_fasta: str, db_prefix: str) -> bool:
        """
        Run foldseek createdb to create database from FASTA file.
        
        Args:
            input_fasta: Path to input FASTA file.
            db_prefix: Prefix for output database files.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            result = subprocess.run(
                [
                    self.foldseek_config.foldseek_exec,
                    "createdb",
                    input_fasta,
                    db_prefix
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                logger.error(f"Foldseek createdb failed: {result.stderr}")
                return False
            
            return True
        except subprocess.TimeoutExpired:
            logger.error("Foldseek createdb timed out")
            return False
        except Exception as exc:
            logger.error(f"Foldseek createdb failed: {exc}")
            return False

    def _run_foldseek_search(self, query_db: str, target_db: str, output_m8: str) -> bool:
        """
        Run foldseek search.
        
        Args:
            query_db: Query database prefix.
            target_db: Target database path/prefix.
            output_m8: Output M8 (TSV) file path.
            
        Returns:
            True if successful, False otherwise.
        """
        try:
            # Use default AFDB if no db_path configured
            db_path = self.foldseek_config.db_path if self.foldseek_config.db_path else "afdb"
            
            result = subprocess.run(
                [
                    self.foldseek_config.foldseek_exec,
                    "search",
                    query_db,
                    db_path,
                    output_m8,
                    "--format-output", "query,target,fident,evalue,bits,alnlen,mismatch,gapopen,qstart,qend,tstart,tend,evalue"
                ],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout for search
            )
            
            if result.returncode != 0:
                logger.error(f"Foldseek search failed: {result.stderr}")
                return False
            
            return True
        except subprocess.TimeoutExpired:
            logger.error("Foldseek search timed out")
            return False
        except Exception as exc:
            logger.error(f"Foldseek search failed: {exc}")
            return False

    def _parse_m8_output(self, m8_path: str) -> list[tuple[str, float]]:
        """
        Parse Foldseek M8 (TSV) output file.
        
        Args:
            m8_path: Path to M8 output file.
            
        Returns:
            List of (target_id, fident*100) tuples.
        """
        results: list[tuple[str, float]] = []
        
        try:
            with open(m8_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        target_id = parts[1]  # Column 2: target identifier
                        try:
                            fident = float(parts[2])  # Column 3: fractional identity
                            results.append((target_id, fident * 100.0))
                        except ValueError:
                            logger.warning(f"Could not parse fident from line: {line}")
                            continue
        except IOError as exc:
            logger.error(f"Failed to read M8 file: {exc}")
        
        return results

    def _run_foldseek_search(self, sequence: str, tmp_dir: str) -> list[tuple[str, float]]:
        """
        Execute complete Foldseek search workflow.
        
        Args:
            sequence: 3Di query sequence.
            tmp_dir: Temporary directory for intermediate files.
            
        Returns:
            List of (UniProt ID, score) tuples.
        """
        # File paths
        query_fasta = os.path.join(tmp_dir, "query.fasta")
        query_db = os.path.join(tmp_dir, "query_db")
        output_m8 = os.path.join(tmp_dir, "results.m8")
        
        # Write query sequence to FASTA
        self._write_fasta_file(sequence, query_fasta)
        
        # Create query database
        if not self._run_foldseek_createdb(query_fasta, query_db):
            return []
        
        # Run search
        if not self._run_foldseek_search(query_db, "", output_m8):
            return []
        
        # Parse results
        return self._parse_m8_output(output_m8)
