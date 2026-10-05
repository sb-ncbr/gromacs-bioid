#!/usr/bin/env python3
"""Task B — coverability probe for the v8-failing organic annotations (read-only).

Phase 0: regenerate the AUTHORITATIVE v8-failing set. The on-disk
         residual_failing_rows.jsonl (649 rows) is the pre-v8 projection set;
         official v8 semantics differ by the identifier tie-break (flip
         dissection: 170 flips to pass; ~65 reverse-flips to fail outside the
         649). We re-evaluate ALL organic annotations with the official metric
         verbatim: verified_hits/_fid_key imported from the patched
         /data/validation/campaign_stats.py, family window 50, fallback 25,
         0.7 validated gate, KSET=(1,5,10).

Classification (2026-10-01 v2): gt_class_for resolves inchikey->SMILES via a
         WEB chain (cactus->pug->idsm, only POSITIVE results cached on NFS) —
         nondeterministic across pods/runs (my first run scored annotations=
         5785 vs published 5784: one key flipped ion<->organic on network
         weather). Frame-exact scheme used here:
           * key has an NFS web-cache entry -> adopt the cache-warm
             gt_class_for verdict (the SAME verdict the v8 run saw; no fetch);
           * otherwise -> deterministic MIRROR-FIRST offline classification
             (PubChemDB.by_inchikey -> skeletize.from_smiles -> the same ion
             rule as gt_class_for: heavy-atom <=2 AND all ionic), with the
             same _FALLBACK_ION_KEY table.
         Cache files newer than v8's generated_at are flagged
         "post_v8_cache: v8 verdict unknowable" and drive gate forensics.
         Every mirror-vs-web disagreement is persisted verbatim (both SMILES)
         to coverability_class_drift.json before any expensive work.

HARD GATE against published v8 anchors (annotations/attempted/pct@k) —
         STRICT ONLY: any mismatch aborts before probe outputs, with drift
         evidence on disk for a user ruling.

Phase 1: probe each unique failing inchikey against the local PubChem mirror
         via PubChemDB (by_inchikey / by_inchikey_block + variant counts).
Phase 2: bucket every failing row (GT_NOT_IN_MIRROR / FIRST_BLOCK_ONLY /
         IN_MIRROR__SURFACED_BUT_LOST / IN_MIRROR__NOT_PROPOSED).
Phase 3: aggregates + honest reporting frame (raw AND coverable-normalized
         always together).

Writes ONLY new probe artifacts under /data/validation; campaign data untouched.
"""
import collections
import hashlib
import importlib.util
import json
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

DATA = "/data/validation"
sys.path.insert(0, DATA)
sys.path.insert(0, "/app")

import psycopg2  # noqa: E402

DB = os.environ.get(
    "DATABASE_URL",
    "postgresql://validation:validation-password-change-me@validation-postgres:5432/bat3_validation",
)
MIRROR = "/app/databases/pubchem/current/pubchem.sqlite"
SIM_CACHE = os.environ.get("SIM_CACHE_ROOT", f"{DATA}/sim_cache")
KSET = (1, 5, 10)
GATE = 0.7
FAM = ("PUBCHEM", "INCHI")
FAMILY_DEPTH = 50
FALLBACK_DEPTH = 25

ANCHOR_JSON = os.environ.get("PROBE_ANCHOR_JSON", f"{DATA}/campaign_stats_v8.json")
OUT_CLASSES = f"{DATA}/coverability_classes.json"
OUT_DRIFT = f"{DATA}/coverability_class_drift.json"
OUT_ROWS_V8 = f"{DATA}/residual_failing_rows_v8.jsonl"
OUT_CACHE = f"{DATA}/coverability_ik_cache.json"
OUT_ROWS = f"{DATA}/coverability_rows.jsonl"
OUT_AGG = f"{DATA}/coverability_probe.json"

spec = importlib.util.spec_from_file_location("cs", f"{DATA}/campaign_stats.py")
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)

