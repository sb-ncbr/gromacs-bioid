#!/usr/bin/env python3
"""molecule_export -- per-molecule signature/identifier/verified channel export.

Deliverable of the S0 closeout wave: one row per (entry_id, gt_type,
gt_value) molecule annotation with all three pipeline channels projected
from sigstage audit shard rows:

  signature channel  (S0): sig_validated, sig_bucket, sig_sim, sig_best_segment
  identifier channel (S5): id_hit@1, id_hit@5, id_hit@10   (exact-match hit@K)
  verified channel   (S7): ver_attempted, ver_class, ver_sim@1/5/10,
                           ver@1, ver@5, ver@10, n_hits

Output: sorted JSONL + CSV (identical rows), deterministic by
(entry_id, gt_type, gt_value). Duplicate keys counted into the summary
(playbook invariant: 0 expected).
"""
import argparse
import csv
import json
import os

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
ROW_KEY = ("entry_id", "gt_type", "gt_value")

COLUMNS = [
    "entry_id", "gt_type", "gt_value",
    "sig_validated", "sig_bucket", "sig_sim", "sig_best_segment",
    "id_hit@1", "id_hit@5", "id_hit@10",
    "ver_attempted", "ver_class",
    "ver_sim@1", "ver_sim@5", "ver_sim@10",
    "ver@1", "ver@5", "ver@10", "n_hits",
]

PROJECTION = {
    "sig_validated": "s0_validated",
    "sig_bucket": "s0_bucket",
    "sig_sim": "s0_sim",
    "sig_best_segment": "s0_best_segment",
    "id_hit@1": "s5_hit@1",
    "id_hit@5": "s5_hit@5",
    "id_hit@10": "s5_hit@10",
    "ver_attempted": "s7_attempted",
    "ver_class": "s7_class",
    "ver_sim@1": "s7_sim@1",
    "ver_sim@5": "s7_sim@5",
    "ver_sim@10": "s7_sim@10",
    "ver@1": "s7_validated@1",
    "ver@5": "s7_validated@5",
    "ver@10": "s7_validated@10",
    "n_hits": "n_hits",
}


def project(row):
    out = {k: row.get(k) for k in ROW_KEY}
    for dst, src in PROJECTION.items():
        out[dst] = row.get(src)
    return out


def merge_shard_rows(shards_dir):
    """-> (rows_sorted_deduped, dups)."""
    seen = set()
    rows = []
    dups = 0
    files = sorted(f for f in os.listdir(shards_dir)
                   if f.startswith("shard_") and f.endswith(".jsonl"))
    for f in files:
        with open(os.path.join(shards_dir, f)) as fh:
            for ln in fh:
                ln = ln.strip()
                if not ln:
                    continue
                r = json.loads(ln)
                k = tuple(r.get(f2) for f2 in ROW_KEY)
                if k in seen:
                    dups += 1
                    continue
                seen.add(k)
                rows.append(r)
    rows.sort(key=lambda r: (r["entry_id"], str(r["gt_type"]), str(r["gt_value"])))
    return rows, dups


def export(args):
    rows, dups = merge_shard_rows(args.shards_dir)
    os.makedirs(args.out_dir, exist_ok=True)
    jsonl_path = os.path.join(args.out_dir, f"per_molecule_{args.tag}.jsonl")
    csv_path = os.path.join(args.out_dir, f"per_molecule_{args.tag}.csv")
    projected = [project(r) for r in rows]
    payload = "".join(json.dumps(p, sort_keys=True) + "\n" for p in projected)
    with open(jsonl_path, "w") as fh:
        fh.write(payload)
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        w.writeheader()
        for p in projected:
            w.writerow({c: p.get(c) for c in COLUMNS})
    summary = {
        "jsonl": jsonl_path, "csv": csv_path,
        "molecules": len(projected), "dup_row_keys": dups,
        "sig_channel": sum(1 for p in projected if p["sig_validated"] is not None),
        "id_channel_hit@1": sum(1 for p in projected if p["id_hit@1"]),
        "ver_channel_attempted": sum(1 for p in projected if p["ver_attempted"]),
        "ver@1_true": sum(1 for p in projected if p["ver@1"] is True),
    }
    print(json.dumps(summary, indent=1))
    return summary


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shards-dir", required=True)
    ap.add_argument("--out-dir", default=os.path.join(DATA, "sigstage", "exports"))
    ap.add_argument("--tag", default="v2")
    export(ap.parse_args(argv))


if __name__ == "__main__":
    main()
