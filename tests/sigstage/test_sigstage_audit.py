"""Offline unit tests for scripts/stats/sigstage_audit.py (pure functions).

Campaign machinery is injected as fakes; no network/NFS/DB.
"""
import collections
import importlib.util
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "sigstage_audit", os.path.join(REPO, "scripts", "stats", "sigstage_audit.py"))
au = importlib.util.module_from_spec(spec)
spec.loader.exec_module(au)


class FakeCampaign:
    GT_FAMILIES = {"pdb": ("PDB", "ALPHAFOLD"), "uniprot": ("UNIPROT",),
                   "inchikey": ("PUBCHEM", "INCHI")}
    FAMILY_DEPTH = 50
    FALLBACK_DEPTH = 25

    @staticmethod
    def norm_ident(t, v):
        v = (v or "").strip().upper()
        if not v:
            return ""
        return v[:4] if "PDB" in (t or "").upper() else v

    @staticmethod
    def validated_threshold(t):
        return 0.7 if t == "inchikey" else 0.9

    @staticmethod
    def verified_hits(doc):
        return []

    @staticmethod
    def _ion_elements_of(doc):
        return set()


class FakeGR:
    @staticmethod
    def gt_class_for(ik):
        return {"IKZN": "ion"}.get(ik, "organic")

    @staticmethod
    def ion_element(ik):
        return "Zn" if ik == "IKZN" else None


class FakeEngine:
    def __init__(self, sims):
        self.sims = sims    # (gt_value, hit_id) -> sim

    def sim(self, gt_type, gt_value, hit_type, hit_id):
        return self.sims.get((gt_value, hit_id), 0.0)


def _hits(*specs):
    """specs = (ident_type, identifier, conf) -> campaign-shaped tuple."""
    return [(t, i, c, None, None, 1) for t, i, c in specs]


def test_norm_value():
    assert au.norm_value("pdb", "1abcXX") == "1ABC"
    assert au.norm_value("inchikey", "abc-def") == "ABC-DEF"


def test_s5_row_membership():
    hits = _hits(("UNIPROT_ID", "P12345", 0.9), ("PDB_ID", "1abc", 0.8))
    row = au.s5_row_for_annotation(FakeCampaign, "uniprot", "P12345", hits)
    assert row == {"s5_hit@1": 1, "s5_hit@5": 1, "s5_hit@10": 1}
    row = au.s5_row_for_annotation(FakeCampaign, "pdb", "9zzz", hits)
    assert row == {"s5_hit@1": 0, "s5_hit@5": 0, "s5_hit@10": 0}


def test_s7_row_ion_channel(monkeypatch):
    monkeypatch.setattr(au, "_GT_RULES", FakeGR)
    row = au.s7_row_for_annotation(FakeCampaign, FakeEngine({}),
                                   "inchikey", "IKZN", _hits(), {"Zn"})
    assert row["s7_class"] == "ion" and row["s7_attempted"] is True
    assert row["s7_sim@1"] == 1.0 and row["s7_sim@10"] == 1.0
    row = au.s7_row_for_annotation(FakeCampaign, FakeEngine({}),
                                   "inchikey", "IKZN", _hits(), set())
    assert row["s7_sim@1"] == 0.0 and row["s7_attempted"] is False


def test_s7_row_family_window_and_k(monkeypatch):
    monkeypatch.setattr(au, "_GT_RULES", FakeGR)
    engine = FakeEngine({("P1", "PX"): 0.2, ("P1", "P1"): 0.99})
    hits = _hits(("UNIPROT_ID", "PX", 0.99), ("UNIPROT_ID", "P1", 0.5))
    row = au.s7_row_for_annotation(FakeCampaign, engine, "uniprot", "P1", hits, set())
    assert row["s7_attempted"] is True
    assert row["s7_sim@1"] == 0.2          # rank1 hit is the wrong member
    assert row["s7_sim@5"] == 0.99         # right one within 5
    assert row["s7_sim@10"] == 0.99


def test_audit_entry_join_and_thresholds(monkeypatch):
    monkeypatch.setattr(au, "_GT_RULES", FakeGR)
    monkeypatch.setattr(au, "_CAMPAIGN", FakeCampaign)
    monkeypatch.setattr(FakeCampaign, "verified_hits",
                        staticmethod(lambda doc: _hits(("UNIPROT_ID", "P1", 0.9))))
    monkeypatch.setattr(FakeCampaign, "_ion_elements_of",
                        staticmethod(lambda doc: {"Zn"}))
    monkeypatch.setattr(au, "sim_call",
                        lambda engine, t, v, ht, hid: engine.sim(t, v, ht, hid))
    engine = FakeEngine({("P1", "P1"): 0.95, ("PX", "P1"): 0.0})
    s0_by_key = {(7, "uniprot", "P1"): {"validated": True, "bucket": "validated",
                                        "sim": 1.0, "best_segment": "SEG",
                                        "smiles_source": None}}
    rows = au.audit_entry(7, {"data": {}}, {("uniprot", "P1")}, s0_by_key,
                          engine, 50)
    assert len(rows) == 1
    r = rows[0]
    assert r["s0_validated"] is True and r["s7_sim@1"] == 0.95
    assert r["s7_validated@1"] is True and r["s5_hit@1"] == 1
    assert r["n_hits"] == 1


