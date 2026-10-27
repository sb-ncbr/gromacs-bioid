"""bughunt BH-022: hydrogen injection on mis-elemented single atoms.

_h_deficiency treated every H-less fragment as united-atom:
h = round((mass - nominal)/1.008) with no valence cap and no mass-residual
check, and the _NOMINAL_MASSES table was keyed UPPERCASE while the lookup
used title-case elements. Consequences: CH23 (CLA/CL guessed as C),
CH28 (CAL), H8P (POT), FH37 (heme FE guessed as F in GRO), H9N (NA->N),
each then answered as ELEMENT at 100.

Fix: valence caps (C4 N4 O3 S2 P3 Si4 B4 Se2), whole-hydrogen residual
tolerance 0.15, metals/halogens never H-injected from mass alone, and the
nominal-mass table re-keyed title-case so two-letter elements are found
at all.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

mda = pytest.importorskip("MDAnalysis")

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src_new.signatures.generators._perceive_cache import _h_deficiency


def _frag(elements, masses):
    """Duck-typed fragment with elements + masses (no H present)."""
    return types.SimpleNamespace(
        atoms=types.SimpleNamespace(elements=elements, masses=masses),
    )


class TestHDeficiencyCaps:
    def test_mis_elemented_chlorine_no_injection(self):
        # CLA guessed as C, mass 35.45 -> old h=23 -> "CH23"
        out = _h_deficiency(_frag(["C"], [35.45]))
        assert out is not None and out == {}  # no counts injected

    def test_mis_elemented_iron_as_fluorine_no_injection(self):
        # GRO heme FE -> F, mass 55.845 -> old h=37 -> "FH37"
        out = _h_deficiency(_frag(["F"], [55.845]))
        assert out is not None and out == {}

    def test_mis_elemented_sodium_as_nitrogen_no_injection(self):
        out = _h_deficiency(_frag(["N"], [22.990]))
        assert out is not None and out == {}

    def test_mis_elemented_potassium_as_phosphorus_no_injection(self):
        out = _h_deficiency(_frag(["P"], [39.098]))
        assert out is not None and out == {}

    def test_united_atom_ch3_still_injected(self):
        out = _h_deficiency(_frag(["C"], [15.035]))
        assert out == {0: 3}

    def test_united_atom_ch2_still_injected(self):
        out = _h_deficiency(_frag(["C"], [14.027]))
        assert out == {0: 2}

    def test_two_letter_element_found_in_table(self):
        # the case fix: "Cl" must find its nominal mass at all — the
        # mass residual of a chloride is 0, so no injection (not skipped-
        # as-None either; both are {} here, so use a united-atom Se stand-in
        # for the lookup proof below)
        out = _h_deficiency(_frag(["Se"], [78.971 + 2 * 1.008]))
        assert out == {0: 2}  # SeH2 within valence cap 2

    def test_selenium_beyond_cap_refused(self):
        out = _h_deficiency(_frag(["Se"], [78.971 + 5 * 1.008]))
        assert out is not None and out == {}

    def test_non_whole_residual_refused(self):
        # residual that does not decompose into whole hydrogens
        out = _h_deficiency(_frag(["C"], [12.011 + 1.5]))
        assert out is not None and out == {}

    def test_explicit_hydrogen_disables_correction(self):
        out = _h_deficiency(_frag(["C", "H"], [35.45, 1.008]))
        assert out is None
