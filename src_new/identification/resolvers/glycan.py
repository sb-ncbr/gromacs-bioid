"""Glycan composition identifier resolver using GlyCosmos API."""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import requests

from ..base import IdentifierResolver, IdentifierResolutionError

if TYPE_CHECKING:
    from ...config.loader import RunConfig

logger = logging.getLogger("identifier")


class GlycanCompositionResolver(IdentifierResolver):
    """Resolver for glycan composition signatures using GlyCosmos API.

    Converts glycan composition (e.g. "Hex(3)HexNAc(2)dHex(1)") to GlyTouCan ID
    via GlyCosmos Composition API.
    """

    name = "glycan_composition"
    identifier_type = "GLYTOUCAN_ID"
    accepted_signatures = ["glycan_composition"]

    def __init__(self, config: RunConfig) -> None:
        """Initialize glycan composition resolver.

        Args:
            config: RunConfig instance (unused, present for API compatibility).
        """
        super().__init__(config)
        self._session = requests.Session()

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature is applicable.

        Args:
            signature: The glycan composition string.

        Returns:
            True (all glycan_composition signatures are applicable).
        """
        return True

    def _parse_composition(self, composition: str) -> dict[str, int]:
        """Parse glycan composition string into dict.

        Args:
            composition: Composition string (e.g. "Hex(3)HexNAc(2)dHex(1)").

        Returns:
            Dict mapping GlyCosmos fields to counts.
        """
        result: dict[str, int] = {}
        
        # Regex to match monosaccharide classes: Name(count)
        pattern = r"([A-Za-z]+)\((\d+)\)"
        
        # Mapping from common names to GlyCosmos fields (case-insensitive)
        field_mapping = {
            "hex": "hex",
            "hexnac": "hexnac",
            "dhex": "dhex",
            "neu5ac": "neu5ac",
            "neu5g": "neu5g",  # Also handle Neu5Gc
        }
        
        for match in re.finditer(pattern, composition):
            name = match.group(1).lower()
            count = int(match.group(2))
            
            if name in field_mapping:
                glycosmos_field = field_mapping[name]
                result[glycosmos_field] = result.get(glycosmos_field, 0) + count
            # Unmatched classes (like "X") are skipped
        
        return result

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve glycan composition to GlyTouCan ID.

        Args:
            signature: Glycan composition string (e.g. "Hex(3)HexNAc(2)dHex(1)").
            working_directory: Unused.

        Returns:
            List containing GlyTouCan ID or WURCS if found, empty list otherwise.

        Raises:
            IdentifierResolutionError: If resolution fails.
        """
        # Parse the composition
        composition_dict = self._parse_composition(signature)
        
        if not composition_dict:
            return []

        url = "https://api.glycosmos.org/glycancompositionconverter/1.0.0/composition2wurcs"
        
        try:
            response = self._session.post(
                url,
                json=composition_dict,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Look for id (GlyTouCan ID) or wurcs in response
            glytoucan_id = data.get("id")
            if glytoucan_id:
                return [str(glytoucan_id)]
            
            wurcs = data.get("wurcs")
            if wurcs:
                return [str(wurcs)]
            
            return []
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code == 404:
                # Glycan not found - return empty, not an error
                return []
            raise IdentifierResolutionError(f"[Identifier] GlyCosmos lookup failed: {exc}")
        except Exception as exc:
            raise IdentifierResolutionError(f"[Identifier] GlyCosmos lookup failed: {exc}")

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve glycan composition to similar identifiers.

        Not implemented for glycan composition. Returns empty list.

        Args:
            signature: Glycan composition string.
            working_directory: Unused.

        Returns:
            Empty list.
        """
        return []
