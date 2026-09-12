"""Compound signature fetcher for small molecules."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time

import requests

from ..base import SignatureFetcher

logger = logging.getLogger(__name__)

_SIM_CACHE = "/data/validation/sim_cache/pubchem_smiles"
_MIN_INTERVAL_S = 0.34         # keep the whole pipeline under PubChem's ~3 rps
_last_request_ts = 0.0


def _cache_path(cid: str) -> str:
    return os.path.join(_SIM_CACHE, hashlib.sha1(f"cid:{cid}".encode()).hexdigest()[:24] + ".json")


def _cache_read(cid: str):
    try:
        with open(_cache_path(cid)) as fh:
            return json.load(fh)
    except Exception:
        return None


def _cache_write(cid: str, smiles) -> None:
    try:
        os.makedirs(_SIM_CACHE, exist_ok=True)
        with open(_cache_path(cid), "w") as fh:
            json.dump(smiles, fh)
    except OSError:
        pass


def _polite_get(url: str, tries: int = 4) -> requests.Response | None:
    """GET with rate-limit etiquette: min interval + 429/503 backoff."""
    global _last_request_ts
    delay = 1.5
    for attempt in range(tries):
        gap = time.time() - _last_request_ts
        if gap < _MIN_INTERVAL_S:
            time.sleep(_MIN_INTERVAL_S - gap)
        try:
            r = requests.get(url, timeout=15)
            _last_request_ts = time.time()
        except Exception as exc:
            logger.warning(f"GET failed {url}: {exc}")
            return None
        status = r.status_code if isinstance(getattr(r, "status_code", None), int) else 200
        if status in (429, 500, 502, 503) and attempt < tries - 1:
            time.sleep(delay)
            delay *= 2
            continue
        if status >= 400:
            # 404/400 (unknown/bad id) and other 4xx: fail soft like the old path
            return None
        r.raise_for_status()
        return r
    return None


def prefetch_pubchem(cids) -> int:
    """Batch-warm the NFS SMILES cache for a list of CIDs (CSV chunked).

    Returns number of CIDs fetched over HTTP (others were already cached).
    """
    todo = [str(c) for c in cids if c and _cache_read(str(c)) is None]
    fetched = 0
    for i in range(0, len(todo), 50):
        chunk = todo[i:i + 50]
        url = ("https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/"
               + ",".join(chunk) + "/property/CanonicalSMILES/JSON")
        r = _polite_get(url)
        if r is None:
            continue
        try:
            props = r.json().get("PropertyTable", {}).get("Properties", [])
            got = set()
            for item in props:
                cid = str(item.get("CID") or item.get("cid") or "")
                smi = item.get("CanonicalSMILES") or item.get("SMILES") or item.get("ConnectivitySMILES")
                if cid:
                    _cache_write(cid, smi)
                    got.add(cid)
            fetched += len(got)
        except Exception as exc:
            logger.warning(f"prefetch parse failed: {exc}")
    return fetched


class CompoundSignatureFetcher(SignatureFetcher):
    """Fetches canonical SMILES for compound identifiers."""
    
    SUPPORTED_TYPES = {"PUBCHEM_CID", "CHEMBL_ID", "CHEBI_ID"}
    
    def supports(self, ident_type: str) -> bool:
        """Check if this fetcher supports the given identifier type."""
        return ident_type in self.SUPPORTED_TYPES
    
    def fetch(self, identifier: str, ident_type: str) -> str | None:
        """Fetch the canonical SMILES for a compound identifier.
        
        Args:
            identifier: The compound identifier (e.g., "962" for PubChem CID).
            ident_type: The type of identifier ("PUBCHEM_CID", "CHEMBL_ID", or "CHEBI_ID").
            
        Returns:
            The canonical SMILES string, or None if not found or on error.
        """
        try:
            if ident_type == "PUBCHEM_CID":
                return self._fetch_pubchem(identifier)
            elif ident_type == "CHEMBL_ID":
                return self._fetch_chembl(identifier)
            elif ident_type == "CHEBI_ID":
                return self._fetch_chebi(identifier)
            else:
                logger.warning(f"Unknown compound ident_type: {ident_type}")
                return None
        except Exception as e:
            logger.warning(f"CompoundSignatureFetcher fetch failed for {identifier}: {e}")
            return None
    
    def _fetch_pubchem(self, cid: str) -> str | None:
        """Fetch SMILES from PubChem (NFS cached + polite HTTP)."""
        cached = _cache_read(str(cid))
        if cached is not None:
            return cached
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/CanonicalSMILES/TXT"
        r = _polite_get(url)
        if r is None:
            logger.warning(f"PubChem {cid} fetch SMILES failed after retries")
            return None
        smiles = r.text.strip() or None
        _cache_write(str(cid), smiles)
        return smiles
    
    def _fetch_chembl(self, chembl_id: str) -> str | None:
        """Fetch SMILES from ChEMBL."""
        # Canonicalize: strip CHEMBL prefix if present, then prepend it back
        chembl_id = chembl_id.upper()
        if chembl_id.startswith("CHEMBL"):
            chembl_id = chembl_id[6:]  # Strip prefix
        chembl_id = f"CHEMBL{chembl_id}"
        url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            return data.get("molecule_structures", {}).get("canonical_smiles")
        except Exception as e:
            logger.warning(f"ChEMBL {chembl_id} fetch SMILES failed: {e}")
            return None
    
    def _fetch_chebi(self, chebi_id: str) -> str | None:
        """Fetch SMILES from ChEBI."""
        # Strip CHEBI: prefix if present
        chebi_num = chebi_id.upper()
        if chebi_num.startswith("CHEBI:"):
            chebi_num = chebi_num[6:]  # Strip prefix
        url = f"https://www.ebi.ac.uk/chebi/backend/api/public/compound/{chebi_num}/"
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            data = r.json()
            smiles = data.get("default_structure", {}).get("smiles")
            return smiles.strip() if smiles else None
        except Exception as e:
            logger.warning(f"ChEBI {chebi_id} fetch SMILES failed: {e}")
            return None
