"""DEPRECATED (frozen 2026-10) — superseded by src_new/loader/. See src/loader/README.md."""
import itertools
import string
from typing import Any

import periodictable

import MDAnalysis
from MDAnalysis import AtomGroup

from ..constants import (
    ATOMTABLE_ELEMENT_MASS_CONFIDENCE_THRESHOLD,
    ATOMTABLE_ELEMENTS_MASSES,
)

def is_close(a, b, rel_tol=1e-09, abs_tol=0.0):
    # https://stackoverflow.com/questions/5595425/how-to-compare-floats-for-almost-equality-in-python
    return abs(a - b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)


def estimate_elements_from_mass(
    universe: MDAnalysis.Universe,
    fragment: MDAnalysis.AtomGroup,
    save_to: list[str] | None = None
) -> bool:
    """
    Attempts fix missing atomic element information in the simulation by determining them using atomic masses
    Fixing is done only on the AtomGroup provided in the arguments (thus, not all the atoms)
    :param universe: containing the fragment
    :param fragment: in which to fix missing atomic elements
    :param save_to: list to store the names of the identified elements, if provided
    :return: True if all elements in fragment were distinguished confidently, False otherwise
    """
    new_elements: list[str] = ["" for _ in range(fragment.n_atoms)]

    all_successful: bool = True
    for i in range(fragment.n_atoms):
        atom_mass: float = fragment.masses[i]
        for element_name, element_mass in ATOMTABLE_ELEMENTS_MASSES.items():
            if is_close(
                element_mass,
                atom_mass,
                rel_tol=0,
                abs_tol=ATOMTABLE_ELEMENT_MASS_CONFIDENCE_THRESHOLD,
            ):
                new_elements[i] = element_name
                break
        else:
            all_successful = False

    if not hasattr(universe, "elements"):
        universe.add_TopologyAttr(
            "elements", ["" for _ in range(universe.atoms.n_atoms)]
        )
    fragment.atoms.elements = new_elements
    if save_to is not None:
        for e in new_elements: save_to.append(e)

    return all_successful and all([x != "" for x in fragment.atoms.elements])

def estimate_elements_from_names(
    universe: MDAnalysis.Universe,
    fragment: MDAnalysis.AtomGroup,
    use_types_not_names: bool = False,
    save_to: list[str] | None = None
) -> bool:
    """
    Attempts fix missing atomic element information in the simulation by determining them using atomic names
    Fixing is done only on the AtomGroup provided in the arguments (thus, not all the atoms)
    :param universe: containing the fragment
    :param fragment: in which to fix missing atomic elements
    :param use_types_not_names: if True, the source of names will be <<types>> field
    :param save_to: list to store the names of the identified elements, if provided
    :return: True if all elements in fragment were distinguished confidently, False otherwise
    """
    new_elements: list[str] = ["" for _ in range(fragment.n_atoms)]

    all_successful: bool = True
    for i in range(fragment.n_atoms):
        atom_name: str = fragment.names[i] if not use_types_not_names else fragment.types[i]

        element_name: str = ""
        for c in atom_name:
            if c.isalpha():
                element_name += c
            else:
                break
        element_name = element_name.title()

        if element_name in ATOMTABLE_ELEMENTS_MASSES.keys():
            new_elements[i] = element_name
        else:
            all_successful = False

    if not hasattr(universe, "elements"):
        universe.add_TopologyAttr(
            "elements", ["" for _ in range(universe.atoms.n_atoms)]
        )
    fragment.atoms.elements = new_elements
    if save_to is not None:
        for e in new_elements: save_to.append(e)

    return all_successful and all([x != "" for x in fragment.atoms.elements])


