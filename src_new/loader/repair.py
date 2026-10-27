from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import MDAnalysis
from MDAnalysis import Universe
from MDAnalysis.guesser.default_guesser import DefaultGuesser

from ..config.loader import RunConfig
from ..constants import KNOWN_RESIDUE_CODES
from ..molecules.nucleic_acid import normalize_nucleic_resname
from .repair_constants import ATOMTABLE_ELEMENTS_MASSES, ATOMTABLE_ELEMENT_MASS_CONFIDENCE_THRESHOLD

# --- wave-2 item 5 (GitHub #2): element guessing order + ion residue names --
# CHARMM / AMBER / GROMACS single-atom ion RESIDUE names. These are only
# consulted for single-atom residues (an ion floating in solvent), so a ligand
# carbon legitimately named "CD" can never be hit by 'CD': 'Cd'.
_ION_RESNAME_ELEMENTS = {
    # CHARMM
    'SOD': 'Na', 'POT': 'K', 'CLA': 'Cl', 'CAL': 'Ca', 'CES': 'Cs',
    'RUB': 'Rb', 'LIT': 'Li',
    # AMBER style (charged suffix)
    'NA+': 'Na', 'CL-': 'Cl', 'K+': 'K', 'BR-': 'Br', 'I-': 'I',
    'CS+': 'Cs', 'RB+': 'Rb', 'MG+': 'Mg', 'CA+': 'Ca', 'ZN+': 'Zn',
    # AMBER style (halide suffix)
    'NAI': 'Na', 'CLI': 'Cl', 'KI': 'K', 'BRI': 'Br',
    # GROMACS / common bare ion resnames (single-atom residues only)
    'ZN': 'Zn', 'ZN1': 'Zn', 'ZN2': 'Zn', 'MG': 'Mg', 'CA': 'Ca',
    'K': 'K', 'NA': 'Na', 'CL': 'Cl', 'BR': 'Br', 'IOD': 'I',
    'FE': 'Fe', 'FE1': 'Fe', 'FE2': 'Fe',
    'MN': 'Mn', 'MN3': 'Mn', 'CU': 'Cu', 'CU1': 'Cu',
    'NI': 'Ni', 'NI2': 'Ni', 'CO': 'Co', 'CD': 'Cd', 'HG': 'Hg',
    'PB': 'Pb', 'AG': 'Ag', 'AU': 'Au',
}

# Mass-match tolerance: force-field masses are isotope/rounding variants of
# the table (Cl 35.45 vs 35.453); anything further away is not a mass match.
_MASS_MATCH_TOLERANCE = 0.5


def _element_from_mass(mass: float) -> str | None:
    """Nearest element by mass (wave-2 item 5): unambiguous for Cl/C, Na/N
    and Ca/C — Ca (40.078) beats K (39.098) by ~1 u, so accurate force-field
    masses resolve correctly."""
    best, best_delta = None, None
    for elem, elem_mass in ATOMTABLE_ELEMENTS_MASSES.items():
        delta = abs(mass - elem_mass)
        if best_delta is None or delta < best_delta:
            best, best_delta = elem, delta
    if best is not None and best_delta <= _MASS_MATCH_TOLERANCE:
        return best
    return None


def _is_polymer_resname(resname: str | None) -> bool:
    """Protein (KNOWN_RESIDUE_CODES) or nucleic (tier-1 normalizer) residue."""
    if not resname:
        return False
    rn = str(resname).strip()
    if rn.upper() in KNOWN_RESIDUE_CODES:
        return True
    return normalize_nucleic_resname(rn) is not None

logger = logging.getLogger("base")


def element_based_vdwradii(u: Universe) -> dict[str, float]:
    """A-04 (red-team 3.2): per-TYPE vdw radius table from repaired ELEMENTS.

    `DefaultGuesser(vdwradii=None)` looks radii up by atom *type*: a single
    unknown type in the whole universe (DUMMY for MW/EP/LP sites, Martini
    beads, force-field names like OW/HW) raised ValueError and ZERO bonds were
    guessed for the entire system — every segment then collapsed into one
    "molecule". MDAnalysis merges a user-supplied table over its own, so we
    supply radii for every type present:

    - mass < 0.5 atom (massless virtual site)  -> 0.0 (never bonds)
    - known repaired element (per 2.7 logic)   -> Bondi radius from MDA tables
    - anything else                            -> 1.5 A audit fallback
    """
    from MDAnalysis.topology.tables import vdwradii as _Bondi

    types = getattr(u.atoms, "types", None)
    if types is None or len(types) == 0:
        return {}
    elements = getattr(u.atoms, "elements", None)
    masses = getattr(u.atoms, "masses", None)
    radii: dict[str, float] = {}
    for i, t in enumerate(types):
        if t in radii:
            continue
        if masses is not None and i < len(masses) and float(masses[i]) < 0.5:
            radii[t] = 0.0  # massless virtual site
            continue
        el = ""
        if elements is not None and i < len(elements):
            raw = str(elements[i]).strip()
            el = raw.capitalize() if raw else ""
        radii[t] = float(_Bondi[el]) if el in _Bondi else 1.5
    return radii


