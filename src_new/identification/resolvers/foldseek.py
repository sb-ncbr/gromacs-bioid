"""Foldseek 3Di structure search resolver.

v3.138 rewrite. Two execution modes (config.foldseek.mode):

- "local": foldseek binary searched against a local database prefix
  (``foldseek databases Alphafold/Swiss-Prot <prefix>`` — populated on the
  cluster PVC by the one-shot bootstrap Job). Any local-stage failure
  (missing binary, missing DB, nonzero exit, malformed output) falls back
  to remote mode so a run never loses the whole channel silently.
- "remote": public foldseek REST server (search.foldseek.com). Field name
  is ``database[]`` (validated 2026-10-19: ``Database``/``databases`` are
  rejected with "JobRequest.Job.Database required").
- "off": resolver disabled.

Targets are normalized to bare UniProt accessions (``AF-P01542-F1-model_vN``
-> ``P01542``) so local-DB (v4-era names) and REST (v6-era names) hits land
in the same identifier space.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import tempfile
import time

import requests

from ...config.loader import RunConfig
from ..base import IdentifierResolver, safe_tmp_dir

logger = logging.getLogger("identifier")

# AFDB-style wrapped target names produced by both local DBs and the REST
# server ("AF-P01542-F1-model_v4" / "..._v6", optionally with a description
# tail separated by whitespace).
_AF_TARGET_RE = re.compile(r"^AF-([A-Z0-9]+)-F\d+-model_v\d+", re.IGNORECASE)
# Bare UniProt accession (canonical + isoform), e.g. P01542, A0A023GPI8.
_UNIPROT_ACC_RE = re.compile(r"^[OPQ][0-9][A-Z0-9]{3}[0-9](-\d+)?$|^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}(-\d+)?$")

_M8_FORMAT_OUTPUT = "query,target,fident,qcov,evalue"


def normalize_foldseek_target(target: str) -> str | None:
    """Normalize a foldseek target identifier to a bare UniProt accession.

    Accepts AFDB-wrapped names ("AF-P01542-F1-model_v6 Swiss-Prot ...") and
    bare accessions; returns None for anything else (e.g. raw PDB ids that
    do not belong in this resolver's UNIPROT_ID identifier space).
    """
    parts = (target or "").split()
    if not parts:
        return None
    head = parts[0].strip()
    m = _AF_TARGET_RE.match(head)
    if m:
        return m.group(1).upper()
    if _UNIPROT_ACC_RE.match(head):
        return head
    return None


class Foldseek3DiResolver(IdentifierResolver):
    """Identifies 3Di sequences using Foldseek (local subprocess or REST)."""

    def __init__(self, config: RunConfig) -> None:
        super().__init__(config)

        self.name = "foldseek_3di"
        self.identifier_type = "UNIPROT_ID"
        self.accepted_signatures = ["3di_sequence"]

        self.config = config
        self.foldseek_config = config.foldseek

        self._binary_available = self._check_binary()

    # ------------------------------------------------------------------ #
    # applicability / availability                                        #
    # ------------------------------------------------------------------ #

    def _check_binary(self) -> bool:
        """Check if the foldseek executable is available.

        Uses the ``version`` subcommand — foldseek has no ``--version`` flag
        (rc=1, "Did you mean convertalis"; empirically verified on the
        9-427df8a static build while gating the v3.138 image).
        """
        try:
            result = subprocess.run(
                [self.foldseek_config.foldseek_exec, "version"],
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError, OSError):
            logger.warning(
                "Foldseek executable '%s' not found or not executable",
                self.foldseek_config.foldseek_exec,
            )
            return False

    def _local_db_present(self) -> bool:
        db_path = (self.foldseek_config.db_path or "").strip()
        if not db_path:
            return False
        return any(
            os.path.exists(p)
            for p in (db_path, db_path + ".index", db_path + "_ss")
        )

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature is a non-empty 3Di sequence string."""
        return bool(signature and signature.strip())

    # ------------------------------------------------------------------ #
    # resolution entry points                                             #
    # ------------------------------------------------------------------ #

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Exact-match is not practical for 3Di; always empty."""
        logger.debug("Foldseek identity search not implemented for 3Di sequences")
        return []

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        mode = (self.foldseek_config.mode or "local").strip().lower()

        if mode == "off":
            logger.info("Foldseek resolver disabled via config (mode=off)")
            return []

        if mode == "remote":
            return self._remote_search(signature) or []

        # mode == "local" (default): local search with remote fallback
        if not self._binary_available:
            logger.warning("Foldseek binary unavailable; falling back to remote mode")
            return self._remote_search(signature) or []
        if not self._local_db_present():
            logger.warning(
                "Foldseek local DB missing at '%s'; falling back to remote mode",
                self.foldseek_config.db_path,
            )
            return self._remote_search(signature) or []

        try:
            results = self._local_search(signature, working_directory)
        except Exception as exc:  # defensive: resolver must never kill a run
            logger.warning(f"Foldseek local search raised: {exc}")
            results = None

        if results is None:
            logger.warning("Foldseek local search failed; falling back to remote mode")
            return self._remote_search(signature) or []
        return results

    # ------------------------------------------------------------------ #
    # local mode                                                          #
    # ------------------------------------------------------------------ #

    def _local_search(self, signature: str, working_directory: str) -> list[tuple[str, float]] | None:
        """Run createdb+search against the local DB.

        Returns:
            List of (UniProt accession, score 0-100) tuples, possibly empty;
            None on any local-stage failure (triggers remote fallback).
        """
        tmp_dir = tempfile.mkdtemp(prefix="foldseek_", dir=safe_tmp_dir(working_directory))
        try:
            query_fasta = os.path.join(tmp_dir, "query.fasta")
            query_db = os.path.join(tmp_dir, "query_db")
            output_m8 = os.path.join(tmp_dir, "results.m8")

            with open(query_fasta, "w") as f:
                f.write(">query\n" + signature.strip() + "\n")

            createdb = subprocess.run(
                [self.foldseek_config.foldseek_exec, "createdb", query_fasta, query_db],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if createdb.returncode != 0:
                logger.error(f"Foldseek createdb failed: {createdb.stderr}")
                return None

            search = subprocess.run(
                [
                    self.foldseek_config.foldseek_exec,
                    "search",
                    query_db,
                    self.foldseek_config.db_path,
                    output_m8,
                    "--format-output",
                    _M8_FORMAT_OUTPUT,
                ],
                capture_output=True,
                text=True,
                timeout=self.foldseek_config.search_timeout_s,
            )
            if search.returncode != 0:
                logger.error(f"Foldseek search failed: {search.stderr}")
                return None

            return self._parse_m8(output_m8)
        except subprocess.TimeoutExpired:
            logger.error("Foldseek local search timed out")
            return None
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def _parse_m8(self, m8_path: str) -> list[tuple[str, float]]:
        """Parse query,target,fident,... TSV rows into (UniProt acc, 0-100) tuples."""
        results: list[tuple[str, float]] = []
        try:
            with open(m8_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split("\t")
                    if len(parts) < 3:
                        continue
                    acc = normalize_foldseek_target(parts[1])
                    if acc is None:
                        continue
                    try:
                        fident = float(parts[2])
                    except ValueError:
                        continue
                    results.append((acc, fident * 100.0))
                    if len(results) >= self.foldseek_config.max_target_hits:
                        break
        except IOError as exc:
            logger.error(f"Failed to read M8 output: {exc}")
        return results

    # ------------------------------------------------------------------ #
    # remote mode (public foldseek REST)                                  #
    # ------------------------------------------------------------------ #

    def _remote_search(self, signature: str) -> list[tuple[str, float]] | None:
        """Submit a 3diaa job to the foldseek REST server and collect hits.

        Returns:
            List of (UniProt accession, score 0-100) tuples, possibly empty;
            None when the remote channel itself fails.
        """
        cfg = self.foldseek_config
        url = (cfg.remote_url or "").rstrip("/")
        try:
            submit = requests.post(
                f"{url}/ticket",
                files={"q": ("query.fasta", f">query\n{signature.strip()}\n")},
                data={"mode": "3diaa", "database[]": cfg.remote_database},
                timeout=cfg.remote_timeout_s,
            )
            submit.raise_for_status()
            ticket = submit.json()
            ticket_id = ticket.get("id")
            if not ticket_id:
                logger.warning(f"Foldseek remote: no ticket id in response: {ticket}")
                return None

            delay = max(0.5, float(cfg.remote_poll_interval_s))
            polls = max(1, int(cfg.remote_polls))
            for _ in range(polls):
                status_r = requests.get(f"{url}/ticket/{ticket_id}", timeout=cfg.remote_timeout_s)
                if status_r.status_code != 200:
                    time.sleep(delay)
                    continue
                status = status_r.json().get("status")
                if status == "COMPLETE":
                    break
                if status == "ERROR":
                    logger.warning(f"Foldseek remote: job {ticket_id} reported ERROR")
                    return None
                time.sleep(delay)
            else:
                logger.warning(f"Foldseek remote: budget exhausted waiting for {ticket_id}")
                return None

            result_r = requests.get(f"{url}/result/{ticket_id}/0", timeout=cfg.remote_timeout_s)
            result_r.raise_for_status()
            return self._parse_rest_result(result_r.json())
        except Exception as exc:
            logger.warning(f"Foldseek remote search failed: {exc}")
            return None

    def _parse_rest_result(self, payload: dict) -> list[tuple[str, float]]:
        """Parse the REST /result payload into (UniProt acc, 0-100) tuples.

        Payload shape (probed 2026-10-19):
        ``results[0].alignments[i]`` with keys ``target``, ``seqId`` (0..1
        fraction), ``eval``, ``prob``, coordinates, etc.
        """
        results: list[tuple[str, float]] = []
        for entry in (payload or {}).get("results", []):
            for aln in entry.get("alignments", []):
                acc = normalize_foldseek_target(aln.get("target", ""))
                if acc is None:
                    continue
                try:
                    seqid = float(aln.get("seqId", 0.0))
                except (TypeError, ValueError):
                    continue
                results.append((acc, seqid * 100.0))
                if len(results) >= self.foldseek_config.max_target_hits:
                    return results
        return results
