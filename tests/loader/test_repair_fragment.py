from ...src.constants import ATOMTABLE_ELEMENTS_MASSES
from ...src.loader.repair_fragment import (
    estimate_elements_from_mass,
    estimate_elements_from_names,
    estimate_elements_multi,
    fix_names,
    guess_element,
)


class FakeAtoms:
    def __init__(self, n_atoms, names=None, masses=None, types=None, elements=None):
        self.n_atoms = n_atoms
        self.names = list(names or [""] * n_atoms)
        self.masses = list(masses or [0.0] * n_atoms)
        self.types = list(types or [""] * n_atoms)
        self.elements = list(elements or [""] * n_atoms)

    def __len__(self):
        return self.n_atoms

    def add_TopologyAttr(self, name, values):
        setattr(self, name, list(values))


class FakeUniverse:
    def __init__(self, n_atoms):
        self.atoms = FakeAtoms(n_atoms)

    def add_TopologyAttr(self, name, values):
        setattr(self, name, list(values))


class FakeFragment:
    def __init__(self, names=None, masses=None, types=None, elements=None):
        n_atoms = len(names or masses or types or elements or [])
        self.n_atoms = n_atoms
        self.atoms = FakeAtoms(n_atoms, names, masses, types, elements)
        self.names = self.atoms.names
        self.masses = self.atoms.masses
        self.types = self.atoms.types
        self.elements = self.atoms.elements


def test_estimate_elements_from_names_infers_simple_atom_name_prefixes():
    universe = FakeUniverse(3)
    fragment = FakeFragment(names=["C1", "H2", "O3"])
    saved = []

    assert estimate_elements_from_names(universe, fragment, save_to=saved)
    assert fragment.atoms.elements == ["C", "H", "O"]
    assert saved == ["C", "H", "O"]


def test_estimate_elements_from_names_reports_unresolved_prefixes():
    universe = FakeUniverse(1)
    fragment = FakeFragment(names=["1BAD"])

    assert not estimate_elements_from_names(universe, fragment)
    assert fragment.atoms.elements == [""]


def test_estimate_elements_from_mass_infers_known_atomic_mass():
    universe = FakeUniverse(1)
    fragment = FakeFragment(masses=[ATOMTABLE_ELEMENTS_MASSES["C"]])
    saved = []

    assert estimate_elements_from_mass(universe, fragment, save_to=saved)
    assert fragment.atoms.elements == ["C"]
    assert saved == ["C"]


def test_estimate_elements_from_mass_reports_unknown_mass():
    universe = FakeUniverse(1)
    fragment = FakeFragment(masses=[9999.0])

    assert not estimate_elements_from_mass(universe, fragment)
    assert fragment.atoms.elements == [""]


def test_estimate_elements_multi_prefers_existing_elements():
    universe = FakeUniverse(1)
    fragment = FakeFragment(elements=[" c "], masses=[9999.0], types=["unknown"])

    assert estimate_elements_multi(universe, fragment)
    assert fragment.atoms.elements == ["C"]


def test_guess_element_leaves_unknown_inputs_unresolved():
    assert guess_element(None, None, None) is None


def test_fix_names_replaces_duplicate_names_with_generated_unique_names():
    universe = FakeUniverse(3)
    fragment = FakeFragment(names=["CA", "CA", "CA"])

    assert fix_names(universe, fragment)
    assert len(set(fragment.atoms.names)) == 3
    assert fragment.atoms.names != ["CA", "CA", "CA"]
