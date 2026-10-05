#!/usr/bin/env python3
"""Audit: where do inchikey (organic) and ion S7 failures come from?

Read-only. One pass over completed entries' results.json.
Outcomes per GT annotation, era-split, rejection-reason taxonomy,
candidate-window forensics. Output: /data/validation/audit_chem_ion.json
"""
import collections
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

DATA = "/data/validation"
sys.path.insert(0, DATA)
for _p in ("/app", DATA):
    if os.path.isdir(os.path.join(_p, "src_new")) and _p not in sys.path:
        sys.path.insert(0, _p)

import psycopg2  # noqa: E402

DB = os.environ.get(
    "DATABASE_URL",
    "postgresql://validation:validation-password-change-me@validation-postgres:5432/bat3_validation",
)
FAM_DEPTH = 50
CHEM = ("PUBCHEM", "INCHI")
METALS = ("Ca", "Mg", "Zn", "Ni", "K", "Na", "Fe", "Cu", "Co", "Mn",
          "Li", "Rb", "Cs", "Sr", "Ba", "Cd", "Hg", "Ag", "Au",
          "Cl", "F", "I", "Br", "Al", "Mo", "W", "V", "Ti", "Cr", "Sn", "Pb")
EL_RE = re.compile(r"elements:([^|]+)")

# era cuts (UTC epochs): 2026-09-24T00:00 = mass-requeue wave start-ish;
# 2026-09-26T00:00 = definitely post spin-fix v2.42
CUT_REQUEUE = 1790208000.0
CUT_SPINFIX = 1790380800.0


def era_of(mtime):
    if POST_F14_MODE:
        return "3_post_v3121"
    if mtime >= CUT_SPINFIX:
        return "2_post_spinfix"
    if mtime >= CUT_REQUEUE:
        return "1_requeue_wave"
    return "0_legacy"


POST_F14_MODE = os.environ.get("POST_F14", "") == "1"
POST_F14_SINCE = os.environ.get("POST_F14_SINCE", "2026-09-26 18:30")