def bonds_insufficient(u) -> bool:
    """wave-2 item 6a/6c: 'enough bonds' predicate — fully bonded systems
    exceed 0.25 bonds per atom (same threshold repair._has_sufficient_bonds
    uses). Partial CONECT (e.g. 1XJR) fails this and must get guessed
    bonds UNIONED in, not skipped."""
    if not hasattr(u.atoms, 'bonds') or len(u.atoms.bonds) == 0:
        return True
    return len(u.atoms.bonds) < u.atoms.n_atoms * 0.25


def guess_bonds_union(u, vdwradii, fudge_factor: float, logger=logging) -> int:
    """Guess bonds from coordinates and UNION them with the existing
    (CONECT) bonds — the guesser must never drop authored bonds (wave-2
    item 6a; 1XJR-type partial CONECT). MDAnalysis' guess_TopologyAttrs
    skips attributes that already exist, so the union dance is:
    snapshot → del → guess → re-add (re-add replaces). On guesser failure
    the original bonds are restored.

    Returns the final bond count (0 only when truly nothing could be made).
    """
    from MDAnalysis.core.topologyattrs import Bonds
    existing: set[tuple[int, int]] = set()
    if hasattr(u.atoms, 'bonds') and len(u.atoms.bonds):
        existing = {tuple(sorted((int(a), int(b)))) for a, b in u.atoms.bonds.indices}
    try:
        if hasattr(u.atoms, 'bonds'):
            u.del_TopologyAttr('bonds')
        u.guess_TopologyAttrs(
            context="default",
            to_guess=['bonds'],
            vdwradii=vdwradii,
            fudge_factor=fudge_factor,
            lower_bound=0.1,
        )
    except Exception as exc:
        # restore authored bonds on any guesser failure
        if existing:
            u.add_TopologyAttr(Bonds(sorted(existing)))
        logger.warning(f"guesser failed during union guess: {exc}")
        return len(existing)
    guessed: set[tuple[int, int]] = set()
    if hasattr(u.atoms, 'bonds') and len(u.atoms.bonds):
        guessed = {tuple(sorted((int(a), int(b)))) for a, b in u.atoms.bonds.indices}
    union = sorted(existing | guessed)
    if union:
        u.add_TopologyAttr(Bonds(union))
    return len(union)


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
        # v3.143 (A-11): intentionally blanked virtual sites ARE resolved
        # (they carry no chemistry); count them with the real guesses.
        guessed = count_after - count_before + getattr(self, "_virtual_sites_blanked", 0)
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
        resnames_arr = list(self.u.atoms.resnames) if hasattr(self.u.atoms, 'resnames') else [None] * n_atoms

        # wave-2 item 5: residue context for element guessing — single-atom
        # (ion) vs polymer residues decide the name-prefix strategy. Group by
        # resindex (true residue identity, v3.143 A-02).
        resindex_arr = self.u.atoms.resindices if hasattr(self.u.atoms, 'resindices') else None
        if resindex_arr is not None:
            residue_sizes: dict[int, int] = {}
            for ri in resindex_arr:
                ri = int(ri)
                residue_sizes[ri] = residue_sizes.get(ri, 0) + 1
        else:
            residue_sizes = {}

        for i in range(n_atoms):
            # Only guess if element is blank or invalid
            if not self._is_valid_element(elements[i]):
                resname = resnames_arr[i] if resnames_arr else None
                ri = int(resindex_arr[i]) if resindex_arr is not None else None
                element = self._guess_single_element(
                    existing="",
                    name=names[i] if names else None,
                    mass=masses[i] if masses else None,
                    atom_type=types[i] if types else None,
                    resname=str(resname) if resname is not None else None,
                    residue_atom_count=residue_sizes.get(ri, 0) if ri is not None else 0,
                )
                if element:
                    elements[i] = element
                elif names[i] is not None and str(names[i]).upper().strip().startswith(
                        ("MW", "EPW", "EP", "LP", "DP", "VS", "DUM")):
                    # v3.143 (A-11/B-13): _guess_single_element returns '' for
                    # virtual-site names — that's an INTENTIONAL blank (no
                    # chemistry), so replace the leftover invalid string.
                    elements[i] = ""
                    self._virtual_sites_blanked = getattr(self, "_virtual_sites_blanked", 0) + 1

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

    def _guess_single_element(self, existing: str, name: str | None, mass: float | None,
                              atom_type: str | None,
                              resname: str | None = None,
                              residue_atom_count: int = 0) -> str:
        """Guess element for a single atom from multiple sources.

        Wave-2 item 5 (GitHub #2): the old order (1-letter name prefix first,
        then a 2-letter lookup that compared ``.upper()`` against title-case
        keys — i.e. NEVER matched — then atom type, mass LAST) turned CHARMM
        ions into wrong elements: SOD → S, CLA → C, NA → N, CL → C even with
        mass 35.45 present. New priority order:
          1. exact name guards (water, virtual sites);
          2. MASS when present and > 0.5 (unambiguous for Cl/C, Na/N, Ca/C);
          3. single-atom ion RESIDUE names (SOD, POT, CLA, NA+, ...);
          4. name prefixes — 2-letter (properly capitalised) BEFORE 1-letter
             for single-atom and non-polymer residues (ligand CL1/BR1);
             inside protein/NA residues the 1-letter prefix stays first
             (protein CA must remain carbon, not calcium);
          5. atom type prefix (unchanged);
          6. mass fallback (unchanged behaviour for pathological masses).
        """
        # Note: existing is intentionally ignored here - caller passes "" for invalid elements

        if name:
            name_upper = name.upper().strip()

            # Special handling for water atoms (common in GROMACS)
            if name_upper.startswith('OW') or name_upper.startswith('OH2'):
                return 'O'
            if name_upper.startswith('HW') or name_upper.startswith('H1') or name_upper.startswith('H2'):
                return 'H'
            # v3.143 (A-11/B-13): virtual sites / lone-pair / massless
            # particles (TIP4P MW*, AMBER EPW, CGenFF LP*, Drude DP*) carry
            # NO chemistry. Guessing 'O' for MW turned TIP4P water into
            # H2O2 (hydrogen peroxide) for formula resolvers; leave them
            # element-blank — the facade's pseudo-atom exclusion (mass<0.5)
            # keeps them out of composition and completeness checks.
            if name_upper.startswith(('MW', 'EPW', 'EP', 'LP', 'DP', 'VS', 'DUM')):
                return ''

        # 2. Mass first: when the topology carries a real mass, it is the
        # most reliable signal (force-field masses are element masses).
        if mass is not None and mass > 0.5:
            elem = _element_from_mass(float(mass))
            if elem:
                return elem

        # 3. Single-atom ion residues (CHARMM/AMBER/GROMACS ion names)
        if residue_atom_count == 1 and name:
            ion = _ION_RESNAME_ELEMENTS.get(name.upper().strip())
            if ion:
                return ion

        # 4. Name prefixes, residue-context aware
        if name:
            name_upper = name.upper().strip()
            single_atom = residue_atom_count == 1
            non_polymer = not _is_polymer_resname(resname)
            two_letter_first = single_atom or non_polymer

            if two_letter_first and len(name) >= 2:
                two_char = name[:2].capitalize()
                if two_char in ATOMTABLE_ELEMENTS_MASSES:
                    return two_char

            first_char = name[0].upper()
            if first_char in ATOMTABLE_ELEMENTS_MASSES:
                return first_char

            if not two_letter_first and len(name) >= 2:
                # polymer path: 2-letter only after 1-letter failed
                two_char = name[:2].capitalize()
                if two_char in ATOMTABLE_ELEMENTS_MASSES:
                    return two_char

            # Full alpha prefix (properly capitalised this time)
            prefix = ""
            for c in name:
                if c.isalpha():
                    prefix += c
                else:
                    break
            prefix = prefix.capitalize()
            if prefix in ATOMTABLE_ELEMENTS_MASSES:
                return prefix

        # 5. From atom type prefix
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

        # 6. From mass
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
        # v3.143 (red-team A-02): group by true residue identity (resindex),
        # not (resid, resname) — homo-oligomers / per-chain numbering must not
        # have chain B atoms renamed (name CA needed intact for ca_only_pdb).
        resindex_arr = self.u.atoms.resindices if hasattr(self.u.atoms, 'resindices') else None
        residue_atoms = {}
        for i in range(n_atoms):
            if resindex_arr is not None:
                key = int(resindex_arr[i])
            else:
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
        """Guess bonds from positions using DefaultGuesser.

        Wave-2 item 6a: guess when bonds are INSUFFICIENT, not only when
        absent — partial CONECT coverage (1XJR class) got no guessing at
        all before, leaving later topology consumers disconnected. Guessed
        bonds are UNIONED with the authored CONECT set (never replaced)."""
        if self._has_sufficient_bonds():
            return 0

        count = guess_bonds_union(
            self.u,
            vdwradii=element_based_vdwradii(self.u),
            fudge_factor=self.config.loader.bond_guess_vdw_factor,
            logger=logger,
        )
        if count == 0:
            self.report.warnings.append("bond_guess_failed: guesser produced no bonds")
        self.report.bonds_guessed = count
        logger.info(f"Bond topology after union guess: {count} bonds")
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
