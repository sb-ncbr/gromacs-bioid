"""Offline unit tests for scripts/stats/sigstage_casefiles.py.

Pure functions + synthetic docs in tmp dirs. No network/NFS/DB.
"""
import importlib.util
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "sigstage_casefiles", os.path.join(REPO, "scripts", "stats", "sigstage_casefiles.py"))
cf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cf)


# ------------------------------------------------------------ nmg_class

@pytest.mark.parametrize("gens,gt_type,expected", [
    ({"fasta_map_protein"}, "uniprot", "protein_fasta_present_but_unmatched"),
    ({"FASTA_MAP_PROTEIN"}, "pdb", "protein_fasta_present_but_unmatched"),  # case-insens
    ({"fasta_map_nucleic"}, "uniprot", "nucleic_only_no_protein_fasta"),
    ({"pdb"}, "uniprot", "struct_only_no_fasta_generator"),
    ({"mmcif"}, "pdb", "struct_only_no_fasta_generator"),
    ({"smiles"}, "uniprot", "ligand_only_signatures"),
    ({"morgan"}, "pdb", "ligand_only_signatures"),
    ({"name"}, "uniprot", "no_macro_no_chem_signatures"),
    (set(), "uniprot", "no_macro_no_chem_signatures"),
    ({"skeleton_fp"}, "inchikey", "chem_present_but_no_smiles"),
    ({"fasta_map_protein"}, "inchikey", "macro_only_no_ligand_signature"),
    (set(), "inchikey", "no_chem_signatures"),
    ({"smiles"}, "glycan", "unmapped_gt_type"),
])
def test_nmg_class(gens, gt_type, expected):
    assert cf.nmg_class(gens, gt_type) == expected


# ------------------------------------------------------------ parse_error_class

@pytest.mark.parametrize("msg,expected", [
    ("Explicit valence for atom # 8 O, 2, is greater than permitted", "explicit_valence"),
    ("SMILES Parse Error: unclosed ring", "unclosed_ring"),
    ("SMILES Parse Error: ring closure mismatch", "ring_closure_mismatch"),
    ("Invalid atom specification somewhere", "invalid_atom"),
    ("SMILES Parse Error: extra open parentheses", "smiles_parse_error"),
    ("something completely different", "other"),
    ("", "unknown"),
    (None, "unknown"),
])
def test_parse_error_class(msg, expected):
    assert cf.parse_error_class(msg) == expected


def test_parse_with_error_valid_and_invalid():
    pytest.importorskip("rdkit")
    ok, err = cf._parse_with_error("c1ccccc1")
    assert ok is True and err is None
    ok, err = cf._parse_with_error("C(C(C")
    assert ok is False
    assert cf.parse_error_class(err) in {
        "smiles_parse_error", "explicit_valence", "other", "unknown"}


# ------------------------------------------------------------ load_targets / scans

def _write_audit_rows(path, rows):
    with open(path, "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")


def test_load_targets(monkeypatch, tmp_path):
    p = tmp_path / "rows.jsonl"
    _write_audit_rows(p, [
        {"entry_id": 1, "gt_type": "uniprot", "gt_value": "P1", "s0_bucket": "no_matching_generator"},
        {"entry_id": 1, "gt_type": "pdb", "gt_value": "1abc", "s0_bucket": "no_matching_generator"},
        {"entry_id": 2, "gt_type": "uniprot", "gt_value": "P2", "s0_bucket": "validated"},
    ])
    monkeypatch.setattr(cf, "AUDIT_ROWS", str(p))
    targets = cf.load_targets("no_matching_generator")
    assert sorted(targets.keys()) == [1]
    assert len(targets[1]) == 2


def _doc(signatures, stage_errors=None):
    data = {"signatures": signatures}
    if stage_errors is not None:
        data["stage_errors"] = {"signatures": stage_errors}
    return {"data": data}


