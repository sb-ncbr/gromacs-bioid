"""Name signature generators."""

from __future__ import annotations

import logging
from enum import Enum

from MDAnalysis import AtomGroup

from ...config.loader import SignaturesConfig
from ...molecules.instances import MoleculeInstance, MoleculeType
from ...loader.universe_facade import LoadedUniverse
from ..base import SignatureGenerator

logger = logging.getLogger("base")


class NameGeneratorSource(Enum):
    CHAIN = 1
    MOLECULE = 2
    SEGMENT = 3


class NameGenerator(SignatureGenerator):
    """Base class for name-based generators."""
    
    signature_type = "name"
    
    def __init__(self, config: SignaturesConfig, source: NameGeneratorSource) -> None:
        super().__init__(config)
        self._source = source
        
        if source == NameGeneratorSource.CHAIN:
            self.name = "name_chain"
        elif source == NameGeneratorSource.MOLECULE:
            self.name = "name_molecule"
        elif source == NameGeneratorSource.SEGMENT:
            self.name = "name_segment"
    
    def _is_applicable(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> bool:
        min_name_len = self.config.name_minimum_length
        
        match self._source:
            case NameGeneratorSource.CHAIN:
                return (
                    len(instance.chain_ids) > 0
                    and len(instance.chain_ids[0]) >= min_name_len
                )
            case NameGeneratorSource.MOLECULE:
                # Use molecule_type as the "moltype" equivalent
                mtype_str = instance.molecule_type.value if instance.molecule_type else ""
                return len(mtype_str) >= min_name_len
            case NameGeneratorSource.SEGMENT:
                return (
                    len(instance.segment_ids) > 0
                    and '_' in instance.segment_ids[0]
                    and len(instance.segment_ids[0].split("_", maxsplit=2)[-1]) >= min_name_len
                )
        return False
    
    def _generate(
        self,
        instance: MoleculeInstance,
        fragment: AtomGroup,
        facade: LoadedUniverse,
    ) -> str:
        match self._source:
            case NameGeneratorSource.CHAIN:
                return instance.chain_ids[0]
            case NameGeneratorSource.MOLECULE:
                return instance.molecule_type.value if instance.molecule_type else ""
            case NameGeneratorSource.SEGMENT:
                return instance.segment_ids[0].split("_", maxsplit=2)[-1]
        
        raise RuntimeError("Unknown name source")


class ChainNameGenerator(NameGenerator):
    """Chain ID-based name generator."""
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, NameGeneratorSource.CHAIN)


class MoleculeNameGenerator(NameGenerator):
    """Molecule type-based name generator."""
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, NameGeneratorSource.MOLECULE)


class SegmentNameGenerator(NameGenerator):
    """Segment ID-based name generator."""
    def __init__(self, config: SignaturesConfig) -> None:
        super().__init__(config, NameGeneratorSource.SEGMENT)
