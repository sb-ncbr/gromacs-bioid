from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import MDAnalysis
from MDAnalysis import Universe
from MDAnalysis.guesser.default_guesser import DefaultGuesser

from ..config.loader import RunConfig
from .repair_constants import ATOMTABLE_ELEMENTS_MASSES, ATOMTABLE_ELEMENT_MASS_CONFIDENCE_THRESHOLD

logger = logging.getLogger("base")


@dataclass
class RepairReport:
    elements_guessed: int = 0
    masses_guessed: int = 0
    names_fixed: int = 0
    bonds_guessed: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "elements_guessed": self.elements_guessed,
            "masses_guessed": self.masses_guessed,
            "names_fixed": self.names_fixed,
            "bonds_guessed": self.bonds_guessed,
            "warnings": self.warnings,
        }


class TopologyRepair:
    def __init__(self, universe: Universe, config: RunConfig):
        self.u = universe
        self.config = config
        self.report = RepairReport()

    def run(self) -> RepairReport:
        """Run all enabled repairs."""
        if self.config.loader.guess_missing_elements:
            self.guess_elements()
        if self.config.loader.guess_missing_masses:
            self.guess_masses()
        if self.config.loader.guess_missing_names:
            self.fix_names()
        if self.config.loader.guess_missing_bonds:
            self.guess_bonds()
        return self.report

    def _has_elements(self) -> bool:
        return hasattr(self.u.atoms, 'elements') and any(e for e in self.u.atoms.elements)

    def _has_masses(self) -> bool:
        return hasattr(self.u.atoms, 'masses') and all(m > 0 for m in self.u.atoms.masses)

    def _has_names(self) -> bool:
        return hasattr(self.u.atoms, 'names') and any(n for n in self.u.atoms.names)

    def _has_bonds(self) -> bool:
        return hasattr(self.u.atoms, 'bonds') and len(self.u.atoms.bonds) > 0

    def guess_elements(self) -> int:
        """Guess missing elements. Returns count of atoms guessed."""
        if self._has_elements():
            return 0

        count_before = sum(1 for e in self.u.atoms.elements if e) if hasattr(self.u.atoms, 'elements') else 0

        try:
            self.u.guess_TopologyAttrs(to_guess=['elements'])
        except Exception as exc:
            logger.warning(f"MDAnalysis element guesser failed: {exc}, using custom fallback")
            self._guess_elements_fallback()

        count_after = sum(1 for e in self.u.atoms.elements if e) if hasattr(self.u.atoms, 'elements') else 0
        guessed = count_after - count_before
        self.report.elements_guessed += guessed
        if guessed == 0:
            self.report.warnings.append("Could not guess elements for any atoms")
        logger.info(f"Guessed elements for {guessed} atoms")
        return guessed

    def _guess_elements_fallback(self) -> None:
        """Custom element guessing when MDAnalysis fails.
        Tries: atom name prefix → atom type prefix → mass match."""
        n_atoms = self.u.atoms.n_atoms
        elements = [""] * n_atoms

        names = list(self.u.atoms.names) if hasattr(self.u.atoms, 'names') else [None] * n_atoms
        types = list(self.u.atoms.types) if hasattr(self.u.atoms, 'types') else [None] * n_atoms
        masses = list(self.u.atoms.masses) if hasattr(self.u.atoms, 'masses') else [None] * n_atoms

        for i in range(n_atoms):
            element = self._guess_single_element(
                existing="" if not hasattr(self.u.atoms, 'elements') else self.u.atoms.elements[i],
                name=names[i] if names else None,
                mass=masses[i] if masses else None,
                atom_type=types[i] if types else None,
            )
            if element:
                elements[i] = element

        # Add topology attr if missing
        if not hasattr(self.u, 'elements'):
            self.u.add_TopologyAttr('elements', elements)
        else:
            self.u.atoms.elements = elements

    def _guess_single_element(self, existing: str, name: str | None, mass: float | None, atom_type: str | None) -> str:
        """Guess element for a single atom from multiple sources."""
        if existing and existing.strip():
            return existing.strip().capitalize()

        # From atom name prefix
        if name:
            prefix = ""
            for c in name:
                if c.isalpha():
                    prefix += c
                else:
                    break
            prefix = prefix.title()
            if prefix in ATOMTABLE_ELEMENTS_MASSES:
                return prefix

        # From atom type prefix
        if atom_type:
            t = atom_type.strip().upper()
            if t.startswith("C"): return "C"
            if t.startswith("N"): return "N"
            if t.startswith("O"): return "O"
            if t.startswith("H"): return "H"
            if t.startswith("P") or "P5" in t or "QA" in t: return "P"
            if t.startswith("S") or "SC" in t: return "S"
            if "NA" in t: return "Na"
            if "CL" in t: return "Cl"
            if "K" in t: return "K"
            if "ZN" in t: return "Zn"

        # From mass
        if mass is not None:
            for elem, elem_mass in ATOMTABLE_ELEMENTS_MASSES.items():
                if abs(elem_mass - mass) <= ATOMTABLE_ELEMENT_MASS_CONFIDENCE_THRESHOLD:
                    return elem

        return ""

    def guess_masses(self) -> int:
        """Guess missing masses from elements."""
        if self._has_masses():
            return 0

        count_before = sum(1 for m in self.u.atoms.masses if m > 0) if hasattr(self.u.atoms, 'masses') else 0

        try:
            self.u.guess_TopologyAttrs(to_guess=['masses'])
        except Exception as exc:
            logger.warning(f"MDAnalysis mass guesser failed: {exc}, using custom fallback")
            self._guess_masses_fallback()

        count_after = sum(1 for m in self.u.atoms.masses if m > 0) if hasattr(self.u.atoms, 'masses') else 0
        guessed = count_after - count_before
        self.report.masses_guessed += guessed
        logger.info(f"Guessed masses for {guessed} atoms")
        return guessed

    def _guess_masses_fallback(self) -> None:
        """Custom mass guessing from elements."""
        n_atoms = self.u.atoms.n_atoms
        masses = [0.0] * n_atoms

        elements = list(self.u.atoms.elements) if hasattr(self.u.atoms, 'elements') else [None] * n_atoms
        for i in range(n_atoms):
            elem = elements[i]
            if elem and elem in ATOMTABLE_ELEMENTS_MASSES:
                masses[i] = ATOMTABLE_ELEMENTS_MASSES[elem]

        if not hasattr(self.u, 'masses'):
            self.u.add_TopologyAttr('masses', masses)
        else:
            # Only fill missing ones
            current = list(self.u.atoms.masses)
            for i in range(n_atoms):
                if current[i] <= 0 and masses[i] > 0:
                    current[i] = masses[i]
            self.u.atoms.masses = current

    def fix_names(self) -> int:
        """Fix duplicate or missing atom names. Returns count fixed."""
        if not self._has_names():
            self.report.warnings.append("Atom names completely missing, cannot fix")
            return 0

        n_atoms = self.u.atoms.n_atoms
        names = list(self.u.atoms.names)

        # Check for duplicates within residues
        fixed_count = 0

        # Group atoms by residue
        residue_atoms = {}
        for i in range(n_atoms):
            resid = self.u.atoms.resids[i] if hasattr(self.u.atoms, 'resids') else 0
            resname = self.u.atoms.resnames[i] if hasattr(self.u.atoms, 'resnames') else ""
            key = (resid, resname)
            if key not in residue_atoms:
                residue_atoms[key] = []
            residue_atoms[key].append(i)

        new_names = names[:]
        for key, atom_indices in residue_atoms.items():
            seen = set()
            for idx in atom_indices:
                name = new_names[idx]
                if not name or name in seen:
                    # Generate unique name
                    suffix = 1
                    candidate = f"{name or 'AT'}{suffix}" if name else f"AT{idx}"
                    while candidate in seen:
                        suffix += 1
                        candidate = f"{name or 'AT'}{suffix}" if name else f"AT{idx}{suffix}"
                    new_names[idx] = candidate
                    fixed_count += 1
                seen.add(new_names[idx])

        if fixed_count > 0:
            self.u.atoms.names = new_names
            self.report.names_fixed += fixed_count
            logger.info(f"Fixed {fixed_count} duplicate/missing atom names")
        return fixed_count

    def guess_bonds(self) -> int:
        """Guess bonds from positions using DefaultGuesser."""
        if self._has_bonds():
            return 0

        try:
            guesser = DefaultGuesser(
                self.u,
                vdwradii=None,
                fudge_factor=self.config.loader.bond_guess_vdw_factor,
                lower_bound=0.1,
            )
            self.u.guess_TopologyAttrs(to_guess=['bonds'], context=guesser)
        except Exception as exc:
            logger.warning(f"MDAnalysis bond guesser failed: {exc}")
            self.report.warnings.append(f"Bond guessing failed: {exc}")
            return 0

        count = len(self.u.atoms.bonds) if hasattr(self.u.atoms, 'bonds') else 0
        self.report.bonds_guessed = count
        logger.info(f"Guessed {count} bonds")
        return count
