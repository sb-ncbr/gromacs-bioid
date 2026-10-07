"""Offline tests for scripts/stats/sigstage_heal.py (pure parts)."""
import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "sigstage_heal", os.path.join(REPO, "scripts", "stats", "sigstage_heal.py"))
hl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hl)


def test_pair_key_sides_ok():
    assert hl.pair_key_sides("skel-cid:123|skel-inchikey:ABC-DEF-G") == \
        (("cid", "123"), ("inchikey", "ABC-DEF-G"))


def test_pair_key_sides_malformed():
    for bad in ("nonsense", "fp-cid:1|fp-inchikey:X", "skel-cid:1",
                "skel-cid:1|skel-inchikey:A|extra", "foo:1|bar:2", ""):
        assert hl.pair_key_sides(bad) is None


def test_fresh_tanimoto_guards():
    pytest.importorskip("rdkit")
    assert hl.fresh_tanimoto(None, "CCO") is None
    assert hl.fresh_tanimoto("CCO", "") is None
    assert hl.fresh_tanimoto("CCO", "C(C(C") is None
    # known values: acetic vs acetate skeleton identical (protonation-blind)
    assert hl.fresh_tanimoto("CC(=O)O", "CC(=O)[O-]") == pytest.approx(1.0)
    assert hl.fresh_tanimoto("CC(=O)O", "CC(=O)O") == pytest.approx(1.0)
    assert hl.fresh_tanimoto("c1ccccc1", "CC(=O)O") < 0.3
