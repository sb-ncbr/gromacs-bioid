#!/usr/bin/env python3
"""Rebuild the paper's S7 block (campaign_stats.py --full --sim) from S7_DUMP
row files, so the S7 pass can run sharded (S7_SHARD=i/n) across pods.

Same arithmetic as campaign_stats.full_section: per annotation type
  annotations = rows, attempted = rows with attempted,
  pct_validated@K = rows with sim@K >= threshold(type) / annotations
  (ions: 1.0 when the curated element is present in the ion channel);
entry_any_validated@% = entries whose best annotation sim@K >= 0.9.

Usage: s7_merge.py OUT.json ROWS.jsonl [ROWS.jsonl ...]
"""
import collections
import json
import sys

KSET = (1, 5, 10)
SIM_VALIDATED = 0.9
SIM_VALIDATED_BY_TYPE = {"inchikey": 0.7}


def main():
    out_path, paths = sys.argv[1], sys.argv[2:]
    per_type = collections.defaultdict(list)
    best = {}
    for p in paths:
        for line in open(p):
            r = json.loads(line)
            if r["t"] == "ion":
                rec = {k: 1.0 if r.get("el_present") else 0.0 for k in KSET}
            else:
                rec = {k: float(r["sim"][str(k)]) for k in KSET}
            rec["_attempted"] = bool(r.get("attempted"))
            per_type[r["t"]].append(rec)
            b = best.setdefault(r["eid"], {k: 0.0 for k in KSET})
            for k in KSET:
                b[k] = max(b[k], rec[k])
    s7 = {"validated_threshold": SIM_VALIDATED, "validated_threshold_by_type": SIM_VALIDATED_BY_TYPE,
          "rebuilt_from_rows": len(paths)}
    for t, rows in sorted(per_type.items()):
        n = len(rows)
        thr = SIM_VALIDATED_BY_TYPE.get(t, SIM_VALIDATED)
        s7[t] = {"annotations": n,
                 "attempted": sum(r["_attempted"] for r in rows),
                 **{f"pct_validated@{k}": round(100.0 * sum(r[k] >= thr for r in rows) / n, 1) for k in KSET}}
    if best:
        s7["entry_any_validated@%"] = {k: round(100.0 * sum(b[k] >= SIM_VALIDATED for b in best.values())
                                                / len(best), 1) for k in KSET}
    json.dump({"full": {"S7_similarity_hit_at_k": s7}}, open(out_path, "w"), indent=1)
    print(json.dumps(s7, indent=1))


if __name__ == "__main__":
    main()
