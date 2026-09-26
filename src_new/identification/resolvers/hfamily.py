"""H-family formula candidate generator (F9).

Protonation-tolerant candidate generation: molecular simulations run charged
species (e.g. azilsartan -2H) while literature/PubChem store neutral forms.
For a formula C25H18N4O5 we query PubChem fastformula over the H-neighborhood
(C25H{H-4..H+4}N4O5) and UNION all CIDs as candidates.

This resolver only GENERATES candidates. Structural corroboration happens in
the verification gate (F7 skeleton fingerprint, manager.py).
"""

from __future__ import annotations

import logging
import re
import time

import requests

from ...config.loader import RunConfig

from ...utils.net import prefer_ipv4 as _prefer_ipv4
_prefer_ipv4()

from ..base import IdentifierResolver, IdentifierResolutionError

logger = logging.getLogger("base")

_PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
_FORMULA_RE = re.compile(r"([A-Z][a-z]?)(\d*)")
_H_RANGE_DEFAULT = 4
_REQUEST_PAUSE_S = 0.35        # keeps us under PubChem's ~3 rps etiquette
_MAX_RECORDS_PER_QUERY = 200
_MAX_TOTAL_CANDIDATES = 500


def _create_retry_session(retry_attempts: int = 3, retry_delay: float = 1.0) -> requests.Session:
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(
        max_retries=0, pool_connections=1, pool_maxsize=1
    )
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session._hf_retry_attempts = retry_attempts
    session._hf_retry_delay = retry_delay
    return session


def _parse_formula(formula: str) -> dict[str, int]:
    text = formula.strip()
    # strict: whole string must be element-count groups
    if not text or not re.fullmatch(r"([A-Z][a-z]?\d*)+", text):
        raise IdentifierResolutionError(f"malformed formula: {formula!r}")
    parts: dict[str, int] = {}
    for sym, num in _FORMULA_RE.findall(text):
        parts[sym] = parts.get(sym, 0) + (int(num) if num else 1)
    return parts


def _hill(parts: dict[str, int]) -> str:
    out = []
    rest = dict(parts)
    if rest.get("C"):
        n = rest.pop("C")
        out.append("C" if n == 1 else f"C{n}")
    if rest.get("H"):
        n = rest.pop("H")
        out.append("H" if n == 1 else f"H{n}")
    for sym in sorted(rest):
        n = rest[sym]
        out.append(sym if n == 1 else f"{sym}{n}")
    return "".join(out) if ("C" in parts or parts) else ""


class FormulaHFamilyResolver(IdentifierResolver):
    """Generates PubChem CID candidates over the protonation (H) neighborhood."""

    name = "formula_hfamily"
    identifier_type = "PUBCHEM_CID"
    accepted_signatures = ["formula", "molecular_formula"]

    def __init__(self, config: RunConfig) -> None:
        super().__init__(config)
        self._session = _create_retry_session(
            retry_attempts=config.pubchem.retry_attempts,
            retry_delay=config.pubchem.retry_delay_s,
        )
        self.h_range = getattr(config.pubchem, "hfamily_h_range", _H_RANGE_DEFAULT)
        # Local PubChem mirror: serves the per-variant fastformula lookups
        # without network. Local lookups are free, so caps rise far beyond the
        # PUG etiquette caps (200/query, 500 total) to actually cover big
        # isomer families; the verification-window rerank (F14) bounds cost.
        self._local_db = None
        local_path = getattr(config.pubchem, "local_db_path", "")
        if local_path:
            try:
                from ...molecules.pubchem_db import PubChemDB

                db = PubChemDB(local_path)
                if db.exists():
                    self._local_db = db
            except Exception:
                self._local_db = None
        self._local_per_query = int(
            getattr(config.pubchem, "hfamily_local_max_per_query", 5000))
        self._local_max_total = int(
            getattr(config.pubchem, "hfamily_local_max_total", 25000))

    def offline_capable(self) -> bool:
        """True when the resolver can serve fully offline (local mirror).

        The PubChem circuit breaker (resolution_manager) consults this before
        skipping the resolver: the local backend needs no NCBI access, so the
        ban-era breaker must not blind the H-family channel.
        """
        return self._local_db is not None

    def _is_applicable(self, signature: str) -> bool:
        try:
            parts = _parse_formula(signature)
        except IdentifierResolutionError:
            return False
        return "H" in parts and len(parts) >= 2

    def _pug_get(self, path: str) -> dict | None:
        delay = self._session._hf_retry_delay
        for attempt in range(self._session._hf_retry_attempts):
            try:
                resp = self._session.get(_PUG + path, timeout=30)
                if resp.status_code == 404:
                    return None
                if resp.status_code in (429, 500, 502, 503) and attempt < self._session._hf_retry_attempts - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                resp.raise_for_status()
                time.sleep(_REQUEST_PAUSE_S)
                return resp.json()
            except requests.RequestException as exc:
                if attempt < self._session._hf_retry_attempts - 1:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise IdentifierResolutionError(f"hfamily query failed: {exc}") from exc
        return None

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        # Not an identity-style resolver: candidates are generated in the
        # similarity channel (formula match alone is not compound identity).
        return []

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        parts = _parse_formula(signature)
        h0 = parts.get("H")
        if h0 is None:
            raise IdentifierResolutionError("formula lacks hydrogen; H-family not applicable")

        candidates: list[str] = []
        seen: set[str] = set()
        total_cap = self._local_max_total if self._local_db is not None else _MAX_TOTAL_CANDIDATES
        for delta in range(-self.h_range, self.h_range + 1):
            if self._over_budget():
                logger.warning("hfamily: stage deadline exceeded after %d candidates for %s; returning partial", len(candidates), signature)
                break
            h = h0 + delta
            if h <= 0:
                continue
            variant = dict(parts)
            variant["H"] = h
            formula = _hill(variant)
            if self._local_db is not None:
                try:
                    cids = list(self._local_db.by_formula(formula, limit=self._local_per_query))
                except Exception:
                    cids = []
            else:
                data = self._pug_get(
                    f"/compound/fastformula/{formula}/cids/JSON?MaxRecords={_MAX_RECORDS_PER_QUERY}"
                )
                cids = (data or {}).get("IdentifierList", {}).get("CID") or []
            for cid in cids:
                scid = str(cid)
                if scid not in seen:
                    seen.add(scid)
                    candidates.append(scid)
                    if len(candidates) >= total_cap:
                        break
            if len(candidates) >= total_cap:
                logger.warning("hfamily: candidate cap hit for %s", signature)
                break
        # flat candidate score; the F7 verification gate does structural rescoring
        return [(cid, 50.0) for cid in candidates]
