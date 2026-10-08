#!/usr/bin/env python3
"""sigstage_merge -- merge sharded S0 probe outputs into the frozen full-set artifact.

Permanent, tested replacement for the ad-hoc merger lost in a hygiene pass
(lesson: anything used twice belongs in scripts/stats). Steps:

  1. concat out_dir/shards/shard_*.jsonl rows; dedupe by
     (entry_id, gt_type, gt_value) -- the playbook requires 0 duplicate row
     keys; duplicate count is asserted into scan.dup_row_keys;
  2. deterministic row order (sort by the same key);
  3. full-set statistics via probe.aggregate() (verbatim probe machinery --
     no replicas);
  4. GATE PASS: recompute the anchor gating counts with the LIVE entry
     census -- gating needs (load_simulation==success AND
     verify_results==success AND has_gt) which per-shard aggregate files do
     NOT carry, so this merger re-reads results.json task blocks (probe's
     own task_success/entry_ids/gating_counts) and joins the has_gt flag
     from Postgres (ground_truth_signatures). Counts are then gated STRICT
     via probe.anchor_check against the anchor JSON; drift is recorded in
     scan.anchor_*_delta (the +5/+5-era discipline; --anchor-lax only with
     recorded warnings);
  5. write sigstage_{tag}.json (v1-shaped: buckets/entries/generated_by/
     per_type/rows/scan).

Pod execution (needs NFS + DATABASE_URL + probe on NFS).
"""
import argparse
import collections
import glob
import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")


def load_probe(path=None):
    for cand in ([path] if path else []) + [
            os.path.join(DATA, "sigstage_probe.py"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))), "scripts", "stats", "sigstage_probe.py")]:
        if cand and os.path.isfile(cand):
            spec = importlib.util.spec_from_file_location("merge_probe", cand)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
    raise RuntimeError("sigstage_probe.py not importable")


ROW_KEY = ("entry_id", "gt_type", "gt_value")


def dedupe_rows(rows):
    """-> (unique_rows_sorted, dups). Deterministic order by ROW_KEY."""
    seen = set()
    uniq = []
    dups = 0
    for r in sorted(rows, key=lambda r: tuple(str(r.get(k)) for k in ROW_KEY)):
        k = tuple(r.get(f) for f in ROW_KEY)
        if k in seen:
            dups += 1
            continue
        seen.add(k)
        uniq.append(r)
    return uniq, dups


def read_shard_rows(shards_dir):
    rows = []
    scanned = 0
    budget_esc = 0
    for path in sorted(glob.glob(os.path.join(shards_dir, "shard_*.jsonl"))):
        with open(path) as fh:
            n = 0
            for ln in fh:
                ln = ln.strip()
                if ln:
                    rows.append(json.loads(ln))
                    n += 1
        scanned += 1
    return rows, scanned


