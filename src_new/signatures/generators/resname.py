"""Residue-name signature generator (thin emitter for CCD resolution).

Emits the raw residue name of a molecule when it is UNAMBIGUOUS (exactly one
distinct resname in the fragment). Zero intelligence here - name semantics,
alias mapping and CCD matching all live in the ccd_template resolver (F8).
"""

from __future__ import annotations

import logging
from typing import Optional

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class ResnameGenerator(SignatureGenerator):
    """Emit the single distinct residue name of a fragment, or None."""

    name = "resname"
    signature_type = "name"

    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)

    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        names = {str(r).strip() for r in (instance.resnames or []) if str(r).strip()}
        if not names:
            try:
                names = {str(x) for x in set(fragment.resnames)} - {""}
            except Exception:
                names = set()
        return len(names) == 1

    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> Optional[str]:
        names = {str(r).strip() for r in (instance.resnames or []) if str(r).strip()}
        if not names and hasattr(fragment, "resnames"):
            names = {str(x) for x in set(fragment.resnames)} - {""}
        return next(iter(names)) if len(names) == 1 else None
