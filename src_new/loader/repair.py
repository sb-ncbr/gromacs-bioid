from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

import MDAnalysis
import numpy as np
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

# W3 A3 (BH-038/BH-045): element symbols that may come from a multi-atom
# residue's atom NAME only when the name IS the symbol (plus optional
# digits/prime), e.g. CL, CL1, BR2, FE, FE1. Deliberately EXCLUDED
# (ambiguous with organic names): CA, CD, CE, NA, NB, NE, HG, HO, OS, PO,
# SC, CO (B12 cobalt is collateral; topology mass rescues it).
EXACT_NAME_ELEMENTS = {"CL": "Cl", "BR": "Br", "FE": "Fe", "ZN": "Zn",
                       "MG": "Mg", "MN": "Mn", "CU": "Cu", "NI": "Ni",
                       "SE": "Se"}
_EXACT_NAME_RE = re.compile(r"^(CL|BR|FE|ZN|MG|MN|CU|NI|SE)\d*['*]?$")
# Organic first letters: after any leading digits, this first letter IS
# the element on element-less atomistic inputs.
_ORGANIC_FIRST = set("CNOSPHFI")
# Martini/coarse-grained bead names for CG detection.
_MARTINI_NAMES = {"BB", "SC1", "SC2", "SC3", "SC4", "SC5", "PO4", "NC3",
                  "NH3", "CNO", "GL1", "GL2", "ROH", "W", "WF", "PW",
                  "BAS", "TP1", "C1", "R1"}

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


def _mass_candidates(mass: float) -> list[str]:
    """W3.1-2: element candidates allowing united-atom masses
    (``m ≈ M(E) + k·1.008``) and HMR heavy atoms (``−2.016`` per
    repartitioned hydrogen). Plain force-field masses match at k=0.
    Returns candidate symbols sorted by closeness."""
    out = []
    for elem, m0 in ATOMTABLE_ELEMENTS_MASSES.items():
        for k in range(-8, 5):
            if abs(mass - (m0 + k * 1.008)) <= _MASS_MATCH_TOLERANCE:
                out.append((elem, abs(mass - (m0 + k * 1.008))))
                break
    out.sort(key=lambda t: t[1])
    return [e for e, _ in out]


def _element_from_mass_name(mass: float, name: str | None) -> str | None:
    """HMR/united-atom-aware mass match with the atom NAME's leading
    letter as the tie-breaker between candidates (AMBER Trp 'NE1' at
    HMR mass 11.99 is N, not C). Only the LEADING letter is used —
    two-letter prefixes would collide with elements (HE1->He, NE2->Ne,
    the audit's `never-from-name` class)."""
    cands = _mass_candidates(mass)
    if not cands:
        return None
    if len(cands) == 1:
        return cands[0]
    if name:
        stripped = str(name).upper().strip().lstrip("0123456789")
        one = stripped[:1].capitalize()
        if one in cands:
            return one
    return cands[0]


# W3.1-2: atom TYPE to element decodes only exact ion-style types —
# never substrings (amber aromatic nitrogen 'NA'/'NB' is not sodium;
# OPLS 'opls_135' is not oxygen).
_EXACT_TYPE_IONS = {
    "NA": "Na", "NA+": "Na", "SOD": "Na",
    "K": "K", "K+": "K", "POT": "K",
    "CL": "Cl", "CL-": "Cl", "CLA": "Cl",
    "ZN": "Zn", "ZN2": "Zn", "MG": "Mg", "MG2": "Mg",
    "CA": "Ca", "CAL": "Ca", "FE": "Fe", "FE2": "Fe",
    "CU": "Cu", "MN": "Mn", "LI": "Li", "RB": "Rb", "CS": "Cs",
}


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
            el = raw.upper() if raw else ""  # BH-021: MDA table keys are
            # UPPERCASE ('CL','ZN'); the old .capitalize() lookup missed
            # every two-letter element and fell back to the 1.5 A audit
            # radius (Zn 1.39, Cl 1.75 in the table).
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


