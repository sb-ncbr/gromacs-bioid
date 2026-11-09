"""Sequence signature fetcher for proteins and nucleic acids."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time

import requests

from ..base import SignatureFetcher, TransientFetchError, memoized_fetch
from . import rcsb_cache

logger = logging.getLogger(__name__)

# Local sequence sources (image-resident BLAST DBs; env-overridable, mirroring
# the BlastConfig defaults in config/loader.py so behavior matches by default).
_BLASTDBCMD = os.environ.get("BAT3_BLASTDBCMD", "/usr/bin/blastdbcmd")
_SWISSPROT_DB = os.environ.get("BAT3_SWISSPROT_DB", "/app/databases/swissprot/swissprot")
_NR_DB = os.environ.get("BAT3_NR_DB", "/app/databases/nr/nr")
# Pod-local persistent sequence cache (successes only — definitive misses and
# transients are never persisted; env-overridable for tests).
_SEQ_CACHE = os.environ.get("BAT3_SEQ_CACHE", "/app/cache/sequence_cache")
# REST retry policy: total tries = _REST_TRIES, backoff doubles from 1 s.
_REST_TRIES = 3
_REST_TIMEOUT_S = 10


def _seqcache_path(accession: str) -> str:
    return os.path.join(_SEQ_CACHE, accession.upper() + ".seq")


def _seqcache_read(accession: str) -> str | None:
    try:
        with open(_seqcache_path(accession)) as fh:
            seq = fh.read().strip()
            return seq or None
    except OSError:
        return None


def _seqcache_write(accession: str, sequence: str) -> None:
    if not sequence:
        return
    # reviewer fix (c13 re-check): atomic write (unique tmp + os.replace).
    # Two threads in one pod can concurrently read a half-written cache
    # file - a silently truncated sequence would produce a wrong S.
    try:
        os.makedirs(_SEQ_CACHE, exist_ok=True)
        final = _seqcache_path(accession)
        tmp = f"{final}.tmp.{os.getpid()}.{threading.get_ident()}"
        with open(tmp, "w") as fh:
            fh.write(sequence)
        os.replace(tmp, final)
    except OSError:
        pass


def _blastdbcmd_sequence(accession: str) -> str | None:
    """Look the accession up in the local BLAST databases (swissprot, then nr).

    Returns None if absent everywhere or if lookup itself fails — absence from
    the local DBs is not "no sequence", it just defers to REST.
    Coverage evidence (397-sample, v3.143-b13 image): 6,975/6,975 distinct
    UniProt accessions resolve from the swissprot DB alone.
    """
    for db in (_SWISSPROT_DB, _NR_DB):
        try:
            out = subprocess.run(
                [_BLASTDBCMD, "-db", db, "-entry", accession, "-outfmt", "%s"],
                capture_output=True, text=True, timeout=15,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug(f"blastdbcmd {db} {accession} lookup failed: {exc}")
            continue
        if out.returncode == 0:
            seq = "".join(out.stdout.split())
            if seq:
                return seq
    return None


class SequenceSignatureFetcher(SignatureFetcher):
    """Fetches canonical sequences for proteins and nucleic acids."""
    
    SUPPORTED_TYPES = {"PDB_ID", "UNIPROT_ID", "ALPHAFOLD_ID", "NR_ID", "SWISSPROT_ID", "NT_ID", "CORE_NT_ID"}
    
    def supports(self, ident_type: str) -> bool:
        """Check if this fetcher supports the given identifier type."""
        return ident_type in self.SUPPORTED_TYPES
    
    @memoized_fetch
    def fetch(self, identifier: str, ident_type: str) -> str | None:
        """Fetch the canonical sequence for a protein/nucleic acid identifier.
        
        Args:
            identifier: The identifier (e.g., "1ABC" for PDB, "P04637" for UniProt).
            ident_type: The type of identifier ("PDB_ID", "UNIPROT_ID", "ALPHAFOLD_ID", 
                       "NR_ID", "SWISSPROT_ID", "NT_ID", or "CORE_NT_ID").
            
        Returns:
            The canonical sequence string (no newlines), or None if not found or on error.
        """
        try:
            if ident_type == "PDB_ID":
                return self._fetch_pdb(identifier)
            elif ident_type == "UNIPROT_ID":
                return self._fetch_uniprot(identifier)
            elif ident_type == "ALPHAFOLD_ID":
                return self._fetch_alphafold(identifier)
            elif ident_type == "NR_ID":
                return self._fetch_ncbi_protein(identifier)
            elif ident_type == "SWISSPROT_ID":
                return self._fetch_uniprot(identifier)
            elif ident_type in ("NT_ID", "CORE_NT_ID"):
                return self._fetch_ncbi_nucleotide(identifier)
            else:
                logger.warning(f"Unknown sequence ident_type: {ident_type}")
                return None
        except TransientFetchError:
            raise
        except Exception as e:
            logger.warning(f"SequenceSignatureFetcher fetch failed for {identifier}: {e}")
            return None
    
    def _fetch_pdb_entities(self, pdb_id: str) -> list[str]:
        """Fetch all polymer entity sequences from PDB.
        
        Args:
            pdb_id: The PDB ID (e.g., "1ABC").
            
        Returns:
            List of canonical sequences for all polymer entities.
            Empty list if no polymer entities found or on error.
        """
        # Strip _entity suffix if present
        if '_' in pdb_id:
            pdb_id = pdb_id.split('_', maxsplit=1)[0]
        
        pdb_id_lower = pdb_id.lower()
        
        # First, fetch entry info to get polymer entity IDs
        entry_url = f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id_lower}"
        try:
            r = rcsb_cache.get_cached(entry_url, timeout=30)
            if r is None:
                return []
            entry_data = r.json()
            
            # Extract polymer entity IDs
            container_ids = entry_data.get("rcsb_entry_container_identifiers", {})
            polymer_entity_ids = container_ids.get("polymer_entity_ids", [])
            
            if not polymer_entity_ids:
                return []
            
            sequences = []
            for entity_id in polymer_entity_ids:
                entity_url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id_lower}/{entity_id}"
                try:
                    r_entity = rcsb_cache.get_cached(entity_url, timeout=30)
                    if r_entity is None:
                        continue
                    entity_data = r_entity.json()
                    
                    seq = entity_data.get("entity_poly", {}).get("pdbx_seq_one_letter_code_can")
                    if seq:
                        seq_clean = seq.replace("\n", "")
                        if seq_clean:  # Skip empty sequences
                            sequences.append(seq_clean)
                except Exception as e:
                    logger.warning(f"PDB {pdb_id} entity {entity_id} fetch failed: {e}")
                    continue
            
            return sequences
        except Exception as e:
            logger.warning(f"PDB {pdb_id} entry fetch failed: {e}")
            return []
    
    def pdb_entity_records(self, pdb_id: str, timeout: int = 30, tries: int = 4,
                           max_entities: int | None = None) -> list[dict]:
        """Display metadata for every polymer entity of a PDB entry.

        Same cached RCSB URLs as _fetch_pdb_entities (entry + one payload per
        polymer entity), so on a verified hit this normally costs no request.
        Each record: entity_id, sequence, description (pdbx_description),
        auth_asym_ids, asym_ids, organism — any field may be None/empty.
        Empty list on any failure; never raises. timeout/tries apply to
        uncached requests (display naming passes short ones); entries with
        more than max_entities polymer entities return [] (one request each).
        """
        pdb_id = (pdb_id or "").split("_", maxsplit=1)[0].lower()
        if not pdb_id:
            return []
        try:
            r = rcsb_cache.get_cached(f"https://data.rcsb.org/rest/v1/core/entry/{pdb_id}",
                                      timeout=timeout, tries=tries)
            if r is None:
                return []
            ids = (r.json().get("rcsb_entry_container_identifiers") or {}).get("polymer_entity_ids") or []
        except Exception:
            return []
        if max_entities is not None and len(ids) > max_entities:
            return []
        records = []
        for entity_id in ids:
            try:
                re_ = rcsb_cache.get_cached(
                    f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id}/{entity_id}",
                    timeout=timeout, tries=tries)
                if re_ is None:
                    continue
                d = re_.json()
                if not isinstance(d, dict):
                    continue
                cont = d.get("rcsb_polymer_entity_container_identifiers") or {}
                orgs = d.get("rcsb_entity_source_organism")
                organism = None
                if isinstance(orgs, list) and orgs and isinstance(orgs[0], dict):
                    organism = orgs[0].get("scientific_name") or None
                seq = (d.get("entity_poly") or {}).get("pdbx_seq_one_letter_code_can")
                records.append({
                    "entity_id": str(entity_id),
                    "sequence": seq.replace("\n", "") if isinstance(seq, str) else None,
                    "description": ((d.get("rcsb_polymer_entity") or {}).get("pdbx_description") or None),
                    "auth_asym_ids": [str(x) for x in (cont.get("auth_asym_ids") or [])],
                    "asym_ids": [str(x) for x in (cont.get("asym_ids") or [])],
                    "organism": organism,
                })
            except Exception:
                continue
        return records

    def _fetch_pdb(self, pdb_id: str) -> str | None:
        """Fetch sequence from PDB (first polymer entity).
        
        Uses _fetch_pdb_entities internally and returns the first sequence.
        """
        sequences = self._fetch_pdb_entities(pdb_id)
        if sequences:
            return sequences[0]
        
        # Fallback to old behavior if entity list is empty
        # Strip _entity suffix if present
        if '_' in pdb_id:
            pdb_id = pdb_id.split('_', maxsplit=1)[0]
        
        url = f"https://data.rcsb.org/rest/v1/core/polymer_entity/{pdb_id.lower()}/1"
        try:
            r = rcsb_cache.get_cached(url, timeout=30)
            if r is None:
                return None
            data = r.json()
            seq = data.get("entity_poly", {}).get("pdbx_seq_one_letter_code_can")
            if seq:
                return seq.replace("\n", "")
            return None
        except Exception as e:
            logger.warning(f"PDB {pdb_id} fetch sequence failed: {e}")
            return None
    
    def _fetch_uniprot(self, uniprot_id: str) -> str | None:
        """Fetch sequence from UniProt (local BLAST DBs first, then REST).

        Order: pod-local sequence cache (successes only) → blastdbcmd against
        swissprot/nr → rest.uniprot.org with retry+backoff. Raises
        TransientFetchError after exhausted 5xx/timeout retries so no None
        reaches the run memo for a transient outage; a definitive 404/empty
        FASTA returns None (memozable miss).
        """
        acc = uniprot_id.strip()
        cached = _seqcache_read(acc)
        if cached:
            return cached
        seq = _blastdbcmd_sequence(acc)
        if seq:
            logger.debug(f"UniProt {acc} FASTA local-db hit")
            _seqcache_write(acc, seq)
            return seq
        url = f"https://rest.uniprot.org/uniprotkb/{uniprot_id}.fasta"
        delay = 1.0
        for attempt in range(_REST_TRIES):
            try:
                r = requests.get(url, timeout=_REST_TIMEOUT_S)
            except requests.RequestException as e:
                if attempt < _REST_TRIES - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                logger.warning(f"UniProt {uniprot_id} fetch FASTA failed: {e}")
                raise TransientFetchError(f"UniProt {acc}: {e}") from e
            transient = r.status_code >= 500 or r.status_code == 429
            if transient and attempt < _REST_TRIES - 1:
                time.sleep(delay)
                delay *= 2
                continue
            if transient:
                # reviewer fix (c13 re-check): EVERY 5xx and 429 is
                # transient - a 504 must never be memoized as a definitive
                # None miss.
                logger.warning(f"UniProt {uniprot_id} fetch FASTA failed: HTTP {r.status_code}")
                raise TransientFetchError(f"UniProt {acc}: HTTP {r.status_code}")
            if r.status_code != 200:
                # definitive miss (404) or other non-retryable status
                logger.warning(f"UniProt {uniprot_id} fetch FASTA failed: HTTP {r.status_code}")
                return None
            lines = r.text.splitlines()
            # Skip header lines (starting with '>') and join sequence lines
            seq = ''.join(line.strip() for line in lines if not line.startswith('>'))
            if seq:
                _seqcache_write(acc, seq)
            return seq if seq else None
        return None
    
    def _fetch_alphafold(self, alphafold_id: str) -> str | None:
        """Fetch sequence for an AlphaFold identifier (via UniProt).

        (v3.142) AlphaFind emits BARE UniProt accessions as identifiers
        (live probe 2026-10-19, see structure_fetcher._alphafold_accession);
        the previous strict "AF-<ACC>-F1-model_vN" parsing returned None for
        every real-world hit of that kind — corpus census: 9,161 ALPHAFOLD_ID
        rows, 0 verified / 0 worker scores / 0 annotation (total coverage
        hole). Accept both forms; a v4/v6 model's sequence is the UniProt
        canonical sequence either way. Only a malformed AF- wrapper is truly
        unusable.
        """
        try:
            ident = alphafold_id.strip().upper()
            if ident.startswith("AF-"):
                parts = ident.split('-')
                if len(parts) < 3:
                    logger.warning(
                        f"AlphaFold ID '{alphafold_id}' malformed (AF- wrapper "
                        "without accession part)")
                    return None
                ident = parts[1]
            return self._fetch_uniprot(ident)
        except TransientFetchError:
            raise
        except Exception as e:
            logger.warning(f"AlphaFold {alphafold_id} fetch FASTA failed: {e}")
            return None
    
    def _fetch_ncbi_protein(self, accession: str) -> str | None:
        """Fetch protein sequence from NCBI (for NR_ID).
        
        Uses NCBI E-utilities EFetch endpoint.
        """
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=protein&id={accession}&rettype=fasta"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            lines = r.text.splitlines()
            # Skip header lines (starting with '>') and join sequence lines
            seq = ''.join(line.strip() for line in lines if not line.startswith('>'))
            return seq if seq else None
        except Exception as e:
            logger.warning(f"NCBI protein {accession} fetch FASTA failed: {e}")
            return None
    
    def _fetch_ncbi_nucleotide(self, accession: str) -> str | None:
        """Fetch nucleotide sequence from NCBI (for NT_ID, CORE_NT_ID).
        
        Uses NCBI E-utilities EFetch endpoint.
        """
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=nuccore&id={accession}&rettype=fasta"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            lines = r.text.splitlines()
            # Skip header lines (starting with '>') and join sequence lines
            seq = ''.join(line.strip() for line in lines if not line.startswith('>'))
            return seq if seq else None
        except Exception as e:
            logger.warning(f"NCBI nucleotide {accession} fetch FASTA failed: {e}")
            return None
