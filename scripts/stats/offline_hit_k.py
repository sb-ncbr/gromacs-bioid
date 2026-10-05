#!/usr/bin/env python3
"""Offline hit@K scoring.

Compares ground_truth_signatures (Postgres) against verified_hits in
per-entry results JSON files (results-v*.json). Computes per-entry and
aggregate hit@1/5/10 and can persist rows into validation_results.

hit@K (entry): fraction of the entry's GT identifiers (uniprot/pdb)
               that appear among the entry's top-K verified hits
               (ranked by final_confidence, identifiers normalized).
"""
import argparse
import json
import os
import collections
import psycopg2
from datetime import datetime

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://validation:validation-password-change-me@validation-postgres:5432/bat3_validation",
)
KSET = (1, 5, 10)


def load_gt(con):
    cur = con.cursor()
    cur.execute("SELECT entry_id, signature_type, signature_value FROM ground_truth_signatures")
    gt = {}
    for eid, t, v in cur.fetchall():
        if v and t:
            gt.setdefault(eid, {}).setdefault(t.strip().lower(), set()).add(v.strip().upper())
    return gt


def norm(ident_type, value):
    v = (value or "").strip().upper()
    if not v:
        return ""
    t = (ident_type or "").strip().upper()
    if "PDB" in t:
        return v[:4]
    return v


def verified_hits(results_doc):
    """[(ident_type, identifier, final_confidence)] ranked desc."""
    out = []
    ver = (results_doc.get("data") or {}).get("verification") or {}
    for _, seg in ver.items():
        for h in (seg or {}).get("verified_hits") or []:
            if isinstance(h, dict):
                try:
                    conf = float(h.get("final_confidence") or 0.0)
                except Exception:
                    conf = 0.0
                out.append((h.get("ident_type"), h.get("identifier"), conf))
    out.sort(key=lambda x: x[2], reverse=True)
    return out


def score_entry(gt_map, hits):
    """Return dict with hit@K per type + overall, GT count."""
    ranked_ids = [norm(t, v) for t, v, _ in hits if norm(t, v)]
    types = set(gt_map.keys()) | {"overall"}
    per = {}
    for t in sorted(types):
        if t == "overall":
            wanted = {v for s in gt_map.values() for v in s}
        else:
            wanted = gt_map.get(t, set())
        row = {"gt": len(wanted)}
        for k in KSET:
            topk = set(ranked_ids[:k])
            row[f"hit@{k}"] = (sum(1 for v in wanted if v in topk) / len(wanted)) if wanted else None
        per[t] = row
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/data/validation")
    ap.add_argument("--pattern", default="results-v3.json")
    ap.add_argument("--write-db", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    con = psycopg2.connect(DATABASE_URL)
    gt = load_gt(con)
    print(f"GT entries: {len(gt)}", flush=True)

    processed = 0
    missing_file = 0
    parse_fail = 0
    agg = collections.defaultdict(lambda: collections.defaultdict(list))
    zero_hit_entries = 0
    inserted = 0
    agg_gt = collections.Counter()

    for eid, gt_map in sorted(gt.items()):
        if args.limit and processed >= args.limit:
            break
        path = os.path.join(args.root, str(eid), args.pattern)
        if not os.path.isfile(path):
            missing_file += 1
            continue
        try:
            doc = json.load(open(path))
        except Exception:
            parse_fail += 1
            continue
        hits = verified_hits(doc)
        per = score_entry(gt_map, hits)
        processed += 1
        if not hits:
            zero_hit_entries += 1
        for t, row in per.items():
            agg_gt[t] += row["gt"]
            for k in KSET:
                if row[f"hit@{k}"] is not None:
                    agg[t][f"hit@{k}"].append(row[f"hit@{k}"])

        if args.write_db:
            metrics = {"per_type": per, "n_verified_hits": len(hits),
                       "pipeline_status": (doc.get("pipeline") or {}).get("status"),
                       "scored_at": datetime.utcnow().isoformat()}
            status = "passed" if (per["overall"].get("hit@5") or 0) > 0 else "failed"
            cur = con.cursor()
            cur.execute(
                "INSERT INTO validation_results (entry_id, run_id, result_type, status, details, metrics, created_at)"
                " VALUES (%s, NULL, %s, %s, %s, %s, %s)",
                (eid, f"offline_hit_k:{args.pattern}", status,
                 f"hit@5={per['overall'].get('hit@5')}", json.dumps(metrics), datetime.utcnow()),
            )
            inserted += 1

    if args.write_db:
        con.commit()

    print(f"\nprocessed: {processed}  missing_file: {missing_file}  parse_fail: {parse_fail}")
    print(f"entries with zero verified hits: {zero_hit_entries}")
    print("\n=== AGGREGATE (mean over entries) ===")
    for t in sorted(agg.keys()):
        row = agg[t]
        parts = [f"gt_total={agg_gt[t]}"]
        for k in KSET:
            vals = row.get(f"hit@{k}") or []
            parts.append(f"hit@{k}={sum(vals)/len(vals):.3f}" if vals else f"hit@{k}=n/a")
        print(f"  {t:8s} " + "  ".join(parts))
    if args.write_db:
        print(f"\nvalidation_results inserted: {inserted}")


if __name__ == "__main__":
    main()
