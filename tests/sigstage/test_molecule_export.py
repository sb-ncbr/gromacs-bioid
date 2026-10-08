"""Offline tests for scripts/stats/molecule_export.py."""
import importlib.util
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
spec = importlib.util.spec_from_file_location(
    "molecule_export", os.path.join(REPO, "scripts", "stats", "molecule_export.py"))
me = importlib.util.module_from_spec(spec)
spec.loader.exec_module(me)

V1_ROW = {"entry_id": 51, "gt_type": "pdb", "gt_value": "1A76", "n_hits": 0,
          "s0_best_segment": None, "s0_bucket": None, "s0_sim": None,
          "s0_smiles_source": None, "s0_validated": None,
          "s5_hit@1": 0, "s5_hit@10": 0, "s5_hit@5": 0,
          "s7_attempted": False, "s7_class": None,
          "s7_sim@1": 0.0, "s7_sim@10": 0.0, "s7_sim@5": 0.0,
          "s7_validated@1": False, "s7_validated@10": False, "s7_validated@5": False}


def test_projection_maps_three_channels():
    p = me.project(V1_ROW)
    assert (p["entry_id"], p["gt_type"], p["gt_value"]) == (51, "pdb", "1A76")
    assert p["sig_validated"] is None and p["sig_bucket"] is None   # null passthrough
    assert (p["id_hit@1"], p["id_hit@5"], p["id_hit@10"]) == (0, 0, 0)
    assert p["ver_attempted"] is False and p["ver@1"] is False and p["n_hits"] == 0
    assert set(me.COLUMNS) == set(p)


def test_merge_dedupes_sorts_and_ignores_non_shards(tmp_path):
    sd = tmp_path / "shards"
    sd.mkdir()
    (sd / "shard_001.jsonl").write_text(json.dumps(V1_ROW) + "\n")
    r2 = dict(V1_ROW, entry_id=7, gt_type="uniprot", gt_value="P9")
    (sd / "shard_000.jsonl").write_text(json.dumps(r2) + "\n" + json.dumps(r2) + "\n")
    (sd / "notes.json").write_text("{}")
    rows, dups = me.merge_shard_rows(str(sd))
    assert dups == 1 and len(rows) == 2
    assert [(r["entry_id"], r["gt_type"]) for r in rows] == [(7, "uniprot"), (51, "pdb")]


def test_export_writes_jsonl_and_csv_deterministically(tmp_path, capsys):
    sd = tmp_path / "in"
    (sd / "shards").mkdir(parents=True)
    (sd / "shards" / "shard_000.jsonl").write_text(json.dumps(V1_ROW) + "\n")
    od = str(tmp_path / "out")

    class _A:
        shards_dir = str(sd / "shards"); out_dir = od; tag = "test"

    s1 = me.export(_A())
    blob1 = (open(s1["jsonl"]).read(), open(s1["csv"]).read())
    s2 = me.export(_A())
    blob2 = (open(s2["jsonl"]).read(), open(s2["csv"]).read())
    assert blob1 == blob2                                  # byte-deterministic
    assert s1["molecules"] == 1 and s1["dup_row_keys"] == 0
    lines = blob1[1].splitlines()
    assert lines[0].split(",")[:3] == ["entry_id", "gt_type", "gt_value"]
    assert len(lines) == 2                                  # header + 1 molecule
    assert s1["sig_channel"] == 0                           # null-guarded counts
    assert json.loads(blob1[0].splitlines()[0])["gt_value"] == "1A76"


def test_summary_counts_channels(tmp_path, capsys):
    rows = [dict(V1_ROW, entry_id=i, gt_type="inchikey", gt_value=f"K{i}",
                 s0_validated=True, s0_bucket="validated", s0_sim=0.9,
                 **{"s5_hit@1": 1, "s7_attempted": True, "s7_validated@1": True})
            for i in range(3)]
    sd = tmp_path / "s2"
    (sd / "shards").mkdir(parents=True)
    (sd / "shards" / "shard_000.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))

    class _A:
        shards_dir = str(sd / "shards"); out_dir = str(tmp_path / "o"); tag = "x"

    s = me.export(_A())
    assert s["sig_channel"] == 3 and s["id_channel_hit@1"] == 3
    assert s["ver_channel_attempted"] == 3 and s["ver@1_true"] == 3
