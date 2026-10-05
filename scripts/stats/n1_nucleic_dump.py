"""N1 P0 nucleic dump — read-only scan of the frozen bag frame (v11, run on NFS in-pod).
For every nucleic molecule-unit (segment property is_nucleic=True, generated sig map
non-empty) emit one JSONL row with: size info (residue_count), signature types +
compact payload summaries, per-signature resolver attempts and hit counts,
hop flags. Also aggregate: per-(sigtype,resolver) attempt/hit-producer matrix,
length-bucket strata, name/resname strata for fragment-content analysis.

Hypotheses target (user): hitless nucleic = fragments/designed oligos with no
PDB homologs (content gap = feature). Length strata + resname shapes test this.

Frame = identical to bag_funnel_v11 (load_simulation+analyze_universe success +
non-empty generated sig map). Read-only; GT-free. Pool of N, streams rows through
main process (no cross-entry retention beyond counters).
"""
import json, os, sys, collections
from multiprocessing import Pool

ROOT = "/data/validation"
OUT_ROWS = f"{ROOT}/n1_nucleic_rows.jsonl"
OUT_MATRIX = f"{ROOT}/n1_nucleic_matrix.json"

A_GEN = {
    "smiles", "smiles_not_sanitized", "selfies", "inchi_key",
    "molecular_formula", "mmcif",
    "pdb_protein", "pdb_backbone_protein", "pdb_not_sanitized_protein",
    "pdb_backbone_not_sanitized_protein", "topology_less_pdb", "ca_only_pdb",
    "fasta_resname_protein", "fasta_map_protein", "fasta_map_nucleic",
    "3di_sequence", "glycan_composition", "pdb_nucleic",
}
NAME_SIGS = {"name_molecule", "name_chain", "name_segment", "resname", "lipid_shorthand"}

LENGTH_BUCKETS = [(1, 5), (6, 15), (16, 30), (31, 100), (101, 500), (501, 10**9)]


def bucket_of(n):
    if n is None:
        return "unknown"
    for lo, hi in LENGTH_BUCKETS:
        if lo <= n <= hi:
            return f"{lo}-{hi if hi < 10**9 else 'inf'}"
    return "unknown"


def summarize(payload):
    """Compact signature payload summary (no big text retention)."""
    if isinstance(payload, str):
        d = {"kind": "str", "len": len(payload), "head": payload[:100]}
        d["atom_lines"] = payload.count("\nATOM") + (1 if payload.startswith("ATOM") else 0)
        if payload.startswith(">"):
            # fasta-like: seq length = total minus header lines/newlines
            d["fa_head"] = payload.split("\n", 1)[0][:100]
        return d
    if isinstance(payload, (list, tuple)):
        return {"kind": "list", "len": len(payload), "head": str(payload[:6])[:100]}
    if isinstance(payload, dict):
        return {"kind": "dict", "len": len(payload), "head": str(list(payload)[:8])[:100]}
    return {"kind": type(payload).__name__, "head": str(payload)[:100]}


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

    rows = []
    for s in segs:
        props = (usegs.get(s) or {}).get("properties") or {}
        if not props.get("is_nucleic"):
            continue
        genmap = (sigmap[s].get("generated") or {})
        row = {
            "eid": eid, "seg": s,
            "residue_count": props.get("residue_count"),
            "atom_count_fragment": props.get("atom_count_fragment"),
            "molecule_count": props.get("molecule_count"),
            "sig_types": sorted(genmap.keys()),
            "sig_summary": {g: summarize(v) for g, v in genmap.items() if g in A_GEN or g in NAME_SIGS},
            "names": {g: (str(genmap[g])[:120] if not isinstance(genmap[g], (dict, list)) else str(genmap[g])[:120])
                      for g in NAME_SIGS if g in genmap},
            "sig_attempted": sigmap[s].get("attempted") or [],
            "resolver_attempts": {},
            "hit": False, "verified": False, "hits_total": 0, "n_verified": 0,
        }
        for g, rmap in (idemap.get(s) or {}).items():
            if not isinstance(rmap, dict):
                continue
            att = rmap.get("attempted") or []
            withh = {}
            for rname, blk in rmap.items():
                if rname == "attempted" or not isinstance(blk, dict):
                    continue
                h = blk.get("hits") or []
                if h:
                    withh[rname] = len(h)
            row["resolver_attempts"][g] = {"attempted": [str(a) for a in att], "with_hits": withh}
            row["hits_total"] += sum(withh.values())
            if withh:
                row["hit"] = True
        ver = (vermap.get(s) or {}).get("verified_hits") or []
        row["n_verified"] = sum(1 for h in ver if isinstance(h, dict) and h.get("is_verified"))
        row["verified"] = row["n_verified"] > 0
        rows.append(row)
    return {"mol_rows": rows}


