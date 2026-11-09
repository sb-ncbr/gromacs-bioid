"""Supplementary: SwissLipids lookups from the local index.

Identity: the molecule's InChIKey matches a SwissLipids structure on the
first two blocks (skeleton + stereo; the protonation flag is ignored, since
SwissLipids records the pH 7.3 form), or its lipid shorthand names an
isomeric subspecies ("PC(16:0/18:1(9Z))" -> SLM:000000651). Similarity: the
first block only (same skeleton, other stereo). Hits are verified like every
chemical candidate (skeleton fingerprint against the index's SMILES).
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..base import IdentifierResolver
from ..reference_indexes import inchikey_blocks, swisslipids_by_abbrev, swisslipids_by_ik

if TYPE_CHECKING:
    from ...config.loader import RunConfig

_MAX_HITS = 10
_STEREO_VARIANT_SCORE = 90.0
_ISOMERIC = "Isomeric subspecies"


class SwissLipidsResolver(IdentifierResolver):
    name = "swisslipids"
    identifier_type = "SLM_ID"
    accepted_signatures = ["inchikey", "lipid_shorthand"]
    supplementary = True

    def __init__(self, config: RunConfig) -> None:
        super().__init__(config)
        self._db = config.identifiers.swisslipids_db

    def _is_applicable(self, signature: str) -> bool:
        return bool(signature and signature.strip())

    def _identity_ids(self, signature: str) -> list[str]:
        blocks = inchikey_blocks(signature)
        if blocks:
            rows = swisslipids_by_ik(self._db, blocks[1], "ik25")
        else:
            rows = [r for r in swisslipids_by_abbrev(self._db, signature.strip()) if r[1] == _ISOMERIC]
        return [r[0] for r in rows[:_MAX_HITS]]

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        return self._identity_ids(signature)

    def _resolve_similarity(self, signature: str, working_directory: str) -> list[tuple[str, float]]:
        blocks = inchikey_blocks(signature)
        if not blocks:
            return []
        exact = set(self._identity_ids(signature))
        rows = [r for r in swisslipids_by_ik(self._db, blocks[2], "ik14") if r[0] not in exact]
        return [(r[0], _STEREO_VARIANT_SCORE) for r in rows[:_MAX_HITS]]
