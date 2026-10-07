"""Offline tests for scripts/stats/sigstage_warmup.py.

Key grounding: the byte format of warmup-appended pair lines MUST equal
SimEngine._save_pair's format -- the campaign rerun reads the union of both
writers' output, so a format drift would corrupt the cache silently. That
drift is guarded against the LIVE engine implementation, not a copy.
"""
import argparse
import importlib.util
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


wu = _load("sigstage_warmup", os.path.join(REPO, "scripts", "stats", "sigstage_warmup.py"))
vsim = _load("warmup_test_vsim", os.path.join(REPO, "scripts", "validation_similarity.py"))


def _engine_saved_line(path, key, sim):
    eng = vsim.SimEngine(budget=1)
    eng.pair_path = str(path)
    eng._save_pair(key, sim)
    with open(eng.pair_path) as fh:
        return fh.read()


def test_pair_line_byte_matches_engine_save(tmp_path):
    """Drift guard vs the live SimEngine._save_pair (not a replica)."""
    for i, (key, sim) in enumerate([("skel-cid:1|skel-cid:2", 1.0),
                                    ("skel-cid:3|skel-inchikey:ABC-DEF-N", 0.0),
                                    ("skel-inchikey:X-A|skel-inchikey:Y-B", 0.7342)]):
        got = _engine_saved_line(tmp_path / f"pairs_{i}.jsonl", key, sim)
        assert wu.pair_line(key, sim) == got


class _FakeHeal:
    @staticmethod
    def pair_key_sides(key):
        parts = key.split("|")
        if len(parts) != 2:
            return None
        out = []
        for p in parts:
            pref, _, val = p.partition(":")
            if pref == "skel-cid":
                out.append(("cid", val))
            elif pref == "skel-inchikey":
                out.append(("inchikey", val))
            else:
                return None
        return out[0], out[1]

    TANI = {}

    @classmethod
    def fresh_tanimoto(cls, sa, sb):
        return cls.TANI.get((sa, sb))


class _FakeVsim:
    SMILES = {}
    FAIL = set()

    @classmethod
    def _cid_smiles(cls, cid):
        if cid in cls.FAIL:
            raise LookupError(cid)
        return cls.SMILES.get(("cid", cid))

    @classmethod
    def _inchikey_smiles(cls, ik):
        if ik in cls.FAIL:
            raise LookupError(ik)
        return cls.SMILES.get(("inchikey", ik))


_FakeVsim.SMILES = {("cid", "1"): "CCO", ("cid", "2"): "CCCO",
                    ("inchikey", "K-A"): "c1ccccc1"}
_FakeHeal.TANI = {("CCO", "CCCO"): 0.85, ("CCO", "c1ccccc1"): 0.0}


def test_resolve_pair_classes():
    fv, fh = _FakeVsim, _FakeHeal
    assert wu.resolve_pair("skel-cid:1|skel-cid:2", fv, fh) == \
        ("skel-cid:1|skel-cid:2", 0.85, "resolved")
    assert wu.resolve_pair("skel-cid:1|skel-inchikey:K-A", fv, fh)[2] == "resolved"
    assert wu.resolve_pair("skel-cid:1|skel-inchikey:K-A", fv, fh)[1] == 0.0  # computed zero OK
    fv.FAIL = {"9"}
    assert wu.resolve_pair("skel-cid:1|skel-cid:9", fv, fh)[2] == "ghost"
    assert wu.resolve_pair("not-a-pair", fv, fh)[2] == "bad_key"
    fh.TANI.pop(("CCO", "CCCO"))
    assert wu.resolve_pair("skel-cid:1|skel-cid:2", fv, fh)[2] == "unparseable"


def _args(keys_file, **kw):
    d = dict(keys_file=str(keys_file), threads=4, limit=0,
             progress_every=10**9, dry_run=False)
    d.update(kw)
    return argparse.Namespace(**d)


def _run_warmup(tmp_path, monkeypatch, keys, dry_run=False):
    kf = tmp_path / "keys.txt"
    kf.write_text("\n".join(keys) + "\n")
    pf = tmp_path / "pairs.jsonl"
    monkeypatch.setattr(wu, "PAIR_FILE", str(pf))
    monkeypatch.setattr(wu, "GHOST_OUT", str(tmp_path / "warmup_ghosts.json"))
    monkeypatch.setattr(wu, "load_vsim", lambda: _FakeVsim)
    monkeypatch.setattr(wu, "load_heal", lambda: _FakeHeal)
    _FakeVsim.FAIL = {"9"}
    _FakeHeal.TANI = {("CCO", "CCCO"): 0.85, ("CCO", "c1ccccc1"): 0.0}
    out = wu.warmup(_args(kf, dry_run=dry_run))
    return out, pf


def test_warmup_appends_sorted_resolved_and_ghost_ledger(tmp_path, monkeypatch):
    keys = ["skel-cid:1|skel-inchikey:K-A",   # resolves 0.0 (computed zero)
            "skel-cid:1|skel-cid:9",          # ghost
            "skel-cid:1|skel-cid:2"]          # resolves 0.85
    out, pf = _run_warmup(tmp_path, monkeypatch, keys)
    assert (out["resolved"], out["ghost"]) == (2, 1)
    assert (out["unparseable"], out["bad_key"], out["appended"]) == (0, 0, 2)
    assert pf.read_text().splitlines() == [
        "skel-cid:1|skel-cid:2\t0.850000",
        "skel-cid:1|skel-inchikey:K-A\t0.000000",
    ]  # sorted append, exact engine format
    ghosts = json.load(open(tmp_path / "warmup_ghosts.json"))
    assert ghosts["ghosts"] == ["skel-cid:1|skel-cid:9"]
    assert ghosts["dropped_input"] == 3


def test_warmup_dry_run_appends_nothing(tmp_path, monkeypatch):
    keys = ["skel-cid:1|skel-cid:2"]
    out, pf = _run_warmup(tmp_path, monkeypatch, keys, dry_run=True)
    assert out["resolved"] == 1 and out["appended"] == 0
    assert not pf.exists()