# W3.1 item 11: metals whose coordination distance exceeds the covalent
# fudge cutoff (heme Fe-N ~2.0 A vs ~1.68 A cutoff with correctly typed
# elements)
_COORDINATION_METAL_ELEMENTS = frozenset({
    "FE", "ZN", "MG", "MN", "CU", "NI", "CO", "MO", "V", "W"})
_COORDINATION_PARTNER_ELEMENTS = frozenset({"N", "O", "S"})
_COORDINATION_CUTOFF_A = 2.6

# W3.1 S17 follow-up: intra-residue completion. A residue is one chemical
# unit, but the conservative vdW-fudge bond-guess cutoff can tear its
# covalent skeleton apart (S17 hemoglobin-as-GRO: each HEM's propionate
# arm sits 2.09 A from the ring carbon — a real C-C bond beyond the
# 1.87 A C-C fudge cutoff — so the heme verifies as a porphyrin plus
# two CO2 fragments). Single-atom METAL/ION components are never merged
# by this rule (bond_stranded_residue_metals owns residue metals; free
# ions are legitimately unbonded — C13 sodium acetate must not gain a
# contact-ion-pair bond).
_INTRA_RESIDUE_COMPLETION_CUTOFF_A = 2.5
_ION_LIKE_ELEMENTS = frozenset({
    # transition/coordination metals (item 11's set) plus the common
    # free-ion elements: alkali, alkaline-earth, halides, aluminium
    "FE", "ZN", "MG", "MN", "CU", "NI", "CO", "MO", "V", "W",
    "NA", "K", "LI", "RB", "CS", "CA", "SR", "BA", "CL", "BR", "I", "F",
    "AL", "CD", "HG", "PB", "SN", "CR", "PT", "PD", "AU", "AG", "SE"})


