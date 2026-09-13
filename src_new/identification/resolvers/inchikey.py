"""InChIKey identifier resolver using PubChem PUG-REST."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

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
    """Create a requests session with retry logic."""
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


class InchiKeyResolver(IdentifierResolver):
    """Resolver for InChIKey signatures using PubChem PUG-REST.

    Converts InChIKey to PubChem CID(s) via exact lookup.
    Similarity search is not applicable for InChIKey (exact identifier).
    """

    name = "inchikey_pubchem"
    identifier_type = "PUBCHEM_CID"
    accepted_signatures = ["inchikey"]

    def __init__(self, config: RunConfig) -> None:
        """Initialize InChIKey resolver.

        Args:
            config: RunConfig instance containing pubchem settings.
        """
        super().__init__(config)
        self._session = _create_retry_session(
            retry_attempts=config.pubchem.retry_attempts,
            retry_delay=config.pubchem.retry_delay_s,
        )

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature looks like a valid InChIKey.

        Args:
            signature: The InChIKey string to check.

        Returns:
            True if signature matches InChIKey format pattern.
        """
        # InChIKey format: 14 chars + "-" + 10 chars + "-" + 1 char (version/protonation)
        # e.g., UHFFFAOYSA-N
        if len(signature) < 27:
            return False
        # Basic format check
        parts = signature.split("-")
        if len(parts) != 3:
            return False
        if len(parts[0]) != 14 or len(parts[1]) != 10 or len(parts[2]) != 1:
            return False
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve InChIKey to PubChem CID(s) via exact lookup.

        Args:
            signature: InChIKey string to resolve.
            working_directory: Unused.

        Returns:
            List of CID strings.

        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        return fetch_cids_from_inchikey(signature.upper(), self._session, self.config)

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve InChIKey to similar identifiers.

        Not applicable for InChIKey (exact identifier). Returns empty list.

        Args:
            signature: InChIKey string.
            working_directory: Unused.

        Returns:
            Empty list (similarity not applicable for InChIKey).
        """
        # InChIKey is an exact identifier; similarity search not applicable
        return []


def fetch_cids_from_inchikey(
    inchikey: str,
    session: requests.Session,
    config: RunConfig,
) -> list[str]:
    """Fetch PubChem CIDs for an InChIKey via PUG-REST.

    Args:
        inchikey: InChIKey string (should be uppercase).
        session: Requests session with retry logic.
        config: RunConfig for retry settings.

    Returns:
        List of CID strings.

    Raises:
        IdentifierResolutionError: If request fails.
    """
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{inchikey}/cids/txt"

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        cids_text = response.text.strip()

        if not cids_text or "status" in cids_text.lower():
            return []

        return [cid.strip() for cid in cids_text.split("\n") if cid.strip().isnumeric()]
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            # InChIKey not found - return empty, not an error
            return []
        raise IdentifierResolutionError(f"[Identifier] PubChem InChIKey lookup failed: {exc}")
    except Exception as exc:
        raise IdentifierResolutionError(f"[Identifier] PubChem InChIKey lookup failed: {exc}")
