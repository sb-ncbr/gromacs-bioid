"""Compound signature fetcher for small molecules."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time

import requests
from ...utils.net import prefer_ipv4 as _prefer_ipv4
_prefer_ipv4()

from ..base import SignatureFetcher

logger = logging.getLogger(__name__)

_SIM_CACHE = "/data/validation/sim_cache/pubchem_smiles"
_MIN_INTERVAL_S = 0.34         # keep the whole pipeline under PubChem's ~3 rps
_last_request_ts = 0.0


def _cache_path(cid: str) -> str:
    return os.path.join(_SIM_CACHE, hashlib.sha1(f"cid:{cid}".encode()).hexdigest()[:24] + ".json")


def _cache_path_ns(ns: str, ident: str) -> str:
    return os.path.join(_SIM_CACHE, hashlib.sha1(f"{ns}:{ident}".encode()).hexdigest()[:24] + ".json")


def _cache_read_ns(ns: str, ident: str):
    try:
        with open(_cache_path_ns(ns, ident)) as fh:
            return json.load(fh)
    except Exception:
        return None


def _cache_write_ns(ns: str, ident: str, val) -> None:
    try:
        os.makedirs(_SIM_CACHE, exist_ok=True)
        with open(_cache_path_ns(ns, ident), "w") as fh:
            json.dump(val, fh)
    except OSError:
        pass


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
            r = requests.get(url, timeout=30)
            _last_request_ts = time.time()
        except Exception as exc:
            if attempt < tries - 1:
                time.sleep(delay)
                delay *= 2
                continue
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
    
    SUPPORTED_TYPES = {"PUBCHEM_CID", "CHEMBL_ID", "CHEBI_ID", "INCHIKEY", "INCHI_KEY"}
    
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
            norm = ident_type.upper()
            if norm in ("INCHIKEY", "INCHI_KEY"):
                return self._fetch_inchikey(identifier)
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
        """Fetch SMILES for a PubChem CID, ordered: NFS cache -> PUG -> IDSM
        (ELIXIR-CZ mirrors the PubChem RDF; works while NCBI blocks cluster IP).
        """
        cached = _cache_read(str(cid))
        if cached is not None:
            return cached
        smiles = None
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/property/CanonicalSMILES/TXT"
        r = _polite_get(url)
        if r is not None:
            smiles = r.text.strip() or None
        if not smiles:
            smiles = self._fetch_idsm_pubchem(cid)
        if smiles:
            _cache_write(str(cid), smiles)
        return smiles

    @staticmethod
    def _fetch_idsm_pubchem(cid: str) -> str | None:
        """CID -> SMILES via IDSM SPARQL (ELIXIR-CZ PubChem mirror)."""
        query = (
            "SELECT ?v WHERE { "
            f"<http://rdf.ncbi.nlm.nih.gov/pubchem/compound/CID{cid}> "
            "<http://semanticscience.org/resource/SIO_000008> ?d . "
            "?d a ?t . "
            'FILTER(CONTAINS(STR(?t), "SMILES")) '
            "?d <http://semanticscience.org/resource/SIO_000300> ?v "
            "} LIMIT 2"
        )
        try:
            r = _polite_get(
                "https://idsm.elixir-czech.cz/sparql/endpoint/idsm"
                "?query=" + requests.utils.quote(query)
                + "&format=application/sparql-results%2Bjson"
            )
            if r is None:
                return None
            bindings = r.json().get("results", {}).get("bindings", [])
            for b in bindings:
                v = (b.get("v") or {}).get("value")
                if v:
                    return v.strip()
        except Exception as exc:
            logger.warning(f"IDSM PubChem mirror fetch failed for {cid}: {exc}")
        return None
    
    def _fetch_inchikey(self, ik: str) -> str | None:
        """InChIKey -> canonical SMILES without PubChem (NCBI blocks cluster IP).

        Fallback order: CACTUS (NCI) -> ChEMBL molecule search -> PUG (last
        resort, may be blocked - soft-failed by polite layer already).
        """
        ik = ik.strip()
        if not ik:
            return None
        # 1) CACTUS
        url1 = f"https://cactus.nci.nih.gov/chemical/structure/{ik}/smiles"
        r = _polite_get(url1)
        if r is not None:
            smiles = r.text.strip()
            if smiles and " " not in smiles and "<" not in smiles:
                return smiles
        # 2) ChEMBL search
        url2 = f"https://www.ebi.ac.uk/chembl/api/data/molecule.json?standard_inchi_key={ik}"
        r = _polite_get(url2)
        if r is not None:
            try:
                mols = r.json().get("molecules") or []
                if mols:
                    smi = (mols[0].get("molecule_structures") or {}).get("canonical_smiles")
                    if smi:
                        return smi
            except Exception:
                pass
        # 3) PUG (likely blocked; kept as last-resort)
        url3 = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{ik}/property/CanonicalSMILES/TXT"
        r = _polite_get(url3)
        if r is not None:
            smiles = r.text.strip()
            if smiles:
                return smiles
        logger.warning(f"InChIKey {ik} unresolved by cactus/chembl/pug")
        return None

    def _fetch_chembl(self, chembl_id: str) -> str | None:
        """Fetch SMILES from ChEMBL (NFS cached + polite transport)."""
        # Canonicalize: strip CHEMBL prefix if present, then prepend it back
        chembl_id = chembl_id.upper()
        if chembl_id.startswith("CHEMBL"):
            chembl_id = chembl_id[6:]  # Strip prefix
        chembl_id = f"CHEMBL{chembl_id}"
        cached = _cache_read_ns("chemb", chembl_id)
        if cached is not None:
            return cached
        url = f"https://www.ebi.ac.uk/chembl/api/data/molecule/{chembl_id}.json"
        r = _polite_get(url)
        smiles = None
        if r is not None:
            try:
                smiles = r.json().get("molecule_structures", {}).get("canonical_smiles")
            except Exception as exc:
                logger.warning(f"ChEMBL {chembl_id} parse failed: {exc}")
        if smiles:
            _cache_write_ns("chemb", chembl_id, smiles)
        else:
            logger.warning(f"ChEMBL {chembl_id} fetch SMILES failed")
        return smiles
    
    def _fetch_chebi(self, chebi_id: str) -> str | None:
        """Fetch SMILES from ChEBI (NFS cached + polite transport)."""
        # Strip CHEBI: prefix if present
        chebi_num = chebi_id.upper()
        if chebi_num.startswith("CHEBI:"):
            chebi_num = chebi_num[6:]  # Strip prefix
        cached = _cache_read_ns("chebi", chebi_num)
        if cached is not None:
            return cached
        url = f"https://www.ebi.ac.uk/chebi/backend/api/public/compound/{chebi_num}/"
        r = _polite_get(url)
        smiles = None
        if r is not None:
            try:
                smi = r.json().get("default_structure", {}).get("smiles")
                smiles = smi.strip() if smi else None
            except Exception as exc:
                logger.warning(f"ChEBI {chebi_id} parse failed: {exc}")
        if smiles:
            _cache_write_ns("chebi", chebi_num, smiles)
        else:
            logger.warning(f"ChEBI {chebi_id} fetch SMILES failed")
        return smiles
