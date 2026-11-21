"""PubChem identifier resolver with structural search."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

import requests


from ...utils.net import prefer_ipv4 as _prefer_ipv4
_prefer_ipv4()

from ... import http_retry
from ..base import IdentifierResolver, IdentifierResolutionError
from ._smiles_query import query_smiles, refusal

if TYPE_CHECKING:
    from ...config.loader import RunConfig

logger = logging.getLogger("identifier")

_PUG = "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
# Identity and similarity searches are asynchronous: PUG answers 202 with a
# ListKey, polled until the result is ready.
_POLL_S = 2.0
_MAX_POLLS = 30


class PubChemResolver(IdentifierResolver):
    """Resolver for SMILES/SELFIES signatures using PubChem structural search."""

    name = "pubchem_struct"
    identifier_type = "PUBCHEM_CID"
    accepted_signatures = ["smiles", "selfies"]

    def __init__(self, config: RunConfig) -> None:
        """Initialize PubChem resolver with configuration.

        Args:
            config: RunConfig instance containing pubchem settings.
        """
        super().__init__(config)
        # 2026-11-21 (mdval audit item 6): retries are http_retry's (the
        # session's urllib3 Retry is gone; pubchempy had none and no timeout)
        self._session = requests.Session()
        # Exact matches from the local PubChem mirror (2026-11-20): the same
        # CIDs PUG's identity search returns (checked on the known-answers
        # cases), with no NCBI call. Similarity and mirror misses stay online.
        self._local_db = None
        path = getattr(config.pubchem, "local_db_path", "")
        if path:
            try:
                from ...molecules.pubchem_db import PubChemDB

                db = PubChemDB(path)
                if db.exists():
                    self._local_db = db
            except Exception:
                self._local_db = None

    def offline_identity(self) -> bool:
        """True when exact matches can come from the mirror (breaker exemption
        for the identity phase only)."""
        return self._local_db is not None

    def _mirror_cids(self, smiles: str) -> list[str]:
        """CIDs whose full InChIKey equals the query's; [] on a miss.

        Several CIDs can share a standard InChIKey (water 962 and
        '[H+].[OH-]' 22247451; tautomers): the one whose own SMILES is the
        same structure as the query is PUG's identity answer, so when exactly
        one matches, only it is returned.
        """
        if self._local_db is None:
            return []
        try:
            from rdkit import Chem, RDLogger

            RDLogger.DisableLog("rdApp.*")
            mol = Chem.MolFromSmiles(smiles)
            key = Chem.MolToInchiKey(mol) if mol is not None else ""
            cids = [str(c) for c in self._local_db.cids_by_inchikey(key)] if key else []
            if len(cids) > 1:
                query = Chem.MolToSmiles(mol)
                rows = self._local_db.by_cids(cids)
                same = []
                for cid in cids:
                    row = rows.get(cid)
                    other = Chem.MolFromSmiles(row.smiles) if row and row.smiles else None
                    if other is not None and Chem.MolToSmiles(other) == query:
                        same.append(cid)
                if len(same) == 1:
                    return same
            return cids
        except Exception as exc:
            logger.warning(f"pubchem_struct: mirror lookup failed: {exc}")
            return []

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature is applicable for PubChem search.

        Args:
            signature: The signature string to check.

        Returns:
            True (assumes valid SMILES/SELFIES from signature generator).
        """
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve SMILES/SELFIES to exact-match PubChem CIDs.

        Args:
            signature: SMILES or SELFIES string to resolve.
            working_directory: Unused.

        Returns:
            List of CID strings (not integers).

        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        # Decode SELFIES to SMILES if needed
        smiles = self._decode_selfies(signature)
        if self._declined(smiles):
            return []
        if self._local_db is not None:
            cids = self._mirror_cids(smiles)
            # One CID: the mirror's answer. Several (tautomers sharing a
            # standard InChIKey): PUG's identity search tells them apart.
            if len(cids) == 1:
                return cids
            from ..resolution_manager import _pubchem_healthy

            if not _pubchem_healthy():
                if cids:
                    # ambiguous stand-in for PUG's answer: never cached
                    self._uncacheable = True
                    return cids
                raise IdentifierResolutionError(
                    "[Identifier] not in the local PubChem mirror and PubChem is unreachable")
        return pubchem_fetch_identity_match(smiles, self._session, self.config,
                                            give_up=self._over_budget)

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve SMILES/SELFIES to similar PubChem CIDs.

        Args:
            signature: SMILES or SELFIES string to resolve.
            working_directory: Unused.

        Returns:
            List of (CID, similarity_score) tuples.

            SCORE SEMANTICS (F-07, known deviation): the score is a CONSTANT
            stub equal to ``config.pubchem.similarity_threshold`` — the
            PubChem similarity API returns candidate CIDs without per-compound
            scores. The value therefore has ordinal meaning ONLY within this
            resolver's own hit list (all items tie); it MUST NOT be compared
            against or rank-mixed with real similarity scores from other
            resolvers (blast/uniprot/alphafind).
            TODO: fetch canonical SMILES per CID (pubchempy.get_properties)
            and compute real Tanimoto via RDKit.

        Raises:
            IdentifierResolutionError: If resolution fails (no results is OK).
        """
        # Decode SELFIES to SMILES if needed
        smiles = self._decode_selfies(signature)
        if self._declined(smiles):
            return []
        threshold = self.config.pubchem.similarity_threshold
        return pubchem_fetch_similarity_match(smiles, threshold, self._session, self.config,
                                              give_up=self._over_budget)

    def _declined(self, smiles: str) -> bool:
        """2026-11-21 (mdval audit item 6): an impossible valence is not sent
        (PubChem answered 400 PUGREST.BadRequest)."""
        reason = refusal(smiles)
        if reason:
            logger.info(f"{self.name}: query declined ({reason})")
            self._last_error = reason
        return bool(reason)

    def _decode_selfies(self, signature: str) -> str:
        """Decode SELFIES to SMILES if signature is SELFIES.

        Args:
            signature: SMILES or SELFIES string.

        Returns:
            SMILES string.
        """
        # 2026-11-21 (mdval audit item 6): by the signature type
        return query_smiles(signature, getattr(self, "_signature_type", None))


# -- PUG REST searches -----------------------------------------------------------
# 2026-11-21 (mdval audit item 6): requests through http_retry instead of
# pubchempy. pubchempy's urlopen had no timeout and no retry, its polling
# loop no end, and a timeout or ServerBusy came back as [] — the same answer
# as "not found". Now 429/5xx/timeouts are retried and, when they persist,
# raised (counted as a retryable gap); 404 is "not found" ([]); any other
# 4xx is raised with PUG's fault code (PUGREST.BadRequest: rejected, not
# retried). Same searches as before: identity / similarity over POSTed
# SMILES, polled by ListKey; on 400 the synchronous fallback endpoints.

class _PugError(Exception):
    def __init__(self, response: requests.Response) -> None:
        self.status = response.status_code
        try:
            fault = response.json().get("Fault") or {}
        except Exception:
            fault = {}
        parts = [fault.get("Code") or "", fault.get("Message") or "",
                 "; ".join(str(d) for d in fault.get("Details") or [])]
        text = " ".join(p for p in parts if p) or http_retry.body_excerpt(response)
        super().__init__(f"HTTP {self.status} {text}".strip())


def _attempts(config: RunConfig) -> int:
    return max(http_retry.ATTEMPTS, int(getattr(config.pubchem, "retry_attempts", 1) or 1))


def _cids(data: dict) -> list[str]:
    if "IdentifierList" in data:
        return [str(c) for c in data["IdentifierList"].get("CID", []) if int(c) > 0]
    out = []
    for record in data.get("PC_Compounds") or []:
        cid = ((record.get("id") or {}).get("id") or {}).get("cid")
        if cid:
            out.append(str(cid))
    return out


def _pug(method: str, url: str, session: Optional[requests.Session], config: RunConfig,
         give_up: Optional[Callable[[], bool]], **kwargs) -> list[str] | None:
    """CIDs of one PUG call, following a ListKey; None while still waiting
    after _MAX_POLLS polls."""
    response = http_retry.request(method, url, session=session, attempts=_attempts(config),
                                  give_up=give_up, timeout=30, **kwargs)
    for _ in range(_MAX_POLLS):
        if response.status_code == 404:
            return []  # PUGREST.NotFound: no compound matches
        if response.status_code >= 400:
            raise _PugError(response)
        data = response.json()
        key = (data.get("Waiting") or {}).get("ListKey")
        if not key:
            return _cids(data)
        http_retry._sleep(_POLL_S)
        response = http_retry.request("GET", f"{_PUG}/listkey/{key}/cids/JSON", session=session,
                                      attempts=_attempts(config), give_up=give_up, timeout=30)
    return None


def _pug_search(kind: str, url: str, fallback_url: str, smiles: str,
                session: Optional[requests.Session], config: RunConfig,
                give_up: Optional[Callable[[], bool]]) -> list[str]:
    try:
        try:
            cids = _pug("POST", url, session, config, give_up, data={"smiles": smiles})
        except _PugError as exc:
            if exc.status != 400:
                raise
            # the synchronous endpoint, as the pubchempy path did on BadRequest
            try:
                cids = _pug("POST", fallback_url, session, config, give_up, data={"smiles": smiles})
            except _PugError:
                raise exc from None
    except (_PugError, requests.exceptions.RequestException, ValueError) as exc:
        raise IdentifierResolutionError(f"[Identifier] PUBCHEM API {kind} search failed: {exc}")
    if cids is None:
        raise IdentifierResolutionError(
            f"[Identifier] PUBCHEM API {kind} search timed out (still running after "
            f"{_MAX_POLLS * _POLL_S:.0f} s)")
    return cids


def pubchem_fetch_identity_match(
    smiles: str,
    session: Optional[requests.Session],
    config: RunConfig,
    give_up: Optional[Callable[[], bool]] = None,
) -> list[str]:
    """Search PubChem for identity match of SMILES.

    Args:
        smiles: SMILES string to search.
        session: Requests session (None: a new connection per request).
        config: RunConfig (pubchem.retry_attempts raises the attempts).
        give_up: Optional callable; True stops the retries (stage budget).

    Returns:
        List of CID strings; [] when PubChem has no match.

    Raises:
        IdentifierResolutionError: On PubChem search failure, including a
            timeout that persists through the retries.
    """
    return _pug_search("identity", f"{_PUG}/identity/smiles/JSON",
                       f"{_PUG}/smiles/cids/JSON", smiles, session, config, give_up)


def pubchem_fetch_similarity_match(
    smiles: str,
    threshold: int,
    session: Optional[requests.Session],
    config: RunConfig,
    give_up: Optional[Callable[[], bool]] = None,
) -> list[tuple[str, float]]:
    """Search PubChem for similar matches of SMILES.

    Args:
        smiles: SMILES string to search.
        threshold: Similarity threshold (0-100).
        session: Requests session (None: a new connection per request).
        config: RunConfig (pubchem.retry_attempts raises the attempts).
        give_up: Optional callable; True stops the retries (stage budget).

    Returns:
        List of (CID, score) tuples.

        SCORE SEMANTICS (F-07, known deviation): every returned score is the
        constant ``threshold`` itself — PubChem returns CIDs, not per-compound
        scores. Ordinal-only within this resolver; do not compare or
        rank-mix with scores from other resolver families.
        TODO: fetch canonical SMILES and compute Tanimoto similarity with
        RDKit for actual per-compound scores.

    Raises:
        IdentifierResolutionError: On PubChem search failure, including a
            timeout that persists through the retries.
    """
    cids = _pug_search(
        "similarity", f"{_PUG}/similarity/smiles/JSON?Threshold={threshold}",
        f"{_PUG}/fastsimilarity_2d/smiles/cids/JSON?Threshold={threshold}",
        smiles, session, config, give_up)
    # F-07: scores are the threshold constant for every CID.
    # Ordinal-only within this resolver; never rank-mix with real
    # per-target scores (see docstring TODO for the Tanimoto fix).
    return [(cid, float(threshold)) for cid in cids]
