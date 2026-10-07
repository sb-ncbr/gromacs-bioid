#!/usr/bin/env python3
"""sigstage_chemrerank -- where does the correct organic molecule sit in the
ranked verified_hits list for the 2,143 S0-validated / S7@1-lost annotations?

For each organic inchikey annotation with S0 pass and S7@1 fail, re-walks the
entry's verified_hits (verbatim campaign ordering: chem-first fid_key) with
the campaign family window (PUBCHEM/INCHI depth 50) and computes the rank of
the first hit recovering the GT skeleton (SimEngine skel sim >= 0.7, the S7
gate). Classes:

  rerank_2_5 / rerank_6_10     -- present, displaced below rank 1 (pure rerank)
  window_11_50                 -- present within family depth but outside @10
  family_mismatch              -- reachable ONLY outside family filter
                                  (ident-type routing defect)
  not_recovered                -- no recovering hit anywhere in verified_hits
                                  (identification gap, NOT reranking)

Captures rank-1 vs true-hit identifiers + final_confidence deltas so the
verification team sees the actual margins. Read-only; scratch outputs to
/data/validation/sigstage/casefiles/chemrerank.{jsonl,summary.json}.
"""
import argparse
import collections
import importlib.util
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
AUDIT_ROWS = os.path.join(DATA, "sigstage", "audit", "shards", "shard_000.jsonl")
OUT_PREFIX = os.path.join(DATA, "sigstage", "casefiles", "chemrerank")
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GATE = 0.7


def _load_module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CAMPAIGN = None


def load_campaign():
    global _CAMPAIGN
    if _CAMPAIGN is not None:
        return _CAMPAIGN
    for path in (os.path.join(DATA, "campaign_stats.py"),
                 os.path.join(_REPO_ROOT, "scripts", "campaign_stats.py")):
        if os.path.isfile(path):
            try:
                _CAMPAIGN = _load_module_from(path, "chemrerank_campaign")
                return _CAMPAIGN
            except Exception:
                continue
    raise RuntimeError("campaign_stats.py not importable")


_SIM = None


def load_vsim():
    global _SIM
    if _SIM is not None:
        return _SIM
    for path in (os.path.join(DATA, "validation_similarity.py"),
                 os.path.join(_REPO_ROOT, "scripts", "validation_similarity.py")):
        if os.path.isfile(path):
            try:
                _SIM = _load_module_from(path, "chemrerank_vsim")
                return _SIM
            except Exception:
                continue
    raise RuntimeError("validation_similarity.py not importable")


# ---------------------------------------------------------------- classify

def classify(rank_true_family, family_hit_count, global_recover):
    """rank_true_family: 1-based rank of first skel>=0.7 hit inside the
    family window (None if absent); global_recover: bool."""
    r = rank_true_family
    if r is None:
        return "family_mismatch" if global_recover else "not_recovered"
    if r == 1:
        return "rank1_kept"  # should not occur in this cohort (S7@1 fail)
    if r <= 5:
        return "rerank_2_5"
    if r <= 10:
        return "rerank_6_10"
    return "window_11_50"


def analyze_entry(doc, gt_value, engine):
    """Returns row dict for one (entry, organic-GT) pair."""
    campaign = load_campaign()
    hits = campaign.verified_hits(doc)
    fam = campaign.GT_FAMILIES["inchikey"]
    fam_hits = [h for h in hits
                if any(f in (h[0] or "").upper() for f in fam)][:campaign.FAMILY_DEPTH]

    rank_true, true_hit, true_sim, true_conf = None, None, 0.0, 0.0
    for idx, h in enumerate(fam_hits, 1):
        s = engine.sim("inchikey", gt_value, h[0], h[1])
        if s >= GATE and rank_true is None:
            rank_true, true_hit, true_sim = idx, h[1], s
            true_conf = h[2] if len(h) > 2 and isinstance(h[2], (int, float)) else 0.0

    global_recover, global_rank = False, None
    if rank_true is None:
        for idx, h in enumerate(hits, 1):
            if any(f in (h[0] or "").upper() for f in fam):
                continue
            s = engine.sim("inchikey", gt_value, h[0], h[1])
            if s >= GATE:
                global_recover, global_rank = True, idx
                break

    r1 = fam_hits[0] if fam_hits else (hits[0] if hits else None)
    row = {
        "gt_value": gt_value,
        "n_hits": len(hits), "n_family": len(fam_hits),
        "rank_true_family": rank_true,
        "cls": classify(rank_true, len(fam_hits), global_recover),
        "global_recover_rank": global_rank,
        "rank1_ident": r1[1] if r1 else None,
        "rank1_ident_type": r1[0] if r1 else None,
        "rank1_conf": r1[2] if r1 and len(r1) > 2 else None,
        "true_ident": true_hit,
        "true_conf": true_conf,
        "true_sim": round(true_sim, 4) if true_sim else 0.0,
    }
    if r1 and rank_true is not None and isinstance(row["rank1_conf"], (int, float)):
        row["conf_delta_rank1_minus_true"] = round(row["rank1_conf"] - true_conf, 4)
    return row


