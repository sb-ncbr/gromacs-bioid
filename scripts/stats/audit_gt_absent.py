#!/usr/bin/env python3
"""Drill: why do live organic-inch GT annotations land in gt_absent?

For each live entry's organic inchikey GT with best candidate sim < 0.5:
- compare GT skeleton-FP vs every segment's skeleton_fp signature (F7 currency)
- check formula deltas (adduct/salt hints)
- check whether GT is in the mirror at all (coverage)
- check full hit list (beyond top-50 window) for identity
- check whether the matched fragment's formula resolvers were attempted

Output: /data/validation/audit_gt_absent.json + audit_gt_absent_rows.jsonl
"""
import collections
import json
import os
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA = "/data/validation"
sys.path.insert(0, DATA)
sys.path.insert(0, "/app")

import psycopg2  # noqa: E402

DB = os.environ.get(
    "DATABASE_URL",
    "postgresql://validation:validation-password-change-me@validation-postgres:5432/bat3_validation",
)
CHEM = ("PUBCHEM", "INCHI")
FAM_DEPTH = 50
CUT_REQUEUE = 1790208000.0
CUT_SPINFIX = 1790380800.0


def era_of(m):
    return ("2_post_spinfix" if m >= CUT_SPINFIX
            else "1_requeue_wave" if m >= CUT_REQUEUE else "0_legacy")


def parse_entry(eid):
    path = f"{DATA}/{eid}/results.json"
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except Exception:
        return eid, None
    data = doc.get("data") or {}
    tasks = doc.get("tasks") or {}
    ts = {n: ((tasks.get(n) or {}).get("status")) for n in
          ("load_simulation", "verify_results")}
    if ts.get("load_simulation") != "success" or ts.get("verify_results") != "success":
        return eid, None
    ver = data.get("verification") or {}
    hits = []
    for seg, sv in ver.items():
        for h in (sv or {}).get("verified_hits") or []:
            if isinstance(h, dict):
                try:
                    conf = float(h.get("final_confidence") or 0.0)
                except Exception:
                    conf = 0.0
                hits.append({"t": h.get("ident_type"), "v": h.get("identifier"),
                             "conf": conf, "ver": bool(h.get("is_verified")),
                             "rej": h.get("rejection_reason"),
                             "skel": h.get("skeleton_sim"), "seg": seg})
    hits.sort(key=lambda x: -x["conf"])
    sigs = {}
    for seg, payload in (data.get("signatures") or {}).items():
        gen = (payload or {}).get("generated") or {}
        sk = gen.get("skeleton_fp")
        if sk:
            hexpart = str(sk.get("value") if isinstance(sk, dict) else sk)
            hexpart = hexpart.split(":", 2)[-1].split("|")[0] if "skelfp" in hexpart else hexpart
            sigs[seg] = {"skel_hex": hexpart,
                         "formula": (gen.get("molecular_formula") or {}).get("value")
                         if isinstance(gen.get("molecular_formula"), dict)
                         else gen.get("molecular_formula")}
    idents = {}
    for seg, bysig in (data.get("identifiers") or {}).items():
        att = set()
        for st, info in (bysig or {}).items():
            for r in (info or {}).get("attempted") or []:
                att.add(r)
        idents[seg] = sorted(att)
    fr = (data.get("fragments") or {})
    return eid, {"hits": hits, "sigs": sigs, "idents": idents,
                 "frag_type_counts": fr.get("type_counts") or {},
                 "mtime": os.path.getmtime(path)}


def sig_value(v):
    if isinstance(v, dict):
        return v.get("value")
    return v