from gt_rules import _FALLBACK_ION_KEY, _METALS, gt_class_for  # noqa: E402
from validation_similarity import SimEngine  # noqa: E402

_IONIC_ATOMS = _METALS | {"Cl", "F", "I", "S", "N", "O", "B", "C"}


# ------------------------------------------------------ classification

def class_map_mirror(iks, t0):
    """Deterministic offline gt class for each inchikey (mirror-first)."""
    from src_new.molecules.pubchem_db import PubChemDB
    from src_new.signatures.skeletize import from_smiles
    db = PubChemDB(MIRROR)
    out = {}
    for i, ik in enumerate(iks, 1):
        row = db.by_inchikey(ik)
        m = None
        if row and row.smiles:
            try:
                m = from_smiles(row.smiles)
            except Exception:
                m = None
        if m is None:
            out[ik] = "ion" if ik.split("-")[0] in _FALLBACK_ION_KEY else "unresolved"
        else:
            heavy = [a.GetSymbol() for a in m.GetAtoms() if a.GetSymbol() != "H"]
            out[ik] = ("ion" if len(heavy) <= 2 and all(s in _IONIC_ATOMS for s in heavy)
                       else "organic")
        if i % 3000 == 0:
            print(f"[cls] {i}/{len(iks)} ({time.time()-t0:.0f}s)",
                  file=sys.stderr, flush=True)
    db.close()
    return out


def _web_cache_path(ik):
    h = hashlib.sha1(ik.encode()).hexdigest()[:24] + ".json"
    return os.path.join(SIM_CACHE, "inchikey_smiles", h)


def effective_classes(iks, cls_mirror, v8_ts, t0):
    """Frame-exact classes: cache-warm gt_class_for verdict where an NFS
    web-cache entry exists (the same verdict v8 saw); mirror-first elsewhere.
    Returns (final_map, drift_list, n_uncached)."""
    final = {}
    drift = []
    checked = 0
    for ik in iks:
        p = _web_cache_path(ik)
        if not os.path.isfile(p):
            final[ik] = cls_mirror[ik]
            continue
        checked += 1
        try:
            web_cls = gt_class_for(ik)  # cache-warm: no fetch
        except Exception:
            web_cls = cls_mirror[ik]
        final[ik] = web_cls
        if web_cls != cls_mirror[ik]:
            ev = {"ik": ik, "mirror_cls": cls_mirror[ik], "web_cls": web_cls,
                  "cache_mtime": os.path.getmtime(p),
                  "post_v8_cache": os.path.getmtime(p) > v8_ts}
            try:
                with open(p) as fh:
                    ev["cached_web_smiles"] = json.load(fh)
            except Exception:
                pass
            drift.append(ev)
    print(f"[cls] v8-frame: {checked} cache-warm keys, "
          f"{len(iks)-checked} uncached (mirror-first), {len(drift)} "
          f"mirror-vs-web disagreements ({time.time()-t0:.0f}s)",
          file=sys.stderr, flush=True)
    return final, drift, len(iks) - checked


# ------------------------------------------------------------- phase 0

def parse_entry(eid, iks):
    path = f"{DATA}/{eid}/results.json"
    try:
        with open(path) as fh:
            raw = fh.read()
        doc = json.loads(raw)
    except Exception:
        return eid, None
    tasks = doc.get("tasks") or {}
    if not ((tasks.get("load_simulation") or {}).get("status") == "success"
            and (tasks.get("verify_results") or {}).get("status") == "success"):
        return eid, None
    hits = cs.verified_hits(doc)  # official ordering (patched _fid_key)
    tc = ((doc.get("data") or {}).get("fragments") or {}).get("type_counts") or {}
    vpos = raw.find('"verification"')
    ver_raw = raw[vpos:vpos + 3000000] if vpos >= 0 else ""
    presence = {}
    for ik in iks:
        block = ik.split("-")[0]
        presence[ik] = (ik in raw, block in raw, block in ver_raw)
    return eid, {"hits": hits, "tc": tc, "presence": presence}