def guess_element(atom_element: str | None, atom_mass: float | None, atom_type: str | None) -> str | None:
    """
    Attempts to guess atomic element given various information from MDAnalysis
    :param atom_element: element value of AtomGroup
    :param atom_mass: mass value of AtomGroup
    :param atom_type: type of AtomGroup
    :return: atomic symbol or None
    """

    if atom_element is not None and atom_element.strip():
        return atom_element.strip().capitalize()

    if atom_mass is not None:
        closest = None  # type: ignore
        closest_diff: float | None = None
        for elem in periodictable.elements:
            diff = abs(elem.mass - atom_mass)
            if closest_diff is None or diff < closest_diff:
                closest_diff = diff
                closest = elem

        tolerance_daltons: float = 1.0 if atom_mass < 40 else 2.0
        if closest is not None and closest_diff is not None and closest_diff <= tolerance_daltons:
            return closest.symbol

    if atom_type is not None:
        t: str = atom_type.strip().upper()

        if t.startswith("C"): return "C"
        if t.startswith("N"): return "N"
        if t.startswith("O"): return "O"
        if t.startswith("H"): return "H"
        if t.startswith("P") or "P5" in t or "QA" in t: return "P"
        if t.startswith("S") or "SC" in t: return "S"
        if "NA" in t: return "N"
        if "CL" in t: return "CL"
        if "K" in t: return "K"
        if "ZN" in t: return "ZN"

    return None


def atom_group_get_attribute(molecule: AtomGroup, attribute: str) -> list[Any]:
    """
    Fetches an attribute from the molecule, if available
    :param molecule: to fetch attribute from
    :param attribute: name of the attribute
    :return: lift of values, if available, else list of Nones
    """
    return getattr(molecule, attribute) if hasattr(molecule, attribute) else [None for _ in range(len(molecule.atoms))]


def estimate_elements_multi(
    universe: MDAnalysis.Universe,
    fragment: MDAnalysis.AtomGroup,
    save_to: list[str] | None = None
) -> bool:
    """
    Attempts fix missing atomic element information in the simulation by all available sources altogether
    Fixing is done only on the AtomGroup provided in the arguments (thus, not all the atoms)
    :param universe: containing the fragment
    :param fragment: in which to fix missing atomic elements
    :param save_to: list to store the names of the identified elements, if provided
    :return: True if all elements in fragment were distinguished confidently, False otherwise
    """
    new_elements: list[str] = ["" for _ in range(fragment.n_atoms)]

    all_successful: bool = True
    for i in range(fragment.n_atoms):
        atom_element: str | None = fragment.elements[i] if hasattr(fragment, "elements") else None
        atom_mass: float | None = fragment.masses[i] if hasattr(fragment, "masses") else None
        atom_type: str | None = fragment.types[i] if hasattr(fragment, "types") else None

        guessed_element: str | None = guess_element(atom_element, atom_mass, atom_type)
        if guessed_element is not None:
            new_elements[i] = guessed_element
        else:
            all_successful = False

    if not hasattr(universe, "elements"):
        universe.add_TopologyAttr(
            "elements", ["" for _ in range(universe.atoms.n_atoms)]
        )
    fragment.atoms.elements = new_elements
    if save_to is not None:
        for e in new_elements: save_to.append(e)

    return all_successful and all([x != "" for x in fragment.atoms.elements])

def fix_names(
    universe: MDAnalysis.Universe,
    fragment: MDAnalysis.AtomGroup,
) -> bool:
    """
    Attempts fix names of atoms in the fragment so each atom in reside has a unique one
    Fixing is done only on the AtomGroup provided in the arguments (thus, not all the atoms)
    :param universe: containing the fragment
    :param fragment: in which to fix missing atomic names
    :return: always True
    :raises AssertionError: if simulation is not loaded before
    """

    if not hasattr(universe.atoms, "names"):
        universe.atoms.add_TopologyAttr(
            "names", ["" for _ in range(universe.atoms.n_atoms)]
        )

    symbols: str = string.ascii_letters + string.digits
    new_names: list[str] = []
    for item in itertools.product(symbols, repeat=2):
        if len(new_names) == fragment.atoms.n_atoms:
            break
        new_names.append("".join(item))

    fragment.atoms.names = new_names
    return True
