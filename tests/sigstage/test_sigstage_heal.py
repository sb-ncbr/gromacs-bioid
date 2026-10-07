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


# ------------------------------------------------------------------ purge()
# Regression for the 2026-10-07 live dry-run crash: purge() unpacked the
# ("cid", value) tuple as (ka, a) and then splatted the STRING ka into
# smiles_for(*ka) -- every purge invocation died with TypeError before any
# rewrite. The purge driver had zero coverage; these tests pin the full
# rewrite contract (heal / still-zero / drop / untouched + backup + dry-run).

import argparse  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402

SMILES = {
    ("cid", "111"): "CCO",
    ("cid", "222"): "CCCO",
    ("cid", "333"): "c1ccccc1",
    ("inchikey", "AAA-BBB-N"): "O=C=O",
    ("cid", "444"): None,      # unresolvable side
    ("cid", "555"): "CC",
}
TANIMOTO = {
    ("CCO", "CCCO"): 0.85,          # >= GATE 0.7 -> healed
    ("c1ccccc1", "O=C=O"): 0.10,    # < GATE -> genuinely zero, kept
}

PAIR_LINES = [
    "skel-cid:111|skel-cid:222\t0.000000",           # heals -> 0.850000
    "skel-cid:333|skel-inchikey:AAA-BBB-N\t0.000000",  # computed zero -> kept
    "skel-cid:444|skel-cid:555\t0.000000",           # unresolvable -> dropped
    "skel-cid:111|skel-cid:333\t0.730000",           # nonzero -> untouched
    "garbage-line-no-tab",                           # malformed -> dropped
    # (documented purge semantics: only 2-field rows survive a rewrite;
    #  live-run verification must therefore account line-count deltas
    #  against the malformed-line census, not just heal/drop counters)
]


def _pair_file(tmp_path):
    pf = tmp_path / "pairs.jsonl"
    pf.write_text("\n".join(PAIR_LINES) + "\n")
    return pf


def _args(**kw):
    d = dict(root="", pattern="results.json", budget=500, limit=0,
             measure=False, purge=True, dry_run=False, stamp="test")
    d.update(kw)
    return argparse.Namespace(**d)


def _patch(monkeypatch, pf):
    monkeypatch.setattr(hl, "PAIR_FILE", str(pf))
    monkeypatch.setattr(hl, "smiles_for",
                        lambda kind, value, allow_web=False: SMILES.get((kind, value)))
    monkeypatch.setattr(hl, "fresh_tanimoto",
                        lambda sa, sb: TANIMOTO.get((sa, sb)))


def test_purge_calls_smiles_for_with_kind_and_value(tmp_path, monkeypatch):
    """The exact live-failure regression: smiles_for must be called as
    smiles_for(kind, value) -- not with a splatted kind string."""
    pf = _pair_file(tmp_path)
    seen = []

    def spy(kind, value, allow_web=False):
        seen.append((kind, value))
        return SMILES.get((kind, value))

    monkeypatch.setattr(hl, "smiles_for", spy)
    monkeypatch.setattr(hl, "fresh_tanimoto", lambda sa, sb: TANIMOTO.get((sa, sb)))
    monkeypatch.setattr(hl, "PAIR_FILE", str(pf))
    hl.purge(_args())
    assert ("cid", "111") in seen and ("cid", "222") in seen
    assert ("inchikey", "AAA-BBB-N") in seen
    assert all(k in ("cid", "inchikey") for k, _ in seen)


def test_purge_rewrite_semantics(tmp_path, monkeypatch, capsys):
    pf = _pair_file(tmp_path)
    original = pf.read_bytes()
    _patch(monkeypatch, pf)
    hl.purge(_args())
    out = json.loads(capsys.readouterr().out)
    # backup exists and is byte-identical to the original
    backup = str(pf) + ".bak-pre-heal-test"
    assert os.path.isfile(backup)
    assert hashlib.md5(open(backup, "rb").read()).hexdigest() == \
        hashlib.md5(original).hexdigest()
    assert (out["healed"], out["still_zero"], out["dropped_unresolved"]) == (1, 1, 1)
    assert pf.read_text().splitlines() == [
        "skel-cid:111|skel-cid:222\t0.850000",            # healed, rewritten
        "skel-cid:333|skel-inchikey:AAA-BBB-N\t0.000000",  # computed zero kept
        "skel-cid:111|skel-cid:333\t0.730000",            # untouched
        # 444|555 dropped (unresolvable); malformed line dropped (documented)
    ]


def test_purge_dry_run_writes_nothing(tmp_path, monkeypatch, capsys):
    pf = _pair_file(tmp_path)
    before = pf.read_bytes()
    _patch(monkeypatch, pf)
    hl.purge(_args(dry_run=True))
    out = json.loads(capsys.readouterr().out)
    assert (out["candidates"], out["healed"], out["still_zero"],
            out["dropped_unresolved"]) == (3, 1, 1, 1)
    assert pf.read_bytes() == before                  # untouched, byte-exact
    assert not os.path.exists(str(pf) + ".bak-pre-heal-test")


def test_purge_budget_excess_zeros_dropped_without_recompute(tmp_path, monkeypatch):
    """Budget exhaustion drops remaining zeros WITHOUT a fresh value -- under
    the A1 engine that means retry-on-demand (never a re-poisoned zero).
    Pinned: budget-drops are NOT counted in dropped_unresolved."""
    pf = _pair_file(tmp_path)
    calls = []
    monkeypatch.setattr(hl, "smiles_for",
                        lambda k, v, allow_web=False: calls.append((k, v)) or SMILES.get((k, v)))
    monkeypatch.setattr(hl, "fresh_tanimoto", lambda sa, sb: TANIMOTO.get((sa, sb)))
    monkeypatch.setattr(hl, "PAIR_FILE", str(pf))
    hl.purge(_args(budget=1))
    # only the first zero pair was resolved through smiles_for
    kinds = {k for k, _ in calls}
    assert ("cid", "444") not in calls and ("cid", "555") not in calls
    lines = pf.read_text().splitlines()
    assert "skel-cid:111|skel-cid:222\t0.850000" in lines      # healed
    assert not any(l.startswith("skel-cid:333|") for l in lines)   # budget-dropped
    assert not any(l.startswith("skel-cid:444|") for l in lines)   # budget-dropped
    assert any(l.startswith("skel-cid:111|skel-cid:333\t0.730000") for l in lines)
    assert len(kinds) <= 4