def parse_entry(eid):
    path = f"{DATA}/{eid}/results.json"
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except Exception:
        return eid, None
    data = doc.get("data") or {}
    ver = data.get("verification") or {}
    hits = []
    for seg, sv in ver.items():
        for h in (sv or {}).get("verified_hits") or []:
            if isinstance(h, dict):
                try:
                    conf = float(h.get("final_confidence") or 0.0)
                except Exception:
                    conf = 0.0
                hits.append({
                    "t": h.get("ident_type"), "v": h.get("identifier"),
                    "conf": conf, "ver": bool(h.get("is_verified")),
                    "rej": h.get("rejection_reason"),
                    "skel": h.get("skeleton_sim"), "seg": seg})
    hits.sort(key=lambda x: -x["conf"])
    fr = data.get("fragments") or {}
    u = fr.get("unique") or {}
    els, metal_sources = set(), collections.Counter()
    for k in u.keys():
        m = EL_RE.search(str(k))
        if not m:
            continue
        ktype = str(k).split("|")[0]
        for tok in m.group(1).split(","):
            if "=" in tok:
                sym = tok.split("=", 1)[0].strip()
                if sym in METALS:
                    els.add(sym)
                    metal_sources[f"{ktype}:{sym}"] += 1
    # F19: canonical union — fragments/metals presence (add-only), with
    # source attribution for the ion_metal_sources diagnostics table
    token_els = set(els)
    fm = fr.get("metals") or {}
    if isinstance(fm, dict):
        for sym in (fm.get("present_elements") or []):
            if sym in METALS:
                els.add(sym)
                if sym not in token_els:
                    metal_sources[f"fragments.metals:{sym}"] += 1
    idents = data.get("identifiers") or {}
    resolvers = set()
    for mol, by_sig in idents.items():
        for sig_type, info in (by_sig or {}).items():
            for rname in (info or {}).get("attempted") or []:
                resolvers.add(rname)
    mol = data.get("molecules") or {}
    tasks = doc.get("tasks") or {}
    ts = {n: ((tasks.get(n) or {}).get("status")) for n in
          ("load_simulation", "analyze_universe", "generate_signatures",
           "identify_molecules", "verify_results", "export_results")}
    deepest = next((n for n in reversed(list(ts)) if ts[n] == "success"), None)
    load_status = (data.get("loading") or {})
    return eid, {
        "hits": hits, "ion_els": sorted(els),
        "metal_sources": dict(metal_sources),
        "type_counts": fr.get("type_counts") or {},
        "mol_type_counts": mol.get("type_counts") or {},
        "resolvers": sorted(resolvers),
        "mtime": os.path.getmtime(path),
        "tasks": ts, "deepest": deepest,
        "load_ok": ts["load_simulation"] == "success",
        "verify_ok": ts["verify_results"] == "success",
        "export_ok": ts["export_results"] == "success",
        "crit": [c.get("code") for c in doc.get("critical_errors") or []
                 if isinstance(c, dict)],
    }


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

    uniq_iks = sorted({v for vs in gt.values() for v in vs})
    print(f"GT inchikey annotations: {sum(len(v) for v in gt.values())} "
          f"({len(uniq_iks)} unique) on {len(gt)} entries", file=sys.stderr)

    from gt_rules import gt_class_for, ion_element
    cls = {}
    for i, ik in enumerate(uniq_iks, 1):
        c = gt_class_for(ik)
        cls[ik] = (c, ion_element(ik) if c == "ion" else None)
        if i % 500 == 0:
            print(f"  classified {i}/{len(uniq_iks)} ({time.time()-t0:.0f}s)", file=sys.stderr)
    cls_counts = collections.Counter(c for c, _ in cls.values())
    print("GT classes:", dict(cls_counts), file=sys.stderr)

    gtmap = json.load(open(f"{DATA}/gt_compound_map.json"))
    if POST_F14_MODE:
        con2 = psycopg2.connect(DB)
        cur2 = con2.cursor()
        cur2.execute(
            "SELECT entry_id FROM validation_queue WHERE status='completed' "
            "AND completed_at > %s", (POST_F14_SINCE,))
        cohort = {r[0] for r in cur2.fetchall()}
        con2.close()
        print(f"post-v3.121 cohort since {POST_F14_SINCE}: {len(cohort)} entries",
              file=sys.stderr)
        entries = [e for e in gt if e in cohort
                   and os.path.exists(f"{DATA}/{e}/results.json")]
    else:
        entries = [e for e in gt if os.path.exists(f"{DATA}/{e}/results.json")]
    print(f"parsing {len(entries)} entries...", file=sys.stderr)
    results = {}
    with ThreadPoolExecutor(max_workers=24) as ex:
        futs = {ex.submit(parse_entry, e): e for e in entries}
        for i, fut in enumerate(as_completed(futs), 1):
            eid, r = fut.result()
            if r is not None:
                results[eid] = r
            if i % 2000 == 0:
                print(f"  parsed {i}/{len(entries)} ({time.time()-t0:.0f}s)", file=sys.stderr)

    from validation_similarity import SimEngine
    eng = SimEngine(budget=50000)
    print(f"sim engine: {len(eng.pairs)} cached pairs", file=sys.stderr)

    ion_rows, org_rows = [], []
    dead = collections.Counter()
    dead_stage = collections.Counter()
    dead_crit = collections.Counter()
    for eid, iks in gt.items():
        r = results.get(eid)
        if r is None:
            dead["no_results_json"] += len(iks)
            continue
        if not r["load_ok"]:
            dead["load_failed"] += len(iks)
            dead_stage[r["deepest"] or "none"] += 1
            dead_crit.update(r["crit"])
            continue
        if not r["verify_ok"]:
            dead[f"partial_{r['deepest'] or 'none'}"] += len(iks)
            dead_stage[r["deepest"] or "none"] += 1
            continue
        # live entry: pipeline reached verify_results successfully
        era = era_of(r["mtime"])
        fam = [h for h in r["hits"]
               if any(f in (h["t"] or "").upper() for f in CHEM)][:FAM_DEPTH]
        e_cids = {str(c) for c in (gtmap.get(str(eid)) or {}).get("cids") or []}
        for ik in iks:
            c, el = cls[ik]
            if c == "ion":
                els = set(r["ion_els"])
                out = ("validated" if (el and el in els)
                       else ("metal_but_not_el" if els else "no_metals"))
                ion_rows.append({"eid": eid, "ik": ik, "el": el, "cls": out,
                                 "els": r["ion_els"], "era": era,
                                 "frag_types": r["type_counts"],
                                 "mol_types": r["mol_type_counts"],
                                 "metal_sources": r["metal_sources"]})
                continue
            # organic path (includes cls 'unresolved', mirroring v6.5 routing)
            base = {"eid": eid, "ik": ik, "gtcls": c, "era": era,
                    "n_fam": len(fam), "n_hits": len(r["hits"])}
            if not fam:
                base["out"] = "no_family"
                base["resolvers"] = r["resolvers"]
                base["mol_types"] = r["mol_type_counts"]
                org_rows.append(base)
                continue
            block = ik.split("-")[0]
            sims = []
            for idx, h in enumerate(fam, 1):
                ident_present = False
                hv = (h["v"] or "").strip().upper()
                if "INCHI" in (h["t"] or "").upper():
                    ident_present = hv.split("-")[0] == block
                elif str(h["v"]) in e_cids and e_cids:
                    ident_present = True
                s = eng.sim("inchikey", ik, h["t"], h["v"])
                sims.append((idx, s, h, ident_present))
            best = max(sims, key=lambda x: x[1])
            at = {k: max((s for idx, s, _, _ in sims if idx <= k), default=0.0)
                  for k in (1, 5, 10)}
            val = {k: at[k] >= 0.7 for k in at}
            any_ident = any(ip for _, _, _, ip in sims)
            rej = collections.Counter(h["rej"] or "verified"
                                      for _, _, h, _ in sims[:10] if not h["ver"])
            base.update({
                "at1": round(at[1], 3), "at5": round(at[5], 3),
                "at10": round(at[10], 3),
                "val1": val[1], "val5": val[5], "val10": val[10],
                "best50_sim": round(best[1], 3), "best50_rank": best[0],
                "best50_hit": f"{best[2]['t']}:{best[2]['v']}",
                "best50_ver": best[2]["ver"], "best50_rej": best[2]["rej"],
                "gt_ident_present": any_ident, "rej_top10": dict(rej),
            })
            if val[10]:
                first = next(k for k in (1, 5, 10) if val[k])
                base["out"] = f"validated@{first}"
            elif any_ident:
                base["out"] = "engine_miss_identity"
            elif best[1] >= 0.5:
                base["out"] = "prodrug_band" if best[0] <= 10 else "band_buried"
            else:
                base["out"] = "gt_absent" if not any_ident else "present_but_low"
                if best[1] >= 0.3:
                    base["out"] += "_best0.3-0.5"
                else:
                    base["out"] += "_best<0.3"
            org_rows.append(base)

    # aggregates
    def agg(rows, key="cls"):
        by = collections.defaultdict(collections.Counter)
        for r in rows:
            by["ALL"][r[key]] += 1
            by[r["era"]][r[key]] += 1
        return {k: dict(v) for k, v in by.items()}

    org_agg = agg(org_rows, "out")
    ion_agg = agg(ion_rows, "cls")

    rej_hist = collections.Counter()
    for r in org_rows:
        if not r.get("val10"):
            rej_hist.update(r.get("rej_top10") or {})

    ion_el = collections.defaultdict(collections.Counter)
    ion_frag_types_nom = collections.Counter()
    ion_metal_sources = collections.Counter()
    for r in ion_rows:
        ion_el[r["el"]][r["cls"]] += 1
        ion_metal_sources.update(r["metal_sources"])
        if r["cls"] == "no_metals":
            for t, n in (r["frag_types"] or {}).items():
                ion_frag_types_nom[t] += 1

    ex = collections.defaultdict(list)
    for r in org_rows:
        if len(ex[r["out"]]) < 8:
            ex[r["out"]].append({"eid": r["eid"], "ik": r["ik"][:27],
                                 "best": r.get("best50_sim"),
                                 "rank": r.get("best50_rank")})
    for r in ion_rows:
        kk = "ion_" + r["cls"]
        if len(ex[kk]) < 8:
            ex[kk].append({"eid": r["eid"], "el": r["el"], "els": r["els"][:8]})

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "entries_parsed": len(results),
        "excluded_annotations": dict(dead),
        "excluded_entries_by_deepest": dict(dead_stage.most_common()),
        "excluded_critical": dict(dead_crit.most_common()),
        "gt_classes": dict(cls_counts),
        "organic_annotations": len(org_rows), "ion_annotations": len(ion_rows),
        "organic_outcomes": org_agg, "ion_outcomes": ion_agg,
        "failing_top10_rejection_reasons": dict(rej_hist.most_common()),
        "ion_by_element": {k: dict(v) for k, v in sorted(ion_el.items())},
        "ion_no_metals_frag_types": dict(ion_frag_types_nom.most_common()),
        "ion_metal_sources": dict(ion_metal_sources.most_common(15)),
        "sim_unmapped_delta": eng.unmapped, "sim_errors_delta": eng.errors,
        "sim_new_pairs": eng.new_pairs,
        "examples": dict(ex),
    }
    out_name = ("audit_chem_ion_postf14.json" if POST_F14_MODE
                else "audit_chem_ion.json")
    with open(f"{DATA}/{out_name}", "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))
    print(f"DONE in {time.time()-t0:.0f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
