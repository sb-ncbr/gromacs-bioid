"""mmCIF signature generator."""

from __future__ import annotations

import logging
from io import StringIO

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance
from ...loader.universe_facade import LoadedUniverse, SegmentProperty
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class MmCifGenerator(SignatureGenerator):
    """mmCIF string generator."""
    
    name = "mmcif"
    signature_type = "mmcif"
    
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config)
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        segment_name = fragment.segids[0] if len(fragment.segids) > 0 else ""
        props = facade.get_segment_properties(segment_name)
        
        # Need positions
        return props.flags.get(SegmentProperty.HAS_POSITIONS.value, False)
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        stringio = StringIO()
        fragment.write(stringio, format="mmCIF")
        return stringio.getvalue()
