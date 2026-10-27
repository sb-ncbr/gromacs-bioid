"""Periodic boundary unwrapping for single-frame MD simulations."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from MDAnalysis import Universe
from MDAnalysis.guesser.default_guesser import DefaultGuesser

from ..config.loader import RunConfig

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
    jumps_detected: bool = False
    max_bond_length: float | None = None
    bond_jumps: int = 0
    max_backbone_gap: float | None = None
    backbone_jumps: int = 0
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
            "jumps_detected": self.jumps_detected,
            "max_bond_length": self.max_bond_length,
            "bond_jumps": self.bond_jumps,
            "max_backbone_gap": self.max_backbone_gap,
            "backbone_jumps": self.backbone_jumps,
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

            # Guess bonds if missing or insufficient (e.g. partial CONECT) and enabled
            if self.loader_config.unwrap_guess_bonds_if_missing:
                from .repair import TopologyRepair
                repair_helper = TopologyRepair(self.u, self.config)
                if not repair_helper._has_sufficient_bonds():
                    report.bonds_guessed = self._guess_bonds()

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

        return report

    def _guess_bonds(self) -> int:
        """Guess bonds using TopologyRepair (merges partial CONECT, prunes H-bridges, repairs halogens)."""
        try:
            from .repair import TopologyRepair
            repair_helper = TopologyRepair(self.u, self.config)
            return repair_helper.guess_bonds()
        except Exception as exc:
            logger.warning(f"Bond guessing for unwrap failed: {exc}")
            return 0

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

        # Bond-length scan
        if hasattr(self.u.atoms, 'bonds') and len(self.u.atoms.bonds) > 0:
            threshold = min_box_edge * self.loader_config.unwrap_max_bond_length_factor
            max_len = 0.0
            bond_jumps = 0

            for atom1, atom2 in self.u.atoms.bonds:
                dist = np.linalg.norm(atom1.position - atom2.position)
                if dist > max_len:
                    max_len = dist
                if dist > threshold:
                    bond_jumps += 1

            result["max_bond_length"] = max_len
            result["bond_jumps"] = bond_jumps

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
                    # Select CA atoms from segment
                    ca_selection = f"segid {seg.segid} and name CA"
                    ca_atoms = self.u.select_atoms(ca_selection)
                    if len(ca_atoms) > 1:
                        gaps = self._compute_consecutive_gaps(ca_atoms)
                        for gap in gaps:
                            if gap > max_gap:
                                max_gap = gap
                            if gap > self.loader_config.unwrap_max_backbone_gap:
                                backbone_jumps += 1

                elif is_nucleic:
                    # Select P atoms from segment
                    p_selection = f"segid {seg.segid} and name P"
                    p_atoms = self.u.select_atoms(p_selection)
                    if len(p_atoms) > 1:
                        gaps = self._compute_consecutive_gaps(p_atoms)
                        for gap in gaps:
                            if gap > max_gap:
                                max_gap = gap
                            if gap > self.loader_config.unwrap_max_backbone_gap:
                                backbone_jumps += 1
        except Exception:
            # Skip backbone scan if segment topology is incomplete
            pass

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
        """Compute distances between consecutive atoms in sorted order."""
        # Sort by residue id
        sorted_atoms = sorted(atom_group, key=lambda a: a.resid)
        gaps = []
        for i in range(1, len(sorted_atoms)):
            dist = np.linalg.norm(sorted_atoms[i].position - sorted_atoms[i-1].position)
            gaps.append(dist)
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