def complete_intra_residue_fragments(u, report=None) -> int:
    """W3.1 S17 follow-up: merge bond-connected components inside a
    multi-atom residue when the closest cross-component HEAVY-atom pair
    is <= 2.5 A (not a value fitted to S17: the merge only applies
    WITHIN one residue, metals/ions and water are excluded, and
    non-bonded heavy-atom contacts stay >= ~2.6-2.7 A even in short
    H-bonds).

    Root cause (live evidence, S17 4HHB.gro): the heme propionate
    C(ring)-C(arm) bond is 2.09 A — beyond the 0.55 vdW-fudge cutoff
    (1.87 A for C-C) — so each HEM residue tears into a porphyrin plus
    two carboxylate (CO2) fragments and the gate's heme expectation
    (C34FeN4O4) fails. Guards (user-approved):
      - water residues are never touched;
      - single-atom metal/ion components are never merged (item 11's
        coordination rule owns residue metals; contact ion pairs stay
        ions);
      - heavy atoms only (GRO hydrogen positions are too noisy to
        trust for connectivity)."""
    import numpy as np
    try:
        elements = [str(e or "").strip().upper() for e in u.atoms.elements]
    except Exception:
        return 0
    try:
        resindices = [int(r) for r in u.atoms.resindices]
        resnames = [str(r or "").strip().upper() for r in u.atoms.resnames]
    except Exception:
        return 0
    from ..molecules.instances import WATER_RESNAMES

    # union-find over the existing bonds
    n = len(u.atoms)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    if hasattr(u.atoms, "bonds") and len(u.atoms.bonds):
        for a, b in u.atoms.bonds.indices:
            ra, rb = find(int(a)), find(int(b))
            if ra != rb:
                parent[ra] = rb

    by_residue: dict[int, list[int]] = {}
    for i, ri in enumerate(resindices):
        by_residue.setdefault(ri, []).append(i)

    pos = u.atoms.positions
    new_bonds: set[tuple[int, int]] = set()
    for ri, atoms in by_residue.items():
        if len(atoms) < 2:
            continue  # single-atom residue: a free ion
        if resnames[atoms[0]] in WATER_RESNAMES:
            continue  # water is never intra-residue completed
        comps: dict[int, list[int]] = {}
        for i in atoms:
            comps.setdefault(find(i), []).append(i)
        if len(comps) < 2:
            continue
        mergeable = []
        for root, members in comps.items():
            if (len(members) == 1
                    and elements[members[0]] in _ION_LIKE_ELEMENTS):
                continue  # single-atom metal/ion component: never merged
            # heavy atoms only for the distance criterion
            heavy = [i for i in members if elements[i] != "H"]
            if heavy:
                mergeable.append(heavy)
        if len(mergeable) < 2:
            continue
        roots = list(mergeable)
        for a in range(len(roots)):
            for b in range(a + 1, len(roots)):
                pa = pos[roots[a]]
                pb = pos[roots[b]]
                d = np.linalg.norm(pa[:, None, :] - pb[None, :, :], axis=-1)
                flat = int(d.argmin())
                ia, ib = divmod(flat, len(roots[b]))
                if d[ia, ib] <= _INTRA_RESIDUE_COMPLETION_CUTOFF_A:
                    x, y = roots[a][ia], roots[b][ib]
                    new_bonds.add((min(x, y), max(x, y)))
    if not new_bonds:
        return 0
    existing: set[tuple[int, int]] = set()
    if hasattr(u.atoms, "bonds") and len(u.atoms.bonds):
        existing = {tuple(sorted((int(a), int(b))))
                    for a, b in u.atoms.bonds.indices}
    merged = sorted(existing | new_bonds)
    if hasattr(u.atoms, "bonds"):
        u.del_TopologyAttr("bonds")
    from MDAnalysis.core.topologyattrs import Bonds
    u.add_TopologyAttr(Bonds(merged))
    if report is not None:
        try:
            report.intra_residue_bonds = len(new_bonds)
        except Exception:
            pass
    for x, y in sorted(new_bonds):
        logger.info(
            "intra_residue_completion: bonded %s-%s (residue %s %d, "
            "%.2f A)",
            u.atoms[x].name, u.atoms[y].name,
            u.atoms[x].residue.resname, u.atoms[x].residue.resid,
            float(np.linalg.norm(pos[x] - pos[y])))
    logger.info(
        f"complete_intra_residue_fragments: added {len(new_bonds)} "
        f"intra-residue completion bonds")
    return len(new_bonds)


