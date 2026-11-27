"""GitHub #38: the catalog key separates molecules with equal composition
but different residues; identical copies still collapse."""
from src_new.molecules.instances import MoleculeInstance, MoleculeType
from src_new.molecules.uniqueness import collapse_to_unique_instances, compute_uniqueness_key


def _inst(seg, mtype, resnames, comp, atoms):
    return MoleculeInstance(instance_id=seg, segment_ids=[seg], molecule_type=mtype,
                            resnames=list(resnames), resids=list(range(1, len(resnames) + 1)),
                            element_composition=dict(comp), atom_count=atoms)


def test_reversed_nucleic_strands_are_distinct():
    comp = {"C": 38, "N": 15, "O": 28, "P": 4}
    a = _inst("A", MoleculeType.NUCLEIC, ["A", "C", "G", "U"], comp, 85)
    b = _inst("B", MoleculeType.NUCLEIC, ["U", "G", "C", "A"], comp, 85)
    assert compute_uniqueness_key(a) != compute_uniqueness_key(b)


def test_same_formula_different_ligands_are_distinct():
    comp = {"C": 2, "H": 6, "O": 1}
    eth = _inst("L1", MoleculeType.SMALL_MOLECULE, ["EOH"], comp, 9)
    dme = _inst("L2", MoleculeType.SMALL_MOLECULE, ["DME"], comp, 9)
    assert len(collapse_to_unique_instances([eth, dme])) == 2


def test_identical_copies_still_collapse():
    comp = {"C": 42, "H": 82, "N": 1, "O": 8, "P": 1}
    copies = [_inst(f"P{i}", MoleculeType.LIPID, ["POPC"], comp, 134) for i in range(5)]
    assert len(collapse_to_unique_instances(copies)) == 1
