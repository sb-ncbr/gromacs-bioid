from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import MDAnalysis
from MDAnalysis import Universe, AtomGroup

from ..config.loader import RunConfig
from ..input.models import LoadDecision
from ..loader.repair import RepairReport
from ..molecules.instances import MoleculeInstance, MoleculeType
from ..molecules.nucleic_acid import (
    has_cross_residue_phosphodiester,
    normalize_nucleic_resname,
    residue_has_sugar_phosphate,
)
from ..results.results_manager import ResultsManager

logger = logging.getLogger("base")

# Import residue/nucleic constants from src (read-only import, do not modify src)
try:
    from src.constants import KNOWN_RESIDUE_CODES, KNOWN_NUCLEIC_ACIDS_CODES
except ImportError:
    # Fallback minimal copies for isolated execution
    KNOWN_RESIDUE_CODES = {
        'ALA': 'A', 'ARG': 'R', 'ASN': 'N', 'ASP': 'D', 'CYS': 'C',
        'GLU': 'E', 'GLN': 'Q', 'GLY': 'G', 'HIS': 'H', 'ILE': 'I',
        'LEU': 'L', 'LYS': 'K', 'MET': 'M', 'PHE': 'F', 'PRO': 'P',
        'SER': 'S', 'THR': 'T', 'TRP': 'W', 'TYR': 'Y', 'VAL': 'V',
    }
    KNOWN_NUCLEIC_ACIDS_CODES = {
        'A': 'A', 'C': 'C', 'T': 'T', 'G': 'G', 'U': 'U',
        'DA': 'A', 'DC': 'C', 'DT': 'T', 'DG': 'G', 'DU': 'U',
        'RA': 'A', 'RC': 'C', 'RT': 'T', 'RG': 'G', 'RU': 'U',
    }


class SegmentProperty(str, Enum):
    HAS_ELEMENTS = "has_elements"
    HAS_MASSES = "has_masses"
    HAS_POSITIONS = "has_positions"
    HAS_NAMES = "has_names"
    HAS_UNIQUE_NAMES = "has_unique_names"
    IS_PROTEIN = "is_protein"
    IS_NUCLEIC = "is_nucleic"
    HAS_MULTI_ATOM_RESIDUES = "has_multi_atom_residues"


class UniverseParameter(str, Enum):
    ATOM_COUNT = "atom_count"
    RESIDUE_COUNT = "residue_count"
    SEGMENT_COUNT = "segment_count"
    FRAGMENT_COUNT = "fragment_count"


@dataclass
class SegmentProperties:
    atom_count_total: int = 0
    atom_count_fragment: int = 0
    residue_count: int = 0
    bond_count_total: int = 0
    bond_count_fragment: int = 0
    molecule_count: int = 0
    flags: dict[str, bool] = field(default_factory=dict)
    # Enhanced nucleic acid recognition audit trail (wave-7):
    # "name" = tier-1 resname match, "structure" = tier-2 structural probe,
    # "legacy_*" = enhanced mode disabled, "none" = not nucleic.
    na_detection: str = "none"
    na_structural_promotions: int = 0

    def to_dict(self) -> dict:
        return {
            "atom_count_total": self.atom_count_total,
            "atom_count_fragment": self.atom_count_fragment,
            "residue_count": self.residue_count,
            "bond_count_total": self.bond_count_total,
            "bond_count_fragment": self.bond_count_fragment,
            "molecule_count": self.molecule_count,
            "na_detection": self.na_detection,
            "na_structural_promotions": self.na_structural_promotions,
            **self.flags,
        }


