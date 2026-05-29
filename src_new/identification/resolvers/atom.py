"""Atom element identifier resolver."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..base import IdentifierResolver, IdentifierResolutionError

if TYPE_CHECKING:
    from ...config.loader import RunConfig

logger = logging.getLogger("identifier")


class AtomResolver(IdentifierResolver):
    """Resolver for element signatures.

    Pass-through resolver that returns the element signature as-is.
    Similarity search is not applicable for atoms.
    """

    name = "atom"
    identifier_type = "ELEMENT"
    accepted_signatures = ["element"]

    def __init__(self, config: RunConfig) -> None:
        """Initialize atom resolver.

        Args:
            config: RunConfig instance (unused, present for API compatibility).
        """
        super().__init__(config)

    def _is_applicable(self, signature: str) -> bool:
        """Check if signature is applicable.

        Args:
            signature: The element symbol.

        Returns:
            True (all element signatures are applicable).
        """
        return True

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve element signature to identifier.

        Pass-through: returns the signature as-is.

        Args:
            signature: Element symbol (e.g. "C", "N", "O").
            working_directory: Unused.

        Returns:
            List containing the element symbol.
        """
        return [signature]

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        """Resolve element to similar identifiers.

        Atomic similarity is not applicable (as per design decision).
        Returns empty list.

        Args:
            signature: Element symbol.
            working_directory: Unused.

        Returns:
            Empty list.
        """
        return []
