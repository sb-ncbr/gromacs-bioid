#!/usr/bin/env python3
"""Intermediate (no-sim) audit of inchikey + ion S7 failures.

Read-only forensics over live entries' results.json. No SimEngine, no pair
computation -- safe to run concurrently with campaign_stats v7.

Per GT inchikey annotation (split organic vs ion via gt_rules):
  - entry liveness gate (load_simulation && verify_results success)
  - organic: family-candidate window presence (PUBCHEM/INCHI hits <= depth 50),
    gate outcome distribution (verified vs rejection_reasons) within window
  - ion: metal-element detection coverage (ions found in fragments) +
    verified element match presence.
Output: /data/validation/audit_interm_chem_ion.json + stdout summary.
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
OUT = f"{DATA}/audit_interm_chem_ion.json"


def parse_entry(eid):
    path = f"{DATA}/{eid}/results.json"
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except Exception:
        return eid, None
    tasks = doc.get("tasks") or {}
    live = ((tasks.get("load_simulation") or {}).get("status") == "success"
            and (tasks.get("verify_results") or {}).get("status") == "success")
    if not live:
        return eid, {"live": False}
    data = doc.get("data") or {}
    ver = data.get("verification") or {}
    fam_hits = []
    for seg, sv in ver.items():
        for h in (sv or {}).get("verified_hits") or []:
            if isinstance(h, dict) and any(
                    f in (h.get("ident_type") or "").upper() for f in CHEM):
                fam_hits.append({
                    "v": h.get("identifier"),
                    "ver": bool(h.get("is_verified")),
                    "rej": h.get("rejection_reason"),
                    "skel": h.get("skeleton_sim"),
                })
    fam_hits.sort(key=lambda x: -(x["skel"] or 0.0))
    fr = (data.get("fragments") or {}).get("unique") or {}
    els = set()
    for k in fr.keys():
        m = EL_RE.search(str(k))
        if m:
            for tok in m.group(1).split(","):
                if "=" in tok and tok.split("=", 1)[0].strip() in METALS:
                    els.add(tok.split("=", 1)[0].strip())
    return eid, {"live": True, "fam": fam_hits[:FAM_DEPTH], "els": sorted(els)}


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
    uniq = sorted({v for vs in gt.values() for v in vs})
    print(f"GT inchikey annotations: {sum(len(v) for v in gt.values())} "
          f"({len(uniq)} unique) on {len(gt)} entries", file=sys.stderr)

    from gt_rules import gt_class_for, ion_element
    cls = {}
    for i, ik in enumerate(uniq, 1):
        c = gt_class_for(ik)
        cls[ik] = (c, ion_element(ik) if c == "ion" else None)
        if i % 500 == 0:
            print(f"  classified {i}/{len(uniq)} ({time.time()-t0:.0f}s)", file=sys.stderr)

    entries = [e for e in gt if os.path.exists(f"{DATA}/{e}/results.json")]
    print(f"parsing {len(entries)} entries (no-sim)...", file=sys.stderr)
    res = {}
    with ThreadPoolExecutor(max_workers=16) as ex:
        futs = {ex.submit(parse_entry, e): e for e in entries}
        for i, fut in enumerate(as_completed(futs), 1):
            eid, r = fut.result()
            if r is not None:
                res[eid] = r
            if i % 3000 == 0:
                print(f"  parsed {i}/{len(entries)} ({time.time()-t0:.0f}s)",
                      file=sys.stderr)

    A = {"organic": collections.Counter(), "ion": collections.Counter()}
    rej = collections.Counter()
    ion_el_missing = collections.Counter()   # GT ion element not detected
    ion_el_present = collections.Counter()   # GT ion element detected somewhere
    skel_ver_nonzero = []
    for eid, iks in gt.items():
        r = res.get(eid)
        for ik in iks:
            c, el = cls.get(ik, ("organic", None))
            grp = "ion" if c == "ion" else "organic"
            if r is None:
                A[grp]["unreadable"] += 1
                continue
            if not r["live"]:
                A[grp]["not_live"] += 1
                continue
            if grp == "ion":
                A[grp]["total_live"] += 1
                det = set(r["els"])
                if el is None:
                    A[grp]["gt_element_unknown"] += 1
                elif el in det:
                    A[grp]["element_detected"] += 1
                    ion_el_present[el] += 1
                else:
                    A[grp]["element_NOT_detected"] += 1
                    ion_el_missing[el or "?"] += 1
                if not det:
                    A[grp]["no_ion_fragments_at_all"] += 1
            else:
                A[grp]["total_live"] += 1
                fam = r["fam"]
                if not fam:
                    A[grp]["no_family_candidates"] += 1
                    continue
                A[grp]["has_family_candidates"] += 1
                if any(h["ver"] for h in fam):
                    A[grp]["window_has_gate_verified"] += 1
                else:
                    A[grp]["window_all_rejected"] += 1
                    for h in fam:
                        rej[h["rej"] or "none"] += 1
                top_skel = fam[0]["skel"] if fam else None
                if top_skel:
                    skel_ver_nonzero.append(top_skel)

    out = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "entries_parsed": len(res),
        "organic": dict(A["organic"]),
        "ion": dict(A["ion"]),
        "rejection_reasons_all_rejected_windows": dict(rej.most_common(20)),
        "ion_element_detected_hist": dict(ion_el_present.most_common()),
        "ion_element_missing_hist": dict(ion_el_missing.most_common()),
        "skeleton_top_gt0_count": len(skel_ver_nonzero),
        "scan_seconds": round(time.time() - t0, 1),
    }
    with open(OUT, "w") as fh:
        json.dump(out, fh, indent=2)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
