"""Offline tests for scripts/stats/sigstage_report.py (fixtures only)."""
import importlib.util
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(REPO, "tests", "sigstage", "fixtures", "report")
spec = importlib.util.spec_from_file_location(
    "sigstage_report", os.path.join(REPO, "scripts", "stats", "sigstage_report.py"))
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


def _report():
    sig = json.load(open(os.path.join(FIX, "sigstage_v1.json")))
    audit = json.load(open(os.path.join(FIX, "audit_v1.json")))
    s7 = json.load(open(os.path.join(FIX, "campaign_stats_v13.json")))
    return rp.build_report(sig, audit, s7["full"])


def test_t1_numbers_and_s7_side():
    t1 = _report()["t1"]
    assert t1["uniprot"]["s0"]["annotations"] == 4
    assert t1["uniprot"]["s0"]["pct_validated"] == 75.0
    assert t1["uniprot"]["s0"]["mean_sim_attempted"] == 0.95
    assert t1["uniprot"]["s7"]["pct_validated@1"] == 90.0
    assert t1["uniprot"]["s7"]["pct_validated@5"] == 92.0
    assert t1["ion"]["s7"]["pct_validated@10"] == 96.1
    assert t1["inchikey"]["s7_annotations"] == 2


def test_t2_decomposition_cells():
    t2 = _report()["t2"]
    uni = t2["uniprot"]
    assert uni["s7_attempted"] == 5
    assert uni["selection"]["zero_hit_annotations"] == 1
    assert uni["selection"]["s0_pct_on_zero_hit"] == 0.0
    assert uni["oracle@1"] == {"n": 1, "pct_of_att": 20.0}
    chem = t2["inchikey"]
    assert chem["pipeline_loss@1"] == {"n": 1, "pct_of_att": 50.0}
    assert chem["pipeline_loss@10"] == {"n": 0, "pct_of_att": 0.0}
    assert chem["both_fail@10"] == {"n": 0, "pct_of_att": 0.0}


def test_t3_buckets_and_denominators():
    t3 = _report()["t3"]
    assert t3["global"]["validated"] == {"n": 6, "pct": 75.0}
    assert t3["global"]["unparseable_signature"] == {"n": 1, "pct": 12.5}
    assert t3["per_type"]["uniprot"]["below_gate"] == {"n": 1, "pct": 25.0}


def test_t4_bullets_have_denominators():
    bullets = _report()["t4"]
    chem = next(b for b in bullets if "reranking" in b)
    assert "1 organic annotations" in chem and "50.0% of 2 attempted" in chem
    uni = next(b for b in bullets if "UniProt" in b)
    assert "S0 75.0% overall" in uni and "80.0% on S7 subset" in uni
    ion = next(b for b in bullets if "Ion" in b)
    assert "100.0%" in ion


def test_render_md_tables_and_determinism():
    rep = _report()
    md1 = rp.render_md(rep)
    md2 = rp.render_md(_report())
    assert md1 == md2                                   # byte-deterministic
    assert "| uniprot | 4 | 3 (75.0%) | 3 (75.0%) | 0.95 | 90.0 | 92.0 | 95.0 |" in md1
    assert "| inchikey | 2 | 0 (S0 None%) | 0 (0.0%) | 1 (50.0%) | 0 (0.0%) | 0 (0.0%) |" in md1
    assert "| validated | 6 | 75.0% |" in md1
    assert "## T4 headline bullets" in md1


def test_missing_input_raises(tmp_path):
    with pytest.raises(FileNotFoundError) as exc:
        rp._load(str(tmp_path), "sigstage_v1.json")
    assert "required input missing" in str(exc.value)


def test_main_writes_outputs(tmp_path):
    out = str(tmp_path / "rep")
    rp.main(["--input-dir", FIX, "--out", out])
    js = json.load(open(out + ".json"))
    md = open(out + ".md").read()
    assert js["t1"]["uniprot"]["s0"]["validated"] == 3
    assert js["entries"] == {"seen": 3, "any_validated": 3, "any_validated_pct": 100.0}
    assert md.startswith("# S0 signature-stage validation")