class LoadedUniverse:
    """Facade wrapping a loaded+repaired MDAnalysis Universe.
    
    Analyzes segments, extracts fragments, records results, and produces
    MoleculeInstance objects for downstream deduplication.
    """
    
    # Enhanced nucleic acid recognition thresholds (wave-7). The acceptance
    # fraction keeps its historic 0.8 semantics (atom-resname weighted).
    # Segments with less than probe_floor tier-1 coverage are never probed
    # structurally (pure-ligand systems must not pay or risk false hits).
    _NA_ACCEPTANCE = 0.8
    _NA_STRUCTURAL_PROBE_FLOOR = 0.3

    def __init__(
        self,
        universe: Universe,
        decision: LoadDecision,
        repair_report: RepairReport,
        results: ResultsManager | None = None,
        filter_segments: set[str] | None = None,
        enhanced_nucleic_recognition: bool = True,
    ):
        self.universe = universe
        self.decision = decision
        self.repair_report = repair_report
        self.results = results
        self.filter_segments = filter_segments or set()
        self.enhanced_nucleic_recognition = enhanced_nucleic_recognition
        self._segments: set[str] = set()
        self._segment_properties: dict[str, SegmentProperties] = {}
        self._analyze()
        self._discover_virtual_segments()
        self._record_summary()
    
    def _is_polymer_segment(self, selected: AtomGroup) -> bool:
        """Check if segment is a polymer (protein or nucleic acid).
        
        Args:
            selected: AtomGroup for the segment.
            
        Returns:
            True if >= 80% of residues are known protein or nucleic acid residues.
        """
        if not hasattr(selected.atoms, 'resnames'):
            return False
        
        resnames = selected.atoms.resnames
        if len(resnames) == 0:
            return False
        
        # Count how many residues are known protein/nucleic acid
        known_count = sum(
            1 for rn in resnames
            if rn.upper() in KNOWN_RESIDUE_CODES or rn.upper() in KNOWN_NUCLEIC_ACIDS_CODES
        )
        
        # Return True if >= 80% are known
        return known_count / len(resnames) >= 0.8
    
    def _analyze(self) -> None:
        """Analyze all segments in the universe."""
        all_segments = set(self.universe.segments.segids)
        
        if self.filter_segments:
            self._segments = all_segments & self.filter_segments
        else:
            self._segments = all_segments
        
        for segment_name in self._segments:
            selected = self.universe.atoms[self.universe.atoms.segids == segment_name]
            props = SegmentProperties()
            
            props.atom_count_total = len(selected.atoms)
            props.bond_count_total = len(selected.bonds) if hasattr(selected.atoms, 'bonds') else 0
            
            # Get representative fragment using same logic as get_fragment
            fragment = self.get_fragment(segment_name)
            
            if fragment is selected:
                # Fallback case: no bonds or full segment returned
                props.atom_count_fragment = len(selected.atoms)
                props.bond_count_fragment = len(selected.bonds) if hasattr(selected.atoms, "bonds") else 0
                try:
                    fragments = selected.fragments
                except MDAnalysis.exceptions.NoDataError:
                    fragments = []
                props.molecule_count = len(fragments) if fragments else 1
                props.residue_count = len(selected.residues)
            else:
                # Real connected sub-fragment
                props.atom_count_fragment = len(fragment.atoms)
                props.bond_count_fragment = len(fragment.bonds) if hasattr(fragment.atoms, 'bonds') else 0
                try:
                    fragments = selected.fragments
                except MDAnalysis.exceptions.NoDataError:
                    fragments = []
                props.molecule_count = len(fragments)
                props.residue_count = len(fragment.residues)
            
            # Compute flags using the same representative fragment
            props.flags, na_meta = self._compute_flags(selected, fragment)
            props.na_detection = na_meta["na_detection"]
            props.na_structural_promotions = na_meta["na_structural_promotions"]
            
            self._segment_properties[segment_name] = props
    
    def _compute_flags(
        self, selected: AtomGroup, representative: AtomGroup | None
    ) -> tuple[dict[str, bool], dict[str, Any]]:
        """Compute boolean flags for a segment.

        Returns: (flags, na_meta) where na_meta carries the wave-7 nucleic
        acid detection audit trail.
        """
        flags = {}
        na_meta = {"na_detection": "none", "na_structural_promotions": 0}
        
        # HAS_ELEMENTS: all non-empty
        if hasattr(selected.atoms, 'elements'):
            flags[SegmentProperty.HAS_ELEMENTS.value] = all(e for e in selected.atoms.elements)
        else:
            flags[SegmentProperty.HAS_ELEMENTS.value] = False
        
        # HAS_MASSES: all > 0
        if hasattr(selected.atoms, 'masses'):
            flags[SegmentProperty.HAS_MASSES.value] = all(m > 0 for m in selected.atoms.masses)
        else:
            flags[SegmentProperty.HAS_MASSES.value] = False
        
        # HAS_POSITIONS
        flags[SegmentProperty.HAS_POSITIONS.value] = hasattr(selected.atoms, 'positions')
        
        # HAS_NAMES
        if hasattr(selected.atoms, 'names'):
            flags[SegmentProperty.HAS_NAMES.value] = any(n for n in selected.atoms.names)
        else:
            flags[SegmentProperty.HAS_NAMES.value] = False
        
        # HAS_UNIQUE_NAMES: within each residue of the representative fragment, names unique
        if representative is not None and hasattr(representative.atoms, 'names'):
            unique = True
            for residue in representative.residues:
                names = list(residue.atoms.names)
                if len(names) != len(set(names)):
                    unique = False
                    break
            flags[SegmentProperty.HAS_UNIQUE_NAMES.value] = unique
        else:
            flags[SegmentProperty.HAS_UNIQUE_NAMES.value] = False
        
        # IS_PROTEIN (use 80% threshold like _is_polymer_segment)
        if hasattr(selected.atoms, 'resnames'):
            resnames = selected.atoms.resnames
            known_count = sum(
                1 for rn in resnames if rn.upper() in KNOWN_RESIDUE_CODES
            )
            flags[SegmentProperty.IS_PROTEIN.value] = (
                len(resnames) > 0 and known_count / len(resnames) >= 0.8
            )
        else:
            flags[SegmentProperty.IS_PROTEIN.value] = False
        
        # IS_NUCLEIC (80% atom-resname threshold; wave-7 two-tier logic)
        is_nucleic, na_detection, na_promotions = self._classify_nucleic(
            selected, representative
        )
        flags[SegmentProperty.IS_NUCLEIC.value] = is_nucleic
        na_meta = {
            "na_detection": na_detection,
            "na_structural_promotions": na_promotions,
        }
        
        # HAS_MULTI_ATOM_RESIDUES
        if representative is not None:
            flags[SegmentProperty.HAS_MULTI_ATOM_RESIDUES.value] = any(
                len(res.atoms) > 1 for res in representative.residues
            )
        else:
            flags[SegmentProperty.HAS_MULTI_ATOM_RESIDUES.value] = False

        return flags, na_meta

    def _classify_nucleic(
        self, selected: AtomGroup, representative: AtomGroup | None
    ) -> tuple[bool, str, int]:
        """Classify a segment as nucleic acid (wave-7).

        Two modes:
          - enhanced_nucleic_recognition=False: bit-for-bit legacy behavior
            (closed KNOWN_NUCLEIC_ACIDS_CODES table, 80% atom-resname gate).
          - True (default): tier-1 liberal resname normalization; if the
            80% gate is missed but coverage beats the probe floor, a tier-2
            structural probe promotes residues with the full sugar-phosphate
            fingerprint - but only when a mandatory cross-residue
            phosphodiester bond exists in the representative fragment, so
            cofactors (CoA, ATP, NAD, FAD, free nucleotides) can never be
            promoted. Bondless fragments simply cannot promote (graceful).

        Returns: (is_nucleic, detection_tier, promoted_resname_count).
        """
        if not hasattr(selected.atoms, "resnames"):
            return False, "none", 0

        resnames = selected.atoms.resnames
        atom_total = len(resnames)
        if atom_total == 0:
            return False, "none", 0

        if not self.enhanced_nucleic_recognition:
            known_count = sum(
                1 for rn in resnames if rn.upper() in KNOWN_NUCLEIC_ACIDS_CODES
            )
            verdict = known_count / atom_total >= self._NA_ACCEPTANCE
            return verdict, ("legacy_name" if verdict else "none"), 0

        # Tier 1 must be a strict SUPERSET of the legacy table: the live
        # src.constants table already covers terminal codes and many modified
        # bases (PSU, H2U, 5MC, ...). The normalizer adds the long tail the
        # table cannot enumerate. Union -> no behavior regression possible.
        known_count = sum(
            1
            for rn in resnames
            if rn.upper() in KNOWN_NUCLEIC_ACIDS_CODES
            or normalize_nucleic_resname(rn) is not None
        )
        tier1_fraction = known_count / atom_total
        if tier1_fraction >= self._NA_ACCEPTANCE:
            return True, "name", 0

        if tier1_fraction < self._NA_STRUCTURAL_PROBE_FLOOR or representative is None:
            return False, "none", 0

        # Tier-2 structural probe: mandatory phosphodiester linkage guard.
        if not has_cross_residue_phosphodiester(representative):
            return False, "none", 0

        fingerprint_cache: dict[str, bool] = {}
        promoted_atoms = 0
        for residue in representative.residues:
            resname = residue.resname.strip().upper()
            if (
                resname in KNOWN_NUCLEIC_ACIDS_CODES
                or normalize_nucleic_resname(resname) is not None
            ):
                continue
            verdict = fingerprint_cache.get(resname)
            if verdict is None:
                verdict = residue_has_sugar_phosphate(list(residue.atoms.names))
                fingerprint_cache[resname] = verdict
            if verdict:
                promoted_atoms += len(residue.atoms)

        if (known_count + promoted_atoms) / atom_total >= self._NA_ACCEPTANCE:
            promotions = sum(1 for v in fingerprint_cache.values() if v)
            return True, "structure", promotions
        return False, "none", 0
    
    def _record_summary(self) -> None:
        """Record summary data to results manager."""
        if self.results is None:
            return
        
        for segment_name, props in self._segment_properties.items():
            self.results.set_data(f"universe/segments/{segment_name}/properties", props.to_dict())
        
        self.results.set_data("universe/parameters/atom_count", self.get_parameter(UniverseParameter.ATOM_COUNT))
        self.results.set_data("universe/parameters/residue_count", self.get_parameter(UniverseParameter.RESIDUE_COUNT))
        self.results.set_data("universe/parameters/segment_count", self.get_parameter(UniverseParameter.SEGMENT_COUNT))
        self.results.set_data("universe/parameters/fragment_count", self.get_parameter(UniverseParameter.FRAGMENT_COUNT))
        self.results.set_data("universe/repair_report", self.repair_report.to_dict())
        self.results.set_data("universe/decision", self.decision.to_dict())
        self.results.set_data("universe/segment_list", sorted(self._segments))
    
    _MAX_VIRTUAL_PER_SEGMENT = 64

    @staticmethod
    def _species_key(frag) -> tuple:
        """Cheap structural identity for copy clustering
        (atom count, residue count, sorted element counts)."""
        import collections
        try:
            elems = [(e or "?").upper() for e in frag.atoms.elements]
        except Exception:
            elems = ["?"] * len(frag.atoms)
        comp = tuple(sorted(collections.Counter(elems).items()))
        return (len(frag.atoms), len(frag.residues), comp)

    def _discover_virtual_segments(self) -> None:
        """Expose minority molecular species inside segid-coarse topologies.

        Many depositions pack membrane + solutes (ligands, cofactors, ions)
        + solvent under ONE segid; the classic one-instance-per-segment
        flow then only ever identifies the majority fragment class. Each
        unique minority fragment species is exposed as a virtual segment
        "seg__vN" (waters and tiny <=3-atom species skipped), so
        signatures, identification and verification process them.
        """
        self._virtual_fragments: dict = {}
        for segment_name in list(getattr(self, "_segments", ())):
            selected = self.universe.atoms[self.universe.atoms.segids == segment_name]
            try:
                fragments = selected.fragments
            except Exception:
                continue
            if not fragments or len(fragments) < 2:
                continue
            fragments = [f for f in fragments if len(set(f.atoms.segids)) == 1]
            if len(fragments) < 2:
                continue
            clusters: dict = {}
            for frag in fragments:
                clusters.setdefault(self._species_key(frag), []).append(frag)
            if len(clusters) < 2:
                continue
            rep_key = self._species_key(LoadedUniverse.get_fragment(self, segment_name))
            n = 0
            for key, members in sorted(clusters.items(), key=lambda kv: -len(kv[1][0].atoms)):
                if key == rep_key:
                    continue
                if len(members[0].atoms) <= 3:
                    continue  # waters / tiny species keep classic flow
                n += 1
                if n > self._MAX_VIRTUAL_PER_SEGMENT:
                    break
                vname = f"{segment_name}__v{n}"
                frag0 = members[0]
                self._virtual_fragments[vname] = frag0
                props = SegmentProperties(
                    atom_count_total=len(frag0.atoms),
                    atom_count_fragment=len(frag0.atoms),
                    bond_count_fragment=len(frag0.bonds) if hasattr(frag0, "bonds") else 0,
                    molecule_count=len(members),
                    residue_count=len(frag0.residues),
                )
                props.flags = self._compute_flags(frag0, frag0)
                self._segment_properties[vname] = props
        if self._virtual_fragments:
            logger.info(
                "Virtual minority segments discovered: %d (e.g. %s)",
                len(self._virtual_fragments),
                sorted(self._virtual_fragments)[:4],
            )

    def get_segments(self) -> set[str]:
        """Return set of segment IDs, including virtual minority segments."""
        segs = self._segments.copy()
        segs |= set(getattr(self, "_virtual_fragments", {}).keys())
        return segs
    
    def get_fragment(self, segment_name: str) -> AtomGroup:
        """Get the representative fragment for a segment.
        
        For polymer segments with broken bond topologies (e.g., partial CONECT records),
        returns the full segment instead of a tiny fragment.
        
        Args:
            segment_name: The segment ID.
            
        Returns:
            The representative AtomGroup (largest fragment or full segment for polymers).
        """
        virtual = getattr(self, "_virtual_fragments", {})
        if segment_name in virtual:
            return virtual[segment_name]

        if segment_name not in self._segments:
            raise KeyError(f"Segment '{segment_name}' not found")
        
        selected = self.universe.atoms[self.universe.atoms.segids == segment_name]
        
        try:
            fragments = selected.fragments
        except MDAnalysis.exceptions.NoDataError:
            fragments = []
        
        # Filter out fragments that span multiple segments (e.g., cross-segment disulfide bonds)
        if fragments:
            fragments = [
                f for f in fragments
                if len(set(f.atoms.segids)) == 1 and f.atoms.segids[0] == segment_name
            ]
        
        if not fragments:
            return selected  # fallback when no bonds
        
        # Get largest fragment
        largest = max(fragments, key=lambda f: len(f.atoms))
        
        # If largest fragment is most of the segment, return it
        if len(largest.atoms) >= len(selected.atoms) * 0.8:
            return largest
        
        # If this is a polymer segment, return full segment (broken bonds case)
        if self._is_polymer_segment(selected):
            return selected
        
        # Otherwise return largest fragment (small molecule case)
        return largest
    
    def get_segment_properties(self, segment_name: str) -> SegmentProperties:
        """Get properties for a segment."""
        if segment_name not in self._segment_properties:
            raise KeyError(f"Segment '{segment_name}' not found")
        return self._segment_properties[segment_name]
    
    def get_parameter(self, kind: UniverseParameter) -> int:
        """Get a universe-level parameter."""
        match kind:
            case UniverseParameter.ATOM_COUNT:
                return int(self.universe.atoms.n_atoms)
            case UniverseParameter.RESIDUE_COUNT:
                return int(self.universe.atoms.n_residues)
            case UniverseParameter.SEGMENT_COUNT:
                return int(self.universe.atoms.n_segments)
            case UniverseParameter.FRAGMENT_COUNT:
                try:
                    return int(self.universe.atoms.n_fragments)
                except Exception:
                    return 0
            case _:
                raise ValueError(f"Unknown parameter: {kind}")
    
    def extract_molecule_instance(self, segment_name: str) -> MoleculeInstance:
        """Extract a MoleculeInstance from a segment."""
        fragment = self.get_fragment(segment_name)
        props = self.get_segment_properties(segment_name)
        
        # Determine molecule type
        mtype = MoleculeType.UNKNOWN
        if props.flags.get(SegmentProperty.IS_PROTEIN.value):
            mtype = MoleculeType.PROTEIN
        elif props.flags.get(SegmentProperty.IS_NUCLEIC.value):
            mtype = MoleculeType.NUCLEIC
        elif props.atom_count_fragment == 1:
            mtype = MoleculeType.ION
        elif props.atom_count_fragment == 3 and any(rn in ("SOL", "HOH", "WAT") for rn in fragment.residues.resnames):
            mtype = MoleculeType.WATER
        # Element composition
        composition = {}
        if hasattr(fragment.atoms, 'elements'):
            for elem in fragment.atoms.elements:
                if elem:
                    composition[elem] = composition.get(elem, 0) + 1

        # Non-protein/nucleic classification using element composition.
        # Wave-7 fix: this block must only run as a fallback - previously it
        # overwrote PROTEIN/NUCLEIC verdicts whenever C/O heuristics matched
        # (DNA C/O ~= 2.4 hit the lipid band -> nucleic instances were
        # stamped LIPID and even emitted lipid_shorthand signatures).
        # Count C and O atoms from element_composition
        atom_c_cnt = composition.get("C", 0)
        atom_o_cnt = composition.get("O", 0)

        if mtype == MoleculeType.UNKNOWN:
            # Lipid detection: >10 C, >4 O, C/O ratio between 1 and 3
            if atom_c_cnt > 10 and atom_o_cnt > 4:
                c_o_ratio = atom_c_cnt / atom_o_cnt if atom_o_cnt > 0 else float('inf')
                if 1.0 < c_o_ratio < 3.0:
                    mtype = MoleculeType.LIPID

            # Carbohydrate detection: >5 C, >4 O, C/O ratio > 2
            elif atom_c_cnt > 5 and atom_o_cnt > 4:
                c_o_ratio = atom_c_cnt / atom_o_cnt if atom_o_cnt > 0 else float('inf')
                if c_o_ratio > 2.0:
                    mtype = MoleculeType.CARBOHYDRATE

            # Small molecule detection: not any of the above, atom_count > 1
            elif props.atom_count_fragment > 1:
                mtype = MoleculeType.SMALL_MOLECULE
        
        return MoleculeInstance(
            instance_id=f"mol_{segment_name}",
            atom_indices=list(fragment.atoms.indices),
            residue_indices=list(range(len(fragment.residues))),
            segment_ids=[segment_name],
            chain_ids=list(set(fragment.atoms.segids)),
            resids=list(fragment.residues.resids),
            resnames=list(fragment.residues.resnames),
            molecule_type=mtype,
            copy_number=props.molecule_count,
            atom_count=props.atom_count_fragment,
            element_composition=composition,
        )
    
    def extract_all_molecule_instances(self) -> list[MoleculeInstance]:
        """Extract MoleculeInstance for all segments."""
        return [self.extract_molecule_instance(seg) for seg in sorted(self._segments)]
