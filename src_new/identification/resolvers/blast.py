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
from ..base import IdentifierResolver, IdentifierResolutionError, safe_tmp_dir

# Import residue/nucleic codes for alphabet validation.
# F-27 (2026-10-05): single source of truth is src_new/constants.py
# (byte-value-identical promotion from src.constants, md5-verified).
# The old try/except "isolated execution" fallback carried SUBSET copies
# (20/54 residues, 15/80 nucleic codes) = silent degraded validation;
# deleted per ruling so this module always uses the canonical tables.
from ...constants import KNOWN_RESIDUE_CODES, KNOWN_NUCLEIC_ACIDS_CODES

logger = logging.getLogger("identifier")


@dataclass
class BlastHit:
    """Represents a BLAST hit."""
    accessions: list[str]
    evalue: float
    bits: float
    identity_p: float
    coverage_p: float
    subject_len: int | None = None  # F-N1c: needed for both-directions exact rule


# F-N1c: exact short identity rule applies only to nucleotide queries up to
# this length. Rationale (measured 2026-10-03 over the campaign pdbnt DB on the
# full 824-sequence hitless short cohort): a perfect L-mer self-match scores
# eval ~L*DB*2^-bits, physically unreachable to the 51-bit/1e-50 identity gates
# for L<=22ish; 55/824 sequences have true 100% full-length matches (all <=12mers,
# the rest mostly 20-mers with none), 53 of them also subject-length-exact.
_SHORT_IDENTITY_MAX_QLEN = 25


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

    # Maximum fraction of non-alphabet characters tolerated in a sequence.
    # Real structures routinely contain unknown (X) or modified residues;
    # rejecting the whole protein over a few such positions silently
    # destroys recall (INCIDENT_REGISTRY_2026-09 P0-6).
    _MAX_INVALID_CHAR_FRACTION = 0.5
    _MIN_SEQUENCE_LENGTH = 10

    def _valid_chars(self) -> set:
        if self.is_protein:
            return set(v.upper() for v in KNOWN_RESIDUE_CODES.values())
        return set(v.upper() for v in KNOWN_NUCLEIC_ACIDS_CODES.values())

    def _sanitize_sequence(self, signature: str) -> str:
        """Replace non-alphabet characters with wildcards (X / N)."""
        valid = self._valid_chars()
        wildcard = "X" if self.is_protein else "N"
        return "".join(c if c in valid else wildcard for c in signature.upper().strip())

    def _is_applicable(self, signature: str) -> bool:
        """
        Check if signature is applicable for BLAST.

        Accepts sequences that are long enough and whose fraction of
        unknown/modified-residue characters is below the tolerance.
        Offending characters are sanitized to wildcards before search.
        """
        if not signature or len(signature.strip()) == 0:
            return False

        seq_upper = signature.upper().strip()
        if len(seq_upper) < self._MIN_SEQUENCE_LENGTH:
            return False

        valid_chars = self._valid_chars()
        invalid = sum(1 for c in seq_upper if c not in valid_chars)
        if invalid and (invalid / len(seq_upper)) > self._MAX_INVALID_CHAR_FRACTION:
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
        tmp_dir = safe_tmp_dir(working_directory)

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
                input=self._sanitize_sequence(sequence),
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
                
                results.append(BlastHit(accessions, evalue, bits, identity_p, coverage_p,
                                        subject_len=hit.get("len")))
        
        return results

    def _filter_blast_results(self, results: list[BlastHit], 
                              filter_func: Callable[[BlastHit], bool]) -> list[BlastHit]:
        """Filter BLAST results."""
        return [hit for hit in results if filter_func(hit)]

    def _run_blast_identity(self, sequence: str, working_directory: str) -> list[str]:
        """Execute identity search with BLAST."""
        raw_json = self._run_blast_local(sequence, working_directory)
        hits = self._process_blast_results(raw_json)

        # Apply filters for exact matches
        strict_hits = self._filter_blast_results(
            hits,
            lambda hit: hit.evalue <= self.blast_config.exact_match_max_evalue,
        )
        strict_hits = self._filter_blast_results(
            strict_hits,
            lambda hit: hit.bits >= self.blast_config.exact_match_min_bits,
        )
        strict_hits = self._filter_blast_results(
            strict_hits,
            lambda hit: hit.identity_p >= self.blast_config.exact_match_min_identity_p,
        )
        strict_hits = self._filter_blast_results(
            strict_hits,
            lambda hit: hit.coverage_p >= self.blast_config.exact_match_min_query_cov_p,
        )

        # Capture metadata for each hit
        metadata: dict[str, dict] = {}
        for hit in strict_hits:
            meta = {
                "evalue": hit.evalue,
                "bit_score": hit.bits,
                "identity_p": hit.identity_p,
                "coverage_p": hit.coverage_p,
            }
            for accession in hit.accessions:
                metadata[accession] = meta

        accepted: list[str] = [accession for hit in strict_hits for accession in hit.accessions]

        # F-N1c: exact short identity override (nucleotide queries only,
        # len <= _SHORT_IDENTITY_MAX_QLEN). A 100%-identical, full-query-length,
        # subject-length-EXACT match is an identity claim regardless of the
        # evalue/bit-score length ceiling that makes short-mers unreachable for
        # the strict gates. Both-directionality (subject_len == query_len) is
        # required: a 16-mer contained inside a long rRNA is NOT the same
        # molecule. Protein path and the nucleotide similarity path unchanged.
        query_len = len(sequence.strip()) if sequence else 0
        if not self.is_protein and 0 < query_len <= _SHORT_IDENTITY_MAX_QLEN:
            accepted_set = set(accepted)
            for hit in hits:
                if (
                    hit.identity_p == 1.0
                    and hit.coverage_p == 1.0
                    and hit.subject_len is not None
                    and hit.subject_len == query_len
                ):
                    for accession in hit.accessions:
                        if accession not in accepted_set:
                            accepted.append(accession)
                            accepted_set.add(accession)
                            metadata[accession] = {
                                "evalue": hit.evalue,
                                "bit_score": hit.bits,
                                "identity_p": hit.identity_p,
                                "coverage_p": hit.coverage_p,
                                "note": f"exact_short_identity_len_le_{_SHORT_IDENTITY_MAX_QLEN}",
                            }

        self._last_resolution_metadata = metadata
        return accepted

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

