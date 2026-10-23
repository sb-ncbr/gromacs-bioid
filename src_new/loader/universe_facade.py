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
from ..molecules.instances import (
    LIPID_RESNAMES,
    WATER_RESNAMES,
    MoleculeInstance,
    MoleculeType,
)
from ..molecules.nucleic_acid import (
    has_cross_residue_phosphodiester,
    normalize_nucleic_resname,
    residue_has_sugar_phosphate,
)
from ..results.results_manager import ResultsManager

logger = logging.getLogger("base")

# F-27 (2026-10-05): single source of truth is src_new/constants.py
# (byte-value-identical promotion from src.constants, md5-verified).
# The old try/except "isolated execution" fallback carried SUBSET copies
# (20/54 residues, 15/80 nucleic codes) = silent degraded classification;
# deleted per ruling so this module always uses the canonical tables.
from ..constants import KNOWN_RESIDUE_CODES, KNOWN_NUCLEIC_ACIDS_CODES


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
        # A-13 (red-team 3.8): caches — get_fragment was re-selecting whole
        # segment AtomGroups and recomputing fragments and representatives on
        # every call (>=5 times per segment).
        self._selected_cache: dict[str, AtomGroup] = {}
        self._rep_cache: dict[str, AtomGroup] = {}
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
            
            if len(fragment.atoms) == len(selected.atoms):
                # Fallback case: no bonds or representative == whole segment
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
                # A-09 (red-team 3.6): copies = size of the representative's
                # own species cluster — not the raw fragment count, which
                # swept unrelated ions/ligands into the copy number (1920:
                # copies=80 incl. Cl/Na; 1567: copies=2 for one duplex).
                pool = self._polymer_fragments(selected, segment_name) or list(fragments)
                rep_src = max(pool, key=lambda f: len(f.atoms))
                rep_key = self._species_key(rep_src)
                props.molecule_count = sum(
                    1 for f in fragments if self._species_key(f) == rep_key)
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
        
        # Chemistry/typing flags are computed on the representative fragment
        # (v3.143: was the whole segment — ions/waters/virtual sites sharing a
        # segid silently untyped the real molecule, red-team A-01/A-03).
        flag_scope = representative if representative is not None else selected
        
        # HAS_ELEMENTS: all non-empty over REAL atoms (v3.143: massless
        # virtual sites no longer veto the representative's chemistry, A-11).
        if hasattr(flag_scope.atoms, 'elements'):
            pseudo = self._pseudo_atom_indices(flag_scope.atoms)
            elems = flag_scope.atoms.elements
            flags[SegmentProperty.HAS_ELEMENTS.value] = all(
                elems[i] for i in range(len(elems)) if i not in pseudo
            )
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
        if hasattr(flag_scope.atoms, 'resnames'):
            resnames = flag_scope.atoms.resnames
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
            flag_scope, representative
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

        # v3.143 (A-08): a single residue is NEVER a nucleic acid — free
        # nucleosides/nucleotides ('A', 'DA', 'G5') and ligands that collide
        # with base codes (DTX = digitoxigenin, fixture 4725) typed as NUCLEIC.
        n_residues = len(set(int(r) for r in selected.atoms.resindices)) \
            if hasattr(selected.atoms, "resindices") else 0
        if n_residues < 2:
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
        truncated = getattr(self, "_virtual_truncated", None)
        if truncated:
            # A-10: visible record of species dropped by the 64-per-segment cap
            self.results.set_data("universe/virtual_segments_truncated", truncated)
    
    _MAX_VIRTUAL_PER_SEGMENT = 64

    @staticmethod
    def _species_key(frag) -> tuple:
        """Cheap structural identity for copy clustering.

        A-10 (red-team 3.5): the formula-only key (atom count, residue count,
        sorted element counts) collides for ISOMERS — ATP vs dGTP
        (C10H16N5O13P3), glucose vs galactose, enantiomers — and only
        members[0] was ever identified. Extend with a sorted resname multiset
        and sorted bonded element-pair counts; enantiomers/tautomers still
        share a key (graphically indistinguishable at this price).
        """
        import collections
        try:
            elems = [(e or "?").upper() for e in frag.atoms.elements]
        except Exception:
            elems = ["?"] * len(frag.atoms)
        comp = tuple(sorted(collections.Counter(elems).items()))
        resnames = tuple(sorted(
            (r.resname or "?").strip().upper() for r in frag.residues))
        try:
            pair_ctr: collections.Counter = collections.Counter()
            idx2el = {a.index: elems[i] for i, a in enumerate(frag.atoms)}
            for b in frag.bonds:
                pair_ctr[tuple(sorted((idx2el[b.atoms[0].index],
                                       idx2el[b.atoms[1].index])))] += 1
            bond_pairs = tuple(sorted(pair_ctr.items()))
        except Exception:
            bond_pairs = ()
        return (len(frag.atoms), len(frag.residues), comp, resnames, bond_pairs)

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
        self._virtual_truncated: list[dict] = []
        for segment_name in list(getattr(self, "_segments", ())):
            selected = self._selected_cache.get(segment_name)
            if selected is None:  # A-13: compute once, reuse everywhere
                selected = self.universe.atoms[self.universe.atoms.segids == segment_name]
                self._selected_cache[segment_name] = selected
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
            # A-09: skip the representative-generating clusters (polymer
            # fragments when present, else the largest fragment's kind);
            # ligands/ions/waters now form their OWN virtual segments.
            poly = self._polymer_fragments(selected, segment_name)
            rep_pool = poly if poly else [max(fragments, key=lambda f: len(f.atoms))]
            rep_keys = {self._species_key(f) for f in rep_pool}
            rep_key = next(iter(rep_keys))  # kept for key-compat below
            n = 0
            vidx = 0
            # A-10: deterministic order so truncation is reproducible; dropped
            # species are RECORDED (universe/virtual_segments_truncated) instead
            # of vanishing silently past the cap.
            ordered = sorted(clusters.items(),
                             key=lambda kv: (-len(kv[1][0].atoms), repr(kv[0])))
            for key, members in ordered:
                if key in rep_keys:
                    continue
                tiny = len(members[0].atoms) <= 3
                if not tiny:
                    n += 1
                if not tiny and n > self._MAX_VIRTUAL_PER_SEGMENT:
                    cur = next(i for i, kv in enumerate(ordered) if kv[0] is key)
                    dropped = [kv for kv in ordered[cur:]
                               if kv[0] != rep_key and len(kv[1][0].atoms) > 3]
                    self._virtual_truncated.append({
                        "segment": segment_name,
                        "dropped_species": len(dropped),
                        "dropped_keys": [repr(kv[0]) for kv in dropped[:8]],
                    })
                    logger.warning(
                        "virtual_segments_truncated: segment %s dropped %d species past cap %d",
                        segment_name, len(dropped), self._MAX_VIRTUAL_PER_SEGMENT)
                    break
                vidx += 1
                vname = f"{segment_name}__v{vidx}"
                frag0 = members[0]
                self._virtual_fragments[vname] = frag0
                props = SegmentProperties(
                    atom_count_total=len(frag0.atoms),
                    atom_count_fragment=len(frag0.atoms),
                    bond_count_fragment=len(frag0.bonds) if hasattr(frag0, "bonds") else 0,
                    molecule_count=len(members),
                    residue_count=len(frag0.residues),
                )
                props.flags, na_meta = self._compute_flags(frag0, frag0)
                props.na_detection = na_meta["na_detection"]
                props.na_structural_promotions = na_meta["na_structural_promotions"]
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
    
    def _polymer_fragments(self, selected: AtomGroup, seg: str) -> list:
        """A-09 (red-team 3.6): fragments that are polymer by resname content.

        A fragment counts as polymer when >=50% of its atoms carry residues
        from the protein/NA tables. Covalently attached ligands ride along
        inside the same fragment (bond graph), non-covalent species stay in
        their own fragments — which is exactly what the old whole-segment
        representative got wrong (it swept ions/waters/ligands INTO both the
        composition and the copy number).
        """
        try:
            fragments = selected.fragments
        except MDAnalysis.exceptions.NoDataError:
            return []
        out = []
        for f in fragments:
            if len(set(f.atoms.segids)) != 1 or f.atoms.segids[0] != seg:
                continue
            total = 0
            poly = 0
            try:
                residues = list(f.residues)
            except Exception:
                continue
            for res in residues:
                rn = str(res.resname or "").strip().upper()
                n = len(res.atoms)
                total += n
                if (rn in KNOWN_RESIDUE_CODES or rn in KNOWN_NUCLEIC_ACIDS_CODES
                        or normalize_nucleic_resname(rn) is not None):
                    poly += n
                elif residue_has_sugar_phosphate(list(res.atoms.names)):
                    # modified/terminal nucleics the closed tables miss (ENAR
                    # tier-2 signal) — the chain stays polymer even when only
                    # its base atoms happen to carry table resnames
                    poly += n
            if total and poly / total >= 0.5:
                out.append(f)
        return out

    def get_fragment(self, segment_name: str) -> AtomGroup:
        """Get the representative fragment for a segment.
        
        For polymer segments with broken bond topologies (e.g., partial CONECT records),
        returns the full segment instead of a tiny fragment.
        
        Args:
            segment_name: The segment ID.
            
        Returns:
            The representative AtomGroup (largest fragment or full segment for polymers).
        """
        if segment_name in self._rep_cache:  # A-13: computed once per segment
            return self._rep_cache[segment_name]
        virtual = getattr(self, "_virtual_fragments", {})
        if segment_name in virtual:
            return virtual[segment_name]

        if segment_name not in self._segments:
            raise KeyError(f"Segment '{segment_name}' not found")

        selected = self._selected_cache.get(segment_name)
        if selected is None:
            selected = self.universe.atoms[self.universe.atoms.segids == segment_name]
            self._selected_cache[segment_name] = selected
        
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
            self._rep_cache[segment_name] = selected
            return selected  # fallback when no bonds
        
        # Get largest fragment
        largest = max(fragments, key=lambda f: len(f.atoms))

        # If largest fragment is most of the segment, return it
        if len(largest.atoms) >= len(selected.atoms) * 0.8:
            self._rep_cache[segment_name] = largest
            return largest

        # A-09 (red-team 3.6): polymer representative = union of polymer
        # fragments ONLY (both strands, covalently attached partners) — never
        # the whole segment with ions/ligands/waters swept into composition
        # and signatures (fixture 1602's chimeric duplex+92-atom ligand).
        poly = self._polymer_fragments(selected, segment_name)
        if poly:
            import numpy as _np
            idx = _np.array(sorted({int(i) for f in poly for i in f.atoms.indices}),
                            dtype=_np.int64)
            rep = self.universe.atoms[idx]
            self._rep_cache[segment_name] = rep
            return rep

        # If this is a polymer segment, return full segment (broken bonds case)
        if self._is_polymer_segment(selected):
            self._rep_cache[segment_name] = selected
            return selected

        # Otherwise return largest fragment (small molecule case)
        self._rep_cache[segment_name] = largest
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
    
    # --- segment typing (v3.140 rewrite; V-36) ------------------------------
    # Flat decision list — replaces a nested-if that had an unreachable-branch
    # blind spot: molecules with C>10, O>4 but C/O outside (1,3) matched the
    # OUTER if and fell through every branch as UNKNOWN (real phospholipids and
    # cardiolipins live at C/O ~ 4.5-5: TOCL2 81/17=4.76, POPE 39/8=4.88 in the
    # PE_CL regression run a5b785cc/b4813beb).
    #
    # Order (first hit wins):
    #   1. protein/nucleic flags   2. monoatomic ion
    #   3. water (resname table, else structural 1O+2H)
    #   4. lipid resname knowledge (forcefield_maps ground truth)
    #   5. composition bands: legacy glycerol lipid band (1,C/O,3), phospholipid
    #      band (P>0, 2.5<=C/O<=12), sugar band (no P, C/O>2)
    #   6. small molecule           7. UNKNOWN (never silently guessed)
    @staticmethod
    def _pseudo_atom_indices(atoms) -> set[int]:
        """v3.143 (A-11/B-13): virtual sites / massless particles (TIP4P MW,
        EPW, LP*, Drude) are not chemistry. Excluded from composition, water
        atom counts and element-completeness so four-site water is H2O, not
        H2O2 'hydrogen peroxide'. Masses are the robust signal; when absent,
        nothing is excluded (status quo ante)."""
        try:
            masses = atoms.masses
        except Exception:
            return set()
        try:
            return {i for i, m in enumerate(masses) if float(m) < 0.5}
        except Exception:
            return set()

    @staticmethod
    def _real_composition(atoms) -> tuple[dict, int]:
        """Element composition + atom count over REAL (non-pseudo) atoms."""
        composition: dict = {}
        real = 0
        pseudo = LoadedUniverse._pseudo_atom_indices(atoms)
        elements = getattr(atoms, "elements", None)
        try:
            n = len(atoms)
        except TypeError:  # duck-typed fixtures carry only .elements
            n = len(elements) if elements is not None else 0
        for i in range(n):
            if i in pseudo:
                continue
            real += 1
            elem = elements[i] if elements is not None else ""
            if elem:
                composition[elem] = composition.get(elem, 0) + 1
        return composition, real

    @staticmethod
    def _classify_molecule_type(props, fragment) -> MoleculeType:
        if props.flags.get(SegmentProperty.IS_PROTEIN.value):
            return MoleculeType.PROTEIN
        if props.flags.get(SegmentProperty.IS_NUCLEIC.value):
            return MoleculeType.NUCLEIC
        if props.atom_count_fragment == 1:
            return MoleculeType.ION

        # v3.143 (A-11/B-13): pseudo atoms out of composition and counts —
        # a TIP4P water (O,H,H + massless MW) is 3 real atoms and H2O.
        composition, real_atom_count = LoadedUniverse._real_composition(fragment.atoms)
        try:
            resnames = {str(rn).upper() for rn in fragment.residues.resnames}
        except Exception:
            resnames = set()

        # 3. Water
        if real_atom_count == 3 and (
            resnames & WATER_RESNAMES
            or (composition.get("O", 0) == 1 and composition.get("H", 0) == 2
                and composition.get("C", 0) == 0)
        ):
            return MoleculeType.WATER

        # 4. Lipid nomenclature beats composition heuristics when known
        if resnames & LIPID_RESNAMES:
            return MoleculeType.LIPID

        # 5. Composition bands (flat; every branch yields a verdict or falls
        #    through — no unreachable elif chain)
        c_cnt = composition.get("C", 0)
        o_cnt = composition.get("O", 0)
        if c_cnt > 10 and o_cnt > 4:
            ratio = c_cnt / o_cnt
            if 1.0 < ratio < 3.0:
                return MoleculeType.LIPID          # O-rich band (legacy parity; see note)
            if composition.get("P", 0) > 0 and 2.5 <= ratio <= 12.0:
                return MoleculeType.LIPID          # phospho/cardiolipin band
        # NOTE: no carbohydrate band here. The legacy `c>5, o>4, ratio>2` band
        # is provably unreachable (o>=5 AND c>2*o forces c>10, which the band
        # above always matches first) — it was dead code whose flat reform
        # would newly misclassify mid-range non-P molecules as sugar.
        # MoleculeType.CARBOHYDRATE remains reserved for future resname-table
        # typing; the O-rich band above keeping sysugars-dubious verdicts is a
        # documented legacy quirk, not an endorsement (never-wrong doctrine).

        # 6./7.
        if props.atom_count_fragment > 1:
            return MoleculeType.SMALL_MOLECULE
        return MoleculeType.UNKNOWN

    def extract_molecule_instance(self, segment_name: str) -> MoleculeInstance:
        """Extract a MoleculeInstance from a segment."""
        fragment = self.get_fragment(segment_name)
        props = self.get_segment_properties(segment_name)

        mtype = self._classify_molecule_type(props, fragment)

        # Element composition (recorded on the instance regardless of type)
        # v3.143 (A-11/B-13): pseudo/virtual-site atoms excluded.
        composition, _real_n = self._real_composition(fragment.atoms)
        
        # resname-less engines (LAMMPS .data) carry no residue nomenclature:
        # degrade to UNK per residue instead of crashing (NoDataError from
        # MDAnalysis __getattr__); downstream catalog then contains no
        # resname-driven identifications — valid empty-catalog semantic.
        try:
            resnames = list(fragment.residues.resnames)
        except Exception:  # NoDataError in MDAnalysis 2.x
            resnames = ["UNK"] * len(fragment.residues)

        return MoleculeInstance(
            instance_id=f"mol_{segment_name}",
            atom_indices=list(fragment.atoms.indices),
            residue_indices=list(range(len(fragment.residues))),
            segment_ids=[segment_name],
            chain_ids=list(set(fragment.atoms.segids)),
            resids=list(fragment.residues.resids),
            resnames=resnames,
            molecule_type=mtype,
            copy_number=props.molecule_count,
            atom_count=props.atom_count_fragment,
            element_composition=composition,
        )
    
    def extract_all_molecule_instances(self) -> list[MoleculeInstance]:
        """Extract MoleculeInstance for all segments."""
        return [self.extract_molecule_instance(seg) for seg in sorted(self._segments)]
