"""PubChem identifier resolver with structural search."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import pubchempy
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


from ...utils.net import prefer_ipv4 as _prefer_ipv4
_prefer_ipv4()

from ..base import IdentifierResolver, IdentifierResolutionError

if TYPE_CHECKING:
    from ...config.loader import RunConfig

logger = logging.getLogger("identifier")


def _create_retry_session(retry_attempts: int = 1, retry_delay: int = 10) -> requests.Session:
    """Create a requests session with retry logic for PubChem API calls."""
    session = requests.Session()
    retry = Retry(
        total=retry_attempts,
        backoff_factor=retry_delay,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


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
        self._session = _create_retry_session(
            retry_attempts=config.pubchem.retry_attempts,
            retry_delay=config.pubchem.retry_delay_s,
        )
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
        if self._local_db is not None:
            cids = self._mirror_cids(smiles)
            # One CID: the mirror's answer. Several (tautomers sharing a
            # standard InChIKey): PUG's identity search tells them apart.
            if len(cids) == 1:
                return cids
            from ..resolution_manager import _pubchem_healthy

            if not _pubchem_healthy():
                if cids:
                    return cids
                raise IdentifierResolutionError(
                    "[Identifier] not in the local PubChem mirror and PubChem is unreachable")
        return pubchem_fetch_identity_match(smiles, self._session, self.config)

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
        threshold = self.config.pubchem.similarity_threshold
        return pubchem_fetch_similarity_match(smiles, threshold, self._session, self.config)

    def _decode_selfies(self, signature: str) -> str:
        """Decode SELFIES to SMILES if signature is SELFIES.

        Args:
            signature: SMILES or SELFIES string.

        Returns:
            SMILES string.
        """
        # Check if this looks like SELFIES (contains [C], [O], etc.)
        if "[" in signature and "]" in signature:
            try:
                import selfies
                return selfies.decoder(signature)
            except ImportError:
                logger.warning("selfies package not installed; treating as SMILES")
            except Exception as exc:
                logger.warning(f"SELFIES decode failed: {exc}; treating as SMILES")
        return signature


def pubchem_fetch_identity_match(
    smiles: str,
    session: requests.Session,
    config: RunConfig,
) -> list[str]:
    """Search PubChem for identity match of SMILES.

    Args:
        smiles: SMILES string to search.
        session: Requests session with retry logic.
        config: RunConfig for retry settings.

    Returns:
        List of CID strings.

    Raises:
        IdentifierResolutionError: On PubChem search failure.
    """
    retry_attempts = config.pubchem.retry_attempts
    retry_delay = config.pubchem.retry_delay_s

    for attempt in range(retry_attempts):
        try:
            try:
                exact_matches: list[pubchempy.Compound] = pubchempy.get_compounds(
                    smiles,
                    namespace="smiles",
                    searchtype="identity",
                    as_dataframe=False,
                )
                # Return CIDs as strings (fix: old code returned list[int])
                return [str(match.cid) for match in exact_matches]
            except pubchempy.BadRequestError:
                # Fallback to POST request
                return _pubchem_fetch_identity_match_post(smiles, session)
        except pubchempy.TimeoutError:
            if attempt < retry_attempts - 1:
                time.sleep(retry_delay)
        except Exception as exc:
            if "ServerBusy" in str(exc):
                if attempt < retry_attempts - 1:
                    time.sleep(retry_delay)
            else:
                raise IdentifierResolutionError(f"[Identifier] PUBCHEM API identity search failed: {exc}")
    return []


def _pubchem_fetch_identity_match_post(smiles: str, session: requests.Session) -> list[str]:
    """Fallback POST search for PubChem identity match.

    Args:
        smiles: SMILES string to search.
        session: Requests session with retry logic.

    Returns:
        List of CID strings.

    Raises:
        IdentifierResolutionError: On POST failure.
    """
    try:
        # Add timeout (fix: old code had no timeout)
        response = session.post(
            "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/smiles/cids/txt",
            data={"smiles": smiles},
            timeout=30,
        )
        cids_text = response.text.strip()
        if "status" in cids_text.lower():
            return []
        return [cid for cid in cids_text.split("\n") if cid.isnumeric()]
    except Exception as exc:
        if "ServerBusy" in str(exc):
            return []
        raise IdentifierResolutionError(f"[Identifier] PUBCHEM POST identity search failed: {exc}")


def pubchem_fetch_similarity_match(
    smiles: str,
    threshold: int,
    session: requests.Session,
    config: RunConfig,
) -> list[tuple[str, float]]:
    """Search PubChem for similar matches of SMILES.

    Args:
        smiles: SMILES string to search.
        threshold: Similarity threshold (0-100).
        session: Requests session with retry logic.
        config: RunConfig for retry settings.

    Returns:
        List of (CID, score) tuples.

        SCORE SEMANTICS (F-07, known deviation): every returned score is the
        constant ``threshold`` itself — PubChem returns CIDs, not per-compound
        scores. Ordinal-only within this resolver; do not compare or
        rank-mix with scores from other resolver families.
        TODO: fetch canonical SMILES via pubchempy.get_properties and compute
        Tanimoto similarity with RDKit for actual per-compound scores.

    Raises:
        IdentifierResolutionError: On PubChem search failure.
    """
    retry_attempts = config.pubchem.retry_attempts
    retry_delay = config.pubchem.retry_delay_s

    for attempt in range(retry_attempts):
        try:
            try:
                compounds: list[pubchempy.Compound] = pubchempy.get_compounds(
                    smiles,
                    namespace="smiles",
                    searchtype="similarity",
                    as_dataframe=False,
                    Threshold=threshold,
                )
                cids: list[str] = [str(match.cid) for match in compounds]
            except pubchempy.BadRequestError:
                # Fallback to POST request
                cids = _pubchem_fetch_similar_match_post(smiles, threshold, session)

            # F-07: scores are the threshold constant for every CID.
            # Ordinal-only within this resolver; never rank-mix with real
            # per-target scores (see docstring TODO for the Tanimoto fix).
            return [(cid, float(threshold)) for cid in cids]
        except pubchempy.TimeoutError:
            if attempt < retry_attempts - 1:
                time.sleep(retry_delay)
        except Exception as exc:
            if "ServerBusy" in str(exc):
                if attempt < retry_attempts - 1:
                    time.sleep(retry_delay)
            else:
                raise IdentifierResolutionError(f"[Identifier] PUBCHEM API similarity search failed: {exc}")
    return []


def _pubchem_fetch_similar_match_post(
    smiles: str,
    threshold: int,
    session: requests.Session,
) -> list[str]:
    """Fallback POST search for PubChem similarity match.

    Args:
        smiles: SMILES string to search.
        threshold: Similarity threshold.
        session: Requests session with retry logic.

    Returns:
        List of CID strings.

    Raises:
        IdentifierResolutionError: On POST failure.
    """
    try:
        # Add timeout (fix: old code had no timeout)
        response = session.post(
            f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/fastsimilarity_2d/smiles/cids/txt?Threshold={threshold}",
            data={"smiles": smiles},
            timeout=30,
        )
        cids_text = response.text.strip()
        if "status" in cids_text.lower():
            return []
        return [cid for cid in cids_text.split("\n") if cid.isnumeric()]
    except Exception as exc:
        if "ServerBusy" in str(exc):
            return []
        raise IdentifierResolutionError(f"[Identifier] PUBCHEM POST similarity search failed: {exc}")
