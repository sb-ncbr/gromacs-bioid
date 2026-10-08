#!/usr/bin/env python3
"""sigstage_audit -- why is S0 (signature-stage vs GT) sometimes WORSE than S7
(verified-hits vs GT)? Per-annotation joined re-scoring + decomposition.

For every GT annotation of every load-ok entry, regenerates the OFFICIAL
S7-style outcome with verbatim campaign machinery (importlib-loaded from
NFS campaign_stats.py: verified_hits + _fid_key ordering, GT_FAMILIES family
windows depth 50 / fallback 25, thresholds chem 0.7 / seq&pdb 0.9, ion
element channel) and joins it against the sigstage S0 row
(/data/validation/sigstage/shards/shard_*.jsonl). S5 exact-match membership
@1/5/10 is computed in the same pass for completeness.

Hypotheses under test (audit questions):
  Q1 selection    -- S7 denominators exclude zero-verified-hit entries; S0
                     includes them. Share of the gap explained by re-scoring
                     S0 on S7's exact denominator subset.
  Q2 oracle        -- S7 compares GT vs reference-DB molecule (identity ~1.0
                     by construction); S0 vs simulation construct. Count
                     annotations S0-fail & S7@1-pass = DB-recovery cases.
  Q3 pipeline loss -- annotations S0-pass & S7@K-fail = verification loss.
  Q4 ion gap       -- S0 ion 2726 vs S7 ion 1876: class/denominator causes.

Outputs (scratch): /data/validation/sigstage/audit/shards/shard_XXX.jsonl
and, via main-merge, /data/validation/sigstage/audit_v1.json.
Read-only on results; writes ONLY under audit out dir (replay protocol).
"""
import argparse
import collections
import hashlib
import importlib.util
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA = os.environ.get("VALIDATION_DATA_ROOT", "/data/validation")
SIG_DIR = os.path.join(DATA, "sigstage")
AUDIT_DIR = os.path.join(DATA, "sigstage", "audit")
KSET = (1, 5, 10)
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SIM_CACHE = os.environ.get("SIM_CACHE_ROOT", os.path.join(DATA, "sim_cache"))


# ---------------------------------------------------------------- loaders

