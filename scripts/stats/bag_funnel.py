"""Bag-of-molecules funnel (v11 frame) — user-specified S-metric.
Per live entry, every molecule-UNIT = segment with a non-empty generated-signature map
(the pipeline's own operational molecule unit: signatures/identifiers/verification all
key by segment).

Hops (absolute + pct at each; denominator = hop0 molecules):
  hop0 molecules (bag)
  hop1 signature present: A=searchable-structural, B=names, C=atom/ion (independent flags)
  hop2 >=1 identifier hit (any gen/resolver with non-empty hits)
  hop3 >=1 verified result (any is_verified verified_hit)

Frame: results.json parseable AND tasks.load_simulation.status==success AND
tasks.analyze_universe.status==success. Exclusions counted and reported.
Read-only; GT-free. Streams per entry (no cross-entry retention). Pool of N.
"""
import json, os, sys, collections
from multiprocessing import Pool

ROOT = "/data/validation"
OUT_JSON = f"{ROOT}/bag_funnel_v11.json"

A_GEN = {  # searchable structural (see approved classification 2026-10-03)
    "smiles", "smiles_not_sanitized", "selfies", "inchi_key",
    "molecular_formula", "mmcif",
    "pdb_protein", "pdb_backbone_protein", "pdb_not_sanitized_protein",
    "pdb_backbone_not_sanitized_protein", "topology_less_pdb", "ca_only_pdb",
    "fasta_resname_protein", "fasta_map_protein", "fasta_map_nucleic",
    "3di_sequence", "glycan_composition", "pdb_nucleic",
}
B_GEN = {"name_molecule", "name_chain", "name_segment", "resname", "lipid_shorthand"}
C_GEN = {"atom"}


def scan_one(eid):
    p = os.path.join(ROOT, str(eid), "results.json")
    try:
        with open(p) as fh:
            d = json.load(fh)
    except Exception:
        return {"excluded": "no_results_or_unparseable"}
    tasks = d.get("tasks") or {}
    if (tasks.get("load_simulation") or {}).get("status") != "success":
        return {"excluded": "load_not_success"}
    if (tasks.get("analyze_universe") or {}).get("status") != "success":
        return {"excluded": "analyze_not_success"}
    data = d.get("data") or {}
    sigmap = data.get("signatures") or {}
    segs = [s for s, b in sigmap.items() if isinstance(b, dict) and (b.get("generated") or {})]
    if not segs:
        return {"excluded": "no_molecule_units"}
    idemap = data.get("identifiers") or {}
    vermap = data.get("verification") or {}
    usegs = ((data.get("universe") or {}).get("segments")) or {}

    mol = []
    for s in segs:
        gen = set((sigmap[s].get("generated") or {}).keys())
        cats = {"A": bool(gen & A_GEN), "B": bool(gen & B_GEN), "C": bool(gen & C_GEN)}
        hop2 = False
        for g, rmap in (idemap.get(s) or {}).items():
            if not isinstance(rmap, dict):
                continue
            for rname, blk in rmap.items():
                if rname == "attempted":
                    continue
                if isinstance(blk, dict) and blk.get("hits"):
                    hop2 = True
                    break
            if hop2:
                break
        hop3 = any(h.get("is_verified") for h in ((vermap.get(s) or {}).get("verified_hits") or []))
        props = (usegs.get(s) or {}).get("properties") or {}
        if props.get("is_protein"):
            cls = "protein"
        elif props.get("is_nucleic"):
            cls = "nucleic"
        else:
            cls = "chem_other"
        mol.append((cats["A"], cats["B"], cats["C"], hop2, hop3, cls))
    return {"mol": mol}


def main():
    lo, hi = (int(x) for x in (sys.argv[1:3] or ["1", "14623"]))
    per_class = collections.Counter()
    per_entry = collections.Counter()
    excluded = collections.Counter()
    funnel = collections.Counter()
    class_funnel = collections.defaultdict(collections.Counter)
    t0 = 0
    with Pool(8) as pool:
        for i, res in enumerate(pool.imap_unordered(scan_one, range(lo, hi + 1), chunksize=16), 1):
            if "excluded" in res:
                excluded[res["excluded"]] += 1
            else:
                mols = res["mol"]
                funnel["molecules"] += len(mols)
                funnel["with_A"] += sum(1 for m in mols if m[0])
                funnel["with_B"] += sum(1 for m in mols if m[1])
                funnel["with_C"] += sum(1 for m in mols if m[2])
                funnel["with_AorB"] += sum(1 for m in mols if m[0] or m[1])
                funnel["no_signature_at_all"] += sum(1 for m in mols if not (m[0] or m[1] or m[2]))
                funnel["with_hit"] += sum(1 for m in mols if m[3])
                funnel["with_verified"] += sum(1 for m in mols if m[4])
                per_entry["entries_in_frame"] += 1
                per_entry["entries_with_molecule"] += 1
                if any(m[4] for m in mols):
                    per_entry["entries_with_verified_molecule"] += 1
                for m in mols:
                    cf = class_funnel[m[5]]
                    cf["molecules"] += 1
                    cf["with_A"] += m[0]
                    cf["with_B"] += m[1]
                    cf["with_C"] += m[2]
                    cf["with_hit"] += m[3]
                    cf["with_verified"] += m[4]
            if i % 1500 == 0:
                print(f"[{lo}-{hi}] scanned {i}/{hi-lo+1} funnel={dict(funnel)}", flush=True)
    total = funnel["molecules"]
    out = {
        "frame_range": [lo, hi],
        "excluded": dict(excluded),
        "entries_in_frame": per_entry["entries_in_frame"],
        "entries_with_verified_molecule": per_entry["entries_with_verified_molecule"],
        "funnel_abs": dict(funnel),
        "funnel_pct_of_molecules": {k: round(100.0 * v / total, 2) if total else None
                                     for k, v in funnel.items()},
        "per_class": {c: {"abs": dict(cf),
                          "pct": {k: round(100.0 * v / cf["molecules"], 2) if cf["molecules"] else None
                                  for k, v in cf.items()}}
                      for c, cf in class_funnel.items()},
    }
    with open(OUT_JSON, "w") as fh:
        json.dump(out, fh, indent=1)
    print("FINAL", json.dumps(out["funnel_abs"]), flush=True)
    print("written", OUT_JSON, flush=True)


if __name__ == "__main__":
    main()
