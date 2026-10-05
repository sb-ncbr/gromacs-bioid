#!/usr/bin/env python3
"""Rerank audit (read-only): per inchikey-GT entry, rank chemical candidates by
the pipeline-final confidence vs a skeleton-first rule, and measure where the
GT-covering candidate (skel-sim vs GT >= 0.7) would land.

Uses only persisted results.json + sim_cache structures (cached GT + candidates).
No live fetches - candidates whose structure is not cached count as unknown."""
import json, os, sys, hashlib, time, traceback
from collections import Counter, defaultdict
sys.path.insert(0, "/data/validation/patched_src")
from src_new.signatures.skeletize import from_smiles, skeleton_fp, tanimoto

VAL = "/data/validation"; SIM = os.path.join(VAL, "sim_cache")
CHEM = ("PUBCHEM_CID","PUBCHEM_ID","PUBCHEM","INCHIKEY","INCHI_KEY","CHEMBL_ID","CHEBI_ID","SMILES","SELFIES")
CIDC = ("PUBCHEM_CID","PUBCHEM_ID","PUBCHEM")

def cache_get(sub, key):
    p = os.path.join(SIM, sub, hashlib.sha1(key.encode()).hexdigest()[:24] + ".json")
    try:
        with open(p) as fh: return json.load(fh)
    except Exception: return None

def cand_smiles(it, ident):
    u = (it or "").upper()
    if u in CIDC and str(ident).isdigit(): return cache_get("pubchem_smiles", f"cid:{ident}")
    if u == "CHEMBL_ID":
        c = str(ident).upper(); c = c[6:] if c.startswith("CHEMBL") else c
        return cache_get("pubchem_smiles", f"chemb:CHEMBL{c}")
    if u == "CHEBI_ID":
        c = str(ident).upper(); c = c[6:] if c.startswith("CHEBI:") else c
        return cache_get("pubchem_smiles", f"chebi:{c}")
    if u in ("INCHIKEY","INCHI_KEY"):
        return cache_get("inchikey_smiles", str(ident))
    return None

memo = {}
def fp_of(smi):
    if not smi: return None
    if smi in memo: return memo[smi]
    try:
        m = from_smiles(smi); fp = skeleton_fp(m) if m is not None else None
    except Exception: fp = None
    memo[smi] = fp; return fp

def main():
    t0 = time.time()
    gt = defaultdict(set)
    for line in open(f"{VAL}/inchikey_gt.csv"):
        eid, k = line.strip().split(",", 1); gt[int(eid)].add(k)
    sample = [int(l) for l in open(f"{VAL}/funnel_sample_ids.txt") if l.strip()]
    out = open(f"{VAL}/rank_audit.jsonl", "w")
    bins = {"baseline": Counter(), "skelfirst": Counter(), "oracle": Counter()}
    agg = Counter(); hist_base = Counter()
    for i, eid in enumerate(sample):
        rec = {"entry": eid}
        try:
            r = json.load(open(f"{VAL}/{eid}/results.json"))
        except Exception as ex:
            rec["error"] = str(ex)[:60]; out.write(json.dumps(rec)+"\n"); continue
        d = r.get("data") or {}
        gfps = []; gres = 0
        for k in gt.get(eid, ()):
            smi = cache_get("inchikey_smiles", k)
            if smi:
                gres += 1
                fp = fp_of(smi)
                if fp is not None: gfps.append(fp)
        hits = {}
        for seg, vblk in (d.get("verification") or {}).items():
            for h in ((vblk or {}).get("verified_hits") or []):
                it = (h.get("ident_type") or "").upper()
                if it not in CHEM: continue
                ident = str(h.get("identifier"))
                key = (it, ident)
                prev = hits.get(key)
                rec_h = {"ident_type": it, "identifier": ident,
                         "conf": float(h.get("final_confidence") or 0.0),
                         "verified": bool(h.get("is_verified")),
                         "skeleton_sim": h.get("skeleton_sim"),
                         "resolver_score": float(h.get("resolver_score") or 0.0)}
                if prev is None or rec_h["conf"] > prev["conf"]:
                    hits[key] = rec_h
        if not gfps or not hits:
            rec.update({"gt_resolved": gres, "pool_n": len(hits), "skip": "no_gt_or_no_pool"})
            out.write(json.dumps(rec)+"\n"); agg["skip"] += 1; continue
        pool = []; cache_miss = 0
        for (it, ident), h in hits.items():
            smi = cand_smiles(it, ident)
            fp = fp_of(smi) if smi else None
            if fp is None: cache_miss += 1
            gsim = 0.0
            for g in gfps:
                if fp is not None:
                    gsim = max(gsim, tanimoto(fp, g))
            pool.append({**h, "gsim": round(gsim, 3)})
        has_cov = any(p["gsim"] >= 0.7 for p in pool)
        rec.update({"gt_resolved": gres, "pool_n": len(pool), "cache_miss": cache_miss,
                    "has_covering": has_cov})
        if not has_cov:
            out.write(json.dumps(rec)+"\n"); agg["no_covering"] += 1; continue
        agg["with_covering"] += 1
        base = sorted(pool, key=lambda p: (-p["conf"], -p["resolver_score"]))
        sk = sorted(pool, key=lambda p: (-p["gsim"], -p["conf"]))
        ora = sorted(pool, key=lambda p: -p["gsim"])
        def rank_of(order):
            for i2, p in enumerate(order):
                if p["gsim"] >= 0.7: return i2 + 1
            return None
        rb, rs, ro = rank_of(base), rank_of(sk), rank_of(ora)
        rec.update({"rank_base": rb, "rank_skelfirst": rs, "rank_oracle": ro,
                    "top_base": [{kk: p[kk] for kk in ("ident_type","identifier","conf","gsim","verified")} for p in base[:5]],
                    "top_skelfirst": [{kk: p[kk] for kk in ("ident_type","identifier","conf","gsim","verified")} for p in sk[:5]]})
        hist_base[rb if rb is not None else ">10"] += 1
        for name, rr in (("baseline", rb), ("skelfirst", rs), ("oracle", ro)):
            if rr == 1: bins[name]["@1"] += 1
            if rr is not None and rr <= 5: bins[name]["@5"] += 1
            if rr is not None and rr <= 10: bins[name]["@10"] += 1
        out.write(json.dumps(rec) + "\n"); out.flush()
        if (i + 1) % 50 == 0: print(f"[ra] {i+1}/{len(sample)} {int(time.time()-t0)}s", flush=True)
    out.close()
    print("=== RANK AUDIT SUMMARY ===", flush=True)
    print(json.dumps({"sample": len(sample), "agg": dict(agg), "hit": {k: dict(v) for k, v in bins.items()}, "rank_hist_base": dict(hist_base), "elapsed_s": int(time.time()-t0)}, indent=1), flush=True)

if __name__ == "__main__":
    try: main()
    except Exception:
        traceback.print_exc(); sys.exit(1)
