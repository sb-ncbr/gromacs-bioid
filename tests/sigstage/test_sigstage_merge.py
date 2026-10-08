"""Offline tests for scripts/stats/sigstage_merge.py (A7)."""
import importlib.util
import json
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "sigstage_merge", os.path.join(REPO, "scripts", "stats", "sigstage_merge.py"))
mg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mg)


def _row(eid, t, v, **kw):
    r = {"entry_id": eid, "gt_type": t, "gt_value": v,
         "bucket": "validated", "validated": True, "attempted": True, "sim": 1.0}
    r.update(kw)
    return r


def test_dedupe_counts_duplicates_and_sorts():
    rows = [_row(2, "uniprot", "B"), _row(1, "inchikey", "C"),
            _row(1, "inchikey", "C"),  # dup
            _row(1, "inchikey", "A")]
    uniq, dups = mg.dedupe_rows(rows)
    assert dups == 1 and len(uniq) == 3
    keys = [(r["entry_id"], r["gt_type"], r["gt_value"]) for r in uniq]
    assert keys == sorted(keys)


def test_read_shard_rows_and_missing_shards(tmp_path, capsys):
    sd = tmp_path / "shards"
    sd.mkdir()
    (sd / "shard_000.jsonl").write_text(
        json.dumps(_row(1, "pdb", "1ABC")) + "\n" + json.dumps(_row(1, "uniprot", "P1")) + "\n")
    (sd / "shard_001.jsonl").write_text(json.dumps(_row(2, "pdb", "2XYZ")) + "\n")
    rows, n = mg.read_shard_rows(str(sd))
    assert n == 2 and len(rows) == 3

    class _A:
        shards_dir = str(sd); expected_shards = 50

    with pytest.raises(SystemExit):
        mg.merge(_A())


def _mk_entry(root, eid, tasks, extra=None):
    d = root / str(eid)
    d.mkdir(parents=True)
    doc = {"tasks": {k: {"status": v} for k, v in tasks.items()}}
    if extra:
        doc.update(extra)
    (d / "results.json").write_text(json.dumps(doc))


def test_gate_counts_uses_probe_gating(tmp_path):
    probe = mg.load_probe()
    root = tmp_path
    _mk_entry(root, 1, {"load_simulation": "success", "verify_results": "success"})
    _mk_entry(root, 2, {"load_simulation": "success", "verify_results": "failed"})
    _mk_entry(root, 3, {"load_simulation": "failed", "verify_results": "success"})
    _mk_entry(root, 4, {"load_simulation": "success", "verify_results": "success"})
    counts, census = mg.gate_counts(str(root), "results.json", {1, 2, 4}, probe)
    # load_ok AND verify_ok: entries 1 and 4; has_gt among those: both
    assert counts == {"scanned": 2, "gt_covered": 2}
    assert census == 4


def test_merge_full_pipeline_strict_gate_and_deltas(tmp_path, capsys, monkeypatch):
    sd = tmp_path / "shards"
    sd.mkdir()
    _mk_entry(tmp_path, 10, {"load_simulation": "success", "verify_results": "success"})
    _mk_entry(tmp_path, 11, {"load_simulation": "success", "verify_results": "success"})
    (sd / "shard_000.jsonl").write_text(json.dumps(_row(10, "pdb", "1AAA")) + "\n")
    (sd / "shard_001.jsonl").write_text(json.dumps(_row(11, "uniprot", "Q9")) + "\n")
    anchor = {"full": {"pattern": "results.json",
                       "scanned_entries": 1,       # drift: we have 2 -> +1
                       "gt_covered_scanned": 2}}
    anchor_path = tmp_path / "anchor.json"
    anchor_path.write_text(json.dumps(anchor))
    monkeypatch.setattr(mg, "gt_entry_ids_from_pg", lambda: {10, 11})
    oj = str(tmp_path / "sigstage_v2test.json")
    ap = str(anchor_path)

    class _A:
        shards_dir = str(sd); out_json = oj; anchor = ap
        root = str(tmp_path); threads = 2; tag = "2test"; expected_shards = 2
        anchor_lax = True; skip_gate = False; pattern = "results.json"

    out = mg.merge(_A())
    assert os.path.exists(oj)
    assert out["scan"]["anchor_scanned_delta"] == 1
    assert out["scan"]["anchor_gt_covered_delta"] == 0
    assert out["scan"]["dup_row_keys"] == 0
    assert out["scan"]["gate_warnings"]            # lax-documented drift
    assert out["rows"] == 2 and out["generated_by"] == "sigstage_merge.py v2test"

    # STRICT raises on the same drifted counts
    _A.anchor_lax = False
    with pytest.raises(Exception):
        mg.merge(_A())


def test_merge_skip_gate_rows_only(tmp_path, monkeypatch):
    sd = tmp_path / "shards"
    sd.mkdir()
    (sd / "shard_000.jsonl").write_text(json.dumps(_row(1, "pdb", "1A")) + "\n")
    monkeypatch.setattr(mg, "gt_entry_ids_from_pg",
                        lambda: pytest.fail("gate must be skipped"))

    class _A:
        shards_dir = str(sd); out_json = str(tmp_path / "o.json"); anchor = None
        root = str(tmp_path); threads = 2; tag = "x"; expected_shards = 1
        anchor_lax = False; skip_gate = True; pattern = "results.json"

    out = mg.merge(_A())
    assert out["rows"] == 1