def test_scan_nmg_entry(tmp_path):
    eid = 900201
    d = tmp_path / str(eid)
    d.mkdir()
    doc = _doc(
        {"SEG_A": {"generated": {"smiles": "CCO", "morgan": "fp"}},
         "SEG_B": {"generated": {"name": "LIG"}}},
        stage_errors={"SEG_A": [{"generator": "pdb", "error": "no topology for PDB writer"}]},
    )
    (d / "results.json").write_text(json.dumps(doc))
    rows = cf.scan_nmg_entry(
        eid, [{"gt_type": "uniprot", "gt_value": "P1"}], str(tmp_path), "results.json")
    assert len(rows) == 1
    r = rows[0]
    assert r["nmg_class"] == "ligand_only_signatures"
    assert r["n_segments"] == 2
    assert r["generators"] == ["morgan", "name", "smiles"]
    assert len(r["stage_errors_first"]) == 1
    assert "no topology" in r["stage_errors_first"][0]


def test_scan_unparseable_entry(tmp_path):
    pytest.importorskip("rdkit")
    eid = 900202
    d = tmp_path / str(eid)
    d.mkdir()
    doc = _doc({"LIG1": {"generated": {"smiles": "C(C(C"}},
                "LIG2": {"generated": {"smiles": "c1ccccc1"}}})
    (d / "results.json").write_text(json.dumps(doc))
    rows = cf.scan_unparseable_entry(
        eid, [{"gt_type": "inchikey", "gt_value": "IKX"}], str(tmp_path), "results.json")
    assert len(rows) == 1
    r = rows[0]
    assert r["segment"] == "LIG1" and r["gt_value"] == "IKX"
    assert r["raw_smiles"] == "C(C(C"
    assert r["error_class"] in {"smiles_parse_error", "explicit_valence", "other", "unknown"}
    assert r["rdkit_error"]


# ------------------------------------------------------------ run driver

def test_run_driver_writes_jsonl(monkeypatch, tmp_path):
    rows_file = tmp_path / "rows.jsonl"
    _write_audit_rows(rows_file, [
        {"entry_id": 11, "gt_type": "uniprot", "gt_value": "P1", "s0_bucket": "no_matching_generator"},
    ])
    d = tmp_path / "data" / "11"
    d.mkdir(parents=True)
    (d / "results.json").write_text(json.dumps(_doc({"S": {"generated": {"smiles": "CCO"}}})))
    out_dir = tmp_path / "out"
    monkeypatch.setattr(cf, "AUDIT_ROWS", str(rows_file))
    monkeypatch.setattr(cf, "OUT_DIR", str(out_dir))
    rows, errors = cf.run("no_matching_generator", cf.scan_nmg_entry,
                          "nmg.jsonl", str(tmp_path / "data"), "results.json", 2, 0)
    assert errors == 0 and len(rows) == 1
    written = (out_dir / "nmg.jsonl").read_text().strip()
    assert json.loads(written)["entry_id"] == 11


# ------------------------------------------------------------ summary schema

def test_summary_keys_when_one_bucket(monkeypatch, tmp_path):
    rows_file = tmp_path / "rows.jsonl"
    _write_audit_rows(rows_file, [
        {"entry_id": 11, "gt_type": "uniprot", "gt_value": "P1", "s0_bucket": "no_matching_generator"},
    ])
    d = tmp_path / "data" / "11"
    d.mkdir(parents=True)
    (d / "results.json").write_text(json.dumps(_doc({"S": {"generated": {"smiles": "CCO"}}})))
    out_dir = tmp_path / "out"
    monkeypatch.setattr(cf, "AUDIT_ROWS", str(rows_file))
    monkeypatch.setattr(cf, "OUT_DIR", str(out_dir))
    cf.main(["--bucket", "no_matching_generator", "--root", str(tmp_path / "data"),
             "--threads", "2"])
    summ = json.loads((out_dir / "summary.json").read_text())
    assert set(summ) == {"S0-OQ-1"}
    assert summ["S0-OQ-1"]["rows"] == 1
    assert summ["S0-OQ-1"]["class_counts"] == {"ligand_only_signatures": 1}
