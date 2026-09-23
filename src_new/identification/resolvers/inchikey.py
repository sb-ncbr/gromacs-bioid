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


class InchiKeySelfResolver(IdentifierResolver):
    """Offline identity pass-through: an InChIKey signature is itself the
    identity candidate (PUB-dead-proof).

    Since 2026-09-12 PubChem is cluster-blocked (503), and the InChIKey->CID
    reverse lookups (PUG, IDSM thin SPARQL) return nothing from the cluster.
    But simulation ligand segments already carry the InChIKey itself; making
    it a first-class identity candidate lets verification fetch its structure
    via the cactus-first chain (NFS cache -> cactus 200-OK) and judge the exact
    match vs ground truth without PubChem. Protonation-layer variants are
    handled downstream by the charged-species (-N first) fetch guideline.
    """

    name = "inchikey_self"
    identifier_type = "INCHIKEY"
    accepted_signatures = ["inchikey"]

    def __init__(self, config: RunConfig) -> None:
        """No network needed; only config for the enablement flag."""
        super().__init__(config)

    def _is_applicable(self, signature: str) -> bool:
        """Validate InChIKey format: 14-10-1 (e.g. BSYNRYMUTXBXSQ-UHFFFAOYSA-N)."""
        if not isinstance(signature, str):
            return False
        parts = signature.strip().split("-")
        return len(parts) == 3 and len(parts[0]) == 14 and len(parts[1]) == 10 and len(parts[2]) == 1

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Return the InChIKey itself as the identity candidate."""
        return [signature.strip().upper()]

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Not applicable (exact identifier)."""
        return []


def _sparql_reverse_lookup(
    inchikey_variant: str,
    session: requests.Session,
) -> list[str]:
    """IDSM SPARQL reverse lookup for InChIKey -> CID.

    Args:
        inchikey_variant: InChIKey variant string.
        session: Requests session with retry logic.

    Returns:
        List of unique CID strings extracted from PubChem compound URIs.
        Returns [] on any exception (soft-fail).
    """
    import re
    from urllib.parse import quote

    q = (
        'SELECT ?c WHERE { '
        '?c <http://semanticscience.org/resource/SIO_000008> ?d . '
        '?d a ?t . FILTER(CONTAINS(STR(?t), "InChIKey")) '
        '?d <http://semanticscience.org/resource/SIO_000300> ?v . '
        f'FILTER(?v = "{inchikey_variant}") '
        '}} LIMIT 2'
    )
    url = (
        "https://idsm.elixir-czech.cz/sparql/endpoint/idsm"
        f"?query={quote(q)}&format=application/sparql-results%2Bjson"
    )

    try:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        cids: list[str] = []
        seen: set[str] = set()
        for b in data.get("results", {}).get("bindings", []):
            uri = b.get("c", {}).get("value", "")
            m = re.search(r"/CID(\d+)", uri)
            if m:
                cid = m.group(1)
                if cid not in seen:
                    seen.add(cid)
                    cids.append(cid)
        return cids
    except Exception:
        return []


def fetch_cids_from_inchikey(
    inchikey: str,
    session: requests.Session,
    config: RunConfig,
) -> list[str]:
    """Fetch PubChem CIDs for an InChIKey via PUG-REST with IDSM SPARQL fallback.

    Args:
        inchikey: InChIKey string (should be uppercase).
        session: Requests session with retry logic.
        config: RunConfig for retry settings.

    Returns:
        List of CID strings. May be empty. Does not raise for network failures.

    Raises:
        IdentifierResolutionError: Only for truly malformed usage.
    """
    # (a) Build query variants: if key ends with '-N' use [key]; else use [key, key[:-1] + 'N']
    if inchikey.endswith("-N"):
        variants = [inchikey]
    else:
        variants = [inchikey, inchikey[:-1] + "N"]

    all_cids: list[str] = []
    seen: set[str] = set()

    for variant in variants:
        # (b) Try the existing PUG call first
        url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/{variant}/cids/txt"
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 404:
                # InChIKey not found - try next variant
                continue
            response.raise_for_status()
            cids_text = response.text.strip()

            if cids_text and "status" not in cids_text.lower():
                for cid in cids_text.split("\n"):
                    cid = cid.strip()
                    if cid.isnumeric() and cid not in seen:
                        seen.add(cid)
                        all_cids.append(cid)
                if all_cids:
                    return all_cids  # PUG succeeded, return immediately
        except requests.HTTPError:
            # Non-404 HTTP error -> fall through to SPARQL
            pass
        except Exception:
            # Other exception -> fall through to SPARQL
            pass

        # (c) If PUG failed or returned no CIDs, try IDSM SPARQL reverse lookup
        sparql_cids = _sparql_reverse_lookup(variant, session)
        for cid in sparql_cids:
            if cid not in seen:
                seen.add(cid)
                all_cids.append(cid)

    # (d) Return the collected CID list (may be empty). Never raise for network failures.
    return all_cids
