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
    subject_cov_p: float | None = None  # v3.143 (C-21): merged subject coverage
    # D-13 (Fix B): merged subject alignment span (1-based, inclusive) and the
    # longest unaligned subject stretch BETWEEN HSPs — the geometry the
    # terminal-overhang subject-coverage rule needs to tell expression tags /
    # unobserved termini apart from domain-in-larger-protein matches.
    subject_span: tuple[int, int] | None = None
    subject_max_internal_gap: int | None = None


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
        # D-13 (2a): processed-hits cache, one BLAST run per (db, sequence)
        self._processed_hits_cache: dict[tuple[str, str], list[BlastHit]] = {}

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

            # v3.143 (C-16): a single BLAST subprocess must not run past the
            # stage deadline (timeout was a fixed config 300 s).
            result = subprocess.run(
                cmd,
                input=self._sanitize_sequence(sequence),
                text=True,
                capture_output=True,
                timeout=self._call_timeout(timeout_s),
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
                hsps: list[dict] = hit["hsps"]
                # v3.143 (C-21): pool ALL HSPs (was: hsps[0] only — split or
                # multidomain alignments lost coverage). Coverage is computed
                # from MERGED alignment intervals, not align_len/query_len:
                # align_len counts gap columns, so the old formula could
                # exceed 1.0 and gaps inflated it. Identity stays
                # identity/align_len pooled over HSPs.
                total_identity = sum(h.get("identity", 0) for h in hsps)
                total_align = sum(h.get("align_len", 0) for h in hsps)
                identity_p = total_identity / total_align if total_align > 0 else 0.0

                def _merged_coverage(k_from: str, k_to: str, total_len) -> float | None:
                    ivs = sorted(
                        (h[k_from], h[k_to]) for h in hsps
                        if k_from in h and k_to in h
                    )
                    if not ivs:
                        return None
                    covered = 0
                    cs, ce = ivs[0]
                    for st, en in ivs[1:]:
                        if st <= ce + 1:
                            ce = max(ce, en)
                        else:
                            covered += ce - cs + 1
                            cs, ce = st, en
                    covered += ce - cs + 1
                    return covered / total_len if total_len > 0 else 0.0

                def _subject_geometry() -> tuple[tuple[int, int] | None, int | None]:
                    """D-13 (Fix B): merged subject span + longest internal
                    unaligned gap (1-based inclusive coords; None = unknown)."""
                    ivs = sorted(
                        (h["hit_from"], h["hit_to"]) for h in hsps
                        if "hit_from" in h and "hit_to" in h
                    )
                    if not ivs:
                        return None, None
                    span_lo, span_hi = ivs[0][0], ivs[0][1]
                    max_gap, ce = 0, ivs[0][1]
                    for st, en in ivs[1:]:
                        if st > ce + 1:
                            max_gap = max(max_gap, st - ce - 1)
                        span_lo = min(span_lo, st)
                        ce = max(ce, en)
                        span_hi = max(span_hi, en)
                    return (span_lo, span_hi), max_gap

                qcov = _merged_coverage("query_from", "query_to", query_len)
                if qcov is None:  # malformed payload: keep legacy estimate
                    qcov = total_align / query_len if query_len > 0 else 0.0
                subject_len = hit.get("len")
                scov = (_merged_coverage("hit_from", "hit_to", subject_len)
                        if subject_len else None)
                subj_span, subj_gap = _subject_geometry()
                # Pooled long-run gates stay meaningful: strictest evalue and
                # best bit score across the hit's HSPs.
                bits: float = max((h.get("bit_score", 0.0) for h in hsps), default=0.0)
                evalue: float = min((h.get("evalue", 1.0) for h in hsps), default=1.0)

                results.append(BlastHit(accessions, evalue, bits, identity_p, qcov,
                                        subject_len=subject_len,
                                        subject_cov_p=scov,
                                        subject_span=subj_span,
                                        subject_max_internal_gap=subj_gap))
        
        return results

    def _filter_blast_results(self, results: list[BlastHit], 
                              filter_func: Callable[[BlastHit], bool]) -> list[BlastHit]:
        """Filter BLAST results."""
        return [hit for hit in results if filter_func(hit)]

    def _processed_hits(self, sequence: str, working_directory: str) -> list[BlastHit]:
        """D-13 (2a): ONE BLAST run per (resolver, signature) — the identity
        and similarity tiers are two views over the same processed hits
        (previously each phase re-ran blastp, doubling the protein BLAST
        wall time that dominates the identify stage)."""
        cache = getattr(self, "_processed_hits_cache", None)
        if cache is None:
            cache = self._processed_hits_cache = {}
        key = (self.db_path, sequence)
        if key not in cache:
            cache[key] = self._process_blast_results(
                self._run_blast_local(sequence, working_directory)
            )
        return cache[key]

    # --- D-13 protein identity gate (C-03) as a pure per-hit predicate ---
    # Threshold order preserved: identity -> qcov -> scov; the first
    # failing gate is recorded so similarity metadata can say WHY an
    # exact-looking hit stayed similarity (2d).

    def _identity_thresholds(self) -> tuple[float, float]:
        id_min = max(0.99, self.blast_config.exact_match_min_identity_p)
        qcov_min = max(0.99, self.blast_config.exact_match_min_query_cov_p)
        return id_min, qcov_min

    def _subject_cov_ok(self, hit: BlastHit) -> bool:
        """C-03 subject-coverage gate: a short exact alignment inside a
        much larger subject is not the same molecule (58-aa ligase inside a
        580-aa fusion). Unknown coverage stays admissible (legacy)."""
        return hit.subject_cov_p is None or hit.subject_cov_p >= 0.9

    def _identity_gate_fail(self, hit: BlastHit) -> str | None:
        """None if the hit passes the protein C-03 identity gate, else the
        first failing gate name: 'identity' | 'qcov' | 'scov'."""
        id_min, qcov_min = self._identity_thresholds()
        if hit.identity_p < id_min:
            return "identity"
        if hit.coverage_p < qcov_min:
            return "qcov"
        if not self._subject_cov_ok(hit):
            return "scov"
        return None

    def _run_blast_identity(self, sequence: str, working_directory: str) -> list[str]:
        """Execute identity search with BLAST."""
        hits = self._processed_hits(sequence, working_directory)

        # Apply filters for exact matches
        if self.is_protein:
            # v3.143 (C-03): length-aware protein identity. evalue/bit-score
            # scale with query length x database size, so the strict gates
            # (e <= 1e-50, bits >= 51) are physically unreachable below
            # ~75-80 aa and arbitrary near the boundary (composition-based
            # statistics give IDENTICAL subjects different evalues; probe:
            # ubiquitin76 on pdbaa kept 9 of 70+1314 perfect matches, BPTI/
            # villin/insulin kept 0; the lost perfects were not even kept as
            # similarity because identity-hits-present skips the phase).
            # Protein identity is therefore defined on absolute measures
            # only: identity >= 0.99, true query coverage >= 0.99 (C-21 math)
            # and subject coverage >= 0.9 (a 58-aa exact alignment inside a
            # 580-aa fusion protein is not the same molecule). The F-N1c
            # nucleotide rule below already worked this way; evalue/bits keep
            # gating the SIMILARITY path unchanged.
            strict_hits = [h for h in hits if self._identity_gate_fail(h) is None]
        else:
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
                "subject_cov_p": hit.subject_cov_p,  # additive (C-21)
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
        hits = self._processed_hits(sequence, working_directory)

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
        
        # Capture metadata for each hit. D-13 (2d): similarity rows now
        # carry subject coverage AND, for protein hits that failed the
        # identity gate, the first failing gate — so a rerun's gate-fail
        # classes are measurable offline (the A/B ablation needs this) and
        # the UI can show "{p}% identity over {c}%".
        metadata: dict[str, dict] = {}
        for hit in hits:
            meta = {
                "evalue": hit.evalue,
                "bit_score": hit.bits,
                "identity_p": hit.identity_p,
                "coverage_p": hit.coverage_p,
                "subject_cov_p": hit.subject_cov_p,
            }
            if self.is_protein:
                fail = self._identity_gate_fail(hit)
                if fail is not None:
                    meta["identity_gate_fail"] = fail
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
            identifier_type="UNIPROT_ID"
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

