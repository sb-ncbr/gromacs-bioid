"""Lipid shorthand identifier resolver using LIPID MAPS REST API."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from urllib.parse import quote

import requests

from ..base import IdentifierResolver, IdentifierResolutionError

if TYPE_CHECKING:
    from ...config.loader import RunConfig

logger = logging.getLogger("identifier")


class LipidShorthandResolver(IdentifierResolver):
    """Resolver for lipid shorthand signatures using LIPID MAPS REST API.

    Converts lipid shorthand (e.g. "PC(16:0/18:1)") to LIPID MAPS ID via REST API.
    """

    name = "lipid_maps"
    identifier_type = "LM_ID"
    accepted_signatures = ["lipid_shorthand"]

    def __init__(self, config: RunConfig) -> None:
        """Initialize lipid shorthand resolver.

        Args:
            config: RunConfig instance (unused, present for API compatibility).
        """
        super().__init__(config)
        self._session = requests.Session()

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature is applicable.

        Args:
            signature: The lipid shorthand string.

        Returns:
            True (all lipid_shorthand signatures are applicable).
        """
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve lipid shorthand to LIPID MAPS ID.

        Args:
            signature: Lipid shorthand string (e.g. "PC(16:0/18:1)").
            working_directory: Unused.

        Returns:
            List containing LIPID MAPS ID if found, empty list otherwise.

        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        # URL-encode the shorthand
        encoded_shorthand = quote(signature, safe="")
        url = f"https://www.lipidmaps.org/rest/compound/abbrev/{encoded_shorthand}/structure"

        try:
            response = self._session.get(url, timeout=30)
            response.raise_for_status()

            # Try to parse as JSON
            try:
                data = response.json()
                # Check for id or lm_id in response
                if isinstance(data, dict):
                    lm_id = data.get("id") or data.get("lm_id")
                    if lm_id:
                        return [str(lm_id)]
            except (ValueError, KeyError):
                pass

            # If response is a single string that looks like an ID, return it
            text = response.text.strip()
            if text and not text.startswith("<"):
                return [text]

            return []
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                # Lipid not found - return empty, not an error
                return []
            raise IdentifierResolutionError(f"[Identifier] LIPID MAPS lookup failed: {exc}")
        except Exception as exc:
            raise IdentifierResolutionError(f"[Identifier] LIPID MAPS lookup failed: {exc}")

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve lipid shorthand to similar identifiers.

        Not implemented for lipid shorthand. Returns empty list.

        Args:
            signature: Lipid shorthand string.
            working_directory: Unused.

        Returns:
            Empty list.
        """
        return []
