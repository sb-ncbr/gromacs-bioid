"""Unit tests for skeleton fingerprints (F12 contract). No network."""
from rdkit import Chem

import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
from src_new.signatures.skeletize import (
    format_signature,
    fp_to_hex,
    from_smiles,
    heavy_formula,
    hex_to_fp,
    parse_signature,
    skeleton_fp,
    tanimoto,
    tanimoto_hex,
)


def test_bond_order_collapse_makes_aromatic_equal_aliphatic():
    benzene = from_smiles("c1ccccc1")
    cyclohexane = from_smiles("C1CCCCC1")
    assert tanimoto(skeleton_fp(benzene), skeleton_fp(cyclohexane)) == 1.0


def test_protonation_insensitive():
    acetic = from_smiles("CC(=O)O")
    acetate = from_smiles("CC(=O)[O-]")
    assert tanimoto(skeleton_fp(acetic), skeleton_fp(acetate)) == 1.0


def test_distinct_molecules_score_low():
    toluene = from_smiles("Cc1ccccc1")
    aniline_vs_phenol = from_smiles("Oc1ccccc1")
    sim = tanimoto(skeleton_fp(toluene), skeleton_fp(aniline_vs_phenol))
    assert sim < 0.9
    glycerol = from_smiles("OCC(O)CO")
    sim2 = tanimoto(skeleton_fp(toluene), skeleton_fp(glycerol))
    assert sim2 < 0.4


def test_heavy_formula_excludes_hydrogen():
    mol = from_smiles("CC(=O)O")  # C2H4O2
    assert heavy_formula(Chem.RemoveHs(Chem.Mol(mol), sanitize=False)) == "C2O2"
    azilsartan_like = from_smiles("c1ccc(cc1)c2nnn[nH]2")
    hf = heavy_formula(Chem.RemoveHs(Chem.Mol(azilsartan_like), sanitize=False))
    assert hf.startswith("C") and "H" not in hf


def test_format_parse_roundtrip():
    val = format_signature(from_smiles("Cc1ccccc1"))
    assert val is not None and val.startswith("skelfp:v1:")
    hex_part, heavy = parse_signature(val)
    assert hex_part and heavy == "C7"
    fp = hex_to_fp(hex_part)
    assert fp is not None
    assert tanimoto_hex(val, val) == 1.0


def test_parse_rejects_foreign_format():
    assert parse_signature("smiles:abc") == (None, "")


def test_robustness_on_none():
    assert skeleton_fp(None) is None
    assert heavy_formula(None) == ""
    assert from_smiles("") is None
    assert tanimoto_hex("", "") == 0.0