def b1b_split_report():
    """Standalone: C1/C2 split over saved B1b rows (mirror-side classification).

    Query plan: index-range scans on GT InChIKey blocks (tiny) + point cid
    lookups, avoiding whole-family row scans on cold sqlite pages.
    """
    t0 = time.time()
    rows = [json.loads(l) for l in open(f"{DATA}/audit_gt_absent_rows.jsonl")]
    b = [r for r in rows if r["cls"] == "B1b_candidates_missed_gt"]
    from src_new.molecules.pubchem_db import normalize_formula
    con = sqlite3.connect("file:/app/databases/pubchem/current/pubchem.sqlite?mode=ro",
                          uri=True)

    blocks = sorted({r["ik"].split("-")[0] for r in b})
    # GT block -> list of (cid, formula_hill) in mirror
    gt_forms = {}
    for blk in blocks:
        out = []
        for cid, in con.execute(
                "SELECT cid FROM compounds WHERE inchikey >= ? AND inchikey < ?",
                (blk, blk + chr(0x7F))):
            fh = con.execute("SELECT formula_hill FROM compounds WHERE cid=?",
                             (cid,)).fetchone()
            out.append((cid, fh[0] if fh else None))
        gt_forms[blk] = out
    print(f"gt block lookups done: {len(blocks)} blocks ({time.time()-t0:.0f}s), "
          f"forms found: {sum(1 for v in gt_forms.values() if v)}", flush=True)

    def parse(f):
        d = {}
        for tok in __import__("re").findall(r"([A-Z][a-z]?)(\d*)", f or ""):
            d[tok[0]] = int(tok[1] or 1)
        return d

    split = collections.Counter()
    ranks = []
    for i, r in enumerate(b, 1):
        ff = r.get("frag_formula")
        block = r["ik"].split("-")[0]
        if not ff:
            split["no_frag_formula"] += 1
            continue
        frag_hill = normalize_formula(ff)
        forms = gt_forms.get(block) or []
        gt_formulas = {normalize_formula(fh) for _cid, fh in forms if fh}
        if frag_hill in gt_formulas:
            # C1: fragment's exact-formula family contains GT connectivity;
            # measure rank of the GT cid within cid order of that family
            gtcid = next(c for c, fh in forms
                         if fh and normalize_formula(fh) == frag_hill)
            rank = con.execute(
                "SELECT count(*) FROM compounds WHERE formula_hill=? AND cid<?",
                (frag_hill, gtcid)).fetchone()[0]
            ranks.append(rank)
            split["C1_in_family_" + ("rank<=100" if rank < 100 else "rank>100")] += 1
        else:
            ph, gh = parse(frag_hill), None
            for gf in gt_formulas:
                gh = parse(gf)
                if {k: v for k, v in ph.items() if k != "H"} == \
                   {k: v for k, v in gh.items() if k != "H"}:
                    gh = gh
                    break
                gh = None
            if gh is not None:
                split["C2_protonation_frame"] += 1
            else:
                split["C3_heavy_formula_differs"] += 1
        if i % 50 == 0:
            print(f"  {i}/{len(b)} ({time.time()-t0:.0f}s)", flush=True)
    print("B1b split (n=%d):" % len(b))
    for k, v in split.most_common():
        print(f"  {v:>4}  {k}")
    if ranks:
        ranks.sort()
        print("C1 rank: n=%d median=%d p90=%d max=%d (window=100)"
              % (len(ranks), ranks[len(ranks)//2],
                 ranks[int(len(ranks)*0.9)], ranks[-1]))
        print("  within-100 rescues:", sum(1 for x in ranks if x < 100))
    print("DONE")


def main():
    t0 = time.time()
    con = psycopg2.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT entry_id, signature_value FROM ground_truth_signatures "
                "WHERE signature_type='inchikey'")
    gt = collections.defaultdict(list)
    for eid, v in cur.fetchall():
        if v and v.strip():
            gt[eid].append(v.strip())
    con.close()
    gtmap = json.load(open(f"{DATA}/gt_compound_map.json"))

    from gt_rules import gt_class_for
    from validation_similarity import SimEngine, _inchikey_smiles
    from src_new.signatures.skeletize import (from_smiles, skeleton_fp,
                                              fp_to_hex, tanimoto_hex,
                                              heavy_formula)
    eng = SimEngine(budget=5000)

    # mirror
    mirror_path = "/app/databases/pubchem/current/pubchem.sqlite"
    mcon = sqlite3.connect(mirror_path) if os.path.exists(mirror_path) else None

    def mirror_ik(ik):
        if mcon is None:
            return None, None
        row = mcon.execute(
            "SELECT cid, formula_hill FROM compounds WHERE inchikey=?",
            (ik,)).fetchone()
        if not row:
            row = mcon.execute(
                "SELECT cid, formula_hill FROM compounds WHERE inchikey LIKE ? LIMIT 1",
                (ik.split("-")[0] + "%",)).fetchone()
        return (row[0], row[1]) if row else (None, None)

    entries = [e for e in gt if os.path.exists(f"{DATA}/{e}/results.json")]
    results = {}
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs = {ex.submit(parse_entry, e): e for e in entries}
        for fut in as_completed(futs):
            eid, r = fut.result()
            if r is not None:
                results[eid] = r
    print(f"live entries parsed: {len(results)} ({time.time()-t0:.0f}s)", file=sys.stderr)

    rows = []
    for eid, iks in gt.items():
        r = results.get(eid)
        if r is None:
            continue
        era = era_of(r["mtime"])
        fam_all = [h for h in r["hits"]
                   if any(f in (h["t"] or "").upper() for f in CHEM)]
        fam = fam_all[:FAM_DEPTH]
        for ik in iks:
            if gt_class_for(ik) == "ion":
                continue
            if not fam:
                continue  # no_family handled elsewhere
            sims = [(idx, eng.sim("inchikey", ik, h["t"], h["v"]), h)
                    for idx, h in enumerate(fam, 1)]
            best = max(sims, key=lambda x: x[1])
            at10 = max((s for idx, s, _ in sims if idx <= 10), default=0.0)
            if at10 >= 0.7 or best[1] >= 0.5:
                continue  # not the gt_absent class we drill
            # --- drill this gt_absent annotation ---
            rec = {"eid": eid, "ik": ik[:27], "era": era,
                   "best50_sim": round(best[1], 3), "best50_rank": best[0],
                   "n_fam": len(fam), "n_chem_hits": len(fam_all),
                   "frag_types": r["frag_type_counts"]}
            try:
                smi = _inchikey_smiles(ik)
            except LookupError:
                smi = None
            if not smi:
                rec["cls"] = "A_gt_unresolvable"
                rows.append(rec)
                continue
            gt_mol = from_smiles(smi)
            gt_fp = fp_to_hex(skeleton_fp(gt_mol)) if gt_mol else None
            gt_heavy = heavy_formula(gt_mol) if gt_mol else ""
            rec["gt_heavy"] = gt_heavy
            mcid, mformula = mirror_ik(ik)
            rec["gt_in_mirror"] = mcid is not None
            rec["gt_cid"] = mcid
            rec["mirror_formula"] = mformula
            # GT identity anywhere in full chem hit list
            block = ik.split("-")[0]
            identity_rank = None
            for idx, h in enumerate(fam_all, 1):
                hv = (h["v"] or "").strip().upper()
                if "INCHI" in (h["t"] or "").upper() and hv.split("-")[0] == block:
                    identity_rank = idx
                    break
                if str(h["v"]).isdigit() and mcid and str(h["v"]) == str(mcid):
                    identity_rank = idx
                    break
            rec["gt_identity_rank_anywhere"] = identity_rank
            # fragment skeleton comparison
            best_frag = (0.0, None, None)
            for seg, sdat in r["sigs"].items():
                if not sdat.get("skel_hex") or not gt_fp:
                    continue
                try:
                    s = tanimoto_hex(gt_fp, sdat["skel_hex"])
                except Exception:
                    continue
                if s > best_frag[0]:
                    best_frag = (s, seg, sdat.get("formula"))
            rec["frag_sim"] = round(best_frag[0], 3)
            rec["frag_seg"] = best_frag[1]
            rec["frag_formula"] = best_frag[2]
            seg = best_frag[1]
            att = set()
            for s2, a in r["idents"].items():
                att.update(a)
            rec["resolvers_attempted"] = sorted(att)
            seg_att = r["idents"].get(seg) if seg else []
            rec["seg_resolvers"] = seg_att
            chem_seg_count = len(r["sigs"])
            rec["chem_seg_count"] = chem_seg_count
            if best_frag[0] >= 0.7:
                if identity_rank is not None:
                    rec["cls"] = ("B0_in_window_unscored" if identity_rank <= 50
                                  else "B2_gt_buried_beyond50")
                elif not att & {"formula_hfamily", "formula_pubchem",
                                "formula_pubchem_local", "inchikey_pubchem"}:
                    rec["cls"] = "B3_fragment_no_formula_resolvers"
                elif not rec["gt_in_mirror"]:
                    rec["cls"] = "B1a_gt_not_in_mirror"
                else:
                    rec["cls"] = "B1b_candidates_missed_gt"
            elif best_frag[0] >= 0.5:
                rec["cls"] = "C_near_fragment"
            elif chem_seg_count > 0:
                rec["cls"] = "D_unrelated_despite_ligands"
            else:
                rec["cls"] = "E_no_chem_segments"
            rows.append(rec)

    bycls = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        bycls["ALL"][r["cls"]] += 1
        bycls[r["era"]][r["cls"]] += 1
    mirror_missing = sum(1 for r in rows if r.get("gt_in_mirror") is False)
    ex = collections.defaultdict(list)
    for r in rows:
        if len(ex[r["cls"]]) < 10:
            ex[r["cls"]].append({k: r[k] for k in
                                 ("eid", "ik", "frag_sim", "frag_formula",
                                  "gt_heavy", "gt_cid", "gt_in_mirror",
                                  "gt_identity_rank_anywhere", "chem_seg_count")
                                 if k in r})
    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "drilled_annotations": len(rows),
        "classes": {k: dict(v) for k, v in bycls.items()},
        "gt_not_in_mirror_count": mirror_missing,
        "from_era_note": "live entries only (load+verify success)",
        "examples": dict(ex),
        "sim_new_pairs": eng.new_pairs, "sim_unmapped": eng.unmapped,
    }
    with open(f"{DATA}/audit_gt_absent.json", "w") as fh:
        json.dump(out, fh, indent=1)
    with open(f"{DATA}/audit_gt_absent_rows.jsonl", "w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(json.dumps(out, indent=1))
    print(f"DONE in {time.time()-t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "split":
        b1b_split_report()
    else:
        main()