def main():
    lo, hi = (int(x) for x in (sys.argv[1:3] or ["1", "14623"]))
    nrows = 0
    frame_entries = 0
    excluded = collections.Counter()
    # matrix[sigtype][resolver] -> {"attempts": n_resolver_invocations,
    #                                "molecules_attempted": n_molecules_where_attempted,
    #                                "molecules_with_hits": n, "hits": total_hits}
    matrix = collections.defaultdict(lambda: collections.defaultdict(
        lambda: collections.Counter()))
    length_strata = collections.defaultdict(collections.Counter)
    sigtype_cov = collections.Counter()   # sigtype presence over nucleic molecules
    totals = collections.Counter()

    fh = open(OUT_ROWS, "w")
    with Pool(6) as pool:
        for i, res in enumerate(pool.imap_unordered(scan_one, range(lo, hi + 1), chunksize=16), 1):
            if "excluded" in res:
                excluded[res["excluded"]] += 1
            else:
                frame_entries += 1
                for row in res["mol_rows"]:
                    fh.write(json.dumps(row) + "\n")
                    nrows += 1
                    totals["nucleic_molecules"] += 1
                    totals["hit"] += row["hit"]
                    totals["verified"] += row["verified"]
                    for g in row["sig_types"]:
                        sigtype_cov[g] += 1
                    lb = bucket_of(row["residue_count"])
                    length_strata[lb]["molecules"] += 1
                    length_strata[lb]["hit"] += row["hit"]
                    length_strata[lb]["verified"] += row["verified"]
                    for g, ra in row["resolver_attempts"].items():
                        seen = set()
                        for rname in ra["attempted"]:
                            matrix[g][rname]["attempts"] += 1
                            seen.add(rname)
                        for rname in seen:
                            matrix[g][rname]["molecules_attempted"] += 1
                        for rname, nh in ra["with_hits"].items():
                            matrix[g][rname]["molecules_with_hits"] += 1
                            matrix[g][rname]["hits"] += nh
            if i % 1500 == 0:
                print(f"[{lo}-{hi}] scanned {i}/{hi-lo+1} rows={nrows} hits={totals['hit']}", flush=True)
    fh.close()

    out = {
        "frame": {"range": [lo, hi], "entries_in_frame": frame_entries,
                  "excluded": dict(excluded)},
        "totals": dict(totals),
        "sigtype_coverage_nucleic": dict(sigtype_cov.most_common()),
        "length_strata": {b: dict(c) for b, c in
                          sorted(length_strata.items(), key=lambda kv: kv[0])},
        "resolver_matrix": {
            g: {r: dict(c) for r, c in sorted(v.items())} for g, v in sorted(matrix.items())
        },
        "rows_file": OUT_ROWS,
    }
    with open(OUT_MATRIX, "w") as fh2:
        json.dump(out, fh2, indent=2)
    print(f"DONE nucleic_molecules={totals['nucleic_molecules']} hit={totals['hit']} "
          f"verified={totals['verified']} excluded={dict(excluded)}")
    print(json.dumps(out["length_strata"], indent=1))
    print(json.dumps(out["resolver_matrix"], indent=1)[:4000])


if __name__ == "__main__":
    main()
