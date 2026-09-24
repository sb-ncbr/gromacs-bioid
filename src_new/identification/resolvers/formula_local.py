"""Molecular formula resolver backed by the local PubChem mirror DB.

Offline-by-design replacement for the PUG fastformula endpoint (our cluster
egress IPs are blacklisted at NCBI; see docs/PLAN_PUBCHEM_MIRROR.md §8).
Lookup is a local SQLite index scan; no network, no pacing needed.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ...molecules.pubchem_db import PubChemDB
from .formula import FormulaResolver
from ..base import IdentifierResolutionError

if TYPE_CHECKING:
    from ...config.loader import RunConfig

logger = logging.getLogger("identifier")

# Legacy PUG `cids/txt` returned the full match list. 2000 keeps recall on
# large formula classes while staying orders of magnitude cheaper than the
# old fetch-every-candidate-from-PUG pattern (verification fetch is local too).
_LIMIT = 2000


class FormulaLocalResolver(FormulaResolver):
    """Molecular formula -> PubChem CIDs via the local mirror DB."""

    name = "formula_pubchem_local"
    identifier_type = "PUBCHEM_CID"
    accepted_signatures = ["formula"]

    def __init__(self, config: "RunConfig") -> None:
        # Skip FormulaResolver.__init__ (it builds a PUG retry session);
        # the base IdentifierResolver init is sufficient for a local source.
        from ..base import IdentifierResolver

        IdentifierResolver.__init__(self, config)
        self._db = PubChemDB(config.pubchem.local_db_path)

    def _resolve_identity(self, signature: str, working_directory: str) -> list[str]:
        """Resolve molecular formula to PubChem CID(s) via the local mirror."""
        try:
            return [str(cid) for cid in self._db.by_formula(signature.strip(), limit=_LIMIT)]
        except ValueError:
            # not a parseable formula -> treat as absent (matches 404 semantics)
            return []
        except Exception as exc:
            raise IdentifierResolutionError(
                f"[Identifier] Local PubChem mirror formula lookup failed: {exc}"
            ) from exc
