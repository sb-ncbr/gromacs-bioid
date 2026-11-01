"""Periodic boundary unwrapping for single-frame MD simulations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from MDAnalysis import Universe
from MDAnalysis.guesser.default_guesser import DefaultGuesser

from ..config.loader import RunConfig
from .repair import element_based_vdwradii  # A-04 (3.2): radii from elements

logger = logging.getLogger("base")

# Defer Biopython import
try:
    from Bio.PDB.mmcifio import MMCIFIO
    BIOPYTHON_AVAILABLE = True
except ImportError:
    BIOPYTHON_AVAILABLE = False
    MMCIFIO = None


@dataclass
class PbcRepairReport:
    """Report from periodic boundary unwrapping repair."""
    enabled: bool = False
    box_dimensions: list[float] | None = None
    unwrapped: bool = False
    unwrap_method: str = ""
    compound: str = ""
    reference: str = ""
    selection: str = ""
    bonds_guessed: int = 0
    # W3.1 item 11: coordination bonds added to stranded residue metals
    metal_coordination_bonds: int = 0
    jumps_detected: bool = False
    max_bond_length: float | None = None
    bond_jumps: int = 0
    max_backbone_gap: float | None = None
    backbone_jumps: int = 0
    # BH-052 self-check fields
    unwrap_incomplete: bool = False
    post_unwrap_bonds_over_4a: int = 0
    post_unwrap_max_bond_length: float | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable dict."""
        return {
            "enabled": self.enabled,
            "box_dimensions": self.box_dimensions,
            "unwrapped": self.unwrapped,
            "unwrap_method": self.unwrap_method,
            "compound": self.compound,
            "reference": self.reference,
            "selection": self.selection,
            "bonds_guessed": self.bonds_guessed,
            "metal_coordination_bonds": self.metal_coordination_bonds,
            "jumps_detected": self.jumps_detected,
            "max_bond_length": self.max_bond_length,
            "bond_jumps": self.bond_jumps,
            "max_backbone_gap": self.max_backbone_gap,
            "backbone_jumps": self.backbone_jumps,
            "unwrap_incomplete": self.unwrap_incomplete,
            "post_unwrap_bonds_over_4a": self.post_unwrap_bonds_over_4a,
            "post_unwrap_max_bond_length": self.post_unwrap_max_bond_length,
            "warnings": self.warnings,
            "error": self.error,
        }


