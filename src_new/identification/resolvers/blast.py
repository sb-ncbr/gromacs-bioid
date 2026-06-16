"""BLAST identifier resolver for protein and nucleotide sequences."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import subprocess
import tempfile
from dataclasses import dataclass
from typing import Callable

from ...config.loader import RunConfig
from ..base import IdentifierResolver, IdentifierResolutionError

# Import residue/nucleic codes for alphabet validation
try:
    from ...src.constants import KNOWN_RESIDUE_CODES, KNOWN_NUCLEIC_ACIDS_CODES
except ImportError:
    # Fallback for isolated execution
    KNOWN_RESIDUE_CODES = {
        'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
        'GLU': 'E', 'GLN': 'Q', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
        'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
        'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V',
    }
    KNOWN_NUCLEIC_ACIDS_CODES = {
        'A': 'A', 'C': 'C', 'T': 'T', 'G': 'G', 'U': 'U',
        'DA': 'A', 'DC': 'C', 'DT': 'T', 'DG': 'G', 'DU': 'U',
        'RA': 'A', 'RC': 'C', 'RT': 'T', 'RG': 'G', 'RU': 'U',
    }

logger = logging.getLogger("identifier")


@dataclass
class BlastHit:
    """Represents a BLAST hit."""
    accessions: list[str]
    evalue: float
    bits: float
    identity_p: float
    coverage_p: float


class BLASTResolver(IdentifierResolver):
    """
    BLASTResolver identifies residue sequences (amino acids or nucleotides) using BLAST.
    """

    # Common BLAST database file extensions (including nucleotide alias and multi-volume)
    _DB_FILE_EXTENSIONS = [".pal", ".nal", ".pin", ".nin", ".phr", ".psq", ".nhr", ".nsq", ".p00", ".n00"]

    def __init__(self, config: RunConfig, db_path: str, is_protein: bool, 
                 resolver_name: str, identifier_type: str) -> None:
        """
        Initialize BLASTResolver.
        
        Args:
            config: RunConfig instance.
            db_path: Path to BLAST database.
            is_protein: True for protein sequences, False for nucleotide.
            resolver_name: Name of the resolver.
            identifier_type: Type of identifier (e.g., "PDB_ID", "UNIPROT_ID").
        """
        # Don't call super().__init__(config) yet - we need to set name/identifier_type first
        self.name = resolver_name
        self.identifier_type = identifier_type
        self.db_path = db_path
        self.is_protein = is_protein
        self.accepted_signatures = ["residue_sequence_protein"] if is_protein else ["residue_sequence_nucleotide"]
        
        # Now initialize base class
        super().__init__(config)
        
        # Store config references
        self.config = config
        self.blast_config = config.blast

    def _preflight_check(self) -> None:
        """
        Check if BLAST database is available before running.
        
        Accepts DB presence if any of these exist:
        - db_path + ".pal" (protein alias)
        - db_path + ".nal" (nucleotide alias)
        - db_path + ".pin" + any of .phr, .psq (protein single volume)
        - db_path + ".nin" + any of .nhr, .nsq (nucleotide single volume)
        - Multi-volume patterns (.p00, .n00, etc.)
        
        Raises:
            IdentifierResolutionError: If database is not available.
        """
        if not self.db_path:
            raise IdentifierResolutionError(
                f"BLAST database path not configured for {self.name}. "
                f"Expected files: {self.db_path}.pal/.nal (alias), or "
                f"{self.db_path}.pin/.phr/.psq (protein), or "
                f"{self.db_path}.nin/.nhr/.nsq (nucleotide)."
            )
        
        db_path = Path(self.db_path)
        
        # Check for alias files first (simplest case)
        if (db_path.with_suffix(db_path.suffix + ".pal")).exists():
            return
        if (db_path.with_suffix(db_path.suffix + ".nal")).exists():
            return
        
        # Check for single-volume protein DB (.pin + .phr or .psq)
        if (db_path.with_suffix(db_path.suffix + ".pin")).exists():
            if (db_path.with_suffix(db_path.suffix + ".phr")).exists() or                (db_path.with_suffix(db_path.suffix + ".psq")).exists():
                return
        
        # Check for single-volume nucleotide DB (.nin + .nhr or .nsq)
        if (db_path.with_suffix(db_path.suffix + ".nin")).exists():
            if (db_path.with_suffix(db_path.suffix + ".nhr")).exists() or                (db_path.with_suffix(db_path.suffix + ".nsq")).exists():
                return
        
        # Check for multi-volume DBs (.p00/.n00 pattern - first volume)
        if (db_path.with_suffix(db_path.suffix + ".p00")).exists() or            (db_path.with_suffix(db_path.suffix + ".n00")).exists():
            return
        
        # Check legacy extensions directly appended
        for ext in self._DB_FILE_EXTENSIONS:
            if (db_path.with_suffix(db_path.suffix + ext)).exists():
                return
        
        raise IdentifierResolutionError(
            f"BLAST database not found at {self.db_path} for {self.name}. "
            f"Expected files: {self.db_path}.pal/.nal (alias), or "
            f"{self.db_path}.pin/.phr/.psq (protein), or "
            f"{self.db_path}.nin/.nhr/.nsq (nucleotide), or "
            f"{self.db_path}.p00/.n00 (multi-volume)."
        )

    def _is_applicable(self, signature: str) -> bool:
        """
        Check if signature is applicable for BLAST.
        
        Validates that the sequence contains only valid residue/nucleic acid codes.
        
        Args:
            signature: The signature string to check.
            
        Returns:
            True if applicable, False otherwise.
        """
        # Basic check: non-empty sequence
        if not signature or len(signature.strip()) == 0:
            return False
        
        # Validate alphabet based on sequence type
        seq_upper = signature.upper().strip()
        
        if self.is_protein:
            # For protein sequences, all characters must be valid amino acid codes
            # Use 1-letter codes from KNOWN_RESIDUE_CODES values
            valid_chars = set(v.upper() for v in KNOWN_RESIDUE_CODES.values())
            for char in seq_upper:
                if char not in valid_chars:
                    return False
        else:
            # For nucleotide sequences, all characters must be valid nucleic acid codes
            # Use 1-letter codes from KNOWN_NUCLEIC_ACIDS_CODES values  
            valid_chars = set(v.upper() for v in KNOWN_NUCLEIC_ACIDS_CODES.values())
            for char in seq_upper:
                if char not in valid_chars:
                    return False
        
        return True

    def _get_exec_path(self) -> str:
        """Get the appropriate BLAST executable path."""
        if self.is_protein:
            return self.blast_config.blastp_exec
        else:
            return self.blast_config.blastn_exec

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """
        Resolve signature to exact-match identifiers.
        
        Args:
            signature: The signature string to resolve.
            working_directory: Working directory for operations.
            
        Returns:
            List of identifier strings.
            
        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        # Preflight check - raises IdentifierResolutionError if database not available
        self._preflight_check()
        
        return self._run_blast_identity(signature, working_directory)

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """
        Resolve signature to similar identifiers.
        
        Args:
            signature: The signature string to resolve.
            working_directory: Working directory for operations.
            
        Returns:
            List of (identifier, similarity_score) tuples with scores as percentages (0-100).
            
        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        # Preflight check - raises IdentifierResolutionError if database not available
        self._preflight_check()
        
        return self._run_blast_similarity(signature, working_directory)

    def _run_blast_local(self, sequence: str, working_directory: str) -> list[dict] | None:
        """
        Execute BLAST search locally.
        
        Args:
            sequence: Query sequence.
            working_directory: Working directory for operations.
            
        Returns:
            List of JSON results, or None on failure.
            
        Raises:
            IdentifierResolutionError: If BLAST execution fails or times out.
        """
        executable_path = self._get_exec_path()
        
        # Use temp directory
        tmp_dir = working_directory if working_directory else tempfile.gettempdir()

        # Create temp file for output using tempfile
        fd, output_path = tempfile.mkstemp(suffix=".json", dir=tmp_dir)
        os.close(fd)

        try:
            # Determine if short search task should be used
            short_search = []
            if len(sequence) < self.blast_config.local_instance_run_short_search_if_under_X_residues:
                short_search = ['-task', 'blastp-short'] if self.is_protein else ['-task', 'blastn-short']

            # Build BLAST command with performance and safety options
            num_threads = self.blast_config.blastp_num_threads if self.is_protein else self.blast_config.blastn_num_threads
            max_target_seqs = self.blast_config.max_target_seqs
            timeout_s = self.blast_config.timeout_s
            
            cmd = [
                executable_path, 
                "-outfmt", "15", 
                "-db", self.db_path, 
                "-out", output_path,
                "-num_threads", str(num_threads),
                "-max_target_seqs", str(max_target_seqs)
            ] + short_search

            result = subprocess.run(
                cmd,
                input=sequence,
                text=True,
                capture_output=True,
                timeout=timeout_s,
            )
            if result.returncode != 0:
                stderr_msg = result.stderr.strip() if result.stderr else "(no stderr)"
                raise IdentifierResolutionError(
                    f"BLAST failed with return code {result.returncode}. "
                    f"Database: {self.db_path}. "
                    f"Executable: {executable_path}. "
                    f"Stderr: {stderr_msg}"
                )
            
            # Log warnings from stderr on successful runs
            if result.stderr and result.stderr.strip():
                logger.warning(f"BLAST completed with warnings: {result.stderr.strip()}")
            
            with open(output_path, "r") as f:
                json_files = [json.load(f)]
                
            return json_files
        except subprocess.TimeoutExpired:
            raise IdentifierResolutionError(
                f"BLAST timed out after {self.blast_config.timeout_s}s. "
                f"Database: {self.db_path}. "
                f"Executable: {executable_path}."
            )
        except Exception as exc:
            raise IdentifierResolutionError(f"Local BLAST failed: {exc}")
        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def _process_blast_results(self, json_files: list[dict]) -> list[BlastHit]:
        """
        Parse BLAST results into standardized format.
        
        Args:
            json_files: Output from _run_blast_local.
            
        Returns:
            List of BlastHit objects.
        """
        if json_files is None:
            return []

        results: list[BlastHit] = []

        for data in json_files:
            if "BlastOutput2" not in data:
                continue

            blast: dict = data["BlastOutput2"]
            if isinstance(blast, list):
                blast = blast[0]

            if (
                "report" not in blast
                or "results" not in blast["report"]
                or "search" not in blast["report"]["results"]
                or "hits" not in blast["report"]["results"]["search"]
            ):
                continue

            for hit in blast["report"]["results"]["search"]["hits"]:
                accessions: list[str] = [match["accession"] for match in hit["description"]]

                query_len: int = blast["report"]["results"]["search"]["query_len"]
                _scores_section: dict = hit["hsps"][0]
                bits: float = _scores_section["bit_score"]
                evalue: float = _scores_section["evalue"]
                aligned_residues: int = _scores_section["align_len"]
                identity_p: float = _scores_section["identity"] / aligned_residues if aligned_residues > 0 else 0.0
                coverage_p: float = aligned_residues / query_len if query_len > 0 else 0.0
                
                results.append(BlastHit(accessions, evalue, bits, identity_p, coverage_p))
        
        return results

    def _filter_blast_results(self, results: list[BlastHit], 
                              filter_func: Callable[[BlastHit], bool]) -> list[BlastHit]:
        """Filter BLAST results."""
        return [hit for hit in results if filter_func(hit)]

    def _run_blast_identity(self, sequence: str, working_directory: str) -> list[str]:
        """Execute identity search with BLAST."""
        hits = self._process_blast_results(
            self._run_blast_local(sequence, working_directory)
        )

        # Apply filters for exact matches
        hits = self._filter_blast_results(
            hits,
            lambda hit: hit.evalue <= self.blast_config.exact_match_max_evalue,
        )
        hits = self._filter_blast_results(
            hits, 
            lambda hit: hit.bits >= self.blast_config.exact_match_min_bits
        )
        hits = self._filter_blast_results(
            hits,
            lambda hit: hit.identity_p >= self.blast_config.exact_match_min_identity_p,
        )
        hits = self._filter_blast_results(
            hits,
            lambda hit: hit.coverage_p >= self.blast_config.exact_match_min_query_cov_p,
        )
        
        # Capture metadata for each hit
        metadata: dict[str, dict] = {}
        for hit in hits:
            meta = {
                "evalue": hit.evalue,
                "bit_score": hit.bits,
                "identity_p": hit.identity_p,
                "coverage_p": hit.coverage_p,
            }
            for accession in hit.accessions:
                metadata[accession] = meta
        self._last_resolution_metadata = metadata
        
        return [accession for hit in hits for accession in hit.accessions]

    def _run_blast_similarity(self, sequence: str, working_directory: str) -> list[tuple[str, float]]:
        """Execute similarity search with BLAST."""
        hits = self._process_blast_results(
            self._run_blast_local(sequence, working_directory)
        )

        # Apply filters for similarity matches
        hits = self._filter_blast_results(
            hits,
            lambda hit: hit.evalue <= self.blast_config.similarity_match_max_evalue,
        )
        hits = self._filter_blast_results(
            hits,
            lambda hit: hit.bits >= self.blast_config.similarity_match_min_bits,
        )
        hits = self._filter_blast_results(
            hits,
            lambda hit: hit.identity_p >= self.blast_config.similarity_match_min_identity_p,
        )
        hits = self._filter_blast_results(
            hits,
            lambda hit: hit.coverage_p >= self.blast_config.similarity_match_min_query_cov_p,
        )
        
        # Capture metadata for each hit
        metadata: dict[str, dict] = {}
        for hit in hits:
            meta = {
                "evalue": hit.evalue,
                "bit_score": hit.bits,
                "identity_p": hit.identity_p,
                "coverage_p": hit.coverage_p,
            }
            for accession in hit.accessions:
                metadata[accession] = meta
        self._last_resolution_metadata = metadata
        
        # Return as percentage (multiply by 100)
        return [(accession, hit.identity_p * 100.0) for hit in hits for accession in hit.accessions]


class BLASTResolverPDBAA(BLASTResolver):
    """BLAST resolver for PDB protein database."""
    
    def __init__(self, config: RunConfig) -> None:
        """Initialize BLAST resolver for PDB protein sequences."""
        # Build database path from config - use a sensible default or empty string
        # In practice, this would be configured via config file
        db_path = getattr(config.blast, 'pdb_aa_db', '')
        super().__init__(
            config=config,
            db_path=db_path,
            is_protein=True,
            resolver_name="blast_pdb_protein",
            identifier_type="PDB_ID"
        )


class BLASTResolverPDBNT(BLASTResolver):
    """BLAST resolver for PDB nucleotide database."""
    
    def __init__(self, config: RunConfig) -> None:
        """Initialize BLAST resolver for PDB nucleotide sequences."""
        db_path = getattr(config.blast, 'pdb_nt_db', '')
        super().__init__(
            config=config,
            db_path=db_path,
            is_protein=False,
            resolver_name="blast_pdb_nucleic",
            identifier_type="PDB_ID"
        )


class BLASTResolverUNIPROT(BLASTResolver):
    """BLAST resolver for UniProt database."""
    
    def __init__(self, config: RunConfig) -> None:
        """Initialize BLAST resolver for UniProt sequences."""
        # Use uniprot_aa_db, or fall back to swissprot_aa_db if not set
        db_path = getattr(config.blast, 'uniprot_aa_db', '')
        if not db_path:
            db_path = getattr(config.blast, 'swissprot_aa_db', '')
        super().__init__(
            config=config,
            db_path=db_path,
            is_protein=True,
            resolver_name="blast_uniprot",
            identifier_type="UNIPROT_ID"
        )

class BLASTResolverNR(BLASTResolver):
    """BLAST resolver for NR (non-redundant protein) database."""
    
    def __init__(self, config: RunConfig) -> None:
        """Initialize BLAST resolver for NR protein sequences."""
        db_path = getattr(config.blast, 'nr_aa_db', '')
        super().__init__(
            config=config,
            db_path=db_path,
            is_protein=True,
            resolver_name="blast_nr_protein",
            identifier_type="NR_ID"
        )


class BLASTResolverSWISSPROT(BLASTResolver):
    """BLAST resolver for Swiss-Prot (curated protein) database."""
    
    def __init__(self, config: RunConfig) -> None:
        """Initialize BLAST resolver for Swiss-Prot protein sequences."""
        db_path = getattr(config.blast, 'swissprot_aa_db', '')
        super().__init__(
            config=config,
            db_path=db_path,
            is_protein=True,
            resolver_name="blast_swissprot_protein",
            identifier_type="SWISSPROT_ID"
        )

class BLASTResolverCORENT(BLASTResolver):
    """BLAST resolver for core_nt (core nucleotide) database."""
    
    def __init__(self, config: RunConfig) -> None:
        """Initialize BLAST resolver for core_nt nucleotide sequences."""
        db_path = getattr(config.blast, 'core_nt_db', '')
        super().__init__(
            config=config,
            db_path=db_path,
            is_protein=False,
            resolver_name="blast_core_nt",
            identifier_type="CORE_NT_ID"
        )


class BLASTResolverNT(BLASTResolver):
    """BLAST resolver for nt (full nucleotide) database."""
    
    def __init__(self, config: RunConfig) -> None:
        """Initialize BLAST resolver for nt nucleotide sequences."""
        db_path = getattr(config.blast, 'nt_db', '')
        super().__init__(
            config=config,
            db_path=db_path,
            is_protein=False,
            resolver_name="blast_nt",
            identifier_type="NT_ID"
        )

