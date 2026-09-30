"""Nucleic acid recognition helpers.

PyMOL-inspired two-tier detection (design: wave-7 "enhanced nucleic acid
recognition"). Deliberate deviations from PyMOL are documented inline:

- tier 1: liberal resname normalization - canonical one-letter bases, the
  ``D`` deoxy- prefix, and AMBER/CHARMM-style ``[3|5]`` terminal suffixes
  (``DA3``, ``RG5``, ...) that PyMOL's own pattern misses. Legacy
  ``RA/RC/RG/RU/RT`` aliases are kept for backward parity.
- tier 2: structural sugar-phosphate fingerprint (PyMOL parity) but with a
  STRICTER guard than PyMOL: a cross-residue phosphodiester bond is
  mandatory. Single-residue cofactors that carry sugar+phosphate atom
  names (CoA 3'-phosphate, ATP, NAD, FAD, free nucleotides) must never be
  promoted to "nucleic acid", because our verdict feeds a segment-level
  80% gate, not a per-residue rendering flag.
- bare ``I``/``DI`` (inosine) is excluded although PyMOL accepts it: in MD
  force fields resn "I" is commonly iodide, and misclassifying an ionic
  segment is worse than missing rare inosine.

This module is the single source of truth for "what counts as a nucleic
acid residue". Do not re-implement tables elsewhere; consumers:

- ``src_new/loader/universe_facade.py`` (segment classification)
- ``src_new/signatures/generators/fasta.py`` (sequence emission)
"""

from __future__ import annotations

from MDAnalysis import AtomGroup
from MDAnalysis.exceptions import NoDataError

# ---------------------------------------------------------------------------
# tier 1: resname normalization
# ---------------------------------------------------------------------------

# Bases acceptable as the final single character after deoxy/terminal strips.
_BASES = frozenset("ACGTU")

# AMBER/CHARMM-style terminal residue suffixes: DA3 / DC3 / A5 / U3 / ...
_TERMINAL_SUFFIXES = frozenset("35")

# Legacy aliases previously covered by KNOWN_NUCLEIC_ACIDS_CODES.
_LEGACY_ALIASES = {
    "RA": "A",
    "RC": "C",
    "RG": "G",
    "RU": "U",
    "RT": "T",
}


def normalize_nucleic_resname(resname: str) -> str | None:
    """Map a residue name to a canonical one-letter base, or None.

    Rules (in order):
      1. legacy aliases (RA/RC/RG/RU/RT) map to their base
      2. strip a leading ``D`` (deoxy) when more characters remain
      3. strip a trailing ``3``/``5`` (terminal code) when more remain
      4. accept iff exactly one character remains and it is a canonical base

    Examples: A -> A, DA -> A, DA3 -> A, DG5 -> G, RC -> C, DU5 -> U,
              PSU -> None, ATP -> None, ALA -> None.
    """
    rn = resname.strip().upper()
    if not rn:
        return None

    alias = _LEGACY_ALIASES.get(rn)
    if alias is not None:
        return alias

    s = rn
    if len(s) > 1 and s[0] == "D":
        s = s[1:]
    if len(s) > 1 and s[-1] in _TERMINAL_SUFFIXES:
        s = s[:-1]

    if len(s) == 1 and s in _BASES:
        return s
    return None


# ---------------------------------------------------------------------------
# shared atom-name normalization
# ---------------------------------------------------------------------------

def normalize_atom_name(name: str) -> str:
    """Canonical atom name: stripped, upper-cased, ``*`` -> ``'``.

    PDB files historically use ``C4*`` instead of ``C4'``; both spellings
    must be treated identically (PyMOL does the same switch).
    """
    return name.strip().upper().replace("*", "'")


# ---------------------------------------------------------------------------
# tier 2: structural sugar-phosphate fingerprint
# ---------------------------------------------------------------------------

# Ribose ring carbons + linkage oxygens (PyMOL Selector.cpp parity).
_SUGAR_PHOSPHATE_ATOMS = frozenset({"O3'", "C3'", "C4'", "C5'", "O5'"})


def residue_has_sugar_phosphate(atom_names: list) -> bool:
    """True if the given atom names cover the NA sugar-phosphate fingerprint.

    All of O3', C3', C4', C5', O5' must be present (after normalization).
    This matches PyMOL's structural fallback for unknown residue names.
    """
    normalized = {normalize_atom_name(n) for n in atom_names}
    return _SUGAR_PHOSPHATE_ATOMS.issubset(normalized)


def has_cross_residue_phosphodiester(fragment: AtomGroup) -> bool:
    """True if a P-O3' bond connects two different residues of the fragment.

    Mandatory guard for tier-2 promotion: real nucleic acid chains show
    3'->5' phosphodiester linkages between consecutive residues; cofactors
    and free nucleotides (CoA, ATP, NAD, FAD, NTP ligands) do not, even
    though they may carry all the sugar-phosphate atom names.

    Degrades gracefully: a fragment without bond information returns False
    (tier-2 promotion simply cannot fire on bondless input).
    """
    try:
        bonds = fragment.bonds
    except (NoDataError, AttributeError):
        return False

    for bond in bonds:
        a1, a2 = bond.atoms[0], bond.atoms[1]
        if a1.resindex == a2.resindex:
            continue
        pair = {normalize_atom_name(a1.name), normalize_atom_name(a2.name)}
        if pair == {"P", "O3'"}:
            return True
    return False


# ---------------------------------------------------------------------------
# backbone trace atom selection (wave-7 B4)
# ---------------------------------------------------------------------------

# PyMOL guide-atom parity: C4' is PyMOL's nucleic acid guide atom; C3' is
# its documented fallback for NA without C4' (PNA); P is our last resort.
_BACKBONE_ATOM_PRIORITY = ("C4'", "C3'", "P")


def select_na_backbone_atom(residue_atoms: AtomGroup):
    """Pick the backbone-trace atom of one nucleic acid residue.

    Args:
        residue_atoms: AtomGroup spanning exactly one residue.

    Returns:
        The chosen MDAnalysis Atom, or None if no backbone atom exists
        (callers must fall back to their legacy behavior).
    """
    by_name: dict[str, object] = {}
    for atom in residue_atoms:
        by_name.setdefault(normalize_atom_name(atom.name), atom)
    for preferred in _BACKBONE_ATOM_PRIORITY:
        atom = by_name.get(preferred)
        if atom is not None:
            return atom
    return None
