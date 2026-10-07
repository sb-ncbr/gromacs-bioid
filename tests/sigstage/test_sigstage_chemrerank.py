"""Offline tests for scripts/stats/sigstage_chemrerank.py."""
import importlib.util
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "sigstage_chemrerank", os.path.join(REPO, "scripts", "stats", "sigstage_chemrerank.py"))
cr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cr)


class FakeCampaign:
    GT_FAMILIES = {"inchikey": ("PUBCHEM", "INCHI")}
    FAMILY_DEPTH = 50

    def __init__(self, hits):
        self._hits = hits

    def verified_hits(self, doc):
        return self._hits


class FakeEngine:
    def __init__(self, sims):
        self.sims = sims

    def sim(self, t, v, ht, hid):
        return self.sims.get((v, hid, ht), self.sims.get((v, hid), 0.0))


def _hit(t, ident, conf):
    return (t, ident, conf, None, None, 1)


@pytest.mark.parametrize("rank,nfam,grec,expected", [
    (2, 8, True, "rerank_2_5"),
    (5, 8, True, "rerank_2_5"),
    (6, 10, True, "rerank_6_10"),
    (11, 30, True, "window_11_50"),
    (50, 50, True, "window_11_50"),
    (None, 0, True, "family_mismatch"),
    (None, 3, False, "not_recovered"),
    (1, 3, True, "rank1_kept"),
])
def test_classify(rank, nfam, grec, expected):
    assert cr.classify(rank, nfam, grec) == expected


def test_analyze_entry_rerank_with_conf(monkeypatch):
    hits = [_hit("PUBCHEM_CID", "111", 0.95),    # rank1, wrong molecule
            _hit("PUBCHEM_CID", "222", 0.60),    # rank2, recovers GT
            _hit("INCHI", "333", 0.50)]
    monkeypatch.setattr(cr, "_CAMPAIGN", FakeCampaign(hits))
    engine = FakeEngine({("IK-GT", "111"): 0.11,
                         ("IK-GT", "222"): 0.83,
                         ("IK-GT", "333"): 0.05})
    row = cr.analyze_entry({"data": {}}, "IK-GT", engine)
    assert row["cls"] == "rerank_2_5"
    assert row["rank_true_family"] == 2
    assert row["rank1_ident"] == "111" and row["true_ident"] == "222"
    assert row["rank1_conf"] == 0.95 and row["true_conf"] == 0.60
    assert row["conf_delta_rank1_minus_true"] == pytest.approx(0.35)
    assert row["n_family"] == 3


def test_analyze_entry_global_only(monkeypatch):
    hits = [_hit("UNIPROT_ID", "P99999", 0.9),   # family filter excludes
            _hit("PUBCHEM_CID", "999", 0.5)]     # family, no match
    monkeypatch.setattr(cr, "_CAMPAIGN", FakeCampaign(hits))
    engine = FakeEngine({("IK-GT", "P99999"): 1.0, ("IK-GT", "999"): 0.2})
    row = cr.analyze_entry({"data": {}}, "IK-GT", engine)
    assert row["cls"] == "family_mismatch"
    assert row["global_recover_rank"] == 1
    assert "conf_delta_rank1_minus_true" not in row


def test_analyze_entry_not_recovered(monkeypatch):
    hits = [_hit("PUBCHEM_CID", "999", 0.5)]
    monkeypatch.setattr(cr, "_CAMPAIGN", FakeCampaign(hits))
    engine = FakeEngine({("IK-GT", "999"): 0.2})
    row = cr.analyze_entry({"data": {}}, "IK-GT", engine)
    assert row["cls"] == "not_recovered"
    assert row["true_ident"] is None


def test_load_candidates_filters(monkeypatch, tmp_path):
    rows = [
        {"entry_id": 1, "gt_type": "inchikey", "gt_value": "IK-A", "s7_class": "organic",
         "s0_validated": True, "s7_attempted": True, "s7_validated@1": False},
        {"entry_id": 1, "gt_type": "inchikey", "gt_value": "IK-B", "s7_class": "ion",
         "s0_validated": True, "s7_attempted": True, "s7_validated@1": False},
        {"entry_id": 2, "gt_type": "inchikey", "gt_value": "IK-C", "s7_class": "organic",
         "s0_validated": True, "s7_attempted": True, "s7_validated@1": True},
        {"entry_id": 3, "gt_type": "uniprot", "gt_value": "P1", "s7_class": None,
         "s0_validated": False, "s7_attempted": True, "s7_validated@1": False},
    ]
    p = tmp_path / "rows.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    monkeypatch.setattr(cr, "AUDIT_ROWS", str(p))
    assert cr.load_candidates() == [(1, "IK-A")]