def bond_stranded_residue_metals(u, report=None) -> int:
    """W3.1 item 11: bond stranded residue metals to their coordination
    partners.

    A metal atom inside a MULTI-ATOM residue can end up with zero
    bonds: metal-ligand coordination distances (heme Fe-N ~2.0 A,
    Zn-finger Zn-S ~2.3 A) exceed the covalent bond-guess fudge
    cutoff, so the metal becomes its own connected component and the
    residue splits into a Fe-free porphyrin plus a phantom 'ion'
    segment (cytc e2e B__v1: HEM verified as C34H30N4O4 plus a bare
    Fe). Bond each STRANDED coordination metal to its same-residue
    N/O/S partners within 2.6 A. Free ions (single-atom residues) are
    never touched — they are legitimately unbonded."""
    import numpy as np
    try:
        elements = [str(e or "").strip().upper() for e in u.atoms.elements]
    except Exception:
        return 0
    try:
        resindices = [int(r) for r in u.atoms.resindices]
    except Exception:
        return 0
    bonded: set[int] = set()
    if hasattr(u.atoms, "bonds") and len(u.atoms.bonds):
        for a, b in u.atoms.bonds.indices:
            bonded.add(int(a))
            bonded.add(int(b))
    by_residue: dict[int, list[int]] = {}
    for i, ri in enumerate(resindices):
        by_residue.setdefault(ri, []).append(i)
    new_bonds: set[tuple[int, int]] = set()
    pos = u.atoms.positions
    for _ri, atoms in by_residue.items():
        if len(atoms) < 2:
            continue  # single-atom residue: a free ion, keep it
        stranded_metals = [
            i for i in atoms
            if i not in bonded
            and elements[i] in _COORDINATION_METAL_ELEMENTS]
        if not stranded_metals:
            continue
        partners = [i for i in atoms
                    if elements[i] in _COORDINATION_PARTNER_ELEMENTS]
        if not partners:
            continue
        for mi in stranded_metals:
            for pi in partners:
                d = float(np.linalg.norm(pos[mi] - pos[pi]))
                if 0.1 < d <= _COORDINATION_CUTOFF_A:
                    new_bonds.add((min(mi, pi), max(mi, pi)))
    if not new_bonds:
        return 0
    existing: set[tuple[int, int]] = set()
    if hasattr(u.atoms, "bonds") and len(u.atoms.bonds):
        existing = {tuple(sorted((int(a), int(b))))
                    for a, b in u.atoms.bonds.indices}
    merged = sorted(existing | new_bonds)
    if hasattr(u.atoms, "bonds"):
        u.del_TopologyAttr("bonds")
    from MDAnalysis.core.topologyattrs import Bonds
    u.add_TopologyAttr(Bonds(merged))
    if report is not None:
        try:
            report.metal_coordination_bonds = len(new_bonds)
        except Exception:
            pass
    logger.info(
        f"bond_stranded_residue_metals: added {len(new_bonds)} "
        f"coordination bonds to stranded residue metals")
    return len(new_bonds)


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
    # bughunt BH-020: a GUESSED bond between two different residues is
    # solvent-solvent contamination, not chemistry — two crystal waters
    # 1.4 A apart (alternate positions) became O=O and verified as
    # PubChem 977 (molecular oxygen) at 84. Never guess bonds across a
    # water residue; authored CONECT bonds (the `existing` set) survive.
    if guessed:
        from ..molecules.instances import WATER_RESNAMES
        try:
            resindices = u.atoms.resindices
            resnames = [str(rn).strip().upper() for rn in u.residues.resnames]
            def _is_water_atom(ai: int) -> bool:
                ri = int(resindices[ai])
                return 0 <= ri < len(resnames) and resnames[ri] in WATER_RESNAMES

            guessed = {
                (a, b) for a, b in guessed
                if not (_is_water_atom(a) and int(resindices[b]) != int(resindices[a]))
                and not (_is_water_atom(b) and int(resindices[a]) != int(resindices[b]))
            }
        except Exception:
            pass  # no residue table (LAMMPS .data): unchanged behaviour
    union = sorted(existing | guessed)
    if union:
        # wave-2 item 6b: a guessed proton can sit within fudge of several
        # donors (cetirizine N-H...O class) — keep only the shortest bond
        # per hydrogen. Skipped when elements are unknown.
        pruned = _prune_multi_bonded_hydrogens(u, set(union))
        u.add_TopologyAttr(Bonds(sorted(pruned)))
        return len(pruned)
    return 0


def _prune_multi_bonded_hydrogens(u, bond_pairs: set) -> set:
    """wave-2 item 6b: the radius guesser can bond one hydrogen to several
    donors (the proton lies within the vdw fudge of both N and O, e.g.
    cetirizine's N-H...O). Keep at most ONE bond per hydrogen — the
    shortest. Applies uniformly to authored+guessed bonds; atoms without
    element info are left untouched."""
    if not hasattr(u.atoms, 'elements') or u.atoms.n_atoms == 0:
        return bond_pairs
    try:
        elements = [str(e).capitalize() for e in u.atoms.elements]
    except Exception:
        return bond_pairs
    pos = u.atoms.positions
    drop: set[tuple[int, int]] = set()
    by_h: dict[int, list[tuple[float, tuple[int, int]]]] = {}
    for a, b in bond_pairs:
        for h, o in ((a, b), (b, a)):
            if elements[h] == 'H' and elements[o] != 'H':
                d = float(np.linalg.norm(pos[h] - pos[o]))
                by_h.setdefault(h, []).append((d, tuple(sorted((h, o)))))
    for h, cands in by_h.items():
        if len(cands) > 1:
            keep = min(cands)[1]
            drop.update(bp for _d, bp in cands if bp != keep)
    return bond_pairs - drop


