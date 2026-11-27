"""GitHub #16: neutral glycerolipids (DAG/TAG/CE) are typed lipid with a
LIPID MAPS shorthand — only when the atoms are exactly the named species,
since several names are PDB CCD codes or other force-field residues."""
import pytest

pytest.importorskip("MDAnalysis")

from src_new.identification.resolvers.lipid import species_shorthand
from src_new.loader.universe_facade import LoadedUniverse
from src_new.molecules.instances import LIPID_RESNAMES, MoleculeType
from src_new.molecules.lipid_names import neutral_glycerolipid_shorthand
from tests.src_new.loader.test_molecule_classification import _fragment, _props

DOG_C39H72O5 = {"C": 39, "H": 72, "O": 5}


def _cls(resname, composition):
    elements = [e for e, n in composition.items() for _ in range(n)]
    return LoadedUniverse._classify_molecule_type(
        _props(atom_count_fragment=len(elements)), _fragment([resname], elements))


def test_amber_dog_dag_is_lipid_with_species():
    # NMRlipids 718: 1,2-dioleoyl-sn-glycerol, C39H72O5
    assert _cls("DOG", DOG_C39H72O5) == MoleculeType.LIPID
    assert species_shorthand(neutral_glycerolipid_shorthand("DOG", DOG_C39H72O5)) == "DG 36:2"


def test_triolein_and_cholesteryl_oleate():
    assert species_shorthand(neutral_glycerolipid_shorthand(
        "TRIO", {"C": 57, "H": 104, "O": 6})) == "TG 54:3"
    assert neutral_glycerolipid_shorthand("CHOLE", {"C": 45, "H": 78, "O": 2}) == "CE 18:1"


@pytest.mark.parametrize("resname,composition", [
    ("DOG", {"C": 6, "H": 12, "O": 5}),               # CCD 2-deoxyglucose
    ("DMG", {"C": 4, "H": 9, "N": 1, "O": 2}),        # CCD dimethylglycine
    ("DPG", {"C": 3, "H": 8, "O": 10, "P": 2}),       # CCD 2,3-diphosphoglycerate
    ("SOG", {"C": 14, "H": 28, "O": 5, "S": 1}),      # CCD octyl thioglucoside
    ("TRIS", {"C": 4, "H": 11, "N": 1, "O": 3}),      # CCD TRIS buffer
    ("TRIP", {"C": 23, "H": 46, "O": 2}),             # CHARMM36 tricosanoic acid
])
def test_other_molecules_with_these_names_get_no_shorthand(resname, composition):
    assert neutral_glycerolipid_shorthand(resname, composition) is None


@pytest.mark.parametrize("resname,composition", [
    ("DOG", {"C": 6, "H": 12, "O": 5}), ("DMG", {"C": 4, "H": 9, "N": 1, "O": 2}),
    ("TRIS", {"C": 4, "H": 11, "N": 1, "O": 3}), ("TRIP", {"C": 23, "H": 46, "O": 2}),
])
def test_other_molecules_are_not_typed_lipid_by_name(resname, composition):
    assert _cls(resname, composition) != MoleculeType.LIPID


def test_names_stay_out_of_plain_lipid_resnames():
    # repair's coarse-grained detection reads LIPID_RESNAMES residue sizes
    assert not {"DOG", "DMG", "DPG", "SOG", "TRIS", "TRIO"} & LIPID_RESNAMES
