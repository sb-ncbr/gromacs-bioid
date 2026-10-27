"""bughunt BH-021: element-case bug in bond-guessing radii.

MDAnalysis's Bondi vdwradii table is keyed UPPERCASE ('CL', 'ZN', 'MG');
the loader looked up `el.capitalize()` ('Cl', 'Zn', 'Mg'), which missed
every two-letter element and silently fell back to the 1.5 A audit radius
(table: Cl 1.75, Zn 1.39, Mg 1.73). Consequences: a 0.55*(1.5+1.55)
cutoff spuriously bonding Zn-O Glu contacts at 1.61 A, and metals with
true bonds just outside the fallback window falling apart (S17 heme).

(The Fe case needs a covalent-radius discussion — BH-024/decision pile —
Fe is absent from the MDA table entirely.)
"""

from unittest import mock

import numpy as np
import pytest
from MDAnalysis import Universe
from MDAnalysis.core.topology import Topology
from MDAnalysis.core.topologyattrs import (
    Atomnames,
    Bonds,
    Elements,
    Masses,
    Resids,
    Resnames,
    Segids,
    Atomtypes,
)

from src_new.config.loader import RunConfig
from src_new.loader.repair import TopologyRepair, element_based_vdwradii


def _universe(elements, bonds=None, spacing=2.0):
    n = len(elements)
    top = Topology(n, 1, 1, attrs=None)
    u = Universe(top)
    u.add_TopologyAttr(Atomnames([f"A{i}" for i in range(n)]))
    u.add_TopologyAttr(Atomtypes([e.capitalize() for e in elements]))
    u.add_TopologyAttr(Elements(elements))
    u.add_TopologyAttr(Masses([12.0] * n))
    u.add_TopologyAttr(Resnames(["LIG"]))
    u.add_TopologyAttr(Resids([1]))
    u.add_TopologyAttr(Segids(["S"]))
    if bonds:
        u.add_TopologyAttr(Bonds(bonds))
    u.load_new(
        np.array([[[i * spacing, 0.0, 0.0] for i in range(n)]], dtype=np.float32),
        format="memory",
    )
    return u


class TestVdwRadiiCase:
    def test_two_letter_elements_get_table_values(self):
        from MDAnalysis.topology.tables import vdwradii
        u = _universe(["ZN", "CL", "MG", "C", "N"])
        radii = element_based_vdwradii(u)
        assert radii["Zn"] == vdwradii["ZN"]
        assert radii["Cl"] == vdwradii["CL"]
        assert radii["Mg"] == vdwradii["MG"]
        assert radii["C"] == vdwradii["C"]
        assert radii["N"] == vdwradii["N"]

    def test_zn_oxygen_contact_no_longer_bonds(self):
        # Zn ... OE2 at 1.61 A was bonded with the 1.5 fallback
        # (0.55*(1.5+1.52)=1.66); with the true radius 1.39 the window is
        # 0.55*(1.39+1.52)=1.60 < 1.61 -> no bond
        u = _universe(["ZN", "O"], bonds=None, spacing=1.61)
        repair = TopologyRepair(u, RunConfig())
        repair.guess_bonds()
        found = {tuple(sorted(b)) for b in u.atoms.bonds.indices}
        assert (0, 1) not in found