@dataclass
class RepairReport:
    elements_guessed: int = 0
    # W3.1-2: provenance of the element assignment — "topology" (real
    # topology/PDB element data), "repaired" (re-derived by us from
    # names/masses because the source was missing or parser-guessed),
    # or "coarse_grained_blank".
    elements_source: str = ""
    masses_guessed: int = 0
    names_fixed: int = 0
    bonds_guessed: int = 0
    # W3.1 item 11: coordination bonds added to stranded residue
    # metals (heme Fe, chlorophyll Mg, Fe-S clusters)
    metal_coordination_bonds: int = 0
    intra_residue_bonds: int = 0
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "elements_guessed": self.elements_guessed,
            "elements_source": self.elements_source,
            "masses_guessed": self.masses_guessed,
            "names_fixed": self.names_fixed,
            "bonds_guessed": self.bonds_guessed,
            "metal_coordination_bonds": self.metal_coordination_bonds,
            "intra_residue_bonds": self.intra_residue_bonds,
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
            # W3.1 item 11: a stranded metal inside a multi-atom residue
            # (heme Fe, chlorophyll Mg, Fe-S clusters) must be bonded to
            # its coordination partners — see bond_stranded_residue_metals.
            self.bond_stranded_residue_metals()
            # W3.1 S17 follow-up: a residue is one chemical unit — merge
            # components torn apart by the conservative fudge cutoff
            # (heme propionate arms at 2.09 A).
            self.complete_intra_residue_fragments()
        
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
        # W3.1-2: parser-GUESSED elements (ITP atom-type guessing etc.)
        # are untrusted — re-derive them from names/masses below.
        attr = getattr(self.u._topology, 'elements', None)
        self._elements_were_guessed = bool(
            attr is not None and getattr(attr, 'is_guessed', False))
        if self._has_elements() and not self._elements_were_guessed:
            self.report.elements_source = "topology"
            return 0
        self.report.elements_source = "repaired"

        count_before = sum(1 for e in self.u.atoms.elements if self._is_valid_element(e)) if hasattr(self.u.atoms, 'elements') else 0

        # Check if there are ANY blank or invalid elements - if so, use fallback
        # Also use fallback if elements attribute doesn't exist
        has_elements_attr = hasattr(self.u.atoms, 'elements')
        has_invalid = has_elements_attr and any(not self._is_valid_element(e) for e in self.u.atoms.elements)
        has_blanks = has_elements_attr and any(not e or not e.strip() for e in self.u.atoms.elements)
        
        if (self._elements_were_guessed or not has_elements_attr
                or has_blanks or has_invalid):
            # Use custom fallback to fill in blanks/invalid — and to
            # RE-DERIVE parser-guessed elements (W3.1-2: ITP atom-type
            # guessing is not evidence).
            logger.debug("Elements missing/blank/invalid/guessed, using custom fallback")
            self._guess_elements_fallback(
                force_all=self._elements_were_guessed)
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

    def _guess_elements_fallback(self, force_all: bool = False) -> None:
        """Custom element guessing when MDAnalysis fails.
        Tries: atom name prefix → atom type prefix → mass match.
        Only fills in blank/invalid elements, preserves valid ones —
        unless ``force_all`` (W3.1-2: parser-guessed elements are
        untrusted, re-derive every atom)."""
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

        # W3 A3 (BH-038/BH-045): mass provenance + once-per-universe
        # coarse-grained detection. MDAnalysis name-derives guessed masses
        # on element-less PDB/GRO (`topology.masses.is_guessed`); those are
        # not evidence. CG systems keep elements blank entirely.
        masses_attr = getattr(self.u._topology, 'masses', None)
        masses_trusted = bool(
            masses_attr is not None and not getattr(masses_attr, 'is_guessed', False))
        coarse_grained, _cg_why = self._looks_coarse_grained(masses_trusted)
        if coarse_grained:
            self.report.elements_source = "coarse_grained_blank"
            self.report.warnings.append(
                f"Coarse-grained topology detected ({_cg_why}) - "
                "elements left blank (no atomistic chemistry to guess)")
            logger.warning("coarse-grained topology detected (%s); elements left blank", _cg_why)

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
            # Only guess if element is blank or invalid (or we are
            # re-deriving parser-guessed elements).
            if force_all or not self._is_valid_element(elements[i]):
                resname = resnames_arr[i] if resnames_arr else None
                ri = int(resindex_arr[i]) if resindex_arr is not None else None
                element = self._guess_single_element(
                    existing="",
                    name=names[i] if names else None,
                    mass=masses[i] if masses else None,
                    atom_type=types[i] if types else None,
                    resname=str(resname) if resname is not None else None,
                    residue_atom_count=residue_sizes.get(ri, 0) if ri is not None else 0,
                    mass_trusted=masses_trusted,
                    coarse_grained=coarse_grained,
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

    def _looks_coarse_grained(self, masses_trusted: bool) -> tuple[bool, str]:
        """W3 A3 (BH-038): once-per-universe coarse-grained detection.

        True when ANY holds:
         - trusted topology masses match an element for < 50% of atoms
           (Martini bead masses 45/54/56/72 are not element masses);
         - polymer residues average < 5 atoms and > 50% carry a BB bead;
         - > 50% of atom names are Martini bead names.
        """
        n = self.u.atoms.n_atoms
        try:
            names0 = list(self.u.atoms.names)
        except Exception:
            names0 = []
        try:
            resnames0 = {str(r).strip().upper() for r in self.u.atoms.resnames}
        except Exception:
            resnames0 = set()
        # W3.1-2: all-atom systems (incl. HMR — heavy masses shifted by
        # −2.016/H) are NOT coarse-grained when their atom names are
        # organic and the residues are standard biomolecule residues.
        if names0:
            organic = sum(1 for nm in names0
                          if str(nm).strip()[:1].upper() in _ORGANIC_FIRST) / len(names0)
            standard = any(_is_polymer_resname(r) for r in resnames0)
            martini = sum(1 for nm in names0
                          if str(nm).upper() in _MARTINI_NAMES) / len(names0)
            if organic >= 0.6 and martini <= 0.2 and (standard or not resnames0):
                return False, ""
        if masses_trusted:
            real = [m for m in self.u.atoms.masses if m > 0.5]
            if real:
                matched = sum(1 for m in real if _mass_candidates(float(m)))
                if matched / len(real) < 0.5:
                    return True, (f"topology masses: {matched}/{len(real)} "
                                  f"match an element")
        # name/shape heuristic (element-less PDB/GRO CG)
        if (hasattr(self.u, 'residues') and len(self.u.residues)
                and hasattr(self.u.atoms, 'resnames')):
            prot = [r for r in self.u.residues if _is_polymer_resname(r.resname)]
            if prot:
                mean = sum(r.atoms.n_atoms for r in prot) / len(prot)
                has_bb = sum(1 for r in prot if "BB" in set(r.atoms.names))
                if mean < 5 and has_bb > 0.5 * len(prot):
                    return True, (f"polymer residues avg {mean:.1f} atoms, "
                                  f"BB in {has_bb}/{len(prot)}")
        names = list(getattr(self.u.atoms, 'names', []))
        if names:
            frac = sum(1 for nm in names if str(nm).upper() in _MARTINI_NAMES) / max(n, 1)
            if frac > 0.5:
                return True, f"martini bead names {frac:.0%}"
        return False, ""

    def _guess_single_element(self, existing: str, name: str | None, mass: float | None,
                              atom_type: str | None,
                              resname: str | None = None,
                              residue_atom_count: int = 0,
                              mass_trusted: bool = True,
                              coarse_grained: bool = False) -> str:
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

        # W3 A3: coarse-grained systems keep elements blank upstream.
        if coarse_grained:
            return ''

        # 2. Mass first — but ONLY when the mass came from the topology
        # (mass_trusted). MDAnalysis name-derives guessed masses on
        # element-less PDB/GRO: trusting them inverted every ambiguity
        # (IRE CAL -> Ca, HEM NA -> Na, Martini -> Sc/Po).
        if mass_trusted and mass is not None and mass > 0.5:
            # W3.1-2: united-atom/HMR-aware mass rule, name breaks ties.
            elem = _element_from_mass_name(float(mass), name)
            if elem:
                return elem

        single_atom = residue_atom_count == 1
        non_polymer = not _is_polymer_resname(resname)

        # 3. Single-atom NON-polymer residues: ion table by RESNAME first,
        # then atom name (the old code keyed on the name only), then the
        # existing residue-aware logic WITHOUT the mass hop again.
        if single_atom and non_polymer and name:
            ion = _ION_RESNAME_ELEMENTS.get((resname or "").upper().strip())
            if not ion:
                ion = _ION_RESNAME_ELEMENTS.get(name.upper().strip())
            if ion:
                return ion

        # 4. Name prefixes, residue-context aware (W3 A3 restructure):
        #    4a. exact-name allowlist ^(CL|BR|FE|ZN|MG|MN|CU|NI|SE)digit*'?$;
        #    4b. organic first letter (C N O S P H F I) after leading digits;
        #    4c. the legacy residue-capitalisation ladder — but NEVER a
        #        two-letter element from: CA CD CE NA NB NE HG OS SC PO CO.
        if name:
            name_upper = name.upper().strip()
            stripped = name_upper.lstrip("0123456789")
            m = _EXACT_NAME_RE.match(stripped)
            if m:
                return EXACT_NAME_ELEMENTS[m.group(1)]
            if stripped and stripped[0] in _ORGANIC_FIRST:
                return stripped[0]

            two_letter_first = single_atom or non_polymer

            if two_letter_first and len(stripped) >= 2:
                two_char = stripped[:2].capitalize()
                if two_char in ATOMTABLE_ELEMENTS_MASSES:
                    return two_char

            first_char = stripped[:1].upper() if stripped else ""
            if first_char and first_char in ATOMTABLE_ELEMENTS_MASSES:
                return first_char

            if not two_letter_first and len(stripped) >= 2:
                # polymer path: 2-letter only after 1-letter failed
                two_char = stripped[:2].capitalize()
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

        # 5. From atom type: exact ion-style types only — never
        # substrings (W3.1-2: amber 'NA' is aromatic N, not sodium;
        # SDS/OPLS 'opls_*' says nothing reliable) then first letter.
        if atom_type:
            t = atom_type.strip().upper()
            if t in _EXACT_TYPE_IONS:
                return _EXACT_TYPE_IONS[t]
            if t[:1] in ("C", "N", "O", "H", "S", "P"):
                return t[0]

        # 6. From mass (only when topology-trusted; name-derived masses on
        # element-less PDB/GRO are not evidence - W3 A3).
        if mass_trusted and mass is not None:
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

    def bond_stranded_residue_metals(self) -> int:
        """W3.1 item 11 — see the module-level function."""
        return bond_stranded_residue_metals(self.u, self.report)

    def complete_intra_residue_fragments(self) -> int:
        """W3.1 S17 follow-up — see the module-level function."""
        return complete_intra_residue_fragments(self.u, self.report)

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