def eval_annotation(hits, ik, eng):
    fhits = [h for h in hits if any(f in (h[0] or "").upper() for f in FAM)][:FAMILY_DEPTH]
    attempted = bool(fhits)
    if not attempted:
        fhits = hits[:FALLBACK_DEPTH]
    rec = {}
    sims = []
    for idx, (ht, hid, _conf, *_g) in enumerate(fhits, 1):
        s = eng.sim("inchikey", ik, ht, hid)
        s = s if s is not None else 0.0
        sims.append(s)
        for k in KSET:
            if idx <= k:
                rec[k] = max(rec.get(k, 0.0), s)
    return attempted, {k: rec.get(k, 0.0) for k in KSET}, sims


def band(s):
    return ("<0.3" if s < 0.3 else "0.3-0.5" if s < 0.5
            else "0.5-0.7" if s < 0.7 else ">=0.7")


def rband(r):
    return ("11-15" if r and r <= 15 else "16-20" if r and r <= 20
            else "21-30" if r and r <= 30 else "31-50")


def phase0(t0):
    print(f"[p0] loading GT + anchors ({ANCHOR_JSON})...", file=sys.stderr,
          flush=True)
    anchor = json.load(open(ANCHOR_JSON))["full"]["S7_similarity_hit_at_k"]
    v8_ts = datetime.fromisoformat(
        json.load(open(ANCHOR_JSON))["generated_at"]
        .replace("Z", "+00:00")).timestamp()
    con = psycopg2.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT entry_id, signature_value FROM ground_truth_signatures "
                "WHERE signature_type='inchikey'")
    gt = collections.defaultdict(list)
    for eid, v in cur.fetchall():
        if v and v.strip():
            gt[eid].append(v.strip())
    con.close()
    uniq = sorted({v.strip().upper() for vs in gt.values()
                   for v in vs if v and v.strip()})

    cls_mirror = class_map_mirror(uniq, t0)
    cls_map, drift, n_uncached = effective_classes(uniq, cls_mirror, v8_ts, t0)
    with open(OUT_CLASSES, "w") as fh:
        json.dump({"classifier": "v8-frame: cache-warm gt_class_for where an "
                                 "NFS web-cache entry exists; deterministic "
                                 "mirror-first (PubChemDB + from_smiles) "
                                 "elsewhere. gt_class_for ion rule in both.",
                   "n_keys": len(uniq), "n_uncached_mirror_first": n_uncached,
                   "counts_final": dict(collections.Counter(cls_map.values())),
                   "counts_mirror_first":
                       dict(collections.Counter(cls_mirror.values())),
                   "classes": cls_map, "classes_mirror_first": cls_mirror}, fh)
    with open(OUT_DRIFT, "w") as fh:
        json.dump({"checked_cache_warm": len(uniq) - n_uncached,
                   "n_uncached_no_crosscheck": n_uncached,
                   "v8_generated_ts": v8_ts,
                   "drift": drift}, fh, indent=2)
    print(f"[cls] final={dict(collections.Counter(cls_map.values()))} "
          f"mirror={dict(collections.Counter(cls_mirror.values()))} "
          f"drift={len(drift)} -> {OUT_CLASSES} ({time.time()-t0:.0f}s)",
          file=sys.stderr, flush=True)

    todo = {e: [ik.upper() for ik in iks if cls_map.get(ik.upper()) != "ion"]
            for e, iks in gt.items() if os.path.exists(f"{DATA}/{e}/results.json")}
    todo = {e: iks for e, iks in todo.items() if iks}
    ion_todo = {e: [ik.upper() for ik in iks if cls_map.get(ik.upper()) == "ion"]
                for e, iks in gt.items() if os.path.exists(f"{DATA}/{e}/results.json")}
    print(f"[p0] {len(uniq)} unique GT iks; {len(todo)} organic-GT entries "
          f"to parse ({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)

    res = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {}
        for e, iks in todo.items():
            futs[ex.submit(parse_entry, e, iks)] = e
        for i, fut in enumerate(as_completed(futs), 1):
            eid, r = fut.result()
            if r is not None:
                res[eid] = r
            if i % 3000 == 0:
                print(f"[p0] parsed {i}/{len(futs)} ({time.time()-t0:.0f}s)",
                      file=sys.stderr, flush=True)

    eng = SimEngine(budget=0)
    print(f"[p0] sim engine: {len(eng.pairs)} cached pairs "
          f"({time.time()-t0:.0f}s)", file=sys.stderr, flush=True)

    annotations = attempted_n = ion_annotations = 0
    val = {k: 0 for k in KSET}
    fail_rows = []
    for eid in sorted(res):
        r = res[eid]
        # Official S7 guard: entries with EMPTY verified hits never enter the
        # annotation loop (`if sim_engine is not None and r["hits"]:`).
        # Missing this was the 5785-vs-5784 phantom (one entry, one organic
        # GT, empty hits → +1 annotation, zero validated delta).
        if not r["hits"]:
            continue
        ion_annotations += len(ion_todo.get(eid, []))
        for ik in todo[eid]:
            annotations += 1
            attempted, rec, sims = eval_annotation(r["hits"], ik, eng)
            if attempted:
                attempted_n += 1
            for k in KSET:
                if rec[k] >= GATE - 1e-9:
                    val[k] += 1
            if rec[10] >= GATE - 1e-9:
                continue
            deep_best = max(sims) if sims else 0.0
            rank_db = sims.index(deep_best) + 1 if sims else None
            full_j, blk_j, blk_ver = r["presence"].get(ik, (False, False, False))
            fail_rows.append({
                "eid": eid, "ik": ik,
                "v8_best1": round(rec[1], 3), "v8_best5": round(rec[5], 3),
                "v8_best10": round(rec[10], 3),
                "attempted": attempted,
                "deep_best": round(deep_best, 3), "rank_db": rank_db,
                "band": band(deep_best), "rband": rband(rank_db),
                "gt_full_in_json": full_j,
                "gt_block_in_json": blk_j,
                "block_in_ver_sec": blk_ver,
                "box_has_chem": any(x in r["tc"] for x in ("small_molecule", "lipid")),
                "frag_types": sorted(r["tc"].keys()),
            })

    anch = anchor["inchikey"]
    got = {f"pct_validated@{k}": round(100.0 * val[k] / annotations, 1) for k in KSET}
    strict_ok = (annotations == anch["annotations"]
                 and attempted_n == anch["attempted"]
                 and all(abs(got[f"pct_validated@{k}"] - anch[f"pct_validated@{k}"]) < 0.051
                         for k in KSET))
    print(f"[p0] regen: annotations={annotations} (anchor={anch['annotations']}, "
          f"delta={annotations - anch['annotations']:+d}) "
          f"attempted={attempted_n} "
          f"ion_ann_in_parsed_subset={ion_annotations} (partial: ion-only "
          f"entries are never parsed here; anchor ion total="
          f"{anchor['ion']['annotations']}) "
          f"validated@k={val} got={got}", file=sys.stderr, flush=True)

    if not strict_ok:
        print("[p0] GATE FAILURE — aborting before any probe output. "
              f"Drift evidence: {OUT_DRIFT} (post_v8_cache flags identify "
              "keys whose v8 verdict is unknowable from cache).",
              file=sys.stderr, flush=True)
        sys.exit(2)

    with open(OUT_ROWS_V8, "w") as fh:
        for row in fail_rows:
            fh.write(json.dumps(row) + "\n")
    print(f"[p0] GATE OK. v8-failing organic rows: {len(fail_rows)} -> "
          f"{OUT_ROWS_V8} (new_pairs={eng.new_pairs}, {time.time()-t0:.0f}s)",
          file=sys.stderr, flush=True)
    return fail_rows, anch, val[10], eng.new_pairs, {
        "gate": f"strict vs {ANCHOR_JSON} S7 anchors: OK",
        "annotations": annotations, "attempted": attempted_n,
        "ion_annotations_in_parsed_subset": ion_annotations,
        "classification_counts_final":
            dict(collections.Counter(cls_map.values())),
        "classification_counts_mirror_first":
            dict(collections.Counter(cls_mirror.values())),
        "mirror_vs_web_drift_n": len(drift),
        "drift_file": OUT_DRIFT,
    }


# ------------------------------------------------------------- phase 1

def phase1(fail_rows, t0):
    from src_new.molecules.pubchem_db import PubChemDB
    iks = sorted({r["ik"] for r in fail_rows})
    cache = {}
    if not os.path.isfile(MIRROR):
        for ik in iks:
            cache[ik] = {"error": "mirror_unreachable"}
        print(f"[p1] MIRROR UNREACHABLE at {MIRROR}", file=sys.stderr, flush=True)
    else:
        db = PubChemDB(MIRROR)
        ro = sqlite3.connect(f"file:{MIRROR}?mode=ro&immutable=1", uri=True)
        for i, ik in enumerate(iks, 1):
            full = db.by_inchikey(ik)
            blk = db.by_inchikey_block(ik)
            block = ik.split("-")[0].upper()
            n_keys = n_rows = None
            try:
                n_rows, n_keys = ro.execute(
                    "SELECT COUNT(*), COUNT(DISTINCT inchikey) FROM compounds "
                    "WHERE inchikey >= ? AND inchikey < ?",
                    (block, block + chr(0x7F))).fetchone()
            except Exception:
                pass
            cache[ik] = {
                "full": ({"cid": full.cid, "smiles": full.smiles,
                          "inchikey": full.inchikey} if full else None),
                "block": ({"cid": blk.cid, "inchikey": blk.inchikey}
                          if blk else None),
                "n_rows_in_block": n_rows,
                "n_keys_in_block": n_keys,
            }
            if i % 100 == 0:
                print(f"[p1] probed {i}/{len(iks)} ({time.time()-t0:.0f}s)",
                      file=sys.stderr, flush=True)
        ro.close()
        db.close()
    with open(OUT_CACHE, "w") as fh:
        json.dump({"mirror": MIRROR, "n_unique_iks": len(iks),
                   "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                 time.gmtime()),
                   "cache": cache}, fh)
    print(f"[p1] probed {len(iks)} unique iks ({time.time()-t0:.0f}s)",
          file=sys.stderr, flush=True)
    return cache


# --------------------------------------------------------- phases 2 + 3

def classify(row, cache, gtmap):
    ik = str(row["ik"])
    c = cache[ik]
    ent = gtmap.get(str(row["eid"])) or {}
    in_map = ik in set(ent.get("keys") or [])
    full = c.get("full")
    blk = c.get("block")
    if c.get("error"):
        bucket = "MIRROR_UNKNOWN"
    elif full:
        bucket = ("IN_MIRROR__SURFACED_BUT_LOST" if row["gt_full_in_json"]
                  else "IN_MIRROR__NOT_PROPOSED")
    elif blk:
        bucket = "FIRST_BLOCK_ONLY"
    else:
        bucket = "GT_NOT_IN_MIRROR"
    out = dict(row)
    out.update({
        "full_key_in_mirror": bool(full),
        "first_block_in_mirror": bool(blk),
        "in_gt_compound_map": in_map,
        "mirror_full_cid": (full or {}).get("cid"),
        "mirror_full_cid_in_expected_cids":
            ((full or {}).get("cid") in set(ent.get("cids") or [])
             if full else None),
        "mirror_block_cid": (blk or {}).get("cid"),
        "mirror_block_key": (blk or {}).get("inchikey"),
        "n_rows_in_block": c.get("n_rows_in_block"),
        "n_keys_in_block": c.get("n_keys_in_block"),
        "unattainable_by_content": not row["box_has_chem"],
        "bucket": bucket,
    })
    return out


def phase23(fail_rows, cache, anch, val10, new_pairs, gate_info, t0):
    gtmap = json.load(open(f"{DATA}/gt_compound_map.json"))
    enriched = [classify(r, cache, gtmap) for r in fail_rows]
    with open(OUT_ROWS, "w") as fh:
        for r in enriched:
            fh.write(json.dumps(r) + "\n")

    N = anch["annotations"]
    nm = sum(1 for r in enriched if r["bucket"] == "GT_NOT_IN_MIRROR")
    fb = sum(1 for r in enriched if r["bucket"] == "FIRST_BLOCK_ONLY")
    frame = {
        "organic_annotations_anchor": N,
        "validated@10": val10,
        "failing@10_in_probe_set": len(enriched),
        "raw_pct_validated@10": round(100.0 * val10 / N, 1),
        "excl_not_in_mirror": {
            "denominator": N - nm,
            "pct_validated@10": round(100.0 * val10 / (N - nm), 1) if N - nm else None,
        },
        "excl_not_in_mirror_and_variant_layer": {
            "denominator": N - nm - fb,
            "pct_validated@10": round(100.0 * val10 / (N - nm - fb), 1) if N - nm - fb else None,
        },
        "note": "raw and normalized frames are reported together; the raw "
                "campaign number (90.6 @10) is never replaced. Normalized "
                "frames subtract the probe's own failing buckets from the "
                "denominator.",
    }
    buckets = collections.Counter(r["bucket"] for r in enriched)
    bx_band = collections.Counter(f"{r['bucket']}|{r['band']}" for r in enriched)
    bx_chem = collections.Counter(
        f"{r['bucket']}|{'boxchem' if r['box_has_chem'] else 'nochem'}"
        for r in enriched)
    examples = collections.defaultdict(list)
    for r in enriched:
        if len(examples[r["bucket"]]) < 10:
            examples[r["bucket"]].append(r)
    vl = [r["n_keys_in_block"] for r in enriched
          if r["bucket"] == "FIRST_BLOCK_ONLY" and isinstance(r["n_keys_in_block"], int)]
    agg = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "task": "B — coverability probe of v8-failing organic annotations",
        "gate_info": gate_info,
        "new_sim_pairs_computed": new_pairs,
        "bucket_counts": dict(sorted(buckets.items())),
        "bucket_x_deepband": dict(sorted(bx_band.items())),
        "bucket_x_boxchem": dict(sorted(bx_chem.items())),
        "first_block_only_variant_depth": {
            "min": min(vl) if vl else None,
            "median": (sorted(vl)[len(vl) // 2] if vl else None),
            "max": max(vl) if vl else None,
        },
        "unattainable_by_content_rows":
            sum(1 for r in enriched if r["unattainable_by_content"]),
        "not_proposed_but_box_has_chem":
            sum(1 for r in enriched
                if r["bucket"] == "IN_MIRROR__NOT_PROPOSED" and r["box_has_chem"]),
        "in_gt_compound_map_mismatch":
            sum(1 for r in enriched if not r["in_gt_compound_map"]),
        "reporting_frame": frame,
        "examples": {k: v for k, v in sorted(examples.items())},
        "rows_file": OUT_ROWS, "v8_rows_file": OUT_ROWS_V8,
        "ik_cache_file": OUT_CACHE,
        "classes_file": OUT_CLASSES, "drift_file": OUT_DRIFT,
    }
    with open(OUT_AGG, "w") as fh:
        json.dump(agg, fh, indent=2)
    print(json.dumps({k: v for k, v in agg.items() if k != "examples"},
                     indent=2))
    print(f"[p3] DONE ({time.time()-t0:.0f}s) -> {OUT_AGG}",
          file=sys.stderr, flush=True)


def main():
    t0 = time.time()
    fail_rows, anch, val10, new_pairs, gate_info = phase0(t0)
    cache = phase1(fail_rows, t0)
    phase23(fail_rows, cache, anch, val10, new_pairs, gate_info, t0)


if __name__ == "__main__":
    main()
