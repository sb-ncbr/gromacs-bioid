"""Molecular formula identifier resolver using PubChem PUG-REST."""

from __future__ import annotations

import logging
import re
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


class FormulaResolver(IdentifierResolver):
    """Resolver for molecular formula signatures using PubChem PUG-REST.

    Converts molecular formula to PubChem CID(s) via exact lookup.
    Similarity search is not applicable for formula (exact composition).
    """

    name = "formula_pubchem"
    identifier_type = "PUBCHEM_CID"
    accepted_signatures = ["formula"]

    def __init__(self, config: RunConfig) -> None:
        """Initialize formula resolver.

        Args:
            config: RunConfig instance containing pubchem settings.
        """
        super().__init__(config)
        self._session = _create_retry_session(
            retry_attempts=config.pubchem.retry_attempts,
            retry_delay=config.pubchem.retry_delay_s,
        )

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature looks like a valid molecular formula.

        Args:
            signature: The formula string to check.

        Returns:
            True if signature matches basic formula pattern.
        """
        # Basic formula validation: element symbols followed by optional numbers
        # e.g., C6H12O6, H2O, NaCl
        # Pattern: element symbol (1-2 letters, first uppercase) + optional digits
        formula_pattern = r"^([A-Z][a-z]?\d*)+$"
        if not re.match(formula_pattern, signature):
            return False
        # Must have at least one element
        return len(signature) > 0

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve molecular formula to PubChem CID(s) via exact lookup.

        Args:
            signature: Molecular formula string to resolve.
            working_directory: Unused.

        Returns:
            List of CID strings.

        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        return fetch_cids_from_formula(signature, self._session, self.config)

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve formula to similar identifiers.

        Not applicable for molecular formula (exact composition). Returns empty list.

        Args:
            signature: Molecular formula string.
            working_directory: Unused.

        Returns:
            Empty list (similarity not applicable for formula).
        """
        # Formula is an exact composition identifier; similarity search not applicable
        return []


def fetch_cids_from_formula(
    formula: str,
    session: requests.Session,
    config: RunConfig,
) -> list[str]:
    """Fetch PubChem CIDs for a molecular formula via PUG-REST.

    Args:
        formula: Molecular formula string.
        session: Requests session with retry logic.
        config: RunConfig for retry settings.

    Returns:
        List of CID strings.

    Raises:
        IdentifierResolutionError: If request fails.
    """
    # Use fastformula endpoint for faster lookup
    url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/fastformula/{formula}/cids/txt"

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        cids_text = response.text.strip()

        if not cids_text or "status" in cids_text.lower():
            return []

        return [cid.strip() for cid in cids_text.split("\n") if cid.strip().isnumeric()]
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            # Formula not found - return empty, not an error
            return []
        raise IdentifierResolutionError(f"[Identifier] PubChem formula lookup failed: {exc}")
    except Exception as exc:
        raise IdentifierResolutionError(f"[Identifier] PubChem formula lookup failed: {exc}")
