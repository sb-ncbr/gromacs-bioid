"""Supplementary: ChEBI lookups from the local index (no network).

Same database as idsm_chebi (one evidence family in verification), but an
exact InChIKey lookup that does not depend on the IDSM service: identity on
the first two blocks (protonation flag ignored), similarity on the first
block (other stereo). Identifiers use the "CHEBI:<n>" form idsm_chebi uses,
so hits from both pool into one candidate.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..base import IdentifierResolver
from ..reference_indexes import chebi_by_ik, inchikey_blocks

if TYPE_CHECKING:
    from ...config.loader import RunConfig

_MAX_HITS = 10
_STEREO_VARIANT_SCORE = 90.0


class ChebiLocalResolver(IdentifierResolver):
    name = "chebi_local"
    identifier_type = "CHEBI_ID"
    accepted_signatures = ["inchikey"]
    supplementary = True

    def __init__(self, config: RunConfig) -> None:
        super().__init__(config)
        self._db = config.identifiers.chebi_db

    def _is_applicable(self, signature: str) -> bool:
        return inchikey_blocks(signature) is not None

    def _identity_ids(self, signature: str) -> list[str]:
        blocks = inchikey_blocks(signature)
        if not blocks:
            return []
        return [r[0] for r in chebi_by_ik(self._db, blocks[1], "ik25")[:_MAX_HITS]]

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        return self._identity_ids(signature)

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        blocks = inchikey_blocks(signature)
        if not blocks:
            return []
        exact = set(self._identity_ids(signature))
        rows = [r for r in chebi_by_ik(self._db, blocks[2], "ik14") if r[0] not in exact]
        return [(r[0], _STEREO_VARIANT_SCORE) for r in rows[:_MAX_HITS]]