def default_since_ts():
    """Mirror campaign_stats.py full_section: CAMPAIGN_STATS_SINCE defines the
    denominator window; the merger must use the SAME window or STRICT drift
    measurements count pre-window entries as phantom growth (2026-10-08:
    gate fired with +508/+508 exactly equal to this difference)."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(
            os.environ.get("CAMPAIGN_STATS_SINCE", "2026-09-10T11:00:00")).timestamp()
    except Exception:
        return 0.0


def gate_counts(root, pattern, gt_entry_ids, probe, since_ts=None, threads=16):
    """Recompute gating counts (anchor discipline) with probe machinery.
    since_ts MUST come from default_since_ts() for live runs."""
    if since_ts is None:
        since_ts = default_since_ts()
    ids = probe.entry_ids(root, pattern, since_ts)

    def one(eid):
        try:
            with open(os.path.join(root, str(eid), pattern)) as fh:
                doc = json.load(fh)
        except Exception:
            return (False, False, False)
        lo = probe.task_success(doc, "load_simulation")
        vo = probe.task_success(doc, "verify_results")
        return (lo, vo, eid in gt_entry_ids)

    gate = []
    with ThreadPoolExecutor(max_workers=threads) as ex:
        for res in ex.map(one, ids):
            gate.append((res[2], res[0], res[1]))
    return probe.gating_counts(gate), len(ids)


def gt_entry_ids_from_pg():
    import psycopg2
    url = os.environ.get(
        "DATABASE_URL",
        "postgresql://validation:validation-password-change-me@"
        "validation-postgres:5432/bat3_validation")
    con = psycopg2.connect(url)
    try:
        cur = con.cursor()
        cur.execute("SELECT DISTINCT entry_id FROM ground_truth_signatures")
        return {int(r[0]) for r in cur.fetchall()}
    finally:
        con.close()


def merge(args):
    probe = load_probe()
    t0 = time.time()
    rows, n_shards = read_shard_rows(args.shards_dir)
    if args.expected_shards and n_shards != args.expected_shards:
        raise SystemExit(f"shard count mismatch: found {n_shards}, "
                         f"expected {args.expected_shards}")
    uniq, dups = dedupe_rows(rows)
    anchor = json.load(open(args.anchor)) if args.anchor else None
    scan = {
        "pattern": anchor.get("full", {}).get("pattern") if anchor else args.pattern,
        "methodology": "M-1",
        "shards": n_shards,
        "rows_read": len(rows),
        "dup_row_keys": dups,
    }
    if anchor is not None and not args.skip_gate:
        gt_ids = gt_entry_ids_from_pg()
        counts, census = gate_counts(args.root, scan["pattern"], gt_ids, probe,
                                     threads=args.threads)
        verdict = probe.anchor_check(counts, anchor, scan["pattern"],
                                     lax=args.anchor_lax)
        full = anchor.get("full", {})
        scan.update({
            "census_entries": census,
            "anchor": args.anchor,
            "anchor_scanned": full.get("scanned_entries"),
            "anchor_scanned_delta":
                (counts.get("scanned") - full.get("scanned_entries"))
                if full.get("scanned_entries") is not None else None,
            "anchor_gt_covered": full.get("gt_covered_scanned"),
            "anchor_gt_covered_delta":
                (counts.get("gt_covered") - full.get("gt_covered_scanned"))
                if full.get("gt_covered_scanned") is not None else None,
            "gate_warnings": verdict.get("warnings", []),
        })
    agg = probe.aggregate(uniq, scan)
    out = dict(agg)
    out["scan"] = scan
    out["scan"]["scan_seconds"] = round(time.time() - t0, 1)
    out["generated_by"] = f"sigstage_merge.py v{args.tag}"
    os.makedirs(os.path.dirname(args.out_json) or ".", exist_ok=True)
    with open(args.out_json, "w") as fh:
        json.dump(out, fh, indent=2, sort_keys=True)
    print(json.dumps({"out": args.out_json, "rows": len(uniq),
                      "dup_row_keys": dups,
                      "anchor_scanned_delta": scan.get("anchor_scanned_delta"),
                      "anchor_gt_covered_delta": scan.get("anchor_gt_covered_delta"),
                      "gate_warnings": scan.get("gate_warnings", [])}, indent=1))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--shards-dir", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--anchor", default=os.path.join(DATA, "campaign_stats_v14.json"))
    ap.add_argument("--no-anchor", dest="anchor", action="store_const", const=None)
    ap.add_argument("--pattern", default="results.json")
    ap.add_argument("--root", default=DATA)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--tag", default="2")
    ap.add_argument("--expected-shards", type=int, default=50)
    ap.add_argument("--anchor-lax", action="store_true",
                    help="WARNING-recording lax mode (documented in scan.gate_warnings)")
    ap.add_argument("--skip-gate", action="store_true",
                    help="rows-only merge (no anchor gate pass)")
    merge(ap.parse_args(argv))


if __name__ == "__main__":
    main()
