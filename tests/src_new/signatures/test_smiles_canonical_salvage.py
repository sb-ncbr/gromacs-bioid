"""A4 tests: canonical salvage of charge-spam-corrupted generator molecules.

Root cause (S0-OQ-2, 525/525 explicit_valence): _fragment_to_rdkit_atoms marks
every atom NoImplicit and topology carries no charge data, so formal charges
in the built molecule are ALL DetermineBondOrders compensation artifacts.
When the partial sanitize fails, the generator used to emit the unsanitized
string -- unparseable downstream (skeletize/metrics). The salvage clears the
compensation charges, lets RDKit re-derive implicit Hs, sanitizes (minus
kekulize, the documented freeze hazard) and emits the canonical neutral-parent
SMILES. Success path of the generator is NOT touched (identification
resolvers consume it byte-identically).

Fixtures: first 20 raw_smiles rows from the real 525-row case file
(/data/validation/sigstage/casefiles/S0-OQ-2_unparseable.jsonl).
"""
import json
import os
import sys

import pytest
from rdkit import Chem

REPO = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
FIX = os.path.join(REPO, "tests", "sigstage", "fixtures", "oq2_raw_smiles_head20.jsonl")
if REPO not in sys.path:
    sys.path.insert(0, REPO)


@pytest.fixture(scope="module")
def gen():
    from src_new.signatures.generators import smiles
    return smiles


def _case_strings():
    rows = []
    with open(FIX) as fh:
        for ln in fh:
            r = json.loads(ln)
            rows.append((r["entry_id"], r["raw_smiles"]))
    return rows


def _parse_unsanitized(raw):
    return Chem.MolFromSmiles(raw, sanitize=False)


@pytest.mark.parametrize("entry_id,raw", _case_strings())
def test_salvage_525_class_reparses_clean(gen, entry_id, raw):
    mol = _parse_unsanitized(raw)
    assert mol is not None, "fixture must parse with sanitize=False"
    out = gen._canonicalize_for_roundtrip(mol)
    assert out, f"entry {entry_id}: salvage must succeed"
    # re-parseable under FULL sanitize (the downstream failure mode before A4)
    reparsed = Chem.MolFromSmiles(out)
    assert reparsed is not None, f"entry {entry_id}: salvaged string must re-parse"
    # atom budget preserved: no atoms lost or gained by normalization
    assert reparsed.GetNumAtoms() == mol.GetNumAtoms()
    # compensation charge spam eliminated; minimal-charge repair may keep
    # single legalizing charges (quaternary [N+] etc.) but never spam
    charges = sum(abs(a.GetFormalCharge()) for a in reparsed.GetAtoms())
    raw_charges = sum(abs(a.GetFormalCharge()) for a in mol.GetAtoms())
    assert charges <= 2, f"entry {entry_id}: charges={charges} raw={raw_charges}"
    assert charges < raw_charges or raw_charges == 0


@pytest.mark.parametrize("entry_id,raw", _case_strings()[:3])
def test_salvage_consumable_by_skeleton_pipeline(gen, entry_id, raw):
    """The exact consumer that failed in OQ-2: skeletize.from_smiles."""
    from src_new.signatures.skeletize import from_smiles, skeleton_fp
    mol = _parse_unsanitized(raw)
    out = gen._canonicalize_for_roundtrip(mol)
    skel = from_smiles(out)
    assert skel is not None
    assert skeleton_fp(skel) is not None


def test_salvage_idempotent(gen):
    raw = _case_strings()[0][1]
    out1 = gen._canonicalize_for_roundtrip(_parse_unsanitized(raw))
    out2 = gen._canonicalize_for_roundtrip(Chem.MolFromSmiles(out1))
    assert out1 == out2


def test_salvage_returns_none_on_unsalvageable(gen):
    # central carbon with FIVE explicit carbon neighbours: valence junk
    # even when neutral and single-bonded
    junk = Chem.MolFromSmiles("[C](C)(C)(C)(C)C", sanitize=False)
    assert junk is not None
    assert gen._canonicalize_for_roundtrip(junk) is None


def test_salvage_leaves_clean_molecules_byte_neutral(gen):
    for smi in ("CCO", "c1ccccc1", "CC(=O)Oc1ccccc1C(=O)O"):
        mol = Chem.MolFromSmiles(smi)
        out = gen._canonicalize_for_roundtrip(mol)
        assert Chem.MolToSmiles(Chem.MolFromSmiles(out)) == \
            Chem.MolToSmiles(Chem.MolFromSmiles(smi))