def test_crosstab_and_hist():
    rows = [
        {"s0_validated": True, "s7_validated@1": True, "s7_attempted": True},
        {"s0_validated": False, "s7_validated@1": True, "s7_attempted": True},
        {"s0_validated": False, "s7_validated@1": False, "s7_attempted": True},
        {"s0_validated": True, "s7_validated@1": False, "s7_attempted": False},
    ]
    tab = au.crosstab(rows, 1)
    assert tab == {"s0_0_s7_0": 1, "s0_0_s7_1": 1, "s0_1_s7_1": 1}
    hist = au.sim_hist([{"s0_sim": 0.1}, {"s0_sim": 0.92}, {"s0_sim": 1.0}], "s0_sim")
    assert hist == {"0-.3": 1, ".9-.95": 1, "1.0": 1}


def test_summarize_selection_fields():
    rows = [
        {"entry_id": 1, "gt_type": "uniprot", "gt_value": "P1", "s0_validated": True,
         "s0_bucket": "validated", "s0_sim": 1.0, "n_hits": 3,
         "s7_attempted": True, "s7_validated@1": True, "s7_validated@10": True},
        {"entry_id": 2, "gt_type": "uniprot", "gt_value": "P2", "s0_validated": True,
         "s0_bucket": "validated", "s0_sim": 1.0, "n_hits": 0,
         "s7_attempted": False, "s7_validated@1": False, "s7_validated@10": False},
        {"entry_id": 3, "gt_type": "inchikey", "gt_value": "IKZN", "s7_class": "ion",
         "s0_validated": True, "s0_bucket": "validated", "s0_sim": 1.0, "n_hits": 1,
         "s7_attempted": True, "s7_validated@1": True, "s7_validated@10": True},
    ]
    s = au.summarize(rows)
    uni = s["types"]["uniprot"]
    assert uni["annotations"] == 2 and uni["s0_pct"] == 100.0
    assert uni["s7_attempted"] == 1
    assert uni["s0_validated_pct_on_s7_subset"] == 100.0
    assert uni["zero_hit_entries_annotations"] == 1
    assert uni["s0_validated_pct_on_zero_hit"] == 100.0
    assert "ion" in s["types"]            # ion split applied
    assert "inchikey" not in s["types"]   # single ion row leaves no organic block


def test_load_s0_rows_honors_explicit_dir(tmp_path):
    rows = [
        {"entry_id": 10, "gt_type": "pdb", "gt_value": "1AAA", "bucket": "validated"},
        {"entry_id": 11, "gt_type": "uniprot", "gt_value": "P9", "bucket": "below_gate"},
    ]
    sd = tmp_path / "some_v2_shards"
    sd.mkdir()
    (sd / "shard_000.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))
    (sd / "other.json").write_text("{}")  # non-shard file ignored
    by_key = au.load_s0_rows(str(sd))
    assert len(by_key) == 2
    assert by_key[(10, "pdb", "1AAA")]["bucket"] == "validated"


def test_summarize_tag_mode_writes_tagged_artifact(tmp_path, capsys):
    row = {"entry_id": 1, "gt_type": "uniprot", "gt_value": "P1",
           "s0_validated": True, "s0_bucket": "validated", "s0_sim": 1.0,
           "n_hits": 3, "s7_attempted": True, "s7_validated@1": True,
           "s7_validated@10": True}
    sd = tmp_path / "out"
    (sd / "shards").mkdir(parents=True)
    (sd / "shards" / "shard_000.jsonl").write_text(json.dumps(row) + "\n")
    (sd / "shards" / "shard_001.jsonl").write_text(json.dumps(row) + "\n")

    import argparse
    class _A:
        root = ""; pattern = "results.json"; threads = 1; shard = "0/1"
        budget = 1; out_dir = str(sd); s0_shards = None; limit = 0
        summarize_tag = "v2test"

    import builtins
    real_parse = au.argparse.ArgumentParser.parse_args
    au.argparse.ArgumentParser.parse_args = lambda self, argv=None: _A()
    try:
        au.main([])
    finally:
        au.argparse.ArgumentParser.parse_args = real_parse
    out = json.load(open(sd / "audit_v2test.json"))
    assert out["rows"] == 2
    assert out["types"]["uniprot"]["s7_validated@1_pct"] == 100.0
    printed = json.loads(capsys.readouterr().out)
    assert printed["rows"] == 2 and "audit_v2test.json" in printed["out"]