# ---------------------------------------------------------------- driver

def load_candidates():
    out = []
    with open(AUDIT_ROWS) as fh:
        for ln in fh:
            r = json.loads(ln)
            if (r.get("gt_type") == "inchikey" and r.get("s7_class") == "organic"
                    and r.get("s0_validated") and r.get("s7_attempted")
                    and not r.get("s7_validated@1")):
                out.append((r["entry_id"], r["gt_value"]))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=DATA)
    ap.add_argument("--pattern", default="results.json")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--budget", type=int, default=50)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=OUT_PREFIX)
    args = ap.parse_args(argv)

    cands = load_candidates()
    if args.limit:
        cands = cands[: args.limit]
    by_entry = collections.defaultdict(list)
    for eid, gtv in cands:
        by_entry[eid].append(gtv)
    print(f"candidates: {len(cands)} over {len(by_entry)} entries", file=sys.stderr)

    vsim = load_vsim()
    engine = vsim.SimEngine(budget=args.budget)
    print(f"sim cache: {len(engine.pairs)} pairs", file=sys.stderr)

    rows = []
    lock = threading.Lock()
    t0 = time.time()

    def _sim(t, v, ht, hid):
        with lock:
            return engine.sim(t, v, ht, hid)

    def _work(eid, gts):
        with open(os.path.join(args.root, str(eid), args.pattern)) as fh:
            doc = json.load(fh)
        eng = type("E", (), {"sim": staticmethod(_sim)})
        return [dict(entry_id=eid, **analyze_entry(doc, g, eng)) for g in gts]

    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        futs = {ex.submit(_work, e, g): e for e, g in by_entry.items()}
        for i, fut in enumerate(as_completed(futs), 1):
            rows.extend(fut.result())
            if i % 200 == 0:
                print(f"  ...{i}/{len(by_entry)} ({time.time()-t0:.0f}s)", file=sys.stderr)

    rows.sort(key=lambda r: (r["entry_id"], r["gt_value"]))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out + ".jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r, sort_keys=True) + "\n")

    cls = collections.Counter(r["cls"] for r in rows)
    deltas = collections.defaultdict(list)
    for r in rows:
        d = r.get("conf_delta_rank1_minus_true")
        if isinstance(d, (int, float)):
            deltas[r["cls"]].append(d)
    conf = {c: {"n": len(v), "median": sorted(v)[len(v) // 2] if v else None,
                "min": min(v) if v else None, "max": max(v) if v else None}
            for c, v in sorted(deltas.items())}
    examples = {}
    for c in ("rerank_2_5", "rerank_6_10", "window_11_50", "family_mismatch",
              "not_recovered"):
        examples[c] = [r for r in rows if r["cls"] == c][:3]
    summ = {"candidates": len(rows), "class_counts": dict(cls.most_common()),
            "conf_delta_rank1_minus_true": conf,
            "examples": {c: [{"entry_id": e["entry_id"], "gt": e["gt_value"],
                              "rank_true": e["rank_true_family"],
                              "rank1": e["rank1_ident"],
                              "rank1_conf": e["rank1_conf"],
                              "true": e["true_ident"],
                              "true_conf": e["true_conf"]}
                             for e in exs]
                         for c, exs in examples.items()},
            "seconds": round(time.time() - t0, 1)}
    with open(args.out + ".summary.json", "w") as fh:
        json.dump(summ, fh, indent=1, sort_keys=True)
    print(json.dumps(summ["class_counts"], indent=1), file=sys.stderr)
    print(json.dumps(conf, indent=1))


if __name__ == "__main__":
    main()
