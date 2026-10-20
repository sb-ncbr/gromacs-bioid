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
        
        # Deduplicate segids to prevent protein and water chains from merging
        self._deduplicate_segids()
        
        return self.report

    def _has_elements(self) -> bool:
        """Return True only if ALL atoms have valid chemical element symbols."""
        if not hasattr(self.u.atoms, 'elements'):
            return False
        elements = self.u.atoms.elements
        if len(elements) == 0:
            return False
        
        return all(self._is_valid_element(e) for e in elements)

    def _has_masses(self) -> bool:
        """Return True only if ALL atoms have mass > 0."""
        if not hasattr(self.u.atoms, 'masses'):
            return False
        masses = self.u.atoms.masses
        if len(masses) == 0:
            return False
        return all(m > 0 for m in masses)

    def _has_names(self) -> bool:
        return hasattr(self.u.atoms, 'names') and any(n for n in self.u.atoms.names)

    def _has_bonds(self) -> bool:
        return hasattr(self.u.atoms, 'bonds') and len(self.u.atoms.bonds) > 0

    def _has_sufficient_bonds(self) -> bool:
        """Return True if the universe has enough bonds for molecule detection."""
        if not self._has_bonds():
            return False
        bond_count = len(self.u.atoms.bonds)
        atom_count = self.u.atoms.n_atoms
        # Loose heuristic: fully bonded systems typically exceed 0.25 bonds/atom.
        return bond_count >= atom_count * 0.25

    def guess_elements(self) -> int:
        """Guess missing elements. Returns count of atoms guessed."""
        if self._has_elements():
            return 0

        count_before = sum(1 for e in self.u.atoms.elements if self._is_valid_element(e)) if hasattr(self.u.atoms, 'elements') else 0

        # Check if there are ANY blank or invalid elements - if so, use fallback
        # Also use fallback if elements attribute doesn't exist
        has_elements_attr = hasattr(self.u.atoms, 'elements')
        has_invalid = has_elements_attr and any(not self._is_valid_element(e) for e in self.u.atoms.elements)
        has_blanks = has_elements_attr and any(not e or not e.strip() for e in self.u.atoms.elements)
        
        if not has_elements_attr or has_blanks or has_invalid:
            # Use custom fallback to fill in blanks/invalid without disturbing valid ones
            logger.debug("Elements missing/blank/invalid, using custom fallback")
            self._guess_elements_fallback()
        else:
            try:
                self.u.guess_TopologyAttrs(to_guess=['elements'])
            except Exception as exc:
                logger.warning(f"MDAnalysis element guesser failed: {exc}, using custom fallback")
                self._guess_elements_fallback()

        count_after = sum(1 for e in self.u.atoms.elements if self._is_valid_element(e)) if hasattr(self.u.atoms, 'elements') else 0
        guessed = count_after - count_before
        self.report.elements_guessed += guessed
        if guessed == 0:
            self.report.warnings.append("Could not guess elements for any atoms")
        logger.info(f"Guessed elements for {guessed} atoms")
        return guessed

    def _guess_elements_fallback(self) -> None:
        """Custom element guessing when MDAnalysis fails.
        Tries: atom name prefix → atom type prefix → mass match.
        Only fills in blank/invalid elements, preserves valid ones."""
        n_atoms = self.u.atoms.n_atoms
        
        # Get current elements (may have some filled)
        if hasattr(self.u.atoms, 'elements'):
            elements = list(self.u.atoms.elements)
        else:
            elements = [""] * n_atoms

        names = list(self.u.atoms.names) if hasattr(self.u.atoms, 'names') else [None] * n_atoms
        types = list(self.u.atoms.types) if hasattr(self.u.atoms, 'types') else [None] * n_atoms
        masses = list(self.u.atoms.masses) if hasattr(self.u.atoms, 'masses') else [None] * n_atoms

        for i in range(n_atoms):
            # Only guess if element is blank or invalid
            if not self._is_valid_element(elements[i]):
                element = self._guess_single_element(
                    existing="",
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

    def _is_valid_element(self, elem: str) -> bool:
        """Check if element string is a known chemical symbol (case-insensitive)."""
        if not elem or not elem.strip():
            return False
        return elem.strip().capitalize() in ATOMTABLE_ELEMENTS_MASSES

    def _guess_single_element(self, existing: str, name: str | None, mass: float | None, atom_type: str | None) -> str:
        """Guess element for a single atom from multiple sources."""
        # Note: existing is intentionally ignored here - caller passes "" for invalid elements

        # From atom name prefix - try multiple strategies
        if name:
            name_upper = name.upper().strip()
            
            # Special handling for water atoms (common in GROMACS)
            if name_upper.startswith('OW') or name_upper.startswith('OH2'):
                return 'O'
            if name_upper.startswith('HW') or name_upper.startswith('H1') or name_upper.startswith('H2'):
                return 'H'
            if name_upper.startswith('MW'):  # Water virtual site - place at oxygen
                return 'O'
            
            # Try single-letter prefix first (most reliable)
            first_char = name[0].upper()
            if first_char in ATOMTABLE_ELEMENTS_MASSES:
                return first_char
            
            # Try two-letter prefix
            if len(name) >= 2:
                two_char = name[:2].upper()
                if two_char in ATOMTABLE_ELEMENTS_MASSES:
                    return two_char
            
            # Try full alpha prefix
            prefix = ""
            for c in name:
                if c.isalpha():
                    prefix += c
                else:
                    break
            prefix = prefix.upper()
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

        # Check if there are ANY zero masses - if so, use fallback to fill them
        has_zero_masses = hasattr(self.u.atoms, 'masses') and any(m <= 0 for m in self.u.atoms.masses)
        
        if has_zero_masses:
            # Use custom fallback to fill in blanks without disturbing existing masses
            logger.debug("Some masses missing/zero, using custom fallback to fill blanks")
            self._guess_masses_fallback()
        else:
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
        """Custom mass guessing from elements. Only fills zero/missing masses."""
        n_atoms = self.u.atoms.n_atoms

        # Get current masses
        if hasattr(self.u.atoms, 'masses'):
            masses = list(self.u.atoms.masses)
        else:
            masses = [0.0] * n_atoms

        elements = list(self.u.atoms.elements) if hasattr(self.u.atoms, 'elements') else [None] * n_atoms
        for i in range(n_atoms):
            # Only fill if mass is zero or missing
            if masses[i] <= 0:
                elem = elements[i] if i < len(elements) else None
                # Defensive: only look up mass if element is valid
                if elem and elem.strip().capitalize() in ATOMTABLE_ELEMENTS_MASSES:
                    masses[i] = ATOMTABLE_ELEMENTS_MASSES[elem.strip().capitalize()]

        if not hasattr(self.u, 'masses'):
            self.u.add_TopologyAttr('masses', masses)
        else:
            self.u.atoms.masses = masses

    def fix_names(self) -> int:
        """Fix duplicate or missing atom names. Returns count fixed."""
        if not self._has_names():
            self.report.warnings.append("Atom names completely missing, cannot fix")
            return 0

        n_atoms = self.u.atoms.n_atoms
        names = list(self.u.atoms.names)

        # Check for duplicates within residues
        fixed_count = 0

        # Group atoms by residue. Hoist attribute arrays ONCE before the
        # O(n) loop: atomgroup.resids[i]/resnames[i] per-iteration triggers a
        # full-array materialization per access (O(n^2)) — measured 60.6 s on
        # an 82k-atom GROMACS TPR fixing 0 names; hoisted form is sub-second
        # (empirical A'-wave diagnosis, 2026-10-20).
        resids_arr = self.u.atoms.resids if hasattr(self.u.atoms, 'resids') else None
        resnames_arr = self.u.atoms.resnames if hasattr(self.u.atoms, 'resnames') else None
        residue_atoms = {}
        for i in range(n_atoms):
            resid = int(resids_arr[i]) if resids_arr is not None else 0
            resname = str(resnames_arr[i]) if resnames_arr is not None else ""
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

    def _deduplicate_segids(self) -> None:
        """Rename duplicate segids so each segment has a unique identifier.
        
        PDB files sometimes assign the same chain ID to both a protein chain
        and its associated water/ions. This merges them in MDAnalysis and
        corrupts downstream analysis. We rename duplicates by appending an
        index (e.g., 'A' -> 'A_1', 'A' -> 'A_2').
        """
        if not hasattr(self.u, 'segments') or len(self.u.segments) == 0:
            return
        
        segid_list = [seg.segid for seg in self.u.segments]
        segid_counts = {}
        for sid in segid_list:
            segid_counts[sid] = segid_counts.get(sid, 0) + 1
        
        # If no duplicates, nothing to do
        if all(c == 1 for c in segid_counts.values()):
            return
        
        # Build new segids: for duplicates, append occurrence index
        occurrence = {sid: 0 for sid in segid_list}
        new_segids_per_segment = []
        for sid in segid_list:
            occurrence[sid] += 1
            if segid_counts[sid] > 1:
                new_segids_per_segment.append(f"{sid}_{occurrence[sid]}")
            else:
                new_segids_per_segment.append(sid)
        
        # Assign segids to segments using the segments.segids setter
        # MDAnalysis will automatically update atom-level segids
        self.u.segments.segids = new_segids_per_segment