class PbcRepair:
    """Periodic boundary unwrapping for single-frame simulations."""

    def __init__(self, universe: Universe, config: RunConfig):
        self.u = universe
        self.config = config
        self.loader_config = config.loader

    def run(self) -> PbcRepairReport:
        """Run periodic boundary unwrapping and jump detection."""
        report = PbcRepairReport(
            enabled=self.loader_config.unwrap_periodic_boundaries,
            compound=self.loader_config.unwrap_compound,
            reference=self.loader_config.unwrap_reference,
            selection=self.loader_config.unwrap_selection,
        )

        # Capture box dimensions
        if hasattr(self.u, 'dimensions') and self.u.dimensions is not None:
            report.box_dimensions = list(self.u.dimensions)

        # Always detect jumps
        jump_info = self.detect_jumps()
        report.jumps_detected = jump_info["jumps_detected"]
        report.max_bond_length = jump_info["max_bond_length"]
        report.bond_jumps = jump_info["bond_jumps"]
        report.max_backbone_gap = jump_info["max_backbone_gap"]
        report.backbone_jumps = jump_info["backbone_jumps"]

        if not self.loader_config.unwrap_periodic_boundaries:
            return report

        # Perform unwrapping
        report.unwrap_method = "AtomGroup.unwrap"

        try:
            ag = self.u.select_atoms(self.loader_config.unwrap_selection)

            # Guess bonds if missing AND enabled
            if self.loader_config.unwrap_guess_bonds_if_missing:
                from .repair import bonds_insufficient
                if bonds_insufficient(self.u):
                    report.bonds_guessed = self._guess_bonds()

            # W3.1 item 11: the pipeline's bond guessing lives HERE (the
            # repair step's guessing is off by default) — bond stranded
            # residue metals (heme Fe, chlorophyll Mg) to their
            # coordination partners so the residue does not split into a
            # metal-free molecule plus a phantom ion segment.
            from .repair import bond_stranded_residue_metals
            report.metal_coordination_bonds = (
                bond_stranded_residue_metals(self.u))

            # Try unwrapping with configured reference
            try:
                ag.unwrap(
                    compound=self.loader_config.unwrap_compound,
                    reference=self.loader_config.unwrap_reference,
                    inplace=True
                )
                report.unwrapped = True
            except (ValueError, Exception) as exc:
                # On ValueError (e.g., zero-mass virtual sites), retry with reference=None
                if self.loader_config.unwrap_reference is not None:
                    logger.warning(f"Unwrap with reference='{self.loader_config.unwrap_reference}' failed: {exc}, retrying with reference=None")
                    try:
                        ag.unwrap(
                            compound=self.loader_config.unwrap_compound,
                            reference=None,
                            inplace=True
                        )
                        report.unwrapped = True
                    except Exception as exc2:
                        report.error = str(exc2)
                        report.warnings.append(f"PBC unwrapping failed: {exc2}")
                else:
                    report.error = str(exc)
                    report.warnings.append(f"PBC unwrapping failed: {exc}")

        except Exception as exc:
            report.error = str(exc)
            report.warnings.append(f"PBC unwrapping failed: {exc}")

        # A-17.1 (red-team 3.7) / BH-052: lock the corrected frame into a
        # mutable single-frame snapshot. Never use transfer_to_memory for
        # this: it re-reads frame 0 from DISK and silently discards the
        # in-memory unwrap corrections (BH-052, found via the W3.1 A8
        # trajectory twins: a wrapped multi-frame XTC kept 67 A broken
        # bonds while the report claimed unwrapped=True, giving wrong
        # stereochemistry and a wrong InChIKey). Snapshot the corrected
        # positions instead.
        try:
            import numpy as _np
            traj = getattr(self.u, "trajectory", None)
            if traj is not None and getattr(traj, "n_frames", 1) > 1:
                dims = getattr(self.u, "dimensions", None)
                coords = _np.array(self.u.atoms.positions, copy=True)
                self.u.load_new(coords, format="memory")
                if dims is not None:
                    self.u.dimensions = dims
        except Exception as exc:
            report.warnings.append(f"frame0 snapshot failed: {exc}")

        # BH-052 self-check: the report must not claim success while
        # bonded atoms are still split across the box. Any bonded pair
        # above 4 A after the snapshot flips unwrapped to False and
        # warns with the count and the maximum.
        if report.unwrapped:
            over, max_bond = self._post_unwrap_bond_check()
            if over:
                report.unwrapped = False
                report.unwrap_incomplete = True
                report.post_unwrap_bonds_over_4a = over
                report.post_unwrap_max_bond_length = max_bond
                report.warnings.append(
                    f"pbc_unwrap_incomplete: {over} bonded pairs above 4 A "
                    f"after unwrapping (max {max_bond:.2f} A); molecules "
                    f"may still be split across the periodic boundary")

        return report

    def _post_unwrap_bond_check(self) -> tuple[int, float | None]:
        """BH-052 self-check: bonded pairs above 4 A and the max distance.

        Reads bonds through the topology storage (same fast path as
        detect_jumps) and needs a box; without a box or bonds there is
        nothing PBC-split to report.
        """
        if getattr(self.u, "dimensions", None) is None:
            return 0, None
        _top = getattr(self.u, "_topology", None)
        _tb = getattr(_top, "bonds", None) if _top is not None else None
        _vals = getattr(_tb, "values", None) if _tb is not None else None
        if _vals is None or len(_vals) == 0:
            return 0, None
        b = np.asarray(_vals, dtype=np.int64).reshape(-1, 2)
        if not len(b):
            return 0, None
        pos = self.u.atoms.positions
        dists = np.linalg.norm(pos[b[:, 0]] - pos[b[:, 1]], axis=1)
        return int((dists > 4.0).sum()), float(dists.max())

    def _guess_bonds(self) -> int:
        """Guess bonds UNIONED with any existing set using DefaultGuesser.

        Wave-2 item 6a: same insufficient-bonds predicate as repair (0.25
        bonds/atom) — partial bond coverage no longer skips guessing."""
        from .repair import guess_bonds_union
        return guess_bonds_union(
            self.u,
            vdwradii=element_based_vdwradii(self.u),
            fudge_factor=self.config.loader.bond_guess_vdw_factor,
            logger=logger,
        )

    def detect_jumps(self) -> dict[str, Any]:
        """Detect periodic boundary jumps in the structure.

        Returns dict with:
        - jumps_detected: bool
        - max_bond_length: float | None
        - bond_jumps: int
        - max_backbone_gap: float | None
        - backbone_jumps: int
        """
        result = {
            "jumps_detected": False,
            "max_bond_length": None,
            "bond_jumps": 0,
            "max_backbone_gap": None,
            "backbone_jumps": 0,
        }

        box = self.u.dimensions if hasattr(self.u, 'dimensions') else None
        if box is None:
            return result

        min_box_edge = min(box[:3])

        # Bond-length scan (A-13, red-team 3.8: vectorized — was a per-bond
        # Python loop, 25 s on a 2M-atom box). Guards go through the topology
        # storage attr: `hasattr(atoms, "bonds")` itself materializes the
        # TopologyGroup (~0.35 s @100k) when bonds exist.
        _top = getattr(self.u, "_topology", None)
        _tb = getattr(_top, "bonds", None) if _top is not None else None
        _vals = getattr(_tb, "values", None) if _tb is not None else None
        if _vals is None:
            # registry-free fallback (exotic MDA builds)
            try:
                _bg = self.u.atoms.bonds
                _vals = _bg.to_indices() if len(_bg) > 0 else []
            except Exception:
                _vals = []
        b = np.asarray(_vals, dtype=np.int64).reshape(-1, 2) if len(_vals) else None
        if b is not None and len(b) > 0:
            threshold = min_box_edge * self.loader_config.unwrap_max_bond_length_factor
            pos = self.u.atoms.positions
            dists = np.linalg.norm(pos[b[:, 0]] - pos[b[:, 1]], axis=1)
            result["max_bond_length"] = float(dists.max())
            result["bond_jumps"] = int((dists > threshold).sum())

        # Backbone scan (simplified - skip for segments without proper topology)
        backbone_jumps = 0
        max_gap = 0.0

        # Note: Backbone scan requires proper segment topology which may not be
        # available in all cases. Skip gracefully if select_atoms is not available.
        try:
            for seg in self.u.segments:
                # Determine if protein or nucleic based on residue names
                resnames = list(set(r.resname for r in seg.residues))
                is_protein = self._is_protein_segment(resnames)
                is_nucleic = self._is_nucleic_segment(resnames)

                if is_protein:
                    # A-18: boolean selection — `segid {seg.segid} ...` breaks
                    # on space-containing/blank segids and the bare except
                    # then silently killed the whole scan
                    try:
                        ca_atoms = seg.atoms[seg.atoms.names == "CA"]
                    except Exception:
                        ca_atoms = []
                    if len(ca_atoms) > 1:
                        gaps = self._compute_consecutive_gaps(ca_atoms)
                        for gap in gaps:
                            if gap > max_gap:
                                max_gap = gap
                            if gap > self.loader_config.unwrap_max_backbone_gap:
                                backbone_jumps += 1

                elif is_nucleic:
                    try:
                        p_atoms = seg.atoms[seg.atoms.names == "P"]
                    except Exception:
                        p_atoms = []
                    if len(p_atoms) > 1:
                        gaps = self._compute_consecutive_gaps(p_atoms)
                        for gap in gaps:
                            if gap > max_gap:
                                max_gap = gap
                            if gap > self.loader_config.unwrap_max_backbone_gap:
                                backbone_jumps += 1
        except Exception as exc:
            logger.debug("Backbone gap scan skipped: %s", exc)

        result["max_backbone_gap"] = max_gap
        result["backbone_jumps"] = backbone_jumps
        result["jumps_detected"] = (result["bond_jumps"] + result["backbone_jumps"]) > 0

        return result

    def _is_protein_segment(self, resnames: list[str]) -> bool:
        """Check if segment is protein based on residue names."""
        if not resnames:
            return False
        # Common protein residue names
        protein_resnames = {
            'ALA', 'ARG', 'ASN', 'ASP', 'CYS', 'GLN', 'GLU', 'GLY',
            'HIS', 'ILE', 'LEU', 'LYS', 'MET', 'PHE', 'PRO', 'SER',
            'THR', 'TRP', 'TYR', 'VAL',
            # Protonated forms
            'ASH', 'GLH', 'HID', 'HIE', 'HIP', 'LYN', 'CYS2', 'CYX',
        }
        matches = sum(1 for rn in resnames if rn in protein_resnames)
        return matches / len(resnames) >= 0.8

    def _is_nucleic_segment(self, resnames: list[str]) -> bool:
        """Check if segment is nucleic acid based on residue names."""
        if not resnames:
            return False
        # Common nucleic acid residue names
        nucleic_resnames = {
            'DA', 'DC', 'DG', 'DT',  # DNA
            'A', 'C', 'G', 'T', 'U',  # RNA/DNA single letter
            'ADE', 'CYT', 'GUA', 'THY', 'URA',  # Full names
            'RA', 'RC', 'RG', 'RU',  # RNA
        }
        matches = sum(1 for rn in resnames if rn in nucleic_resnames)
        return matches / len(resnames) >= 0.8

    def _compute_consecutive_gaps(self, atom_group) -> list[float]:
        """Distances between consecutive backbone atoms, chain-aware.

        A-18 (red-team 3.7): the old resid-only sort merged separate chains
        that share a segment (and restarted numbering), producing false
        `backbone_jumps`. Sort by (chainID, resindex); never compare atoms
        across a chain boundary (or a numbering restart when no chainIDs).
        """
        def _chain(a):
            try:
                return str(a.chainID)
            except Exception:
                return ""
        sorted_atoms = sorted(atom_group, key=lambda a: (_chain(a), int(a.resindex)))
        gaps = []
        for i in range(1, len(sorted_atoms)):
            prev, cur = sorted_atoms[i - 1], sorted_atoms[i]
            c_prev, c_cur = _chain(prev), _chain(cur)
            if c_prev and c_cur and c_prev != c_cur:
                continue
            if not c_prev and not c_cur and int(cur.resid) < int(prev.resid):
                continue  # numbering restart without chainID metadata
            gaps.append(float(np.linalg.norm(cur.position - prev.position)))
        return gaps


class MMCIFIOWithCell(MMCIFIO):
    """MMCIFIO subclass that preserves unit cell parameters."""

    def __init__(self, cell: list[float] | None, space_group: str = "P 1", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cell = cell
        self.space_group = space_group

    def _save_dict(self, out_file):
        if hasattr(self, "dic") and self.cell is not None and len(self.cell) >= 6:
            a, b, c, alpha, beta, gamma = self.cell[:6]
            self.dic.update({
                "_cell.length_a": [f"{float(a):.3f}"],
                "_cell.length_b": [f"{float(b):.3f}"],
                "_cell.length_c": [f"{float(c):.3f}"],
                "_cell.angle_alpha": [f"{float(alpha):.3f}"],
                "_cell.angle_beta": [f"{float(beta):.3f}"],
                "_cell.angle_gamma": [f"{float(gamma):.3f}"],
                "_symmetry.space_group_name_H-M": [self.space_group],
            })
        super()._save_dict(out_file)
