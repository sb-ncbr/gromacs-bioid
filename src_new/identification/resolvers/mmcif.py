"""mmCIF structure identifier resolver using RCSB Search API."""

from __future__ import annotations

import logging
import os
import re
import tempfile

import requests

from ...config.loader import RunConfig
from ...signatures.generators.topology_less_pdb import _pdb_atom_line
from ..base import IdentifierResolver, IdentifierResolutionError, safe_tmp_dir
# _pdb_atom_line is the single home of the PDB ATOM-line format RCSB
# accepted live (2026-11-01 probe); the mmCIF->PDB converter reuses it.
from ...constants import FORCE_FIELD_RESIDUE_PARENTS
from ._rcsb_search import merge_hit_lists, post_rcsb_query, split_oversized_query
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
        comp = FORCE_FIELD_RESIDUE_PARENTS.get(comp, comp)  # c13 S4: CYX/HIE...
        if comp in _AMINO_RESNAMES:
            amino.add(comp)
        elif comp in _NA_RESNAMES:
            na.add(comp)
    return amino, na


def _atom_site_rows(text: str) -> tuple[list[str], list[list[str]]]:
    """Parse the first ``_atom_site`` loop into (column names, data rows).

    Minimal generated mmCIF carries a single bare loop with unquoted,
    whitespace-separated values; anything non-conforming yields empty
    results and callers keep the original query path.
    """
    lines = text.splitlines()
    columns: list[str] = []
    rows: list[list[str]] = []
    i = 0
    while i < len(lines):
        if lines[i].strip() != "loop_":
            i += 1
            continue
        j = i + 1
        cols: list[str] = []
        while j < len(lines) and lines[j].strip().startswith("_"):
            cols.append(lines[j].strip())
            j += 1
        if cols and all(c.startswith("_atom_site.") for c in cols):
            for k in range(j, len(lines)):
                tok = lines[k].strip()
                if not tok or tok == "#" or tok.startswith(("_", "loop_", "data_")):
                    break
                parts = [p.strip().strip("'\"") for p in tok.split()]
                if len(parts) == len(cols):
                    rows.append(parts)
            return cols, rows
        return [], []
    return [], []


def _mmcif_text_to_pdb(text: str) -> str | None:
    """Convert OUR minimal generated mmCIF text to PDB format.

    W3.3 item 1 (live probe 2026-11-01): RCSB's structure-search backend
    rejects our bare-loop mmCIF payloads server-side (HTTP 500) while the
    same structure staged as PDB through the identical adhoc route is
    accepted (HTTP 200, hits). Genuine full mmCIF (declares
    ``_entity_poly.type``) parses fine upstream and stays on the
    ``format: "cif"`` path — this converter only fires for the generated
    minimal format (atom_site loop, no polymer entities).

    Returns the PDB text, or None when the input is not the minimal
    generated format / has no parsable atom rows.
    """
    if "_atom_site.group_PDB" not in text or "_entity_poly.type" in text:
        return None
    columns, rows = _atom_site_rows(text)
    if not columns or not rows:
        return None

    idx = {name: n for n, name in enumerate(columns)}

    def col(row: list[str], name: str) -> str:
        n = idx.get(f"_atom_site.{name}")
        if n is None:
            return ""
        value = row[n]
        return "" if value in ("?", ".") else value

    lines = ["HEADER export"]
    resseq_fallback = 0
    last_res_key: tuple[str, str] | None = None
    for serial, row in enumerate(rows, start=1):
        chain = col(row, "label_asym_id") or "A"
        resseq_token = col(row, "label_seq_id")
        res_key = (chain, resseq_token)
        if res_key != last_res_key:
            resseq_fallback += 1
            last_res_key = res_key
        try:
            residue_idx = int(resseq_token) if resseq_token else resseq_fallback
        except ValueError:
            residue_idx = resseq_fallback
        try:
            x = float(col(row, "Cartn_x"))
            y = float(col(row, "Cartn_y"))
            z = float(col(row, "Cartn_z"))
        except ValueError:
            continue
        atom_name = col(row, "label_atom_id") or col(row, "type_symbol") or "X"
        residue_name = col(row, "label_comp_id") or "UNK"
        element = col(row, "type_symbol") or "".join(
            ch for ch in atom_name if ch.isalpha())[:2]
        lines.append(_pdb_atom_line(
            serial, atom_name, element, residue_name, residue_idx,
            x, y, z, chain_id=chain))
    if len(lines) == 1:
        return None
    lines.append("END")
    return "\n".join(lines) + "\n"


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