def _load_module_from(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_CAMPAIGN = None


def load_campaign():
    """NFS campaign_stats first (official machinery), repo copy fallback."""
    global _CAMPAIGN
    if _CAMPAIGN is not None:
        return _CAMPAIGN
    for path in (os.path.join(DATA, "campaign_stats.py"),
                 os.path.join(_REPO_ROOT, "scripts", "campaign_stats.py")):
        if os.path.isfile(path):
            try:
                _CAMPAIGN = _load_module_from(path, "audit_campaign")
                return _CAMPAIGN
            except Exception:
                continue
    raise RuntimeError("campaign_stats.py not importable")


_GT_RULES = None


def load_gt_rules():
    global _GT_RULES
    if _GT_RULES is not None:
        return _GT_RULES
    for path in (os.path.join(DATA, "gt_rules.py"),
                 os.path.join(_REPO_ROOT, "scripts", "gt_rules.py")):
        if os.path.isfile(path):
            try:
                _GT_RULES = _load_module_from(path, "audit_gt_rules")
                return _GT_RULES
            except Exception:
                continue
    raise RuntimeError("gt_rules.py not importable")


_SIM_ENGINE = None
_SIM_LOCK = None


def get_sim_engine(budget):
    """Main-thread-constructed shared SimEngine (pair cache warm from S7).

    Pair reads/writes are guarded by a lock; alignment only for cache MISSES
    is rare here (hit identifiers repeat S7-covered pairs).
    """
    global _SIM_ENGINE, _SIM_LOCK
    import threading
    if _SIM_ENGINE is None:
        _SIM_LOCK = threading.Lock()
        vsim = None
        for path in (os.path.join(DATA, "validation_similarity.py"),
                     os.path.join(_REPO_ROOT, "scripts", "validation_similarity.py")):
            if os.path.isfile(path):
                try:
                    vsim = _load_module_from(path, "audit_vsim")
                    break
                except Exception:
                    continue
        if vsim is None:
            raise RuntimeError("validation_similarity.py not importable")
        _SIM_ENGINE = vsim.SimEngine(budget=budget)
    return _SIM_ENGINE


def sim_call(engine, gt_type, gt_value, hit_type, hit_id):
    """Thread-safe SimEngine.sim wrapper (engine internals are not)."""
    global _SIM_LOCK
    import threading
    if _SIM_LOCK is None:
        _SIM_LOCK = threading.Lock()
    with _SIM_LOCK:
        return engine.sim(gt_type, gt_value, hit_type, hit_id)


def prewarm():
    load_campaign()
    load_gt_rules()


# ---------------------------------------------------------------- S5/S7 rows

def norm_value(gt_type, value):
    v = (value or "").strip().upper()
    return v[:4] if gt_type == "pdb" else v


def s7_row_for_annotation(campaign, engine, gt_type, gt_value, hits5, ion_elements):
    """Official S7 semantics for one annotation.

    hits5 = campaign.verified_hits(doc) tuples (>=5 fields). Mirrors
    campaign_stats S7v2 logic: ion channel for ion-class inchikeys;
    family window (depth 50) else fallback (depth 25); best sim per K.
    """
    gt_type = gt_type.strip().lower()
    gr = load_gt_rules()
    row = {"s7_attempted": False, "s7_class": None}
    sims = {}

    if gt_type == "inchikey":
        cls = gr.gt_class_for(gt_value)
        row["s7_class"] = cls
        if cls == "ion":
            el = gr.ion_element(gt_value)
            present = bool(el and el in (ion_elements or set()))
            row["s7_attempted"] = bool(ion_elements)
            for k in KSET:
                sims[k] = 1.0 if present else 0.0
            row.update({f"s7_sim@{k}": sims[k] for k in KSET})
            return row

    fam = campaign.GT_FAMILIES.get(gt_type)
    if fam:
        fhits = [h for h in hits5
                 if any(f in (h[0] or "").upper() for f in fam)][:campaign.FAMILY_DEPTH]
    else:
        fhits = hits5[:campaign.FAMILY_DEPTH]
    row["s7_attempted"] = bool(fhits)
    if not fhits:
        fhits = hits5[:campaign.FALLBACK_DEPTH]
    for idx, h in enumerate(fhits, 1):
        s = sim_call(engine, gt_type, gt_value, h[0], h[1])
        for k in KSET:
            if idx <= k:
                sims[k] = max(sims.get(k, 0.0), s)
    row.update({f"s7_sim@{k}": sims.get(k, 0.0) for k in KSET})
    return row


def s5_row_for_annotation(campaign, gt_type, gt_value, hits5):
    """Exact identifier membership @1/5/10 (campaign norm_ident)."""
    gt_type = gt_type.strip().lower()
    v = norm_value(gt_type, gt_value)
    ranked = [campaign.norm_ident(h[0], h[1]) for h in hits5]
    ranked = [x for x in ranked if x]
    out = {}
    for k in KSET:
        topk = set(ranked[:k])
        out[f"s5_hit@{k}"] = 1 if v in topk else 0
    return out


# ---------------------------------------------------------------- entry scan

def audit_entry(eid, doc, annotations, s0_rows_by_key, engine, budget):
    """Returns joined rows for one entry."""
    campaign = load_campaign()
    hits = campaign.verified_hits(doc)
    need_ions = any(t.lower() == "inchikey" for t, _ in annotations)
    ion_elements = campaign._ion_elements_of(doc) if need_ions else set()
    out = []
    for gt_type, gt_value in sorted((t.lower(), v) for t, v in annotations):
        key = (eid, gt_type, norm_value(gt_type, gt_value))
        s0 = s0_rows_by_key.get(key, {})
        row = {"entry_id": eid, "gt_type": gt_type,
               "gt_value": norm_value(gt_type, gt_value),
               "s0_validated": s0.get("validated"),
               "s0_bucket": s0.get("bucket"),
               "s0_sim": s0.get("sim"),
               "s0_best_segment": s0.get("best_segment"),
               "s0_smiles_source": s0.get("smiles_source"),
               "n_hits": len(hits)}
        row.update(s7_row_for_annotation(campaign, engine, gt_type, gt_value,
                                         hits, ion_elements))
        row.update(s5_row_for_annotation(campaign, gt_type, gt_value, hits))
        thr = campaign.validated_threshold("inchikey" if gt_type == "inchikey" else gt_type)
        for k in KSET:
            row[f"s7_validated@{k}"] = row[f"s7_sim@{k}"] >= thr
        out.append(row)
    return out


# ---------------------------------------------------------------- analysis

def crosstab(rows, k):
    """2x2: s0_validated x s7_validated@k over rows with s7_attempted True."""
    tab = collections.Counter()
    for r in rows:
        if not r.get("s7_attempted"):
            continue
        tab[(bool(r["s0_validated"]), bool(r[f"s7_validated@{k}"]))] += 1
    return {(f"s0_{int(a)}_s7_{int(b)}"): n for (a, b), n in sorted(tab.items())}


def sim_hist(rows, field, bins=(0.0, 0.3, 0.6, 0.8, 0.9, 0.95, 0.999, 1.001)):
    labels = ["0-.3", ".3-.6", ".6-.8", ".8-.9", ".9-.95", ".95-1", "1.0"]
    hist = collections.Counter()
    for r in rows:
        v = r.get(field)
        if v is None:
            continue
        for i, (lo, hi) in enumerate(zip(bins, bins[1:])):
            if lo <= v < hi:
                hist[labels[i]] += 1
                break
    return dict(hist)


def summarize(rows):
    """Full audit summary for a merged row set."""
    out = {"rows": len(rows)}
    per_type = collections.defaultdict(list)
    for r in rows:
        t = "ion" if (r["gt_type"] == "inchikey" and r.get("s7_class") == "ion") \
            else r["gt_type"]
        per_type[t].append(r)
    out["types"] = {}
    for t, rs in sorted(per_type.items()):
        n = len(rs)
        s0v = sum(1 for r in rs if r["s0_validated"])
        att = [r for r in rs if r.get("s7_attempted")]
        s0v_in_s7 = sum(1 for r in att if r["s0_validated"])
        zero_hit = [r for r in rs if r["n_hits"] == 0]
        s0v_zero_hit = sum(1 for r in zero_hit if r["s0_validated"])
        blk = {
            "annotations": n,
            "s0_validated": s0v,
            "s0_pct": round(100.0 * s0v / n, 1) if n else None,
            "s7_attempted": len(att),
            "s0_validated_pct_on_s7_subset": (
                round(100.0 * s0v_in_s7 / len(att), 1) if att else None),
            "s7_validated@1_pct": (
                round(100.0 * sum(1 for r in att if r["s7_validated@1"]) / len(att), 1)
                if att else None),
            "s7_validated@10_pct": (
                round(100.0 * sum(1 for r in att if r["s7_validated@10"]) / len(att), 1)
                if att else None),
            "zero_hit_entries_annotations": len(zero_hit),
            "s0_validated_pct_on_zero_hit": (
                round(100.0 * s0v_zero_hit / len(zero_hit), 1) if zero_hit else None),
            "crosstab@1": crosstab(rs, 1),
            "crosstab@10": crosstab(rs, 10),
            "s0_below_gate_sim_hist": sim_hist(
                [r for r in rs if r["s0_bucket"] == "below_gate"], "s0_sim"),
        }
        out["types"][t] = blk
    return out


# ---------------------------------------------------------------- main

def load_s0_rows(shards_dir=None):
    """S0 rows keyed by (entry_id, gt_type, gt_value). shards_dir defaults to
    the v1 shard location; A7 v2 passes run_v2 shards explicitly (2026-10-08:
    the hardcoded path silently mixed era-v1 rows into a v2 audit)."""
    shards_dir = shards_dir or os.path.join(SIG_DIR, "shards")
    by_key = {}
    shards = sorted(f for f in os.listdir(shards_dir)
                    if f.startswith("shard_") and f.endswith(".jsonl"))
    for f in shards:
        with open(os.path.join(shards_dir, f)) as fh:
            for ln in fh:
                r = json.loads(ln)
                by_key[(r["entry_id"], r["gt_type"], r["gt_value"])] = r
    return by_key


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=DATA)
    ap.add_argument("--pattern", default="results.json")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--budget", type=int, default=50)
    ap.add_argument("--out-dir", default=AUDIT_DIR)
    ap.add_argument("--s0-shards", default=None,
                    help="explicit S0 shards dir (v2: sigstage/run_v2/shards)")
    ap.add_argument("--summarize-tag", default="",
                    help="merge out-dir/shards and write audit_{tag}.json, then exit")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args(argv)

    if args.summarize_tag:
        rows = []
        shards_dir = os.path.join(args.out_dir, "shards")
        for f in sorted(os.listdir(shards_dir)):
            if f.startswith("shard_") and f.endswith(".jsonl"):
                with open(os.path.join(shards_dir, f)) as fh:
                    rows.extend(json.loads(ln) for ln in fh if ln.strip())
        summ = summarize(rows)
        out_path = os.path.join(args.out_dir, f"audit_{args.summarize_tag}.json")
        with open(out_path, "w") as fh:
            json.dump(summ, fh, indent=1, sort_keys=True)
        print(json.dumps({"out": out_path, "rows": summ["rows"]}, indent=1))
        return

    prewarm()
    campaign = load_campaign()
    import psycopg2
    con = psycopg2.connect(os.environ.get(
        "DATABASE_URL",
        "postgresql://validation:validation-password-change-me@validation-postgres:5432/bat3_validation"))
    cur = con.cursor()
    cur.execute("SELECT entry_id, signature_type, signature_value "
                "FROM ground_truth_signatures")
    gt = collections.defaultdict(set)
    for eid, t, v in cur.fetchall():
        if v and t:
            gt[eid].add((t.strip().lower(), v.strip()))
    con.close()
    print(f"GT entries: {len(gt)}", file=sys.stderr)

    s0_by_key = load_s0_rows(args.s0_shards)
    print(f"S0 rows loaded: {len(s0_by_key)}", file=sys.stderr)

    engine = get_sim_engine(args.budget)
    print(f"sim engine pairs cached: {len(engine.pairs)}", file=sys.stderr)

    ids = sorted(gt.keys())
    ids = [e for e in ids
           if os.path.isfile(os.path.join(args.root, str(e), args.pattern))]
    try:
        shard_i, shard_n = (int(x) for x in args.shard.split("/"))
    except Exception:
        ap.error("--shard must be i/n")
    if shard_n > 1:
        ids = [e for j, e in enumerate(ids) if j % shard_n == shard_i]
    if args.limit:
        ids = ids[: args.limit]
    print(f"audit entries: {len(ids)} (shard {args.shard})", file=sys.stderr)

    out_rows = []
    import time
    t0 = time.time()

    def _work(eid):
        with open(os.path.join(args.root, str(eid), args.pattern)) as fh:
            doc = json.load(fh)
        if not ((doc.get("tasks") or {}).get("load_simulation") or {}).get("status") == "success":
            return []
        return audit_entry(eid, doc, gt.get(eid) or (), s0_by_key, engine,
                           args.budget)

    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        futs = {ex.submit(_work, e): e for e in ids}
        for i, fut in enumerate(as_completed(futs), 1):
            out_rows.extend(fut.result())
            if i % 1000 == 0:
                print(f"  ...{i}/{len(ids)} ({time.time()-t0:.0f}s)", file=sys.stderr)

    out_rows.sort(key=lambda r: (r["entry_id"], r["gt_type"], r["gt_value"]))
    os.makedirs(os.path.join(args.out_dir, "shards"), exist_ok=True)
    shard_path = os.path.join(args.out_dir, "shards", f"shard_{shard_i:03d}.jsonl")
    payload = "".join(json.dumps(r, sort_keys=True) + "\n" for r in out_rows)
    with open(shard_path, "w") as fh:
        fh.write(payload)
    sha = hashlib.sha1(payload.encode()).hexdigest()[:12]
    print(f"rows={len(out_rows)} shard={shard_path} sha1={sha} "
          f"seconds={round(time.time()-t0, 1)}", file=sys.stderr)

    if shard_n == 1:
        summ = summarize(out_rows)
        with open(os.path.join(args.out_dir, "audit_v1.json"), "w") as fh:
            json.dump(summ, fh, indent=1, sort_keys=True)
        print(json.dumps(summ["types"], indent=1, sort_keys=True))


if __name__ == "__main__":
    main()
