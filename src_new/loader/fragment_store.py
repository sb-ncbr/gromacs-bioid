from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from ..molecules.instances import MoleculeInstance, MoleculeType
from ..molecules.uniqueness import (
    compute_uniqueness_key,
    collapse_to_unique_instances,
    group_by_uniqueness,
    count_unique_by_type,
    create_fingerprint,
)
from ..results.results_manager import ResultsManager
from .universe_facade import LoadedUniverse

logger = logging.getLogger("base")


def _convert_to_native(obj):
    """Convert numpy types to native Python types for JSON serialization."""
    if hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    elif isinstance(obj, dict):
        return {k: _convert_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_native(item) for item in obj]
    return obj


class FragmentStore:
    def __init__(self, facade: LoadedUniverse, results: ResultsManager | None = None):
        self.facade = facade
        self.results = results
        self._instances = self._build_instances()
        self._unique = collapse_to_unique_instances(self._instances)
        self._groups = group_by_uniqueness(self._instances)
        self._whole_system = self._build_whole_system_instance()
        self._record_summary()

    def _build_instances(self) -> list[MoleculeInstance]:
        instances = []
        for segment_name in sorted(self.facade.get_segments()):
            instance = self.facade.extract_molecule_instance(segment_name)
            props = self.facade.get_segment_properties(segment_name)
            
            # Override copy_number with actual fragment count in segment
            instance = MoleculeInstance(
                instance_id=instance.instance_id,
                atom_indices=instance.atom_indices,
                residue_indices=instance.residue_indices,
                segment_ids=instance.segment_ids,
                chain_ids=instance.chain_ids,
                resids=instance.resids,
                resnames=instance.resnames,
                molecule_type=instance.molecule_type,
                copy_number=props.molecule_count,
                confidence=instance.confidence,
                provenance=instance.provenance,
                atom_count=instance.atom_count,
                element_composition=instance.element_composition,
            )
            instances.append(instance)
        return instances

    def _build_whole_system_instance(self) -> MoleculeInstance:
        u = self.facade.universe
        composition = {}
        if hasattr(u.atoms, 'elements'):
            for elem in u.atoms.elements:
                if elem:
                    composition[elem] = composition.get(elem, 0) + 1

        # resname-less engines (LAMMPS .data): UNK instead of NoDataError
        try:
            resnames = list(u.residues.resnames)
        except Exception:  # NoDataError in MDAnalysis 2.x
            resnames = ["UNK"] * len(u.residues)

        return MoleculeInstance(
            instance_id="mol_SYSTEM",
            atom_indices=list(u.atoms.indices),
            residue_indices=list(range(len(u.residues))),
            segment_ids=list(self.facade.get_segments()),
            chain_ids=list(set(u.atoms.segids)),
            resids=list(u.residues.resids),
            resnames=resnames,
            molecule_type=MoleculeType.UNKNOWN,
            copy_number=1,
            atom_count=len(u.atoms),
            element_composition=composition,
            provenance={"source": "whole_system"},
        )

    def get_all_instances(self) -> list[MoleculeInstance]:
        return self._instances.copy()

    def get_unique_molecules(self) -> dict[str, MoleculeInstance]:
        """Key -> representative instance."""
        return dict(self._unique)

    def get_grouped_molecules(self) -> dict[str, list[MoleculeInstance]]:
        """Key -> list of all instances sharing that key."""
        return {k: list(v) for k, v in self._groups.items()}

    def get_copy_count(self, key: str) -> int:
        return len(self._groups.get(key, []))

    def get_segment_names_for_key(self, key: str) -> list[str]:
        return [inst.segment_ids[0] for inst in self._groups.get(key, [])]

    def get_whole_system_instance(self) -> MoleculeInstance:
        return self._whole_system

    def get_unique_counts_by_type(self) -> dict[str, int]:
        return count_unique_by_type(self._instances)

    def get_total_fragment_count(self) -> int:
        return sum(inst.copy_number for inst in self._instances)

    def _record_summary(self) -> None:
        if self.results is None:
            return

        # Record unique molecules
        unique_data = {}
        for key, inst in self._unique.items():
            inst_data = inst.__dict__.copy()
            inst_data["copy_count"] = self.get_copy_count(key)
            inst_data["segment_names"] = self.get_segment_names_for_key(key)
            # Convert all values to native Python types for JSON serialization
            unique_data[key] = _convert_to_native(inst_data)

        self.results.set_data("fragments/unique", unique_data)

        # Record counts by type
        counts = self.get_unique_counts_by_type()
        self.results.set_data("fragments/type_counts", counts)

        # Record total fragment count
        self.results.set_data("fragments/total_fragment_count", self.get_total_fragment_count())

        # Record instance list (simplified)
        self.results.set_data("fragments/segments", [
            {"segment": inst.segment_ids[0], "type": inst.molecule_type.value, "copies": inst.copy_number,
             "atoms_per_copy": inst.atom_count}
            for inst in self._instances
        ])

        # F19: presence/coordination scan for ion-channel elements (metals
        # incl. halides). Add-only; never fails analyze_universe.
        try:
            from .metal_scan import scan_metals
            visible = set()
            for inst in self._instances:
                for el in (inst.element_composition or {}):
                    visible.add(el)
            self.results.set_data(
                "fragments/metals",
                _convert_to_native(scan_metals(self.facade.universe,
                                               visible_elements=visible)),
            )
        except Exception as exc:  # defensive: metals scan must not break the step
            try:
                self.results.set_data(
                    "fragments/metals",
                    {"schema": 1, "error": f"{type(exc).__name__}: {exc}",
                     "present_elements": [], "element_atom_counts": {},
                     "atoms": [],
                     "context": {"computed": False, "reason": "scan_crash",
                                 "transition_atom_count": 0},
                     "newly_visible_elements": []})
            except Exception:
                pass