def _no_polymer_mmcif_payload(text: str) -> bool:
    """c13 S4: True for OUR minimal generated mmCIF whose atom rows carry no
    amino-acid or nucleotide residue — a small-molecule segment. RCSB
    structure search rejects such a query with HTTP 400 ("We could not
    process your search request", live probe 2026-11-04 on T02's 39-atom
    ligand), which the 397 sample logged 66-294 times per arm as
    structure_search_unavailable after a wasted 10 s settle-retry. Full
    mmCIF (declares _entity_poly.type) and unclassifiable text return False
    (server decides)."""
    if _ENTITY_POLY_TYPE_RE.search(text) or "_atom_site.label_comp_id" not in text:
        return False
    amino, na = _resname_token_sets(text)
    if amino or na:
        return False
    return any(line.startswith(("ATOM", "HETATM")) for line in text.splitlines())


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
        if _no_polymer_mmcif_payload(signature):
            logger.info(
                "RCSB structure search skipped (mmcif): no polymer residues "
                "in the payload (small-molecule segment); verdict=no_polymer_payload"
            )
            self._last_error = "no_polymer_payload"
            return []

        # W3.3 item 1: RCSB rejects our minimal generated mmCIF (HTTP 500,
        # live probe 2026-11-01) but accepts the same structure as PDB
        # (HTTP 200, hits) through the identical staging route. Route the
        # generated minimal format through a PDB conversion; genuine full
        # mmCIF (declares polymer entities) stays on format "cif".
        query_text = signature
        query_format = "cif"
        pdb_text = _mmcif_text_to_pdb(signature)
        if pdb_text is not None:
            query_text = pdb_text
            query_format = "pdb"

        # g1: RCSB rejects large query assemblies (HTTP 400 / gateway
        # timeout); converted PDB queries are split per chain and merged
        if query_format == "pdb":
            queries = split_oversized_query(query_text)
            if len(queries) > 1:
                logger.info(f"RCSB structure query oversized; split into "
                            f"{len(queries)} per-chain queries")
                hit_lists, errors = [], []
                for q in queries:
                    self._last_error = None
                    hit_lists.append(self._similarity_one(q, query_format, working_directory))
                    if self._last_error:
                        errors.append(self._last_error)
                # a failed chain is only an error when no chain got through
                self._last_error = errors[0] if len(errors) == len(queries) else None
                return merge_hit_lists(hit_lists)
        return self._similarity_one(query_text, query_format, working_directory)

    def _similarity_one(self, query_text: str, query_format: str,
                        working_directory: str) -> list[tuple[str, float]]:
        """One RCSB similarity search for a query text."""
        # Create temp file for the query structure
        fd, q_path = tempfile.mkstemp(
            suffix=f".{query_format}", dir=safe_tmp_dir(working_directory))
        os.close(fd)

        try:
            with open(q_path, 'w') as f:
                f.write(query_text)

            results = self._mmcif_similarity_search(q_path, query_format)
            return results
        except Exception as exc:
            # A9 (BH-044): never fail silently — the manager's not-result
            # path records _last_error as a stage error/warning.
            self._last_error = str(exc)
            logger.warning(f"MmCif structure resolution failed: {exc}")
            return []
        finally:
            if os.path.exists(q_path):
                os.unlink(q_path)

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

    def _fetch_mmcif_similarity(self, remote_path: str, query_format: str = "cif") -> dict:
        """
        Execute RCSB structural similarity search for a staged structure file.

        Args:
            remote_path: URL to the staged file.
            query_format: RCSB value.format — "cif" for genuine full mmCIF,
                "pdb" for our converted minimal generated payload.

        Returns:
            JSON response from RCSB API.

        Raises:
            IdentifierResolutionError: On request failure.
        """
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
                                "format": query_format
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
        logger.debug(f"Querying RCSB API for structure '{remote_path}' (format={query_format})")
        # W3.3 item 1: shared POST with one settle-retry on HTTP response
        # errors (api-pod NFS negative-cache race -> RCSB fetch 404).
        return post_rcsb_query(request)

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

    def _stage_adhoc_url(self, file_path: str, suffix: str = ".cif") -> str | None:
        """A9 (BH-044): write the query structure file to the shared adhoc
        directory as <sha256><suffix> and return its run-independent public
        URL. Returns None when adhoc staging is not configured/possible;
        callers then keep the legacy per-run URL path."""
        adhoc_dir = getattr(self.config.pdb, "adhoc_files_dir", "") or \
            os.environ.get("BAT3_ADHOC_DIR", "")
        if not adhoc_dir:
            return None
        try:
            import hashlib
            from pathlib import Path
            root = Path(adhoc_dir)
            root.mkdir(parents=True, exist_ok=True)
            content = Path(file_path).read_bytes()
            sha = hashlib.sha256(content).hexdigest()
            target = root / f"{sha}{suffix}"
            if not target.exists():
                tmp = root / f".{sha}.tmp"
                tmp.write_bytes(content)
                os.replace(tmp, target)  # atomic publish
            base = self.config.pdb.deployment_file_url.rstrip('/')
            return f"{base}/files/adhoc/{sha}{suffix}"
        except Exception as exc:
            logger.warning(f"adhoc staging failed: {exc}")
            return None

    def _mmcif_similarity_search(self, q_path: str, query_format: str = "cif") -> list[tuple[str, float]]:
        """
        Execute complete mmCIF similarity search workflow.
        
        Args:
            q_path: Path to the query structure file.
            query_format: RCSB value.format for the staged file.
            
        Returns:
            List of (PDB ID, similarity percentage) tuples.
        """
        logger.debug(f"Resolving mmCIF similarity search for '{q_path}' ({query_format})")
        suffix = f".{query_format}"
        
        # Check if deployment file access is enabled
        if self.config.pdb.use_deployment_file_access:
            # A9 (BH-044): prefer the run-independent adhoc URL — Celery
            # runs are not in the API registry, so /files/{uuid}/...
            # returned 404 for ALL of them (structure search silently off).
            remote_path = self._stage_adhoc_url(q_path, suffix)
            if remote_path is None:
                filename = os.path.basename(q_path)
                uuid = self.config.pdb.curr_uuid
                if not uuid:
                    logger.warning("mmCIF query skipped: curr_uuid is empty")
                    return []
                base = self.config.pdb.deployment_file_url.rstrip('/')
                remote_path = f"{base}/files/{uuid}/input/{filename}"
            logger.info(f"mmCIF query remote_path: {remote_path}")
            
            # Fetch similar structures
            response = self._fetch_mmcif_similarity(remote_path, query_format)
            return self._parse_mmcif_response(response)
        else:
            # Upload mode via SSH
            remote_path = self._upload_cif_file(q_path)
            if remote_path is None:
                logger.warning("mmCIF upload not available and deployment file access disabled; skipping search")
                return []
            logger.info(f"mmCIF upload mode remote_path: {remote_path}")
            
            # Fetch similar structures
            response = self._fetch_mmcif_similarity(remote_path, query_format)
            results = self._parse_mmcif_response(response)
            
            # Clean up uploaded file
            self._delete_cif_file(remote_path)
            
            return results
