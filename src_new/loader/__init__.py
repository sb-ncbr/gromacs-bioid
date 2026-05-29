"""Loader module for BAT3 pipeline."""

from .strategies import LoadStrategy, LoadingResult, load_simulation
from .repair import TopologyRepair, RepairReport
from .universe_facade import (
    LoadedUniverse,
    SegmentProperty,
    SegmentProperties,
    UniverseParameter,
)
from .fragment_store import FragmentStore
from .export_mmcif import export_system_mmcif, export_segment_mmcif

__all__ = [
    "LoadStrategy", "LoadingResult", "load_simulation",
    "TopologyRepair", "RepairReport",
    "LoadedUniverse", "SegmentProperty", "SegmentProperties", "UniverseParameter",
    "FragmentStore",
    "export_system_mmcif", "export_segment_mmcif",
]
